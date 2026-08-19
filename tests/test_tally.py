"""Auszählung: Beispiele plus Eigenschaften, die für ALLE Eingaben gelten müssen."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from plattform_core import Policy, Stimme, auszaehlen
from plattform_core.tally import AuszaehlungsFehler

POLICY = Policy(
    id="test",
    version=1,
    unterstuetzung_schwelle=5,
    unterstuetzung_frist_tage=14,
    beratung_tage=21,
    abstimmung_tage=7,
    mindestbeteiligung=0.05,
    mehrheitsbasis="ja_nein",
)
POLICY_ABGEGEBEN = Policy(**{**POLICY.als_dict(), "mehrheitsbasis": "abgegeben"})


def stimmen(ja=0, nein=0, enthaltung=0):
    out = []
    n = 0
    for wert, anzahl in ((Stimme.JA, ja), (Stimme.NEIN, nein), (Stimme.ENTHALTUNG, enthaltung)):
        for _ in range(anzahl):
            out.append((f"p{n}", wert))
            n += 1
    return out


class TestBeispiele:
    def test_einfache_annahme(self):
        r = auszaehlen(stimmen(ja=6, nein=3, enthaltung=1), stimmberechtigte=100, policy=POLICY)
        assert r.angenommen and r.beteiligung_erreicht
        assert (r.ja, r.nein, r.enthaltung) == (6, 3, 1)

    def test_mindestbeteiligung_verfehlt(self):
        # 4 von 100 = 4 % < 5 % — trotz klarer Mehrheit abgelehnt (§ 5 Abs 4)
        r = auszaehlen(stimmen(ja=4), stimmberechtigte=100, policy=POLICY)
        assert not r.angenommen and not r.beteiligung_erreicht

    def test_beteiligung_exakt_an_der_schwelle_genuegt(self):
        r = auszaehlen(stimmen(ja=3, nein=1, enthaltung=1), stimmberechtigte=100, policy=POLICY)
        assert r.beteiligung_erreicht  # 5/100 == 5 %

    def test_enthaltungen_zaehlen_zur_beteiligung(self):
        r = auszaehlen(stimmen(ja=1, enthaltung=4), stimmberechtigte=100, policy=POLICY)
        assert r.beteiligung_erreicht and r.angenommen  # ja 1 > nein 0

    def test_gleichstand_ist_abgelehnt(self):
        r = auszaehlen(stimmen(ja=5, nein=5), stimmberechtigte=100, policy=POLICY)
        assert not r.angenommen

    def test_mehrheitsbasis_abgegeben_macht_enthaltung_zum_faktischen_nein(self):
        s = stimmen(ja=5, nein=2, enthaltung=4)  # 5 von 11 ist keine Mehrheit der Abgegebenen
        assert auszaehlen(s, 100, POLICY).angenommen
        assert not auszaehlen(s, 100, POLICY_ABGEGEBEN).angenommen

    def test_doppeltes_pseudonym_wird_abgewiesen(self):
        with pytest.raises(AuszaehlungsFehler):
            auszaehlen([("p1", Stimme.JA), ("p1", Stimme.NEIN)], 100, POLICY)

    def test_unbekannter_stimmwert_wird_abgewiesen(self):
        with pytest.raises(AuszaehlungsFehler):
            auszaehlen([("p1", "vielleicht")], 100, POLICY)


@given(
    ja=st.integers(0, 300),
    nein=st.integers(0, 300),
    enthaltung=st.integers(0, 300),
    berechtigte=st.integers(1, 5000),
)
def test_eigenschaft_reihenfolge_ist_egal(ja, nein, enthaltung, berechtigte):
    """Die Auszählung darf niemals von der Reihenfolge der Stimmen abhängen."""
    s = stimmen(ja=ja, nein=nein, enthaltung=enthaltung)
    r1 = auszaehlen(s, berechtigte, POLICY)
    r2 = auszaehlen(list(reversed(s)), berechtigte, POLICY)
    assert r1 == r2


@given(
    ja=st.integers(0, 300),
    nein=st.integers(0, 300),
    enthaltung=st.integers(0, 300),
    berechtigte=st.integers(1, 5000),
)
def test_eigenschaft_annahme_impliziert_beteiligung_und_mehrheit(ja, nein, enthaltung, berechtigte):
    r = auszaehlen(stimmen(ja=ja, nein=nein, enthaltung=enthaltung), berechtigte, POLICY)
    if r.angenommen:
        assert r.beteiligung_erreicht
        assert r.ja > r.nein
    assert r.abgegeben == ja + nein + enthaltung


@given(ja=st.integers(0, 200), nein=st.integers(0, 200), berechtigte=st.integers(1, 2000))
def test_eigenschaft_eine_zusaetzliche_ja_stimme_schadet_nie(ja, nein, berechtigte):
    """Monotonie: Eine zusätzliche Ja-Stimme kann einen angenommenen Antrag nie kippen."""
    s = stimmen(ja=ja, nein=nein)
    vorher = auszaehlen(s, berechtigte, POLICY)
    nachher = auszaehlen(s + [("extra", Stimme.JA)], berechtigte, POLICY)
    if vorher.angenommen:
        assert nachher.angenommen
