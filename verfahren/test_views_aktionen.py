"""Handelnde Ansichten: Einbringen (mit Ähnlichkeitshinweis), Unterstützen,
Beraten, Abstimmen, Export. Die Tests fahren die echten HTTP-Flüsse."""

import importlib.util
import json
from datetime import timedelta
from pathlib import Path

import pytest
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Identitaetsstufe, Mitglied
from verfahren.models import Antrag, Verfahrensordnung, antrag_einbringen

pytestmark = pytest.mark.django_db

REGELN = {
    "id": "test-ordnung",
    "version": 1,
    "unterstuetzung_schwelle": 2,
    "unterstuetzung_frist_tage": 14,
    "beratung_tage": 21,
    "abstimmung_tage": 7,
    "mindestbeteiligung": 0.05,
    "mehrheitsbasis": "ja_nein",
    "wiedereinbringung_sperre_monate": 6,
}

ANTRAG = {
    "titel": "Sitzungsprotokolle binnen 48 Stunden veröffentlichen",
    "wortlaut": "Die DDÖ veröffentlicht Protokolle aller Ratssitzungen binnen 48 Stunden.",
    "begruendung": "Transparenz beginnt bei uns selbst.",
}


@pytest.fixture
def ordnung():
    return Verfahrensordnung.objects.create(policy_id="test-ordnung", version=1, regeln=REGELN, aktiv=True)


def mitglied_anlegen(
    name="anna",
    tage=200,
    stufe=Identitaetsstufe.GEPRUEFT,
    gemeinde="St. Marienkirchen an der Polsenz",
    bundesland="oberoesterreich",
):
    m = Mitglied.objects.create(
        username=name,
        email=f"{name}@example.org",
        is_active=True,
        beitritt=timezone.now().date() - timedelta(days=tage),
        identitaetsstufe=stufe,
        gemeinde=gemeinde,
        bundesland=bundesland,
    )
    m.set_unusable_password()
    m.save()
    return m


def in_abstimmung_bringen(antrag, unterstuetzer):
    """Verfahren im Zeitraffer: Schwelle erreichen, Beratungsfrist zurückdatieren."""
    for u in unterstuetzer:
        antrag.unterstuetzungen.create(mitglied=u)
    antrag.fortschreiben()  # Schwelle erreicht -> Beratung
    antrag.phase_beginn = timezone.now() - timedelta(days=22)
    antrag.save(update_fields=["phase_beginn"])
    antrag.fortschreiben()  # Beratungsfrist um -> Abstimmung (stellt Stimmberechtigte fest)
    assert antrag.phase == "abstimmung"
    return antrag


# --- Einbringen (F-10 + F-35) -------------------------------------------------


def test_einbringen_erstellt_antrag_mit_erster_fassung(client, ordnung):
    client.force_login(mitglied_anlegen())
    antwort = client.post(reverse("verfahren:einbringen"), ANTRAG)
    antrag = Antrag.objects.get()
    assert antwort.status_code == 302
    assert antrag.aktueller_text().wortlaut == ANTRAG["wortlaut"]
    assert antrag.policy_snapshot["id"] == "test-ordnung"  # eingefroren (§ 5 Abs 5)


def test_einbringen_zeigt_aehnliche_antraege_und_blockiert_nie(client, ordnung):
    autorin = mitglied_anlegen()
    antrag_einbringen(autorin, ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    client.force_login(mitglied_anlegen("bernd"))

    fast_gleich = {**ANTRAG, "titel": "Sitzungsprotokolle binnen 24 Stunden veröffentlichen"}
    antwort = client.post(reverse("verfahren:einbringen"), fast_gleich)
    assert antwort.status_code == 200  # Hinweisseite, kein Redirect
    assert antwort.context["aehnliche"]  # Treffer angezeigt …
    assert Antrag.objects.count() == 1  # … noch nichts angelegt

    antwort = client.post(reverse("verfahren:einbringen"), {**fast_gleich, "trotzdem": "1"})
    assert antwort.status_code == 302  # „Trotzdem einbringen" wirkt (§ 2 Abs 6)
    assert Antrag.objects.count() == 2


def test_einbringen_verlangt_bestaetigtes_mitglied(client, ordnung):
    client.force_login(mitglied_anlegen(stufe=Identitaetsstufe.UNGEPRUEFT))
    antwort = client.post(reverse("verfahren:einbringen"), ANTRAG)
    assert antwort.status_code == 403
    assert Antrag.objects.count() == 0


def test_einbringen_ohne_aktive_ordnung_meldet_503(client):
    client.force_login(mitglied_anlegen())
    assert client.get(reverse("verfahren:einbringen")).status_code == 503


# --- Unterstützen (§ 5 Abs 3 lit b) ------------------------------------------


def test_unterstuetzen_ist_umschaltbar(client, ordnung):
    autorin, anna = mitglied_anlegen("autorin"), mitglied_anlegen()
    antrag = antrag_einbringen(autorin, **ANTRAG, ordnung=ordnung)
    client.force_login(anna)
    url = reverse("verfahren:unterstuetzen", args=[antrag.pk])
    client.post(url)
    assert antrag.unterstuetzungen.count() == 1
    client.post(url)  # erneut: zurückziehen
    assert antrag.unterstuetzungen.count() == 0


def test_erreichte_schwelle_startet_die_beratung(client, ordnung):
    autorin = mitglied_anlegen("autorin")
    antrag = antrag_einbringen(autorin, **ANTRAG, ordnung=ordnung)
    antrag.unterstuetzungen.create(mitglied=mitglied_anlegen("anna"))
    client.force_login(mitglied_anlegen("bernd"))
    client.post(reverse("verfahren:unterstuetzen", args=[antrag.pk]))  # 2. Stimme = Schwelle
    antrag.refresh_from_db()
    assert antrag.phase == "beratung"


# --- Beraten ------------------------------------------------------------------


def test_kommentieren_nur_in_offenen_phasen(client, ordnung):
    autorin = mitglied_anlegen("autorin")
    antrag = antrag_einbringen(autorin, **ANTRAG, ordnung=ordnung)
    client.force_login(mitglied_anlegen())
    url = reverse("verfahren:kommentieren", args=[antrag.pk])
    client.post(url, {"text": "Guter Vorschlag."})
    assert antrag.kommentare.count() == 1

    Antrag.objects.filter(pk=antrag.pk).update(phase="angenommen")
    client.post(url, {"text": "Zu spät."})
    assert antrag.kommentare.count() == 1  # abgeschlossen: keine neuen Beiträge


# --- Abstimmen (§ 4 Abs 4, § 5 Abs 3 lit d) -----------------------------------


def test_abstimmen_ohne_anwartschaft_wird_abgewiesen(client, ordnung, settings):
    settings.DDOE_UEBERGANGSREGEL = False
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    frisch = mitglied_anlegen("frisch", tage=10)  # 10 Tage < 3 Monate Anwartschaft
    client.force_login(frisch)
    antwort = client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    assert antwort.status_code == 403
    assert antrag.stimmabgaben.count() == 0


def test_uebergangsregel_laesst_junge_mitglieder_abstimmen(client, ordnung, settings):
    settings.DDOE_UEBERGANGSREGEL = True  # § 4 Abs 4 lit d (Aufbauphase)
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    client.force_login(mitglied_anlegen("frisch", tage=10))
    antwort = client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    assert antwort.status_code == 302
    assert antrag.stimmabgaben.count() == 1


def test_stimme_aendern_ueberschreibt_statt_zu_doppeln(client, ordnung):
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    client.force_login(leute[1])
    url = reverse("verfahren:abstimmen", args=[antrag.pk])
    client.post(url, {"stimme": "ja"})
    client.post(url, {"stimme": "nein"})
    assert antrag.stimmabgaben.count() == 1  # eine Stimme je Mensch (§ 4 Abs 4 lit e)
    assert antrag.stimmabgaben.get().stimme == "nein"


# --- Export & Nachrechnen (F-21/F-23, § 5 Abs 8) ------------------------------


NACHRECHNEN_PFAD = Path(__file__).resolve().parents[1] / "verify" / "nachrechnen.py"


def _nachrechnen_laden():
    spec = importlib.util.spec_from_file_location("nachrechnen", NACHRECHNEN_PFAD)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul.nachrechnen


# Ein Kandidatur-Export, wie export_json ihn schreibt: Bewerbung 5 zurückgezogen, eine
# Zustimmung zu ihr (zählt nicht), 3 und 7 mit je zwei Zustimmungen (3 war früher da).
PERSONENWAHL_EXPORT = {
    "art": "mandat",
    "policy": {"mindestbeteiligung": 0.05},
    "stimmberechtigte": 10,
    "stimmen": [],
    "bewerbungen": [
        {"bewerbung": 3, "name": "Anna Ö.", "eingereicht_am": "2026-09-01", "zurueckgezogen": False},
        {"bewerbung": 5, "name": "Bernd →", "eingereicht_am": "2026-09-02", "zurueckgezogen": True},
        {"bewerbung": 7, "name": "Carla", "eingereicht_am": "2026-09-03", "zurueckgezogen": False},
    ],
    "zustimmungen": [
        {"pseudonym": "p1", "bewerbung": 3},
        {"pseudonym": "p1", "bewerbung": 7},
        {"pseudonym": "p2", "bewerbung": 7},
        {"pseudonym": "p3", "bewerbung": 3},
        {"pseudonym": "p4", "bewerbung": 5},
    ],
}


def test_das_pruefskript_rechnet_eine_personenwahl_wie_der_kern():
    """§ 5 Abs 8: Das Skript rechnete Kandidatur-Exporte still als Sachfrage mit 0 Stimmen
    („angenommen: False“ neben „Gewählt ist Bewerbung 3“ auf der Antragsseite). Jetzt spiegelt
    es die Zustimmungswahl aus plattform_core.tally — samt Ausschluss zurückgezogener
    Bewerbungen, Reihung nach Einreichreihenfolge bei Gleichstand und Beteiligung nur aus
    zählenden Zustimmungen — und kommt zum selben Ergebnis wie der Kern."""
    from types import SimpleNamespace

    from plattform_core.tally import personenwahl_auszaehlen

    ergebnis = _nachrechnen_laden()(PERSONENWAHL_EXPORT)
    kern = personenwahl_auszaehlen(
        [("p1", 3), ("p1", 7), ("p2", 7), ("p3", 3)],
        bewerbungen=[3, 7],
        stimmberechtigte=10,
        policy=SimpleNamespace(mindestbeteiligung=0.05),
    )
    assert ergebnis["art"] == "mandat"
    assert [(p["platz"], p["bewerbung"], p["zustimmungen"]) for p in ergebnis["plaetze"]] == [
        (p.platz, p.bewerbung_id, p.stimmen) for p in kern.plaetze
    ] == [(1, 3, 2), (2, 7, 2)]
    assert ergebnis["beteiligung"] == kern.beteiligung == 3  # p4 stimmte nur der zurückgezogenen zu
    assert ergebnis["gewaehlt"] == kern.gewonnen_id == 3 and ergebnis["angenommen"] is True
    assert ergebnis["gewaehlt_name"] == "Anna Ö."


def test_das_pruefskript_meldet_doppelte_zustimmungen_und_fremde_antragsarten():
    """Ein Skript, das etwas Unbekanntes still als Sachfrage rechnet, wäre schlimmer als eines,
    das nicht rechnet: Unbekannte Antragsart und doppelte Zustimmung enden mit Fehlermeldung."""
    nachrechnen = _nachrechnen_laden()
    with pytest.raises(SystemExit, match="Antragsart"):
        nachrechnen({**PERSONENWAHL_EXPORT, "art": "rat"})
    doppelt = {
        **PERSONENWAHL_EXPORT,
        "zustimmungen": [{"pseudonym": "p1", "bewerbung": 3}, {"pseudonym": "p1", "bewerbung": 3}],
    }
    with pytest.raises(SystemExit, match="doppelt"):
        nachrechnen(doppelt)


def test_das_pruefskript_laeuft_auch_auf_einer_windows_konsole(tmp_path):
    """Der Probelauf auf cp1252 brach zuletzt mit UnicodeEncodeError am Pfeil der Schlusszeile ab —
    für ein Werkzeug „ohne Spezialkenntnisse“ (§ 5 Abs 8) ein schlechter letzter Eindruck. Der Lauf
    als eigenes Programm muss mit Exit 0 enden, auch wenn ein Name Zeichen außerhalb der
    Konsolenkodierung trägt, und die Plätze lesbar ausgeben."""
    import os
    import subprocess
    import sys

    export = tmp_path / "export.json"
    export.write_text(json.dumps(PERSONENWAHL_EXPORT, ensure_ascii=False), encoding="utf-8")
    lauf = subprocess.run(
        [sys.executable, str(NACHRECHNEN_PFAD), str(export)],
        capture_output=True,
        env={**os.environ, "PYTHONIOENCODING": "cp1252", "PYTHONUTF8": "0"},
    )
    ausgabe = lauf.stdout.decode("cp1252", errors="replace")
    assert lauf.returncode == 0, lauf.stderr.decode(errors="replace")
    assert "plaetze:" in ausgabe and "1. Bewerbung 3 (Anna Ö.): 2" in ausgabe
    assert "angenommen: True" in ausgabe and "gewaehlt: 3" in ausgabe


def test_export_erst_nach_ende_und_unabhaengig_nachrechenbar(client, ordnung):
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    for m, wahl in zip(leute, ["ja", "ja", "nein"], strict=True):
        client.force_login(m)
        client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": wahl})

    url = reverse("verfahren:export", args=[antrag.pk])
    assert client.get(url).status_code == 409  # laufende Abstimmung: kein Zwischenstand

    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))
    antwort = client.get(url)
    assert antwort.status_code == 200
    daten = json.loads(antwort.content)
    assert len(daten["stimmen"]) == 3
    assert daten["stimmberechtigte"] >= 3

    ergebnis = _nachrechnen_laden()(daten)  # zweite, unabhängige Auszählung
    assert ergebnis["ja"] == 2 and ergebnis["nein"] == 1
    assert ergebnis["angenommen"] is True
    antrag.refresh_from_db()
    assert antrag.phase == "angenommen"  # Plattform kommt zum selben Schluss


def test_eigene_stimme_zeigt_pseudonym_nur_der_stimmenden_person(client, ordnung):
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    url = reverse("verfahren:eigene_stimme", args=[antrag.pk])
    assert client.get(url).status_code == 302  # anonym: zum Login

    client.force_login(leute[1])
    client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    pseudonym = antrag.stimmregister.get(mitglied=leute[1]).pseudonym.hex
    assert pseudonym in client.get(url).content.decode()


# --- Beanstanden (§ 6 Abs 11 lit b) ------------------------------------------


def _beanstandung_absetzen(client, mitglied, antrag):
    client.force_login(mitglied)
    return client.post(reverse("verfahren:beanstanden", args=[antrag.pk]), {"text": "Die Zahl stimmt nicht."})


def test_beanstanden_verlangt_bestaetigtes_aktives_mitglied(client, ordnung):
    """Eine Beanstandung steht mit Namen öffentlich im Arbeitsbereich — dieselbe Sperre wie beim
    Kommentieren: ungeprüfte Identität (§ 4) und ruhende Mitwirkung (F-51) werden abgewiesen,
    sonst könnte ein frisch registriertes Konto unbegrenzt öffentliche Texte absetzen."""
    from mitglieder.models import Mitgliedsstatus
    from verfahren.models import Beanstandung

    antrag = antrag_einbringen(mitglied_anlegen("autorin"), **ANTRAG, ordnung=ordnung)
    ungeprueft = mitglied_anlegen("neu", stufe=Identitaetsstufe.UNGEPRUEFT)
    ungeprueft.beitritt = None
    ungeprueft.save(update_fields=["beitritt"])
    assert _beanstandung_absetzen(client, ungeprueft, antrag).status_code == 403

    pausiert = mitglied_anlegen("pause")
    pausiert.status = Mitgliedsstatus.PAUSIERT
    pausiert.save(update_fields=["status"])
    assert _beanstandung_absetzen(client, pausiert, antrag).status_code == 403
    assert Beanstandung.objects.count() == 0

    antwort = _beanstandung_absetzen(client, mitglied_anlegen("bernd"), antrag)
    assert antwort.status_code == 302 and Beanstandung.objects.count() == 1


def test_beanstandung_verspricht_keinen_korrekturlauf(client, ordnung):
    """Öffentliche Texte sagen, was der Code tut: Einen Korrekturlauf der Zukunftswerkstatt gibt es
    noch nicht (kein Codepfad schreibt `erledigt_vermerk`) — also verspricht ihn weder die Rückmeldung
    noch der Hilfetext am Formular."""
    antrag = antrag_einbringen(mitglied_anlegen("autorin"), **ANTRAG, ordnung=ordnung)
    antwort = _beanstandung_absetzen(client, mitglied_anlegen("bernd"), antrag)
    seite = client.get(antwort.url).content.decode()
    assert "rechnet den Punkt nach" not in seite
    assert "noch nicht gebaut" in seite  # Rückmeldung und Hilfetext sagen es offen
