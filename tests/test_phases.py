"""Phasenautomat: Fristen, Schwellen, Determinismus."""

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from plattform_core import Phase, Policy, Stimme, auszaehlen, naechster_uebergang
from plattform_core.phases import END_PHASEN, abstimmung_frist_ende, stimme_zulaessig

T0 = datetime(2026, 9, 1, 12, 0, tzinfo=UTC)
POLICY = Policy(
    id="test",
    version=1,
    unterstuetzung_schwelle=10,
    unterstuetzung_frist_tage=14,
    beratung_tage=21,
    abstimmung_tage=7,
    mindestbeteiligung=0.05,
    mehrheitsbasis="ja_nein",
)


def tage(n) -> timedelta:
    return timedelta(days=n)


class TestUnterstuetzung:
    def test_vor_frist_und_unter_schwelle_passiert_nichts(self):
        assert naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(3), POLICY, 9) is None

    def test_schwelle_erreicht_wechselt_sofort_in_beratung(self):
        t = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(3), POLICY, 10)
        assert t.neue_phase is Phase.BERATUNG
        assert t.wirksam_ab == T0 + tage(3)

    def test_frist_abgelaufen_ohne_schwelle_verfaellt_zum_fristende(self):
        t = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(20), POLICY, 9)
        assert t.neue_phase is Phase.VERFALLEN
        assert t.wirksam_ab == T0 + tage(14)  # Fristende, nicht Jobzeitpunkt

    def test_spaete_verarbeitung_verfaelscht_den_uebergang_nicht(self):
        """Schwelle war rechtzeitig erreicht, der Hintergrundjob lief erst später:
        der Übergang wird rückwirkend zum Fristende wirksam."""
        t = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(30), POLICY, 15)
        assert t.neue_phase is Phase.BERATUNG
        assert t.wirksam_ab == T0 + tage(14)


class TestBeratungUndAbstimmung:
    def test_beratung_endet_exakt_nach_21_tagen(self):
        assert (
            naechster_uebergang(Phase.BERATUNG, T0, T0 + tage(21) - timedelta(seconds=1), POLICY, 0) is None
        )
        t = naechster_uebergang(Phase.BERATUNG, T0, T0 + tage(21), POLICY, 0)
        assert t.neue_phase is Phase.ABSTIMMUNG and t.wirksam_ab == T0 + tage(21)

    def test_abstimmungsende_braucht_auszaehlung(self):
        with pytest.raises(ValueError):
            naechster_uebergang(Phase.ABSTIMMUNG, T0, T0 + tage(7), POLICY, 0, auszaehlung=None)

    def test_abstimmungsende_uebernimmt_das_ausgezaehlte_ergebnis(self):
        angenommen = auszaehlen([(f"p{i}", Stimme.JA) for i in range(6)], 100, POLICY)
        t = naechster_uebergang(Phase.ABSTIMMUNG, T0, T0 + tage(7), POLICY, 0, angenommen)
        assert t.neue_phase is Phase.ANGENOMMEN
        abgelehnt = auszaehlen([(f"p{i}", Stimme.NEIN) for i in range(6)], 100, POLICY)
        t = naechster_uebergang(Phase.ABSTIMMUNG, T0, T0 + tage(7), POLICY, 0, abgelehnt)
        assert t.neue_phase is Phase.ABGELEHNT


class TestStimmzulaessigkeit:
    def test_nur_waehrend_laufender_abstimmung(self):
        assert not stimme_zulaessig(Phase.BERATUNG, T0, T0 + tage(1), POLICY)
        assert stimme_zulaessig(Phase.ABSTIMMUNG, T0, T0 + tage(1), POLICY)

    def test_keine_stimme_ab_fristende(self):
        frist = abstimmung_frist_ende(T0, POLICY)
        assert stimme_zulaessig(Phase.ABSTIMMUNG, T0, frist - timedelta(seconds=1), POLICY)
        assert not stimme_zulaessig(Phase.ABSTIMMUNG, T0, frist, POLICY)


@given(
    stunden=st.integers(0, 24 * 60),
    unterstuetzungen=st.integers(0, 40),
)
def test_eigenschaft_endphasen_sind_endgueltig(stunden, unterstuetzungen):
    """Aus einer Endphase führt niemals ein Übergang heraus."""
    jetzt = T0 + timedelta(hours=stunden)
    for endphase in END_PHASEN:
        assert naechster_uebergang(endphase, T0, jetzt, POLICY, unterstuetzungen) is None


@given(stunden=st.integers(0, 24 * 60), unterstuetzungen=st.integers(0, 40))
def test_eigenschaft_determinismus(stunden, unterstuetzungen):
    """Gleiche Eingaben ⇒ exakt gleicher Übergang (keine versteckte Uhr, kein Zufall)."""
    jetzt = T0 + timedelta(hours=stunden)
    a = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, jetzt, POLICY, unterstuetzungen)
    b = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, jetzt, POLICY, unterstuetzungen)
    assert a == b
