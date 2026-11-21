"""Formungültiger Bericht (GP-144): Die Karte nennt den Korrekturweg und verweist nach erledigter
Nachrechnung auf die Beanstandung. Kein Netz (Attrappe)."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from gremien.models import Gremium, Rolle
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.korrekturen import anfordern
from ki.test_folgenauftraege import ANTWORT, attrappe, neu  # noqa: F401
from ki.test_kontext import antrag  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren
from verfahren.models import Beanstandung
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures('abrufuhr')]

KORREKTURWEG = 'zuständige Gruppe 1 kann ihn nachrechnen lassen'


def _formungueltig(antrag, monkeypatch):
    monkeypatch.setattr(AttrappenAnbieter, 'frage', lambda *a: Antwort('Kein JSON, nur Prosa.', 'test', 1, 2))
    job = neu(antrag)
    assert auftrag_ausfuehren(job.pk) == 'erledigt'
    job.refresh_from_db()
    return job


def _karte(client, antrag):
    html = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    anfang = html.index('id="rechtsbezug"')
    return html[anfang:html.index('ki-historie', anfang) if 'ki-historie' in html[anfang:] else None]


def test_formungueltiger_bericht_nennt_den_korrekturweg(antrag, attrappe, monkeypatch, client):
    _formungueltig(antrag, monkeypatch)
    assert KORREKTURWEG in _karte(client, antrag)


def test_gueltiger_bericht_nennt_keinen_korrekturweg(antrag, attrappe, client):
    job = neu(antrag)
    assert auftrag_ausfuehren(job.pk) == 'erledigt'
    assert KORREKTURWEG not in _karte(client, antrag)


def test_nach_erledigter_nachrechnung_verweist_die_karte_auf_die_beanstandung(antrag, attrappe, monkeypatch, client):
    job = _formungueltig(antrag, monkeypatch)
    m = antrag.eingebracht_von
    Rolle.objects.create(mitglied=m, antrag=antrag, gremium=Gremium.EXPERTENRAT_1, bestaetigt=True,
                         endet_am=timezone.localdate() + timedelta(days=30))
    b = Beanstandung.objects.create(antrag=antrag, lauf=job.lauf, mitglied=m, text='Die Form ist ungültig.')
    korrektur = anfordern(b, m)
    assert f'href="#beanstandung-{b.pk}"' not in _karte(client, antrag)  # wartet noch
    monkeypatch.setattr(AttrappenAnbieter, 'frage', lambda *a: Antwort(ANTWORT, 'test', 1, 2))
    assert auftrag_ausfuehren(korrektur.pk) == 'erledigt'
    karte = _karte(client, antrag)
    assert f'href="#beanstandung-{b.pk}"' in karte
