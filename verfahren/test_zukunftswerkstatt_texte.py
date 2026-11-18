"""Die Erklärseite der Zukunftswerkstatt ohne Grammatikfehler (GP-205, GAST-20)."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_erklaerseite_ohne_die_zwei_grammatikfehler(client):
    inhalt = ' '.join(client.get(reverse('verfahren:zukunftswerkstatt')).content.decode().split())
    assert 'seine Vorschlag' not in inhalt and 'so bleibt sie dem Anliegen treu' not in inhalt
    assert 'seinen Vorschlag' in inhalt and 'so bleibt er dem Anliegen treu' in inhalt
