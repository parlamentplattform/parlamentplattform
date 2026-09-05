"""Interne Beschlüsse der Räte (FB-I4, § 6 Abs 2 lit e)."""

from __future__ import annotations

import pytest

from plattform_core.gremienbeschluss import (
    VERSION,
    Auswertung,
    BeschlussFehler,
    auswerten,
    noetige_stimmen,
)

OPTIONEN = ("validieren", "zurueck", "austausch")


def test_die_haelfte_wird_aufgerundet():
    """Bei fünf aktiven Rollen sind drei nötig, nicht zweieinhalb."""
    assert [noetige_stimmen(n) for n in (0, 1, 2, 3, 4, 5, 7)] == [0, 1, 1, 2, 2, 3, 4]


def test_ohne_beschlussfaehigkeit_gibt_es_kein_ergebnis():
    """Zwei von fünf sind kein Rat — auch wenn beide dasselbe wollen."""
    a = auswerten(["validieren", "validieren"], OPTIONEN, aktive=5)
    assert a.beschlussfaehig is False and a.ergebnis is None and a.offen is True
    assert (a.abgegeben, a.noetig) == (2, 3)


def test_einfache_mehrheit_der_abgegebenen_stimmen():
    """Nicht der aktiven Rollen: Wer schweigt, ist abwesend — nicht dagegen."""
    a = auswerten(["validieren", "validieren", "zurueck"], OPTIONEN, aktive=5)
    assert a.beschlussfaehig is True and a.ergebnis == "validieren"
    assert a.zaehlung == {"validieren": 2, "zurueck": 1, "austausch": 0}


def test_gleichstand_ist_kein_beschluss():
    """Sonst entschiede die Reihenfolge der Optionen — eine verdeckte Reihung (Grundregel 6)."""
    a = auswerten(["validieren", "zurueck"], OPTIONEN, aktive=4)
    assert a.beschlussfaehig is True and a.gleichstand is True and a.ergebnis is None


def test_die_reihenfolge_der_stimmen_aendert_nichts():
    stimmen = ["zurueck", "validieren", "zurueck", "austausch"]
    erste = auswerten(stimmen, OPTIONEN, aktive=6)
    zweite = auswerten(list(reversed(stimmen)), OPTIONEN, aktive=6)
    assert erste == zweite and erste.ergebnis == "zurueck"


def test_eine_unbekannte_option_ist_ein_fehler():
    """Stillschweigend verwerfen hieße, dass ein Tippfehler ein Ergebnis verschiebt."""
    with pytest.raises(BeschlussFehler):
        auswerten(["validieren", "vielleicht"], OPTIONEN, aktive=3)


def test_ein_beschluss_ohne_optionen_ist_keiner():
    with pytest.raises(BeschlussFehler):
        auswerten([], (), aktive=3)


def test_ohne_eine_einzige_stimme_ist_nichts_beschlossen():
    """Auch bei null aktiven Rollen: kein Gremium, kein Beschluss."""
    assert auswerten([], OPTIONEN, aktive=0).beschlussfaehig is False
    assert auswerten([], OPTIONEN, aktive=3).ergebnis is None


def test_die_auswertung_traegt_ihre_regelfassung():
    """Ein alter Beschluss muss nach seiner eigenen Regel nachrechenbar bleiben."""
    a = auswerten(["validieren"], OPTIONEN, aktive=1)
    assert isinstance(a, Auswertung) and a.version == VERSION == 1


def test_ein_gremium_ohne_mitglieder_beschliesst_nichts():
    """Sonst entschiede eine einzelne Stimme allein — die Hälfte von null ist null.

    Über die Stimmabgabe ist das nicht erreichbar (sie verlangt eine aktive Rolle), wohl aber
    danach: Läuft die Berufung ab und die Frist des Beschlusses danach aus, stünde am Ende eine
    Stimme gegen ein leeres Gremium."""
    a = auswerten(["validieren"], OPTIONEN, aktive=0)
    assert a.beschlussfaehig is False and a.ergebnis is None and a.offen is True
    assert a.noetig == 0 and a.abgegeben == 1


def test_ausgeschiedene_stimmen_zaehlen_weiter_der_nenner_schrumpft_mit():
    """Wer beim Abgeben berufen war, dessen Stimme bleibt gültig (FB-I1).

    Der Nenner ist die Zahl der Rollen im Augenblick der Auszählung. Drei Stimmen bei nur noch
    einer aktiven Rolle sind deshalb beschlussfähig — abgestimmt haben sie, als sie durften."""
    a = auswerten(["validieren", "validieren", "zurueck"], OPTIONEN, aktive=1)
    assert a.beschlussfaehig is True and a.ergebnis == "validieren"
