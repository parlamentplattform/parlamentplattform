"""Gesamtprüfung 18.11.2026, erste Behebungsrunde: Zählkern, Prüfskript, Regelverzeichnis.

Jeder Test stellt einen Befund (GP-Kennung) nach und hält die Behebung fest."""

from hypothesis import given
from hypothesis import strategies as st

from plattform_core import Policy
from plattform_core.tally import auszaehlen, personenwahl_auszaehlen
from verify.nachrechnen import nachrechnen

ZEIT = '2026-11-18T12:58:55.763580+00:00'


def _policy(prozent=5, mehrheitsbasis='ja_nein'):
    return Policy(
        id='test',
        version=1,
        unterstuetzung_schwelle=5,
        unterstuetzung_frist_tage=14,
        beratung_tage=21,
        abstimmung_tage=7,
        mindestbeteiligung=prozent / 100,
        mehrheitsbasis=mehrheitsbasis,
    )


def _kandidatur_export(bewerbungen, zustimmungen, berechtigte, prozent=5):
    """Ein Kandidatur-Export, wie `export_json` ihn schreibt. `bewerbungen`: (nummer, zurueckgezogen);
    `zustimmungen`: (pseudonym, nummer, ruecknahme) mit ruecknahme None (gilt), 'wert' (neue
    Schreibweise `zurueckgenommen: true`) oder 'zeit' (alte Schreibweise mit Zeitangabe)."""
    zeilen = []
    for pseudonym, nummer, ruecknahme in zustimmungen:
        zeile = {'pseudonym': pseudonym, 'bewerbung': nummer}
        if ruecknahme == 'wert':
            zeile['zurueckgenommen'] = True
        elif ruecknahme == 'zeit':
            zeile['zurueckgenommen_am'] = ZEIT
        elif ruecknahme == 'offen':
            zeile['zurueckgenommen'] = False
            zeile['zurueckgenommen_am'] = None
        zeilen.append(zeile)
    return {
        'art': 'mandat',
        'policy': {'mindestbeteiligung': prozent / 100},
        'stimmberechtigte': berechtigte,
        'stimmen': [],
        'bewerbungen': [
            {'bewerbung': nummer, 'name': f'B{nummer}', 'eingereicht_am': '2026-11-01', 'zurueckgezogen': weg}
            for nummer, weg in bewerbungen
        ],
        'zustimmungen': zeilen,
    }


def _kern(bewerbungen, zustimmungen, berechtigte, prozent=5):
    """Dieselbe Wahl, wie `Antrag.kandidatur_auszaehlen` sie dem Kern übergibt: nur wählbare
    Bewerbungen, nur gültige Zustimmungen zu ihnen."""
    waehlbar = [nummer for nummer, weg in bewerbungen if not weg]
    gueltig = [(p, nummer) for p, nummer, ruecknahme in zustimmungen if ruecknahme in (None, 'offen') and nummer in waehlbar]
    return personenwahl_auszaehlen(gueltig, waehlbar, berechtigte, _policy(prozent))


def _gleich(skript, kern):
    assert skript['gewaehlt'] == kern.gewonnen_id
    assert skript['beteiligung'] == kern.beteiligung
    assert skript['beteiligung_erreicht'] is kern.beteiligung_erreicht
    assert skript['angenommen'] is kern.angenommen
    assert [(p['platz'], p['bewerbung'], p['zustimmungen']) for p in skript['plaetze']] == [
        (p.platz, p.bewerbung_id, p.stimmen) for p in kern.plaetze
    ]


# --- GP-022: zurückgenommene Zustimmungen zählen im Prüfskript nicht -------------------------------


def test_pruefskript_ueberspringt_zurueckgenommene_zustimmungen():
    """ASR-01: Zwei Mitglieder stimmen B zu und nehmen zurück, eines stimmt A zu. Die Plattform wählt
    A mit Beteiligung 1; das Skript nannte B mit Beteiligung 3. Beide Schreibweisen der Rücknahme
    (Wahrheitswert und alte Zeitangabe) müssen übersprungen werden."""
    bewerbungen = [(1, False), (2, False)]
    for schreibweise in ('wert', 'zeit'):
        zustimmungen = [('p1', 2, schreibweise), ('p2', 2, schreibweise), ('p3', 1, 'offen')]
        skript = nachrechnen(_kandidatur_export(bewerbungen, zustimmungen, 10))
        kern = _kern(bewerbungen, zustimmungen, 10)
        _gleich(skript, kern)
        assert skript['gewaehlt'] == 1 and skript['beteiligung'] == 1
        assert skript['zurueckgenommen'] == 2


def test_pruefskript_nur_zurueckgenommene_zustimmungen_tragen_keine_beteiligung():
    """ASR-01, zweiter Fall: Eine gültige Zustimmung bei 40 Stimmberechtigten verfehlt die
    Mindestbeteiligung; drei zurückgenommene dürfen sie nicht über die Schwelle heben."""
    bewerbungen = [(1, False)]
    zustimmungen = [('p1', 1, None), ('p2', 1, 'wert'), ('p3', 1, 'zeit'), ('p4', 1, 'wert')]
    skript = nachrechnen(_kandidatur_export(bewerbungen, zustimmungen, 40))
    kern = _kern(bewerbungen, zustimmungen, 40)
    _gleich(skript, kern)
    assert skript['beteiligung_erreicht'] is False and skript['gewaehlt'] is None
    assert skript['zurueckgenommen'] == 3


def test_pruefskript_weist_doppelte_zeilen_auch_bei_ruecknahme_ab():
    """Die Plattform führt je Pseudonym und Bewerbung genau eine Zeile; eine zweite ist ein Fehler
    im Export, gleich ob eine der beiden zurückgenommen ist."""
    import pytest

    export = _kandidatur_export([(1, False)], [('p1', 1, 'wert'), ('p1', 1, None)], 10)
    with pytest.raises(SystemExit, match='doppelt'):
        nachrechnen(export)


_WAHL = st.integers(1, 6).flatmap(
    lambda anzahl: st.tuples(
        st.lists(st.booleans(), min_size=anzahl, max_size=anzahl),
        st.lists(
            st.tuples(st.integers(0, 11), st.integers(1, anzahl), st.sampled_from([None, 'offen', 'wert', 'zeit'])),
            max_size=40,
            unique_by=lambda z: (z[0], z[1]),
        ),
    )
)


@given(wahl=_WAHL, berechtigte=st.integers(1, 300), prozent=st.integers(5, 100))
def test_eigenschaft_pruefskript_und_kern_zaehlen_jede_kandidatur_gleich(wahl, berechtigte, prozent):
    """§ 5 Abs 8: Für jede Wahl mit zurückgezogenen Bewerbungen und zurückgenommenen Zustimmungen
    nennt das unabhängige Skript dieselben Plätze, dieselbe Beteiligung und denselben Gewinner
    wie der Kern (Schwellen in ganzen Prozent, wie das Register sie führt)."""
    zurueckgezogen, zeilen = wahl
    bewerbungen = [(nummer, weg) for nummer, weg in enumerate(zurueckgezogen, start=1)]
    zustimmungen = [(f'p{p}', nummer, ruecknahme) for p, nummer, ruecknahme in zeilen]
    skript = nachrechnen(_kandidatur_export(bewerbungen, zustimmungen, berechtigte, prozent))
    _gleich(skript, _kern(bewerbungen, zustimmungen, berechtigte, prozent))
    assert skript['zurueckgenommen'] == sum(1 for z in zustimmungen if z[2] in ('wert', 'zeit'))


@given(
    ja=st.integers(0, 120),
    nein=st.integers(0, 120),
    enthaltung=st.integers(0, 120),
    berechtigte=st.integers(1, 3000),
    prozent=st.integers(5, 100),
    basis=st.sampled_from(['ja_nein', 'abgegeben']),
)
def test_eigenschaft_pruefskript_und_kern_zaehlen_jede_sachfrage_gleich(ja, nein, enthaltung, berechtigte, prozent, basis):
    """Dieselbe Gegenprobe für Sachfragen, beide Mehrheitsbasen."""
    werte = ['ja'] * ja + ['nein'] * nein + ['enthaltung'] * enthaltung
    stimmen = [(f'p{i}', wert) for i, wert in enumerate(werte)]
    kern = auszaehlen(stimmen, berechtigte, _policy(prozent, basis))
    skript = nachrechnen(
        {
            'art': 'sache',
            'policy': {'mindestbeteiligung': prozent / 100, 'mehrheitsbasis': basis},
            'stimmberechtigte': berechtigte,
            'stimmen': [{'pseudonym': p, 'stimme': wert} for p, wert in stimmen],
        }
    )
    assert (skript['ja'], skript['nein'], skript['enthaltung']) == (kern.ja, kern.nein, kern.enthaltung)
    assert skript['beteiligung_erreicht'] is kern.beteiligung_erreicht
    assert skript['angenommen'] is kern.angenommen
