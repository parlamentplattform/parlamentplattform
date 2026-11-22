'''Das Ergebniswort der Auszählung (Gesamtprüfung GP-049).

Ein örtlicher Antrag, dessen festgehaltener Kreis bei Abstimmungsbeginn keinen Stimmberechtigten hat,
endet weiter in der Phase „abgelehnt“ — daran ändert sich nichts. Aber er heißt nicht mehr so: Kern,
Antrag, Stimmen-Export, Prüfskript und Archiv nennen ihn „kein Beschluss“.'''

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from verfahren import archiv
from verfahren.models import Antrag, antrag_einbringen, stimme_abgeben
from verfahren.test_oertliche_teilnahme import _abstimmung, _einbringen, menschen  # noqa: F401
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    _nachrechnen_laden,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _frist_um(antrag):
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))


def _leerer_kreis(client, menschen, art='sache'):  # noqa: F811
    leute, _ort, _fremdort = menschen
    a = _einbringen(client, leute['autor'], art=art)
    _abstimmung(a, 0)
    _frist_um(a)
    return a


@pytest.mark.parametrize('art', ['sache', 'mandat'])
def test_leerer_ortskreis_heisst_kein_beschluss_im_antrag_im_export_und_im_pruefskript(client, menschen, ordnung, art):  # noqa: F811
    a = _leerer_kreis(client, menschen, art)
    daten = json.loads(client.get(reverse('verfahren:export', args=[a.pk])).content)
    a.refresh_from_db()
    assert a.phase == 'abgelehnt'  # Phase und Rechtsfolge bleiben
    assert a.ergebnis == 'kein_beschluss' and str(a.ergebnis_name) == 'kein Beschluss'
    assert a.auszaehlen().ergebnis == 'kein_beschluss'
    assert daten['ergebnis'] == 'kein_beschluss'
    assert _nachrechnen_laden()(daten)['ergebnis'] == 'kein_beschluss'


def test_angenommen_und_abgelehnt_stehen_im_export_wie_das_pruefskript_sie_errechnet(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f'e{i}') for i in range(4)]
    for stimme, wort in (('ja', 'angenommen'), ('nein', 'abgelehnt')):
        a = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
        assert a.ergebnis is None and a.ergebnis_name == ''  # solange nichts festgestellt ist
        for m in leute[:3]:
            stimme_abgeben(a, m, stimme)
        _frist_um(a)
        daten = json.loads(client.get(reverse('verfahren:export', args=[a.pk])).content)
        a.refresh_from_db()
        assert a.phase == wort and a.ergebnis == wort and str(a.ergebnis_name) == wort
        assert daten['ergebnis'] == wort == _nachrechnen_laden()(daten)['ergebnis']


def test_altbestand_ohne_festgestellten_nenner_und_ohne_kreis_bleibt_abgelehnt(ordnung):  # noqa: F811
    '''Ein Antrag von vor dem örtlichen Kreis (kein Teilnahmegebiet, Nenner nie festgestellt) hat keinen
    leeren Kreis — er heißt weiter „abgelehnt“.'''
    a = antrag_einbringen(mitglied_anlegen('alt'), **ANTRAG, ordnung=ordnung)
    Antrag.objects.filter(pk=a.pk).update(phase='abgelehnt')
    a.refresh_from_db()
    assert a.teilnahmegebiet is None and a.stimmberechtigte_anzahl is None
    assert a.ergebnis == 'abgelehnt'


def test_ein_export_ohne_ergebnisfeld_wird_weiter_gerechnet():
    '''Früher gespeicherte Exporte nennen kein Ergebnis — das Skript errechnet es trotzdem.'''
    alt = {
        'art': 'sache', 'policy': {'mindestbeteiligung': 0.05, 'mehrheitsbasis': 'ja_nein'}, 'stimmberechtigte': 10,
        'stimmen': [{'pseudonym': 'a', 'stimme': 'ja'}, {'pseudonym': 'b', 'stimme': 'nein'}, {'pseudonym': 'c', 'stimme': 'ja'}],
    }
    assert _nachrechnen_laden()(alt)['ergebnis'] == 'angenommen'
    leer = {**alt, 'stimmberechtigte': 0, 'stimmen': [], 'teilnahmegebiet': {'ebene': 'gemeinde'}}
    assert _nachrechnen_laden()(leer)['ergebnis'] == 'kein_beschluss'


def test_das_archiv_nennt_den_leeren_ortskreis_kein_beschluss(client, menschen, ordnung):  # noqa: F811
    a = _leerer_kreis(client, menschen)
    a.fortschreiben()
    a.refresh_from_db()
    daten = json.loads(archiv.als_json(a))
    assert daten['antrag']['phase'] == 'abgelehnt' and daten['antrag']['ergebnis'] == 'kein_beschluss'
    assert daten['antrag']['ergebnis_name'] == 'kein Beschluss'
    block = next(b for b in daten['zeitleiste'] if b['phase'] == 'abgelehnt')
    assert block['name'] == 'Kein Beschluss'
    kopf = archiv.als_markdown(a).split('\n')[2]
    assert 'Kein Beschluss' in kopf and 'Abgelehnt' not in kopf


def test_das_archiv_eines_abgelehnten_antrags_bleibt_abgelehnt(ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f'r{i}') for i in range(4)]
    a = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    _frist_um(a)
    a.refresh_from_db()
    a.fortschreiben()
    daten = json.loads(archiv.als_json(a))
    assert daten['antrag']['ergebnis'] == 'abgelehnt'
    assert 'Abgelehnt' in archiv.als_markdown(a).split('\n')[2]
    laufend = antrag_einbringen(leute[0], **{**ANTRAG, 'titel': 'Noch offen'}, ordnung=ordnung)
    assert json.loads(archiv.als_json(laufend))['antrag']['ergebnis'] is None
