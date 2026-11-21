"""Die Hülle der offenen Austauschformate (docs/SCHEMA.md Abschnitt 1, „Offen“; GP-199)."""

import pytest

from plattform_core.schema import KOPFZEILEN, oeffnen, offenes_format


class _Antwort(dict):
    """Steht für eine HTTP-Antwort: Kopfzeilen werden wie bei Django per Schlüssel gesetzt."""


class _Anfrage:
    def __init__(self, methode: str):
        self.method = methode


def test_get_und_head_bekommen_die_kopfzeile():
    for methode in ('GET', 'HEAD', 'get'):
        assert oeffnen(_Antwort(), methode)['Access-Control-Allow-Origin'] == '*'
    assert KOPFZEILEN == {'Access-Control-Allow-Origin': '*'}


def test_schreibende_methoden_bleiben_ohne_kopfzeile():
    for methode in ('POST', 'PUT', 'DELETE', 'OPTIONS'):
        assert 'Access-Control-Allow-Origin' not in oeffnen(_Antwort(), methode)


def test_der_dekorator_oeffnet_die_antwort_der_ansicht():
    @offenes_format
    def ansicht(anfrage, zahl):
        '''Eine öffentliche Ansicht.'''
        return _Antwort(zahl=zahl)

    antwort = ansicht(_Anfrage('GET'), 7)
    assert antwort['zahl'] == 7 and antwort['Access-Control-Allow-Origin'] == '*'
    assert 'Access-Control-Allow-Origin' not in ansicht(_Anfrage('POST'), 7)
    assert ansicht.__name__ == 'ansicht' and ansicht.__doc__ == 'Eine öffentliche Ansicht.'


# ── Folgewelle 0.115.0: welche Adressen offen sind, steht in der URL-Konfiguration ───────────────

#: Die offenen Austauschformate (docs/SCHEMA.md Abschnitte 3 bis 5): URL-Name und Beispielargumente.
OFFENE_ADRESSEN = {
    'parameter:export': {},
    'parameter:kennzahlen': {},
    'verfahren:audit_json': {},
    'verfahren:export': {'pk': 1},
    'verfahren:umsetzung_json': {},
    'gremien:protokoll': {'gremium': 'koordinationsrat', 'jahr': 2026},
    'mandatare:rechenschaft_json': {},
}

#: Ansichten, die den Dekorator in diesem Zweig noch nicht tragen — die anderen Pakete der Folgewelle
#: bringen ihn an. Die Schlusspflege leert diese Menge nach der Zusammenführung.
NOCH_OHNE_DEKORATOR = {
    'verfahren:audit_json', 'verfahren:export', 'verfahren:umsetzung_json', 'gremien:protokoll',
    'mandatare:rechenschaft_json',
}


@pytest.mark.parametrize('name', [
    pytest.param(name, marks=pytest.mark.xfail(strict=False, reason='Dekorator folgt mit der Zusammenführung'))
    if name in NOCH_OHNE_DEKORATOR else name
    for name in sorted(OFFENE_ADRESSEN)
])
def test_jede_offene_adresse_traegt_den_dekorator(name):
    from django.urls import resolve, reverse

    ansicht = resolve(reverse(name, kwargs=OFFENE_ADRESSEN[name])).func
    assert getattr(ansicht, 'offenes_format', False) is True, name


def _gekennzeichnete_adressen(muster=None, namensraum='') -> set[str]:
    '''Die Namen aller Adressen der URL-Konfiguration, deren Ansicht das Merkmal des Dekorators trägt.'''
    from django.urls import URLResolver, get_resolver

    namen = set()
    for eintrag in get_resolver().url_patterns if muster is None else muster:
        if isinstance(eintrag, URLResolver):
            raum = ':'.join(teil for teil in (namensraum, eintrag.namespace or '') if teil)
            namen |= _gekennzeichnete_adressen(eintrag.url_patterns, raum)
        elif getattr(eintrag.callback, 'offenes_format', False) is True:
            namen.add(':'.join(teil for teil in (namensraum, eintrag.name or '') if teil))
    return namen


def test_keine_adresse_ist_offen_ohne_in_der_liste_zu_stehen():
    '''Gegenlesen: die Gegenrichtung. Wer eine weitere Ansicht öffnet, trägt ihre Adresse in OFFENE_ADRESSEN
    ein — und damit in docs/SCHEMA.md, Abschnitt 1 (`test_schema_dokument_nennt_jede_offene_adresse`).'''
    gekennzeichnet = _gekennzeichnete_adressen()
    assert gekennzeichnet <= set(OFFENE_ADRESSEN), sorted(gekennzeichnet - set(OFFENE_ADRESSEN))
    # Die Suche findet die Ansichten, die den Dekorator schon tragen — sonst bewiese die Zeile oben nichts.
    assert set(OFFENE_ADRESSEN) - NOCH_OHNE_DEKORATOR <= gekennzeichnet


def test_der_dekorator_kennzeichnet_die_ansicht():
    @offenes_format
    def ansicht(anfrage):
        return _Antwort()

    assert ansicht.offenes_format is True


def test_schema_dokument_nennt_jede_offene_adresse():
    import pathlib

    from django.urls import reverse

    dokument = (pathlib.Path(__file__).resolve().parent.parent / 'docs' / 'SCHEMA.md').read_text(encoding='utf-8')
    offen = next(z for z in dokument.splitlines() if z.startswith('| **Offen** |'))
    for name, argumente in OFFENE_ADRESSEN.items():
        pfad = reverse(name, kwargs=argumente)
        muster = {'verfahren:export': '/antrag/<id>/export.json',
                  'gremien:protokoll': '/gremien/protokoll/<gremium>/<jahr>.json'}.get(name, pfad)
        assert f'`{muster}`' in offen, muster
