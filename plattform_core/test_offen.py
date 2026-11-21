"""Die Hülle der offenen Austauschformate (docs/SCHEMA.md Abschnitt 1, „Offen“; GP-199)."""

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
