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


def test_startseite_laedt_weder_ris_antwort_noch_rohdaten(client):
    """GP-148 (ZWB-05): Die Titelliste lädt die gespeicherte RIS-Antwort und die Rohdaten nicht."""
    from datetime import date

    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from faktenbasis.models import Norm, RisImport

    lauf = RisImport.objects.create(gesetzesnummer='20001234', stand=date(2026, 11, 1), erfolgreich=True,
                                    antwort={'gross': 'x' * 1000})
    RisImport.objects.create(gesetzesnummer='20001234', stand=date(2026, 11, 2), erfolgreich=False,
                             fehlercode='zeitgrenze', antwort={'gross': 'y'})
    Norm.objects.create(ris_id='NOR40000001', gesetzesnummer='20001234', kurztitel='Synthetisches Gesetz',
                        stand=date(2026, 11, 1), quelle='https://example.invalid/', rohdaten={'gross': 'z' * 1000},
                        inhalt_hash='0' * 64, importlauf=lauf)
    with CaptureQueriesContext(connection) as abfragen:
        antwort = client.get(reverse('faktenbasis:index'))
    assert antwort.status_code == 200
    inhalt = antwort.content.decode()
    assert 'Synthetisches Gesetz' in inhalt and 'zeitgrenze' in inhalt
    sql = [q['sql'] for q in abfragen.captured_queries]
    assert not [s for s in sql if '"antwort"' in s or '"rohdaten"' in s]
    assert len(sql) == 6
