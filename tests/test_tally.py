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


# --- GP-050: Mindestbeteiligung als Kopfzahl ---------------------------------------------------------


class TestMindeststimmen:
    def test_kopfzahl_fuer_kleine_und_grosse_kreise(self):
        from plattform_core.tally import mindeststimmen

        assert mindeststimmen(20, 0.05) == 1
        assert mindeststimmen(21, 0.05) == 2  # 1/21 liegt unter 5 %
        assert mindeststimmen(100, 0.05) == 5
        assert mindeststimmen(1234, 0.05) == 62
        assert mindeststimmen(3, 0.5) == 2
        assert mindeststimmen(0, 0.05) == 0  # leerer Kreis: keine Kopfzahl

    def test_begruendung_nennt_die_kopfzahl_und_kein_punktformat(self):
        r = auszaehlen(stimmen(ja=4), stimmberechtigte=100, policy=POLICY)
        assert 'erforderlich 5 Stimmen (5 %)' in r.begruendung
        assert '5.0%' not in r.begruendung and '4/100' in r.begruendung

    def test_begruendung_nennt_eine_einzelne_stimme_in_der_einzahl(self):
        r = auszaehlen([], stimmberechtigte=20, policy=POLICY)
        assert 'erforderlich 1 Stimme (5 %)' in r.begruendung

    def test_begruendung_schreibt_gebrochene_prozente_mit_komma(self):
        ordnung = Policy(**{**POLICY.als_dict(), 'mindestbeteiligung': 0.125})
        r = auszaehlen(stimmen(ja=1), stimmberechtigte=100, policy=ordnung)
        assert 'erforderlich 13 Stimmen (12,5 %)' in r.begruendung

    def test_kandidatur_nennt_die_kopfzahl(self):
        from plattform_core.tally import personenwahl_auszaehlen

        verfehlt = personenwahl_auszaehlen([('p1', 1)], [1, 2], 100, POLICY)
        assert '1/100, erforderlich 5 Stimmen (5 %)' in verfehlt.begruendung
        gewaehlt = personenwahl_auszaehlen([('p1', 1)], [1, 2], 20, POLICY)
        assert 'Mindestbeteiligung von 1 Stimme (5 %)' in gewaehlt.begruendung


@given(
    berechtigte=st.integers(1, 100_000),
    prozent=st.integers(5, 100),
)
def test_eigenschaft_mindeststimmen_ist_die_kleinste_zahl_die_genuegt(berechtigte, prozent):
    """Die Kopfzahl kommt aus derselben Bedingung wie die Auszählung: Mit ihr ist die
    Mindestbeteiligung erreicht, mit einer Stimme weniger nicht."""
    from plattform_core.tally import mindestbeteiligung_erreicht, mindeststimmen

    anteil = prozent / 100
    n = mindeststimmen(berechtigte, anteil)
    assert 1 <= n <= berechtigte
    assert mindestbeteiligung_erreicht(n, berechtigte, anteil)
    assert not mindestbeteiligung_erreicht(n - 1, berechtigte, anteil)


@given(berechtigte=st.integers(1, 5000), anteil=st.floats(0.05, 1.0, allow_nan=False))
def test_eigenschaft_mindeststimmen_gilt_fuer_jeden_anteil(berechtigte, anteil):
    from plattform_core.tally import mindestbeteiligung_erreicht, mindeststimmen

    n = mindeststimmen(berechtigte, anteil)
    assert mindestbeteiligung_erreicht(n, berechtigte, anteil)
    assert n == 0 or not mindestbeteiligung_erreicht(n - 1, berechtigte, anteil)


# --- Gegenprobe und Prüfsumme der Stimmliste (Gesamtprüfung GP-138) -----------------------------------


class TestGegenprobe:
    def test_eine_stimmige_liste_hat_keine_abweichung(self):
        from plattform_core.tally import gegenprobe

        assert gegenprobe(stimmzettel=5, waehler=5, ohne_registerzeile=0, stimmberechtigte=5, stimmereignisse=5) == ()
        assert gegenprobe(stimmzettel=0, waehler=0, ohne_registerzeile=0, stimmberechtigte=0, stimmereignisse=0) == ()

    def test_stimmzettel_ohne_registerzeile(self):
        from plattform_core.tally import OHNE_REGISTERZEILE, gegenprobe

        assert gegenprobe(stimmzettel=6, waehler=6, ohne_registerzeile=1, stimmberechtigte=10, stimmereignisse=6) == (
            OHNE_REGISTERZEILE,
        )

    def test_mehr_stimmen_als_stimmberechtigte(self):
        from plattform_core.tally import UEBERZAHL, gegenprobe

        assert gegenprobe(stimmzettel=9, waehler=9, ohne_registerzeile=0, stimmberechtigte=5, stimmereignisse=9) == (UEBERZAHL,)
        # Zustimmungswahl: mehrere Zustimmungen je Person sind keine Überzahl — es zählen die Menschen.
        assert gegenprobe(stimmzettel=9, waehler=3, ohne_registerzeile=0, stimmberechtigte=5, stimmereignisse=9) == ()

    def test_zahl_der_stimmereignisse_weicht_ab(self):
        from plattform_core.tally import EREIGNISSE_WEICHEN_AB, gegenprobe

        assert gegenprobe(stimmzettel=7, waehler=7, ohne_registerzeile=0, stimmberechtigte=20, stimmereignisse=5) == (
            EREIGNISSE_WEICHEN_AB,
        )

    def test_altbestand_ohne_nenner_und_ohne_versiegelten_beginn_wird_nur_gegen_das_register_geprueft(self):
        from plattform_core.tally import OHNE_REGISTERZEILE, gegenprobe

        assert gegenprobe(stimmzettel=3, waehler=3, ohne_registerzeile=0, stimmberechtigte=None, stimmereignisse=None) == ()
        assert gegenprobe(stimmzettel=3, waehler=3, ohne_registerzeile=2, stimmberechtigte=None, stimmereignisse=None) == (
            OHNE_REGISTERZEILE,
        )

    def test_alle_abweichungen_in_fester_reihenfolge(self):
        from plattform_core.tally import EREIGNISSE_WEICHEN_AB, OHNE_REGISTERZEILE, UEBERZAHL, gegenprobe

        assert gegenprobe(stimmzettel=9, waehler=9, ohne_registerzeile=4, stimmberechtigte=5, stimmereignisse=5) == (
            OHNE_REGISTERZEILE, UEBERZAHL, EREIGNISSE_WEICHEN_AB,
        )


class TestPruefsummeDerStimmliste:
    def test_von_hand_nachrechenbar(self):
        import hashlib

        from plattform_core.tally import stimmliste_pruefsumme

        zeilen = [['b2', 'nein'], ['a1', 'ja']]
        text = '[["a1","ja"],["b2","nein"]]'
        assert stimmliste_pruefsumme(zeilen) == hashlib.sha256(text.encode('utf-8')).hexdigest()

    def test_reihenfolge_ist_gleichgueltig_und_jede_aenderung_sichtbar(self):
        from plattform_core.tally import stimmliste_pruefsumme

        liste = [('a1', 'ja'), ('b2', 'nein'), ('c3', 'enthaltung')]
        summe = stimmliste_pruefsumme(liste)
        assert stimmliste_pruefsumme(list(reversed(liste))) == summe
        assert stimmliste_pruefsumme([('a1', 'ja'), ('b2', 'ja'), ('c3', 'enthaltung')]) != summe
        assert stimmliste_pruefsumme(liste[:2]) != summe
        assert stimmliste_pruefsumme([*liste, ('d4', 'ja')]) != summe
        assert len(summe) == 64

    def test_die_leere_liste_hat_eine_pruefsumme(self):
        import hashlib

        from plattform_core.tally import stimmliste_pruefsumme

        assert stimmliste_pruefsumme([]) == hashlib.sha256(b'[]').hexdigest()


@given(
    ja=st.integers(0, 40), nein=st.integers(0, 40), enthaltung=st.integers(0, 40),
    berechtigte=st.integers(1, 200),
)
def test_eigenschaft_die_gegenprobe_aendert_kein_ergebnis(ja, nein, enthaltung, berechtigte):
    """Die Gegenprobe steht neben der Auszählung, nicht in ihr: `auszaehlen` rechnet für jede Liste,
    wie es immer gerechnet hat — auch für eine mit mehr Stimmen als Stimmberechtigten."""
    from plattform_core.tally import UEBERZAHL, gegenprobe

    r = auszaehlen(stimmen(ja=ja, nein=nein, enthaltung=enthaltung), stimmberechtigte=berechtigte, policy=POLICY)
    abgegeben = ja + nein + enthaltung
    assert (r.ja, r.nein, r.enthaltung) == (ja, nein, enthaltung)
    assert r.beteiligung_erreicht == (abgegeben * 100 >= 5 * berechtigte)
    assert r.angenommen == (r.beteiligung_erreicht and ja > nein)
    befund = gegenprobe(
        stimmzettel=abgegeben, waehler=abgegeben, ohne_registerzeile=0, stimmberechtigte=berechtigte, stimmereignisse=abgegeben
    )
    assert (UEBERZAHL in befund) == (abgegeben > berechtigte)


# --- GP-049: das Ergebniswort der Auszählung ---------------------------------------------------------


class TestErgebniswort:
    def test_leerer_oertlicher_kreis_heisst_kein_beschluss_und_bleibt_nicht_angenommen(self):
        r = auszaehlen([], stimmberechtigte=0, policy=POLICY, leerer_oertlicher_kreis=True)
        assert r.ergebnis == 'kein_beschluss'
        assert not r.angenommen and 'kein Beschluss' in r.begruendung  # Rechtsfolge und Satz unverändert

    def test_angenommen_und_abgelehnt_heissen_wie_bisher(self):
        assert auszaehlen(stimmen(ja=6, nein=3), stimmberechtigte=100, policy=POLICY).ergebnis == 'angenommen'
        assert auszaehlen(stimmen(ja=3, nein=6), stimmberechtigte=100, policy=POLICY).ergebnis == 'abgelehnt'
        # Verfehlte Mindestbeteiligung bleibt „abgelehnt“ — ob sie ein eigenes Wort bekommt, ist nicht entschieden.
        assert auszaehlen(stimmen(ja=4), stimmberechtigte=100, policy=POLICY).ergebnis == 'abgelehnt'

    def test_personenwahl_im_leeren_kreis_heisst_kein_beschluss(self):
        from plattform_core.tally import personenwahl_auszaehlen

        leer = personenwahl_auszaehlen([], [7], 0, POLICY, leerer_oertlicher_kreis=True)
        assert leer.ergebnis == 'kein_beschluss' and not leer.angenommen and leer.gewonnen_id is None
        assert personenwahl_auszaehlen([('p1', 7)], [7], 10, POLICY).ergebnis == 'angenommen'
        assert personenwahl_auszaehlen([], [7], 10, POLICY).ergebnis == 'abgelehnt'

    def test_die_phasenfolge_bleibt_abgelehnt(self):
        from datetime import UTC, datetime, timedelta

        from plattform_core.phases import Phase, naechster_uebergang

        beginn = datetime(2026, 3, 1, 12, 0, tzinfo=UTC)
        r = auszaehlen([], stimmberechtigte=0, policy=POLICY, leerer_oertlicher_kreis=True)
        uebergang = naechster_uebergang(
            Phase.ABSTIMMUNG, beginn, beginn + timedelta(days=8), POLICY, unterstuetzungen=0, auszaehlung=r
        )
        assert uebergang.neue_phase is Phase.ABGELEHNT


@given(ja=st.integers(0, 40), nein=st.integers(0, 40), enthaltung=st.integers(0, 40), berechtigte=st.integers(1, 200))
def test_eigenschaft_das_ergebniswort_folgt_allein_aus_annahme_und_nenner(ja, nein, enthaltung, berechtigte):
    from plattform_core.tally import ergebnis_wort

    r = auszaehlen(stimmen(ja=ja, nein=nein, enthaltung=enthaltung), stimmberechtigte=berechtigte, policy=POLICY)
    assert r.ergebnis == ('angenommen' if r.angenommen else 'abgelehnt') == ergebnis_wort(r.angenommen, berechtigte)
