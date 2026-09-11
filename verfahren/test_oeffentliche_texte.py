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


def test_zukunftswerkstatt_verspricht_keinen_gebauten_korrekturlauf(client):
    """Kein Codepfad beantwortet eine Beanstandung — der Korrekturlauf ist Zielbild, nicht Ist."""
    inhalt = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "die Antwort ist ein Korrekturlauf" not in inhalt
    assert "noch" in inhalt and "nicht gebaut" in inhalt
