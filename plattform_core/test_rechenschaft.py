"""Fristen der Rechenschaft und Berichte (§ 7 Abs 3 lit b, § 7 Abs 5) — jeder Zweig."""

from datetime import date

import pytest

from plattform_core.rechenschaft import (
    BERICHTSPFLICHT_AB,
    RECHENSCHAFT_TAGE,
    SAMMELBERICHT_TAGE,
    VERSION,
    Lage,
    berichtsmonate,
    faellig_am,
    folgemonat,
    lage,
    monatsanfang,
    monatsbericht_faellig_am,
)


def test_die_sieben_tage_sind_satzungsfest():
    """§ 7 Abs 5 und § 7 Abs 3 lit b nennen sieben Tage — Konstanten, keine Stellgrößen."""
    assert RECHENSCHAFT_TAGE == 7 and SAMMELBERICHT_TAGE == 7
    assert VERSION == 1
    assert faellig_am(date(2026, 10, 5), RECHENSCHAFT_TAGE) == date(2026, 10, 12)
    assert faellig_am(date(2026, 12, 28), SAMMELBERICHT_TAGE) == date(2027, 1, 4)  # Jahreswechsel


def test_monatsanfang_und_folgemonat():
    assert monatsanfang(date(2026, 10, 17)) == date(2026, 10, 1)
    assert folgemonat(date(2026, 10, 1)) == date(2026, 11, 1)
    assert folgemonat(date(2026, 12, 1)) == date(2027, 1, 1)
    assert folgemonat(date(2028, 2, 1)) == date(2028, 3, 1)  # Schaltjahr: 29 Tage, trotzdem März


# --- berichtsmonate ------------------------------------------------------------------------


def test_mandat_vor_der_berichtspflicht_schuldet_erst_ab_oktober_2026():
    """Ein Mandat aus 2025 schuldet keine Monatsberichte für die Zeit ohne Werkzeug."""
    monate = berichtsmonate(date(2025, 3, 1), None, heute=date(2026, 12, 15))
    assert monate == [date(2026, 10, 1), date(2026, 11, 1)]
    assert monate[0] == BERICHTSPFLICHT_AB


def test_mandat_nach_der_berichtspflicht_beginnt_mit_dem_ersten_vollen_monat():
    # Angetreten am 10. Oktober: Oktober ist angebrochen, der erste volle Monat ist November.
    assert berichtsmonate(date(2026, 10, 10), None, heute=date(2027, 1, 1)) == [
        date(2026, 11, 1),
        date(2026, 12, 1),
    ]
    # Angetreten am Monatsersten: der Monat zählt.
    assert berichtsmonate(date(2026, 11, 1), None, heute=date(2027, 1, 1)) == [
        date(2026, 11, 1),
        date(2026, 12, 1),
    ]


def test_der_laufende_monat_ist_noch_nicht_geschuldet():
    assert berichtsmonate(date(2026, 10, 1), None, heute=date(2026, 10, 31)) == []
    assert berichtsmonate(date(2026, 10, 1), None, heute=date(2026, 11, 1)) == [date(2026, 10, 1)]


def test_beendetes_mandat_schuldet_nur_volle_monate():
    # Beendet am 15. Dezember: Dezember war nicht voll.
    assert berichtsmonate(date(2026, 10, 1), date(2026, 12, 15), heute=date(2027, 3, 1)) == [
        date(2026, 10, 1),
        date(2026, 11, 1),
    ]
    # Beendet am letzten Tag des Monats: der Monat war voll und zählt.
    assert berichtsmonate(date(2026, 10, 1), date(2026, 11, 30), heute=date(2027, 3, 1)) == [
        date(2026, 10, 1),
        date(2026, 11, 1),
    ]
    # Beendet vor dem ersten vollen Monat: nichts geschuldet.
    assert berichtsmonate(date(2026, 10, 10), date(2026, 10, 20), heute=date(2027, 3, 1)) == []


def test_schaltjahr_und_monatsende():
    """Februar 2028 hat 29 Tage — ein am 29.2. beendetes Mandat hatte den Februar voll."""
    assert berichtsmonate(date(2028, 1, 1), date(2028, 2, 29), heute=date(2028, 6, 1)) == [
        date(2028, 1, 1),
        date(2028, 2, 1),
    ]
    assert berichtsmonate(date(2028, 1, 1), date(2028, 2, 28), heute=date(2028, 6, 1)) == [
        date(2028, 1, 1),
    ]


def test_eigener_beginn_der_pflicht_ist_uebergebbar():
    assert berichtsmonate(date(2020, 1, 1), None, heute=date(2020, 4, 1), ab=date(2020, 2, 1)) == [
        date(2020, 2, 1),
        date(2020, 3, 1),
    ]


# --- Monatsbericht-Frist -------------------------------------------------------------------


def test_monatsbericht_ist_am_siebten_des_folgemonats_faellig():
    assert monatsbericht_faellig_am(date(2026, 10, 1), 7) == date(2026, 11, 7)
    assert monatsbericht_faellig_am(date(2026, 12, 1), 7) == date(2027, 1, 7)
    assert monatsbericht_faellig_am(date(2026, 10, 1), 1) == date(2026, 11, 1)
    # Werte unter 1 wirken wie 1 — eine Frist vor dem Monatsende gibt es nicht.
    assert monatsbericht_faellig_am(date(2026, 10, 1), 0) == date(2026, 11, 1)
    assert monatsbericht_faellig_am(date(2026, 10, 1), -3) == date(2026, 11, 1)
    assert monatsbericht_faellig_am(date(2026, 10, 1), 40) == date(2026, 12, 10)


# --- Lage ----------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("erledigt_am", "heute", "erwartet"),
    [
        (date(2026, 10, 10), date(2026, 10, 20), Lage("fristgerecht", 0, 0)),
        (date(2026, 10, 12), date(2026, 10, 20), Lage("fristgerecht", 0, 0)),  # am letzten Tag
        (date(2026, 10, 15), date(2026, 10, 20), Lage("verspaetet", 0, 3)),
        (None, date(2026, 10, 9), Lage("offen", 3, 0)),
        (None, date(2026, 10, 12), Lage("offen", 0, 0)),  # letzter Tag: noch offen
        (None, date(2026, 10, 13), Lage("ausstaendig", 0, 1)),
        (None, date(2026, 11, 1), Lage("ausstaendig", 0, 20)),
    ],
)
def test_lage_zaehlt_ohne_zu_urteilen(erledigt_am, heute, erwartet):
    faellig = date(2026, 10, 12)
    assert lage(faellig, erledigt_am, heute) == erwartet


def test_lage_kennt_erledigt():
    assert lage(date(2026, 10, 12), date(2026, 10, 1), date(2026, 10, 2)).erledigt
    assert lage(date(2026, 10, 12), date(2026, 10, 30), date(2026, 11, 2)).erledigt
    assert not lage(date(2026, 10, 12), None, date(2026, 10, 2)).erledigt
    assert not lage(date(2026, 10, 12), None, date(2026, 10, 30)).erledigt
