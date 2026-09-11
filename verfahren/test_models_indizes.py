"""Indizes auf den Filter- und Sortierfeldern der Listen (Befund #81).

Heute nicht messbar — der billigste Schritt, der beim Wachsen als Nächstes fehlt: Jede
Listenansicht filtert Anträge nach Phase und reiht nach Phasenbeginn, `faellige_abschliessen`
filtert Beschlüsse nach Status und Frist, die Fachliste sortiert nach `gestrichen_am`."""

import pytest
from django.db import connection

pytestmark = pytest.mark.django_db


def _indizes(tabelle: str) -> list[list[str]]:
    with connection.cursor() as cursor:
        beschraenkungen = connection.introspection.get_constraints(cursor, tabelle)
    return [b["columns"] for b in beschraenkungen.values() if b["index"]]


def test_antrag_beschluss_und_fachliste_sind_auf_ihren_listenfeldern_indiziert():
    assert ["phase", "phase_beginn"] in _indizes("verfahren_antrag")
    assert ["hervorgehoben"] in _indizes("verfahren_antrag")
    assert ["status", "frist"] in _indizes("gremien_gremienbeschluss")
    assert ["gestrichen_am"] in _indizes("gremien_fachliste")
