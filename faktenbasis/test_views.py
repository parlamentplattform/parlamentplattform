"""Öffentliche Seiten der Faktenbasis: was sie über die Verwendung ihrer Daten sagen und wie sparsam sie laden."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import json

import pytest
from django.urls import reverse

from faktenbasis.models import PersonalAggregat, PersonalRessorttabelle
from faktenbasis.test_personalrahmen import daten as personaldaten
from ki.folgenkontext import eingabe, festhalten
from ki.test_kontext import antrag  # noqa: F401
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_personalseiten_nennen_die_uebergabe_an_neue_rechtsfolgenauftraege(client, antrag):
    """GP-152 (ZWB-12): Neue Rechtsfolgenaufträge halten den Personalbestand fest; die Seiten dürfen das
    nicht bestreiten."""
    personaldaten()
    d = json.loads(eingabe(festhalten(antrag, hoechstzeichen=50000)))
    assert d['personal_bestandsgrundlage']['zustand'] == 'vorhanden'
    seiten = (
        reverse('faktenbasis:personal_detail', args=[PersonalAggregat.objects.get().pk]),
        reverse('faktenbasis:personal_ressorts_detail', args=[PersonalRessorttabelle.objects.get().pk]),
    )
    for url in seiten:
        inhalt = client.get(url).content.decode()
        assert 'nicht automatisch in Modellaufträge' not in inhalt
        assert 'Neue Rechtsfolgenaufträge der Zukunftswerkstatt erhalten' in inhalt
