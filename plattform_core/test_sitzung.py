"""Die Rechenregeln des Sitzungsmodus (FB-L5): Beschlusslage, maßgebliche Meldung, wirksames Ende."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from plattform_core import Phase
from plattform_core.sitzung import (
    LAGE_ABGELEHNT,
    LAGE_ABSTIMMUNG,
    LAGE_ANGENOMMEN,
    LAGE_KEIN_ANTRAG,
    LAGE_OHNE_BESCHLUSS,
    LAGE_VORHER,
    VERSION,
    Beschlusslage,
    Meldung,
    berichtigte,
    beschlusslage,
    laeuft,
    massgebliche_meldungen,
    wirksames_ende,
)

T0 = datetime(2026, 10, 1, 9, 0, tzinfo=UTC)


def test_fassung():
    assert VERSION == 1


@pytest.mark.parametrize(
    ("phase", "status"),
    [
        (None, LAGE_KEIN_ANTRAG),
        (Phase.ANGENOMMEN.value, LAGE_ANGENOMMEN),
        (Phase.ABGELEHNT.value, LAGE_ABGELEHNT),
        (Phase.UNTERSTUETZUNG.value, LAGE_VORHER),
        (Phase.BERATUNG.value, LAGE_VORHER),
        (Phase.VERFALLEN.value, LAGE_OHNE_BESCHLUSS),
        (Phase.ZURUECKGEWIESEN.value, LAGE_OHNE_BESCHLUSS),
        (Phase.ZURUECKGEZOGEN.value, LAGE_OHNE_BESCHLUSS),
    ],
)
def test_beschlusslage_je_phase(phase, status):
    lage = beschlusslage(phase, T0)
    assert lage.status == status
    assert lage.bis is None  # nur eine laufende Abstimmung gibt ihr Fristende weiter
    assert lage.entschieden == (status in (LAGE_ANGENOMMEN, LAGE_ABGELEHNT))


def test_jede_phase_hat_eine_lage():
    for phase in Phase:
        assert isinstance(beschlusslage(phase.value), Beschlusslage)


def test_laufende_abstimmung_nur_mit_fristende():
    """§ 5 Abs 3 lit d, D-D2: keine Tendenz, kein Zwischenstand — nur bis wann abgestimmt wird."""
    lage = beschlusslage(Phase.ABSTIMMUNG.value, T0)
    assert lage == Beschlusslage(LAGE_ABSTIMMUNG, T0)
    assert not lage.entschieden
    assert set(Beschlusslage.__dataclass_fields__) == {"status", "bis"}


def test_unbekannte_phase():
    with pytest.raises(ValueError):
        beschlusslage("irgendwas")


def _m(pk, punkt=1, minuten=0, stimme="", abgestimmt=False, berichtigt=None):
    return Meldung(pk, punkt, T0 + timedelta(minutes=minuten), stimme, abgestimmt, berichtigt)


def test_abgestimmt_hat_vorrang_vor_juengerer_ankuendigung():
    meldungen = [
        _m(1, minuten=0, stimme="dafuer"),
        _m(2, minuten=5, stimme="dafuer", abgestimmt=True),
        _m(3, minuten=9, stimme="dagegen"),  # jünger, aber nur angekündigt
    ]
    assert massgebliche_meldungen(meldungen)[1].pk == 2


def test_ankuendigung_gilt_ohne_ergebnis():
    assert massgebliche_meldungen([_m(1, stimme="enthalten"), _m(2, minuten=1)])[1].pk == 1


def test_berichtigte_meldung_zaehlt_nicht():
    meldungen = [
        _m(1, stimme="dafuer", abgestimmt=True),
        _m(2, minuten=2, stimme="dagegen", abgestimmt=True, berichtigt=1),
    ]
    assert berichtigte(meldungen) == frozenset({1})
    assert massgebliche_meldungen(meldungen)[1].pk == 2


def test_berichtigung_auf_anderen_punkt():
    """Die Korrektur kann den Punkt wechseln — dann hat der alte Punkt keine maßgebliche Meldung mehr."""
    meldungen = [_m(1, punkt=1, stimme="dafuer", abgestimmt=True), _m(2, punkt=2, minuten=1, stimme="dafuer", abgestimmt=True, berichtigt=1)]
    ergebnis = massgebliche_meldungen(meldungen)
    assert set(ergebnis) == {2} and ergebnis[2].pk == 2


def test_ohne_punkt_oder_stimme_keine_rechenschaft():
    assert massgebliche_meldungen([_m(1, punkt=None, stimme="dafuer"), _m(2, punkt=3)]) == {}


def test_gleicher_zeitpunkt_hoehere_kennung():
    assert massgebliche_meldungen([_m(7, stimme="dafuer"), _m(4, stimme="dagegen")])[1].pk == 7


@given(st.lists(st.tuples(st.integers(1, 3), st.integers(0, 60), st.sampled_from(["", "dafuer", "dagegen"]), st.booleans()), max_size=12))
def test_massgebliche_meldung_ist_nie_berichtigt_und_hat_stimme(roh):
    meldungen = [_m(i + 1, p, mi, s, a and bool(s)) for i, (p, mi, s, a) in enumerate(roh)]
    # jede zweite Meldung berichtigt ihre Vorgängerin
    meldungen = [
        Meldung(m.pk, m.punkt, m.zeitpunkt, m.stimme, m.abgestimmt, m.pk - 1 if m.pk % 2 == 0 else None) for m in meldungen
    ]
    weg = berichtigte(meldungen)
    for punkt, m in massgebliche_meldungen(meldungen).items():
        assert m.punkt == punkt and m.stimme and m.pk not in weg
        besser = [x for x in meldungen if x.punkt == punkt and x.stimme and x.pk not in weg and x.abgestimmt and not m.abgestimmt]
        assert not besser  # ein Ergebnis schlägt jede Ankündigung


def test_wirksames_ende():
    assert wirksames_ende(T0, None, T0 + timedelta(hours=17), 18) is None
    assert wirksames_ende(T0, None, T0 + timedelta(hours=18), 18) == T0 + timedelta(hours=18)
    assert wirksames_ende(T0, T0 + timedelta(hours=2), T0 + timedelta(hours=1), 18) == T0 + timedelta(hours=2)
    # ein Ende nach der Höchstdauer wird auf sie gekürzt
    assert wirksames_ende(T0, T0 + timedelta(hours=30), T0 + timedelta(hours=40), 18) == T0 + timedelta(hours=18)
    # die Stellgröße kann den Ticker nicht abschalten: unter einer Stunde gilt eine Stunde
    assert wirksames_ende(T0, None, T0 + timedelta(minutes=30), 0) is None


def test_laeuft():
    assert laeuft(T0, None, T0, 18)
    assert not laeuft(T0, None, T0 - timedelta(seconds=1), 18)
    assert not laeuft(T0, T0 + timedelta(minutes=5), T0 + timedelta(minutes=6), 18)
    assert not laeuft(T0, None, T0 + timedelta(hours=18), 18)
