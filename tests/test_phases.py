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


# ── 0.48: Verfahren ohne Beratungsphase (§ 7 Abs 10 lit c und e) ──────────────────────────

import dataclasses  # noqa: E402

from plattform_core.phases import abstimmungsbeginn_ohne_beratung  # noqa: E402

VERTRAUENSFRAGE = dataclasses.replace(
    POLICY,
    unterstuetzung_schwelle=5,
    unterstuetzung_frist_tage=30,
    beratung_entfaellt=True,
    abstimmung_fruehestens_tage=7,
    abstimmung_spaetestens_tage_nach_schwelle=3,
)
BESTAETIGUNG = dataclasses.replace(VERTRAUENSFRAGE, unterstuetzung_schwelle=0)


class TestOhneBeratung:
    def test_vor_der_schwelle_passiert_nichts(self):
        assert naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(10), VERTRAUENSFRAGE, 4) is None

    def test_schwelle_frueh_erreicht_abstimmung_beginnt_am_siebten_tag(self):
        """Schwelle an Tag 2: frühestens Tag 7 (§ 7 Abs 10 lit e) — vorher kein Übergang."""
        erreicht = T0 + tage(2)
        assert (
            naechster_uebergang(
                Phase.UNTERSTUETZUNG, T0, T0 + tage(6), VERTRAUENSFRAGE, 5, schwelle_erreicht_am=erreicht
            )
            is None
        )
        t = naechster_uebergang(
            Phase.UNTERSTUETZUNG, T0, T0 + tage(7), VERTRAUENSFRAGE, 5, schwelle_erreicht_am=erreicht
        )
        assert t.neue_phase is Phase.ABSTIMMUNG and t.wirksam_ab == T0 + tage(7)
        assert "Wartezeit" in t.grund  # Tag 7 liegt nach Schwelle + 3 — die Satzung will es so

    def test_schwelle_spaet_erreicht_abstimmung_beginnt_mit_der_schwelle(self):
        erreicht = T0 + tage(20)
        t = naechster_uebergang(
            Phase.UNTERSTUETZUNG, T0, T0 + tage(25), VERTRAUENSFRAGE, 7, schwelle_erreicht_am=erreicht
        )
        assert t.neue_phase is Phase.ABSTIMMUNG and t.wirksam_ab == erreicht
        assert "Wartezeit" not in t.grund
        assert t.wirksam_ab <= erreicht + tage(3)  # spätestens am dritten Tag danach

    def test_ohne_zeitpunkt_gilt_jetzt_begrenzt_auf_das_fristende(self):
        t = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(12), VERTRAUENSFRAGE, 5)
        assert t.neue_phase is Phase.ABSTIMMUNG and t.wirksam_ab == T0 + tage(12)
        spaet = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(40), VERTRAUENSFRAGE, 5)
        assert spaet.neue_phase is Phase.ABSTIMMUNG and spaet.wirksam_ab == T0 + tage(30)

    def test_schwelle_nach_fristende_zaehlt_nicht(self):
        zu_spaet = T0 + tage(30) + timedelta(hours=1)
        t = naechster_uebergang(
            Phase.UNTERSTUETZUNG, T0, T0 + tage(31), VERTRAUENSFRAGE, 5, schwelle_erreicht_am=zu_spaet
        )
        assert t.neue_phase is Phase.VERFALLEN and t.wirksam_ab == T0 + tage(30)

    def test_frist_abgelaufen_ohne_schwelle_verfaellt_zum_fristende(self):
        assert naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(30), VERTRAUENSFRAGE, 3) is None
        t = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(45), VERTRAUENSFRAGE, 3)
        assert t.neue_phase is Phase.VERFALLEN and t.wirksam_ab == T0 + tage(30)
        assert "§ 7 Abs 10 lit c" in t.grund

    def test_schwelle_null_gilt_mit_dem_einbringen_als_erreicht(self):
        """Bestätigungsantrag (§ 7 Abs 10 lit f Z 3): Abstimmung am siebten Tag nach Einbringung."""
        assert naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(6), BESTAETIGUNG, 0) is None
        t = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, T0 + tage(9), BESTAETIGUNG, 0)
        assert t.neue_phase is Phase.ABSTIMMUNG and t.wirksam_ab == T0 + tage(7)

    def test_ein_veroeffentlichtes_erreichen_bleibt_trotz_rueckzug_bestehen(self):
        """Schwelle an Tag 2 veröffentlicht (lit c, Anfechtungsfrist lit h) — zieht danach jemand
        zurück, fällt der Antrag nicht zurück: Die Abstimmung beginnt an Tag 7, kein Verfall."""
        erreicht = T0 + tage(2)
        t = naechster_uebergang(
            Phase.UNTERSTUETZUNG, T0, T0 + tage(7), VERTRAUENSFRAGE, 4, schwelle_erreicht_am=erreicht
        )
        assert t.neue_phase is Phase.ABSTIMMUNG and t.wirksam_ab == T0 + tage(7)
        spaet = naechster_uebergang(
            Phase.UNTERSTUETZUNG, T0, T0 + tage(40), VERTRAUENSFRAGE, 4, schwelle_erreicht_am=erreicht
        )
        assert spaet.neue_phase is Phase.ABSTIMMUNG and spaet.wirksam_ab == T0 + tage(7)

    def test_sofortiger_beginn_ohne_wartezeit(self):
        sofort = dataclasses.replace(VERTRAUENSFRAGE, abstimmung_fruehestens_tage=0)
        erreicht = T0 + tage(1)
        assert abstimmungsbeginn_ohne_beratung(T0, erreicht, sofort) == erreicht
        t = naechster_uebergang(Phase.UNTERSTUETZUNG, T0, erreicht, sofort, 5, schwelle_erreicht_am=erreicht)
        assert t.wirksam_ab == erreicht

    def test_die_uebrigen_phasen_bleiben_wie_bisher(self):
        """Ohne Beratungsphase gibt es keine Beratung — die Abstimmung endet wie bei jedem Antrag."""
        angenommen = auszaehlen([(f"p{i}", Stimme.JA) for i in range(6)], 100, VERTRAUENSFRAGE)
        t = naechster_uebergang(Phase.ABSTIMMUNG, T0, T0 + tage(7), VERTRAUENSFRAGE, 0, angenommen)
        assert t.neue_phase is Phase.ANGENOMMEN
        for endphase in END_PHASEN:
            assert naechster_uebergang(endphase, T0, T0 + tage(3), VERTRAUENSFRAGE, 9) is None


@given(stunden=st.integers(0, 24 * 60), unterstuetzungen=st.integers(0, 12), erreicht_h=st.integers(0, 24 * 40))
def test_eigenschaft_ohne_beratung_beginnt_nie_vor_tag_sieben(stunden, unterstuetzungen, erreicht_h):
    """§ 7 Abs 10 lit e: frühestens am siebten Tag nach Einbringung — für jede Eingabe."""
    jetzt = T0 + timedelta(hours=stunden)
    t = naechster_uebergang(
        Phase.UNTERSTUETZUNG, T0, jetzt, VERTRAUENSFRAGE, unterstuetzungen,
        schwelle_erreicht_am=T0 + timedelta(hours=erreicht_h),
    )
    if t is not None and t.neue_phase is Phase.ABSTIMMUNG:
        assert t.wirksam_ab >= T0 + tage(7) and t.wirksam_ab <= jetzt
    if t is not None and t.neue_phase is Phase.VERFALLEN:
        assert t.wirksam_ab == T0 + tage(30)
