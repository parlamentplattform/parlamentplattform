"""Das Fundament der Mandatar-Rolle (S10): abgeleitete Rolle, Aufgabe mit Zeitpunkt und
Sitzungstag, Rechenschaft und Berichte mit ihren Fristen (§ 7 Abs 3 lit b, § 7 Abs 5)."""

from datetime import date, datetime, time, timedelta

import pytest
from django.utils import timezone

from mandatare.models import Aufgabe, Bericht, Berichtsart, Beschluss, Mandat, Rechenschaft, Stimmverhalten
from parameter.models import Parameter
from verfahren.models import Antrag, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def wiener(tag: date, stunde: int = 18, minute: int = 0):
    return timezone.make_aware(datetime.combine(tag, time(stunde, minute)))


def mandat_anlegen(mitglied, angetreten=None, **extra):
    felder = {
        "bezeichnung": "Gemeinderat",
        "ebene": "gemeinde",
        "gebiet": "St. Marienkirchen an der Polsenz",
        "angetreten": angetreten or date(2026, 9, 1),
        **extra,
    }
    return Mandat.objects.create(mitglied=mitglied, **felder)


# --- Rolle „Mandatar“ ist abgeleitet -----------------------------------------------------


def test_ist_mandatar_entsteht_und_endet_mit_dem_mandat():
    anna = mitglied_anlegen("anna")
    assert anna.ist_mandatar is False and not anna.aktive_mandate.exists()
    mandat = mandat_anlegen(anna)
    assert anna.ist_mandatar is True
    assert list(anna.aktive_mandate) == [mandat]
    mandat.beendet = timezone.localdate()
    mandat.save(update_fields=["beendet"])
    assert anna.ist_mandatar is False  # kein gespeichertes Flag — die Abfrage entscheidet


def test_aktive_von_reiht_nach_ebene_gebiet_antritt():
    anna = mitglied_anlegen("anna")
    bert = mitglied_anlegen("bert")
    gemeinde = mandat_anlegen(anna, ebene="gemeinde", gebiet="Wels")
    land = mandat_anlegen(anna, ebene="land", gebiet="Oberösterreich", bezeichnung="Landtag")
    mandat_anlegen(anna, beendet=date(2026, 9, 10))  # beendet: zählt nicht
    mandat_anlegen(bert)  # fremd: zählt nicht
    assert list(Mandat.aktive_von(anna)) == [gemeinde, land]  # Meta-Ordnung: ebene, gebiet, angetreten
    assert not Mandat.aktive_von(None).exists()
    from django.contrib.auth.models import AnonymousUser

    assert not Mandat.aktive_von(AnonymousUser()).exists()


# --- Aufgabe: Zeitpunkt statt Kalendertag ------------------------------------------------


def test_ueberfaellig_rechnet_mit_uhrzeit():
    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    bald = Aufgabe.objects.create(mandat=mandat, titel="Bald", frist=timezone.now() + timedelta(minutes=30))
    vorbei = Aufgabe.objects.create(mandat=mandat, titel="Vorbei", frist=timezone.now() - timedelta(minutes=30))
    ohne = Aufgabe.objects.create(mandat=mandat, titel="Ohne Frist")
    assert bald.ueberfaellig is False and vorbei.ueberfaellig is True and ohne.ueberfaellig is False
    vorbei.status = "erledigt"
    assert vorbei.ueberfaellig is False
    assert ohne.sitzungstag_datum is None
    sitzung = Aufgabe.objects.create(mandat=mandat, titel="Sitzung", frist=wiener(date(2026, 10, 5), 23, 30), sitzungstag=True)
    assert sitzung.sitzungstag_datum == date(2026, 10, 5)  # Wiener Kalendertag, nicht UTC


# --- Offene Pflichten: Sammelbericht, Rechenschaft, Monatsbericht -------------------------


def test_nach_dem_sitzungstag_sind_sammelbericht_und_rechenschaft_faellig():
    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    sitzung = Aufgabe.objects.create(mandat=mandat, titel="Sitzung", frist=wiener(date(2026, 10, 5)), sitzungstag=True)
    Aufgabe.objects.create(mandat=mandat, titel="Später", frist=wiener(date(2026, 10, 20)), sitzungstag=True)
    Aufgabe.objects.create(mandat=mandat, titel="Kein Sitzungstag", frist=wiener(date(2026, 10, 1)))

    # Vor dem Sitzungstag: nichts fällig
    assert mandat.offene_pflichten(heute=date(2026, 10, 4)) == {
        "sammelberichte": [],
        "rechenschaften": [],
        "monatsberichte": [],
    }
    # Am Tag danach: beides offen, sieben Tage Frist
    pflichten = mandat.offene_pflichten(heute=date(2026, 10, 6))
    (sb,) = pflichten["sammelberichte"]
    (rs,) = pflichten["rechenschaften"]
    assert sb["aufgabe"] == rs["aufgabe"] == sitzung
    assert sb["sitzungstag"] == date(2026, 10, 5) and sb["faellig"] == date(2026, 10, 12)
    assert sb["lage"].status == "offen" and sb["lage"].resttage == 6
    assert rs["faellig"] == date(2026, 10, 12)
    # Nach der Frist: ausständig seit n Tagen
    pflichten = mandat.offene_pflichten(heute=date(2026, 10, 15))
    assert pflichten["rechenschaften"][0]["lage"].status == "ausstaendig"
    assert pflichten["rechenschaften"][0]["lage"].seit_tagen == 3

    # Einträge erledigen die Pflicht
    Bericht.objects.create(mandat=mandat, art=Berichtsart.SAMMELBERICHT, aufgabe=sitzung, text="Bericht.")
    pflichten = mandat.offene_pflichten(heute=date(2026, 10, 15))
    assert pflichten["sammelberichte"] == [] and len(pflichten["rechenschaften"]) == 1
    Rechenschaft.objects.create(
        mandat=mandat, aufgabe=sitzung, gegenstand="Radweg", sitzung_am=date(2026, 10, 5),
        stimme=Stimmverhalten.DAFUER, begruendung="Weil.",
    )
    pflichten = mandat.offene_pflichten(heute=date(2026, 10, 15))
    assert pflichten["rechenschaften"] == []


def test_ohne_heute_zaehlt_der_zeitpunkt_des_sitzungstags():
    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    Aufgabe.objects.create(mandat=mandat, titel="Gleich", frist=timezone.now() + timedelta(hours=2), sitzungstag=True)
    Aufgabe.objects.create(mandat=mandat, titel="Eben", frist=timezone.now() - timedelta(hours=2), sitzungstag=True)
    pflichten = mandat.offene_pflichten()
    assert [p["aufgabe"].titel for p in pflichten["rechenschaften"]] == ["Eben"]


def test_monatsberichte_ab_oktober_2026_und_karenz_aus_dem_register():
    mandat = mandat_anlegen(mitglied_anlegen("anna"), angetreten=date(2026, 3, 1))
    # Im Oktober selbst: noch nichts geschuldet
    assert mandat.offene_pflichten(heute=date(2026, 10, 20))["monatsberichte"] == []
    # Anfang November: Oktober geschuldet, fällig am 7.11. (Standard 7)
    (okt,) = mandat.offene_pflichten(heute=date(2026, 11, 3))["monatsberichte"]
    assert okt["monat"] == date(2026, 10, 1) and okt["faellig"] == date(2026, 11, 7)
    assert okt["lage"].status == "offen" and okt["lage"].resttage == 4
    # Register: Karenz 10 Tage → fällig am 10.11.
    Parameter.objects.create(schluessel="mandatar-monatsbericht-frist-tage", wert="10", einheit="Tage",
                             beschreibung="Test", quelle="§ 7 Abs 3 lit b")
    (okt,) = mandat.offene_pflichten(heute=date(2026, 11, 3))["monatsberichte"]
    assert okt["faellig"] == date(2026, 11, 10)
    # Dezember: Oktober ausständig, November offen
    monate = mandat.offene_pflichten(heute=date(2026, 12, 2))["monatsberichte"]
    assert [m["monat"] for m in monate] == [date(2026, 10, 1), date(2026, 11, 1)]
    assert monate[0]["lage"].status == "ausstaendig" and monate[1]["lage"].status == "offen"
    # Ein Monatsbericht erledigt seinen Monat
    Bericht.objects.create(mandat=mandat, art=Berichtsart.MONATSBERICHT, monat=date(2026, 10, 1), text="Oktober.")
    monate = mandat.offene_pflichten(heute=date(2026, 12, 2))["monatsberichte"]
    assert [m["monat"] for m in monate] == [date(2026, 11, 1)]


def test_beendetes_mandat_schuldet_nur_volle_monate():
    mandat = mandat_anlegen(mitglied_anlegen("anna"), angetreten=date(2026, 10, 1), beendet=date(2026, 11, 20))
    monate = mandat.offene_pflichten(heute=date(2027, 1, 15))["monatsberichte"]
    assert [m["monat"] for m in monate] == [date(2026, 10, 1)]


# --- Rechenschaft und Bericht -------------------------------------------------------------


def test_rechenschaft_leitet_den_plattformbeschluss_aus_dem_antrag_ab(ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    mandat = mandat_anlegen(anna)
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    assert Rechenschaft.beschluss_aus_antrag(None) == Beschluss.KEINER
    assert Rechenschaft.beschluss_aus_antrag(antrag) == Beschluss.KEINER  # läuft noch
    Antrag.objects.filter(pk=antrag.pk).update(phase="angenommen")
    antrag.refresh_from_db()
    assert Rechenschaft.beschluss_aus_antrag(antrag) == Beschluss.ANGENOMMEN
    Antrag.objects.filter(pk=antrag.pk).update(phase="abgelehnt")
    antrag.refresh_from_db()
    assert Rechenschaft.beschluss_aus_antrag(antrag) == Beschluss.ABGELEHNT

    eintrag = Rechenschaft.objects.create(
        mandat=mandat, antrag=antrag, gegenstand="Protokolle", sitzung_am=date(2026, 10, 5),
        stimme=Stimmverhalten.DAFUER, begruendung="Trotzdem dafür.",
        eingetragen_am=wiener(date(2026, 10, 14)),
    )
    assert eintrag.beschluss_plattform == Beschluss.ABGELEHNT  # beim Speichern gesetzt
    assert eintrag.weicht_ab is True  # sichtbar nebeneinander, nicht bewertet
    assert eintrag.frist == date(2026, 10, 12)
    assert eintrag.lage().status == "verspaetet" and eintrag.lage().seit_tagen == 2
    assert "Protokolle" in str(eintrag)
    ohne = Rechenschaft.objects.create(
        mandat=mandat, gegenstand="Frei", sitzung_am=date(2026, 10, 5),
        stimme=Stimmverhalten.NICHT_TEILGENOMMEN, begruendung="Krank.", eingetragen_am=wiener(date(2026, 10, 6)),
    )
    assert ohne.beschluss_plattform == Beschluss.KEINER and ohne.weicht_ab is False
    assert ohne.lage().status == "fristgerecht"
    assert list(Rechenschaft.objects.all()) == [eintrag, ohne]  # Meta: gleicher Sitzungstag, zuletzt eingetragen zuerst


def test_bericht_kennt_seine_frist_und_seine_lage():
    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    sitzung = Aufgabe.objects.create(mandat=mandat, titel="Sitzung", frist=wiener(date(2026, 10, 5)), sitzungstag=True)
    sammel = Bericht.objects.create(
        mandat=mandat, art=Berichtsart.SAMMELBERICHT, aufgabe=sitzung, text="Bericht.",
        eingereicht_am=wiener(date(2026, 10, 10)),
    )
    assert sammel.faellig_am == date(2026, 10, 12) and sammel.lage().status == "fristgerecht"
    monat = Bericht.objects.create(
        mandat=mandat, art=Berichtsart.MONATSBERICHT, monat=date(2026, 10, 1), text="Oktober.",
        eingereicht_am=wiener(date(2026, 11, 9)),
    )
    assert monat.faellig_am == date(2026, 11, 7) and monat.lage().status == "verspaetet"
    lose = Bericht(mandat=mandat, art=Berichtsart.SAMMELBERICHT, text="Ohne Bezug.")
    assert lose.faellig_am is None and lose.lage() is None
    assert "Monatsbericht" in str(monat)


def test_monatsbericht_je_monat_nur_einmal():
    from django.db import IntegrityError

    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    Bericht.objects.create(mandat=mandat, art=Berichtsart.MONATSBERICHT, monat=date(2026, 10, 1), text="A")
    with pytest.raises(IntegrityError):
        Bericht.objects.create(mandat=mandat, art=Berichtsart.MONATSBERICHT, monat=date(2026, 10, 1), text="B")


def test_sammelberichte_duerfen_sich_wiederholen():
    """Nachtrag statt Bearbeiten (Grundregel 7): mehrere Sammelberichte je Sitzungstag sind erlaubt."""
    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    sitzung = Aufgabe.objects.create(mandat=mandat, titel="Sitzung", frist=wiener(date(2026, 10, 5)), sitzungstag=True)
    Bericht.objects.create(mandat=mandat, art=Berichtsart.SAMMELBERICHT, aufgabe=sitzung, text="A")
    Bericht.objects.create(mandat=mandat, art=Berichtsart.SAMMELBERICHT, aufgabe=sitzung, text="Nachtrag: B")
    assert mandat.berichte.count() == 2
