"""Die Aussetzung nach § 6 Abs 3 lit d — Sieben-Tage-Frist und Hemmung."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from plattform_core.aussetzung import (
    SCHIEDSGERICHT_TAGE,
    VERSION,
    ende_von,
    frist_ende,
    grund_des_endes,
    hemmung_sekunden,
    laeuft,
    wirksamer_beginn,
)

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)


def tage(n: float) -> timedelta:
    return timedelta(days=n)


def test_die_frist_sind_sieben_tage_und_stehen_nicht_im_register():
    """Wer sie verlängern könnte, könnte eine Abstimmung beliebig lange anhalten."""
    assert SCHIEDSGERICHT_TAGE == 7 and VERSION == 1
    assert frist_ende(T0) == T0 + tage(7)


def test_ohne_antrag_endet_die_aussetzung_von_selbst():
    """§ 6 Abs 3 lit d wörtlich: „unterbleibt der Antrag, endet die Aussetzung von selbst"."""
    assert laeuft(T0, T0 + tage(6)) is True
    assert laeuft(T0, T0 + tage(7)) is False
    assert "von selbst geendet" in grund_des_endes(T0, T0 + tage(8))
    assert ende_von(T0) == T0 + tage(7)


def test_mit_antrag_laeuft_sie_weiter():
    """Ist das Schiedsgericht angerufen, endet sie nicht mit der Frist — es entscheidet."""
    antrag = T0 + tage(3)
    assert laeuft(T0, T0 + tage(30), schiedsgericht_am=antrag) is True
    assert ende_von(T0, schiedsgericht_am=antrag) is None
    # Sie läuft — also hat sie keinen Grund zu enden.
    assert grund_des_endes(T0, T0 + tage(30), schiedsgericht_am=antrag) == ""
    assert grund_des_endes(T0, T0 - tage(1)) == "noch nicht begonnen"


def test_eine_aufhebung_beendet_sie_sofort():
    ende = T0 + tage(2)
    assert laeuft(T0, T0 + tage(3), schiedsgericht_am=T0 + tage(1), beendet_am=ende) is False
    assert "aufgehoben" in grund_des_endes(T0, T0 + tage(3), beendet_am=ende)


def test_die_hemmung_zaehlt_nur_was_in_der_phase_liegt():
    """Der Phasenbeginn wird bei jedem Wechsel neu geschrieben — eine Lebenssumme bekäme jede
    Folgephase erneut geschenkt."""
    vorher = (T0 - tage(10), T0 - tage(9))  # eine Aussetzung aus einer früheren Phase
    innen = (T0 + tage(1), T0 + tage(3))
    assert hemmung_sekunden([vorher], ab=T0, jetzt=T0 + tage(5)) == 0
    assert hemmung_sekunden([vorher, innen], ab=T0, jetzt=T0 + tage(5)) == int(tage(2).total_seconds())


def test_zwei_gleichzeitige_aussetzungen_hemmen_nicht_doppelt():
    """Sonst käme eine zweite Aussetzung einer Verdopplung der Frist gleich."""
    a = (T0 + tage(1), T0 + tage(4))
    b = (T0 + tage(2), T0 + tage(3))  # ganz innerhalb von a
    c = (T0 + tage(3), T0 + tage(6))  # überlappt a
    assert hemmung_sekunden([a, b], ab=T0, jetzt=T0 + tage(9)) == int(tage(3).total_seconds())
    assert hemmung_sekunden([a, b, c], ab=T0, jetzt=T0 + tage(9)) == int(tage(5).total_seconds())


def test_eine_laufende_aussetzung_haelt_die_frist_an():
    """Solange sie läuft, wandert der wirksame Beginn mit der Uhr — die Frist rückt nie näher."""
    laufend = [(T0 + tage(1), None)]
    for spaeter in (2, 5, 30):
        wirksam = wirksamer_beginn(T0, laufend, T0 + tage(spaeter))
        verstrichen = (T0 + tage(spaeter)) - wirksam
        assert verstrichen == tage(1), "es bleibt bei dem einen Tag vor der Aussetzung"


def test_ohne_aussetzung_aendert_sich_nichts():
    assert wirksamer_beginn(T0, [], T0 + tage(4)) == T0


def test_die_reihenfolge_der_abschnitte_aendert_nichts():
    abschnitte = [(T0 + tage(4), T0 + tage(5)), (T0 + tage(1), T0 + tage(2))]
    erste = hemmung_sekunden(abschnitte, ab=T0, jetzt=T0 + tage(9))
    zweite = hemmung_sekunden(list(reversed(abschnitte)), ab=T0, jetzt=T0 + tage(9))
    assert erste == zweite == int(tage(2).total_seconds())
