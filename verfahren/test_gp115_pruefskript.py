'''verify/README.md sagt, was verify/nachrechnen.py tut (Folgewelle 0.115.0).

Die Beschreibung des Ergebnisworts behauptete „beide müssen gleich lauten“, als prüfte das Skript
das Wort des Exports gegen sein eigenes. Es errechnet und nennt nur sein eigenes; den Vergleich zieht,
wer nachrechnet.'''

from pathlib import Path

from verfahren.test_views_aktionen import _nachrechnen_laden

VERIFY = Path(__file__).resolve().parent.parent / 'verify'

EXPORT = {
    'art': 'sache', 'policy': {'mindestbeteiligung': 0.05, 'mehrheitsbasis': 'ja_nein'}, 'stimmberechtigte': 10,
    'stimmen': [{'pseudonym': 'a', 'stimme': 'ja'}, {'pseudonym': 'b', 'stimme': 'nein'}, {'pseudonym': 'c', 'stimme': 'ja'}],
}


def test_das_skript_errechnet_sein_wort_und_vergleicht_es_nicht_mit_dem_des_exports():
    '''So verhält sich das Skript: Ein abweichendes Wort im Export bricht nicht ab und ändert nichts.'''
    nachrechnen = _nachrechnen_laden()
    assert nachrechnen({**EXPORT, 'ergebnis': 'angenommen'})['ergebnis'] == 'angenommen'
    assert nachrechnen({**EXPORT, 'ergebnis': 'abgelehnt'})['ergebnis'] == 'angenommen'


def test_die_beschreibung_behauptet_keinen_vergleich_den_das_skript_nicht_zieht():
    liesmich = (VERIFY / 'README.md').read_text(encoding='utf-8')
    skript = (VERIFY / 'nachrechnen.py').read_text(encoding='utf-8')
    for text in (liesmich, skript):
        assert 'beide müssen gleich lauten' not in text
    absatz = next(a for a in liesmich.split('\n\n') if '`kein_beschluss`' in a)
    assert 'vergleicht' in absatz and 'nicht' in absatz and 'Feld `ergebnis`' in absatz
