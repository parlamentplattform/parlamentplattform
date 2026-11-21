"""GP-199 in den Gremien: Das Gremienprotokoll als JSON ist ein offenes Format.

Es hängt nicht an der Anmeldung; damit ein Nachrechenwerkzeug im Browser einer Schwesterpartei es
lesen kann, trägt jede lesende Antwort `Access-Control-Allow-Origin: *` (docs/SCHEMA.md, „Offen“)."""

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import Gremium

pytestmark = pytest.mark.django_db


def _ziel():
    return reverse('gremien:protokoll', args=[Gremium.KOORDINATIONSRAT.value, timezone.localdate().year])


def test_das_protokoll_traegt_die_kopfzeile_der_offenen_formate(client):
    for antwort in (client.get(_ziel()), client.head(_ziel())):
        assert antwort.status_code == 200
        assert antwort['Access-Control-Allow-Origin'] == '*'


def test_eine_schreibende_anfrage_bekommt_die_kopfzeile_nicht(client):
    assert 'Access-Control-Allow-Origin' not in client.post(_ziel())


def test_angemeldet_und_als_gast_dieselbe_antwort(client):
    """Die Kopfzeile gehört nur an Antworten, die nicht von der Anmeldung abhängen."""
    from verfahren.test_views_aktionen import mitglied_anlegen

    gast = client.get(_ziel()).json()
    client.force_login(mitglied_anlegen('leserin'))
    angemeldet = client.get(_ziel()).json()
    gast.pop('exportiert_am')
    angemeldet.pop('exportiert_am')
    assert gast == angemeldet
