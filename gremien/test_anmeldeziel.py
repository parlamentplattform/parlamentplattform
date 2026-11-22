"""GP-100 in den Gremien: Wer als Gast eine Gremienseite öffnet und sich anmeldet, landet wieder dort.

Die Gremienansichten schickten Gäste bisher ohne Ziel zur Anmeldung (`redirect('mitglieder:login')`);
nach dem Anmeldelink stand man im Parlament statt auf der Seite, die man öffnen wollte."""

from __future__ import annotations

from urllib.parse import urlencode

import pytest
from django.test import Client
from django.urls import reverse

from gremien.models import Gremium
from mitglieder.test_views import _aktives_konto, _link_mit_ziel

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('name, args', [
    ('gremien:expertenrat', []),
    ('gremien:koordination', []),
    ('gremien:integritaet', []),
    ('gremien:pruefung', []),
    ('gremien:mein', []),
    ('gremien:rat', [Gremium.BERICHTSWESENRAT.value]),
])
def test_gast_wird_mit_der_gremienseite_als_ziel_zur_anmeldung_geschickt(client, name, args):
    pfad = reverse(name, args=args)
    antwort = client.get(pfad)
    assert antwort.status_code == 302
    assert antwort['Location'] == reverse('mitglieder:login') + '?' + urlencode({'next': pfad})


def test_nach_dem_anmeldelink_steht_der_gast_wieder_auf_der_gremienseite(client):
    _aktives_konto()
    pfad = reverse('gremien:expertenrat')
    umleitung = client.get(pfad)
    html = client.get(umleitung['Location']).content.decode()
    assert f'name="ziel" value="{pfad}"' in html
    link, weiter = _link_mit_ziel(client, pfad)
    assert weiter == pfad
    antwort = Client().post(link)  # der Link wird oft auf einem anderen Gerät geöffnet
    assert antwort.status_code == 302 and antwort['Location'] == pfad


def test_schreibende_gremienwege_schicken_ohne_ziel_zur_anmeldung(client):
    """Ein POST hat kein lesbares Ziel — die Anmeldung führt dann wie bisher ins Parlament."""
    for name, args in (('gremien:ueberlastung_melden', []), ('gremien:rat_beschluss', [Gremium.BERICHTSWESENRAT.value])):
        antwort = client.post(reverse(name, args=args), {})
        assert antwort.status_code == 302 and antwort['Location'] == reverse('mitglieder:login')
