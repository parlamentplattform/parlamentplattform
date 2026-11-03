"""Öffentliche Texte müssen wahr sein: Sie sagen, was der Code tut — und zitieren die eigene Satzung richtig."""

from __future__ import annotations

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_zukunftswerkstatt_kennt_ihre_eigene_satzung(client):
    """Die Unterstützer-Schleife (Schritt 4) steht im Satzungsentwurf 2.5 als § 5 Abs 12 und 13 —
    die Seite darf nicht behaupten, dafür läge erst ein Baustein vor."""
    inhalt = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "Satzungsbaustein zur Beschlussfassung" not in inhalt
    assert "Alle sechs Schritte entsprechen dem Satzungsentwurf 2.5" in inhalt
    assert "§ 5 Abs 12 und 13" in inhalt and "Satzung 1.3" in inhalt


def test_zukunftswerkstatt_begrenzt_den_gebauten_korrekturlauf_ehrlich(client):
    """Die erste Nachrechnung betrifft öffentliche Rechtsbezüge, keine internen Werkstatttexte."""
    inhalt = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "die Antwort ist ein Korrekturlauf" not in inhalt
    assert "Nachrechnung" in inhalt and "diesem ersten Korrekturweg noch nicht enthalten" in inhalt
