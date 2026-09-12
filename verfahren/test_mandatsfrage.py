"""Die Mandatsfrage (§ 7 Abs 9): aus dem Instant-Report direkt in die Abstimmung.

Fachoperation `mandatsfrage_eroeffnen` — Dauer aus dem Register, eingefroren in die Ordnung
des Antrags (§ 5 Abs 5), nie unter dem Satzungsminimum (§ 5 Abs 3 lit d); Stimmberechtigte am
Stichtag festgestellt (§ 4 Abs 4 lit a); ausgezählt und nachgerechnet wie ein Sachantrag."""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Aufgabe, Mandat
from parameter.models import Parameter
from verfahren.models import (
    Antrag,
    Antragsart,
    AuditEintrag,
    MandatsfrageFehler,
    mandatsfrage_eroeffnen,
)
from verfahren.test_views_aktionen import (  # noqa: F401
    REGELN,
    _nachrechnen_laden,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

FRAGE = {
    "titel": "Soll die Gemeinde dem Radweg an der Bundesstraße zustimmen?",
    "wortlaut": "Der Gemeinderat stimmt am Sitzungstag über den Radweg ab. Ja heißt: zustimmen.",
}


def mandat_mit_report(mitglied, frist_tage=14, **extra):
    mandat = Mandat.objects.create(
        mitglied=mitglied,
        bezeichnung="Gemeinderat",
        ebene="gemeinde",
        gebiet="St. Marienkirchen an der Polsenz",
    )
    aufgabe = Aufgabe.objects.create(
        mandat=mandat,
        titel="Gemeinderatssitzung: Radweg",
        frist=timezone.now() + timedelta(days=frist_tage),
        sitzungstag=extra.pop("sitzungstag", True),
    )
    return mandat, aufgabe


def eroeffnen(mandat, aufgabe, ordnung, **extra):  # noqa: F811
    return mandatsfrage_eroeffnen(mandat, aufgabe, FRAGE["titel"], FRAGE["wortlaut"], ordnung, **extra)


# --- Eröffnen -----------------------------------------------------------------------------


def test_mandatsfrage_steht_sofort_in_der_abstimmung_mit_eingefrorener_dauer(ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    mandat, aufgabe = mandat_mit_report(leute[0])
    Parameter.objects.create(schluessel="mandatsfrage-abstimmung-tage", wert="9", einheit="Tage",
                             beschreibung="Test", quelle="§ 7 Abs 9")

    antrag = eroeffnen(mandat, aufgabe, ordnung)

    assert antrag.art == Antragsart.MANDATSFRAGE and antrag.phase == "abstimmung"
    assert antrag.policy_snapshot["abstimmung_tage"] == 9  # Dauer aus dem Register
    assert antrag.policy().abstimmung_tage == 9  # und als Ordnung lesbar
    assert antrag.eingebracht_von == leute[0]
    assert antrag.ebene == "gemeinde" and antrag.gebiet == "St. Marienkirchen an der Polsenz"
    # § 4 Abs 4 lit a: Stichtag und Zahl der Stimmberechtigten sind beim Eröffnen festgestellt
    assert antrag.stimmberechtigung_stichtag == timezone.localdate()
    assert antrag.stimmberechtigte_anzahl == 3
    fassung = antrag.aktueller_text()
    assert fassung.nummer == 1 and fassung.wortlaut == FRAGE["wortlaut"]
    assert "Sitzungstag" in fassung.begruendung
    aufgabe.refresh_from_db()
    assert aufgabe.antrag == antrag  # der Report kennt seine Abstimmung


def test_dauer_klemmt_auf_dem_satzungsminimum(ordnung):  # noqa: F811
    """Ein Registerwert 3 ergibt sieben Tage (§ 5 Abs 3 lit d) — und keinen PolicyFehler."""
    mandat, aufgabe = mandat_mit_report(mitglied_anlegen())
    Parameter.objects.create(schluessel="mandatsfrage-abstimmung-tage", wert="3", einheit="Tage",
                             beschreibung="Test", quelle="§ 7 Abs 9")
    antrag = eroeffnen(mandat, aufgabe, ordnung)
    assert antrag.policy().abstimmung_tage == 7


def test_ohne_registereintrag_gilt_der_eingebaute_zielwert(ordnung):  # noqa: F811
    mandat, aufgabe = mandat_mit_report(mitglied_anlegen())
    antrag = eroeffnen(mandat, aufgabe, ordnung)
    assert antrag.policy().abstimmung_tage == 7


def test_laufende_mandatsfrage_behaelt_ihre_dauer_bei_registeraenderung(ordnung):  # noqa: F811
    """§ 5 Abs 5: Die Ordnung ist eingefroren — auch die Dauer aus dem Register."""
    mandat, aufgabe = mandat_mit_report(mitglied_anlegen(), frist_tage=30)
    p = Parameter.objects.create(schluessel="mandatsfrage-abstimmung-tage", wert="8", einheit="Tage",
                                 beschreibung="Test", quelle="§ 7 Abs 9")
    antrag = eroeffnen(mandat, aufgabe, ordnung)
    p.wert = "20"
    p.save(update_fields=["wert"])
    antrag.refresh_from_db()
    assert antrag.policy().abstimmung_tage == 8
    # Frist ist Beginn + 8 Tage: kurz davor läuft sie noch, danach ist sie um
    assert antrag.fortschreiben(jetzt=antrag.phase_beginn + timedelta(days=7, hours=23)) is False
    assert antrag.fortschreiben(jetzt=antrag.phase_beginn + timedelta(days=8)) is True


def test_zu_knappe_frist_erzeugt_keine_abstimmung(ordnung):  # noqa: F811
    """Frist in fünf Tagen, Abstimmung braucht sieben: Fehler — der Report bleibt ohne Antrag."""
    mandat, aufgabe = mandat_mit_report(mitglied_anlegen(), frist_tage=5)
    with pytest.raises(MandatsfrageFehler) as fehler:
        eroeffnen(mandat, aufgabe, ordnung)
    assert "mindestens 7 Tage" in str(fehler.value)
    aufgabe.refresh_from_db()
    assert aufgabe.antrag is None
    assert Antrag.objects.count() == 0
    assert not AuditEintrag.objects.filter(ereignis__typ="mandatsfrage_eroeffnet").exists()


def test_frist_genau_auf_dem_ende_der_abstimmung_reicht(ordnung):  # noqa: F811
    mandat, aufgabe = mandat_mit_report(mitglied_anlegen())
    jetzt = timezone.now()
    aufgabe.frist = jetzt + timedelta(days=7)
    aufgabe.save(update_fields=["frist"])
    antrag = eroeffnen(mandat, aufgabe, ordnung, jetzt=jetzt)
    assert antrag.phase_beginn == jetzt


def test_ohne_frist_keine_mandatsfrage(ordnung):  # noqa: F811
    mandat, aufgabe = mandat_mit_report(mitglied_anlegen())
    aufgabe.frist = None
    aufgabe.save(update_fields=["frist"])
    with pytest.raises(MandatsfrageFehler):
        eroeffnen(mandat, aufgabe, ordnung)


def test_weitere_tore(ordnung):  # noqa: F811
    anna, bert = mitglied_anlegen("anna"), mitglied_anlegen("bert")
    mandat, aufgabe = mandat_mit_report(anna)
    fremdes_mandat, fremde_aufgabe = mandat_mit_report(bert)
    # Aufgabe eines anderen Mandats
    with pytest.raises(MandatsfrageFehler):
        eroeffnen(mandat, fremde_aufgabe, ordnung)
    # Report hat schon eine Abstimmung
    eroeffnen(mandat, aufgabe, ordnung)
    aufgabe.refresh_from_db()
    with pytest.raises(MandatsfrageFehler):
        eroeffnen(mandat, aufgabe, ordnung)
    # Beendetes Mandat
    fremdes_mandat.beendet = timezone.localdate()
    fremdes_mandat.save(update_fields=["beendet"])
    with pytest.raises(MandatsfrageFehler):
        eroeffnen(fremdes_mandat, fremde_aufgabe, ordnung)
    assert Antrag.objects.count() == 1


def test_audit_traegt_beide_ereignisse(ordnung):  # noqa: F811
    mandat, aufgabe = mandat_mit_report(mitglied_anlegen())
    antrag = eroeffnen(mandat, aufgabe, ordnung)
    typen = list(
        AuditEintrag.objects.filter(ereignis__antrag=antrag.pk).order_by("lfd").values_list("ereignis__typ", flat=True)
    )
    assert typen == ["kategorien_zugeordnet", "mandatsfrage_eroeffnet", "phasenwechsel"]
    eroeffnet = AuditEintrag.objects.get(ereignis__typ="mandatsfrage_eroeffnet").ereignis
    assert eroeffnet["mandat"] == mandat.pk and eroeffnet["aufgabe"] == aufgabe.pk
    assert eroeffnet["policy"] == "test-ordnung v1" and "frist_ende" in eroeffnet
    wechsel = AuditEintrag.objects.get(ereignis__typ="phasenwechsel").ereignis
    assert wechsel["neue_phase"] == "abstimmung" and "§ 7 Abs 9" in wechsel["grund"]
    # Nie Werte: keine E-Mail, kein Name, kein Ort
    for ereignis in (eroeffnet, wechsel):
        text = json.dumps(ereignis)
        assert "example.org" not in text and "Marienkirchen" not in text


# --- Laufen, Auszählen, Nachrechnen -------------------------------------------------------


def test_fortschreiben_beendet_die_abstimmung_erst_zum_fristende(ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    mandat, aufgabe = mandat_mit_report(leute[0])
    antrag = eroeffnen(mandat, aufgabe, ordnung)
    assert antrag.fortschreiben() is False  # vor Fristende tut sich nichts
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung"
    # Niemand stimmt: Mindestbeteiligung verfehlt → abgelehnt, mit Audit
    assert antrag.fortschreiben(jetzt=antrag.phase_beginn + timedelta(days=7)) is True
    assert antrag.phase == "abgelehnt"
    assert antrag.auszaehlen().beteiligung_erreicht is False
    assert AuditEintrag.objects.filter(ereignis__typ="phasenwechsel", ereignis__antrag=antrag.pk).count() == 2


def test_abstimmen_export_und_nachrechnen(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    mandat, aufgabe = mandat_mit_report(leute[0])
    antrag = eroeffnen(mandat, aufgabe, ordnung)

    for m, wahl in zip(leute, ["ja", "ja", "nein"], strict=True):
        client.force_login(m)
        antwort = client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": wahl})
        assert antwort.status_code == 302
    assert antrag.stimmabgaben.count() == 3

    url = reverse("verfahren:export", args=[antrag.pk])
    assert client.get(url).status_code == 409  # läuft noch
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))
    antwort = client.get(url)
    assert antwort.status_code == 200
    daten = json.loads(antwort.content)
    assert daten["art"] == "mandatsfrage" and daten["stimmberechtigte"] == 3

    ergebnis = _nachrechnen_laden()(daten)  # zweite, unabhängige Auszählung (§ 5 Abs 8)
    assert ergebnis["art"] == "mandatsfrage"
    assert ergebnis["ja"] == 2 and ergebnis["nein"] == 1 and ergebnis["angenommen"] is True
    antrag.refresh_from_db()
    assert antrag.phase == "angenommen"


def test_einbringen_per_post_kennt_keine_mandatsfrage(client, ordnung):  # noqa: F811
    """Niemand legt per POST auf /einbringen/ eine Mandatsfrage mit Unterstützungsphase an."""
    client.force_login(mitglied_anlegen())
    antwort = client.post(
        reverse("verfahren:einbringen"),
        {"titel": "Schein-Mandatsfrage", "wortlaut": "…", "begruendung": "…", "art": "mandatsfrage"},
    )
    assert not Antrag.objects.filter(art=Antragsart.MANDATSFRAGE).exists()
    assert antwort.status_code in (200, 302)


def test_antragsseite_und_kachel_rendern_die_mandatsfrage(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(2)]
    mandat, aufgabe = mandat_mit_report(leute[0])
    antrag = eroeffnen(mandat, aufgabe, ordnung)
    client.force_login(leute[1])
    assert client.get(reverse("verfahren:antrag", args=[antrag.pk])).status_code == 200
    inhalt = client.get(reverse("verfahren:parlament")).content.decode()
    assert FRAGE["titel"] in inhalt
