"""Betrieb und Nachweis, erste Behebungsrunde nach der Gesamtprüfung (0.113.0)."""

import pytest
from django.urls import reverse

from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


# --- GP-154: Persönliche Antworten landen in keinem Zwischenspeicher --------------------------------


@pytest.mark.parametrize('name', ['mitglieder:profil', 'mitglieder:profil_export', 'verfahren:audit'])
def test_jede_antwort_an_ein_angemeldetes_konto_traegt_no_store(client, name):
    client.force_login(mitglied_anlegen('cache'))
    antwort = client.get(reverse(name))
    assert antwort.status_code == 200
    assert 'no-store' in antwort['Cache-Control'] and 'private' in antwort['Cache-Control']


def test_gastantworten_bleiben_unveraendert(client):
    antwort = client.get(reverse('verfahren:audit'))
    assert antwort.status_code == 200
    assert 'Cache-Control' not in antwort


def test_eine_eigene_festlegung_der_ansicht_bleibt():
    from django.contrib.auth.models import AnonymousUser
    from django.http import HttpResponse
    from django.test import RequestFactory

    from config.sicherheitsheader import PersoenlichesNichtSpeichern

    anfrage = RequestFactory().get('/')
    anfrage.user = type('Angemeldet', (AnonymousUser,), {'is_authenticated': True})()
    eigene = HttpResponse('x')
    eigene['Cache-Control'] = 'max-age=60, public'
    assert PersoenlichesNichtSpeichern(lambda r: eigene)(anfrage)['Cache-Control'] == 'max-age=60, public'
