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


def _nachrechnen_laden():
    pfad = Path(__file__).resolve().parents[1] / "verify" / "nachrechnen.py"
    spec = importlib.util.spec_from_file_location("nachrechnen", pfad)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul.nachrechnen


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
