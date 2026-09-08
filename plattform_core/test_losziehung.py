"""Die Auslosung des Expertenrats (§ 6 Abs 7) — nachrechenbar und unvorhersehbar zugleich."""

from __future__ import annotations

import hashlib

import pytest

from plattform_core.losziehung import (
    SATZUNG_MIN_RATSGROESSE,
    VERSION,
    Kandidat,
    LosFehler,
    lostopf,
    loswert,
    ziehen,
)

ANKER = "9f2c" * 16


def liste(anzahl: int, fachgebiete=("verkehr",)) -> list[Kandidat]:
    return [
        Kandidat(schluessel=f"k{i:03d}", fachgebiete=frozenset(fachgebiete)) for i in range(anzahl)
    ]


def test_der_loswert_ist_mit_jedem_pruefsummenwerkzeug_nachzurechnen():
    """Sonst wäre „offengelegtes Zufallsverfahren" nur ein Wort (§ 6 Abs 7, § 2 Abs 6)."""
    erwartet = hashlib.sha256(f"{ANKER}|k007".encode()).hexdigest()
    assert loswert(ANKER, "k007") == erwartet


def test_dieselbe_ziehung_zweimal_ergibt_dasselbe():
    kandidaten = liste(10)
    erste = ziehen(ANKER, kandidaten, [3])
    zweite = ziehen(ANKER, list(reversed(kandidaten)), [3])
    assert erste == zweite, "die Reihenfolge der Eingabe darf nichts ändern"


def test_ein_anderer_anker_ergibt_eine_andere_ziehung():
    """Der Anker ist der Zufall. Wäre er es nicht, wäre die Ziehung vorhersehbar."""
    kandidaten = liste(30)
    eine = {p.schluessel for p in ziehen(ANKER, kandidaten, [3]).plaetze}
    andere = {p.schluessel for p in ziehen("1234" * 16, kandidaten, [3]).plaetze}
    assert eine != andere


def test_die_beiden_gruppen_sind_durch_die_konstruktion_getrennt():
    """§ 6 Abs 7: „zwei unabhängig voneinander besetzten Gruppen".

    Gruppe 2 wird aus dem Rest gezogen, nicht aus dem ganzen Topf — eine Prüfung, die man
    vergessen kann, gibt es hier nicht."""
    ziehung = ziehen(ANKER, liste(12), [3, 3])
    erste = {p.schluessel for p in ziehung.gruppen[0]}
    zweite = {p.schluessel for p in ziehung.gruppen[1]}
    assert len(erste) == len(zweite) == 3
    assert not (erste & zweite)


def test_zu_wenige_kandidaten_ergeben_keine_halbe_ziehung():
    """Eine halb besetzte zweite Gruppe sähe nach Prüfung aus und wäre keine."""
    with pytest.raises(LosFehler, match="Lostopf"):
        ziehen(ANKER, liste(5), [3, 3])


def test_eine_gruppe_unter_drei_gibt_es_nicht():
    """§ 6 Abs 8: „mindestens drei Mitglieder" — satzungsfest, keine Stellgröße."""
    assert SATZUNG_MIN_RATSGROESSE == 3
    with pytest.raises(LosFehler, match="Satzungsminimum"):
        ziehen(ANKER, liste(10), [2])


def test_ohne_anker_keine_ziehung():
    with pytest.raises(LosFehler, match="Anker"):
        ziehen("", liste(10), [3])


def test_wer_ausgeschlossen_ist_lost_nicht_mit_und_der_grund_steht_dabei():
    """§ 6 Abs 3 lit a und § 6 Abs 7: Unvereinbarkeiten sind offenzulegen, nicht zu verschweigen."""
    kandidaten = liste(9) + [
        Kandidat("gesperrt", frozenset({"verkehr"}), True, "Mitglied des Integritätsrats")
    ]
    ziehung = ziehen(ANKER, kandidaten, [3])
    assert "gesperrt" not in ziehung.lostopf
    assert ("gesperrt", "Mitglied des Integritätsrats") in ziehung.ausgeschlossen


def test_nur_wer_das_fach_fuehrt_kommt_in_den_topf():
    kandidaten = liste(6, ("verkehr",)) + liste(6, ("bildung",))
    kandidaten = [Kandidat(f"{k.schluessel}-{sorted(k.fachgebiete)[0]}", k.fachgebiete) for k in kandidaten]
    drin, draussen = lostopf(kandidaten, ["verkehr"])
    assert len(drin) == 6 and len(draussen) == 6
    assert all(g == "kein passendes Fachgebiet" for _s, g in draussen)


def test_ohne_fachangabe_lost_die_ganze_liste_mit():
    drin, draussen = lostopf(liste(7), [])
    assert len(drin) == 7 and not draussen


def test_ein_doppelter_schluessel_ist_ein_fehler():
    """Sonst hinge das Ergebnis davon ab, welcher Eintrag zuerst gelesen wird."""
    kandidaten = liste(9) + [Kandidat("k000", frozenset({"verkehr"}))]
    with pytest.raises(LosFehler, match="zweimal"):
        ziehen(ANKER, kandidaten, [3])


def test_die_ziehung_traegt_alles_zum_nachrechnen():
    ziehung = ziehen(ANKER, liste(10), [3, 3])
    assert ziehung.anker == ANKER and ziehung.version == VERSION == 1
    assert len(ziehung.lostopf) == 10
    for platz in ziehung.plaetze:
        assert platz.loswert == loswert(ANKER, platz.schluessel)
    # Die Gezogenen sind genau die mit den kleinsten Loswerten.
    kleinste = sorted(ziehung.lostopf, key=lambda s: (loswert(ANKER, s), s))[:6]
    assert [p.schluessel for p in ziehung.plaetze] == kleinste
