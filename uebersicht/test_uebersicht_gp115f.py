'''Übersicht, Folgewelle 0.115.0: die Mitgliederzeile (GP-076) und das Ergebniswort „kein Beschluss“ (GP-049).'''

import re
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Identitaetsstufe
from verfahren.models import Antrag, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _mitgliederzeile(client) -> str:
    inhalt = client.get(reverse('uebersicht:index')).content.decode()
    return re.search(r'<p class="erk">([^<]*neu in den letzten 7 Tagen)</p>', inhalt).group(1)


def test_die_mitgliederzeile_heisst_wie_auf_der_startseite(client):
    '''GP-076: Die Zahl zählt alle aktiven Parteikonten, nicht nur bestätigte — also heißt sie „Mitglieder“.'''
    mitglied_anlegen('bestaetigt')
    zeile = _mitgliederzeile(client)
    assert 'bestätigte' not in zeile and zeile.startswith('Mitglieder ·')
    vorher = client.get(reverse('uebersicht:index')).context['mitglieder_gesamt']
    mitglied_anlegen('ungeprueft', tage=0, stufe=Identitaetsstufe.UNGEPRUEFT)
    nachher = client.get(reverse('uebersicht:index')).context['mitglieder_gesamt']
    assert nachher == vorher + 1  # ein ungeprüftes Konto zählt mit — die Zeile behauptet keine Bestätigung
    assert 'bestätigte Mitglieder' not in client.get(reverse('uebersicht:index')).content.decode()


def test_ein_leerer_oertlicher_kreis_heisst_kein_beschluss_nicht_abgelehnt(client, ordnung):  # noqa: F811
    '''GP-049: Ein örtlicher Antrag ohne Stimmberechtigte endet in der Phase „abgelehnt“; sein Ergebnis
    heißt „kein Beschluss“ — so auch in der Liste der Übersicht. Ein gewöhnlich abgelehnter bleibt abgelehnt.'''
    autor = mitglied_anlegen('autor')
    leer = antrag_einbringen(autor, **{**ANTRAG, 'titel': 'Ohne Stimmberechtigte'}, ordnung=ordnung)
    abgelehnt = antrag_einbringen(autor, **{**ANTRAG, 'titel': 'Gewöhnlich abgelehnt'}, ordnung=ordnung)
    gestern = timezone.now() - timedelta(days=1)
    # Der Zustand eines beendeten örtlichen Verfahrens: am Schreibriegel des Kreises vorbei hergestellt
    Antrag._base_manager.filter(pk=leer.pk).update(
        phase='abgelehnt', phase_beginn=gestern, stimmberechtigte_anzahl=0, ebene='gemeinde',
        teilnahmegebiet={'art': 'gemeinde', 'kennziffer': '10101'},
    )
    Antrag._base_manager.filter(pk=abgelehnt.pk).update(phase='abgelehnt', phase_beginn=gestern, stimmberechtigte_anzahl=5)
    leer.refresh_from_db()
    assert leer.ergebnis == 'kein_beschluss'
    inhalt = client.get(reverse('uebersicht:index')).content.decode()
    karten = inhalt.split('<div class="karte">')
    karte_leer = next(k for k in karten if 'Ohne Stimmberechtigte' in k)
    karte_abgelehnt = next(k for k in karten if 'Gewöhnlich abgelehnt' in k)
    assert 'kein Beschluss' in karte_leer and '>abgelehnt<' not in karte_leer
    assert '>abgelehnt<' in karte_abgelehnt and 'kein Beschluss' not in karte_abgelehnt
