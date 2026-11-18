"""Gesamtprüfung 0.113: Die Übersicht sagt, was sie zählt, und schreibt wie der Rest der Plattform."""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_mitgliederverlauf_nennt_seine_zaehlweise(client):
    """GP-198 (RVA-23): Die Kurve entsteht aus den Beitrittsdaten der heutigen Mitglieder — ein
    Austritt senkt rückwirkend alle früheren Punkte. Die Beschriftung sagt das, statt einen
    Zeitverlauf der Mitgliederzahl zu behaupten."""
    inhalt = client.get(reverse("uebersicht:index"), headers={"accept-language": "de"}).content.decode()
    assert "Mitglieder im Zeitverlauf" not in inhalt
    assert "Heutige Mitglieder nach Beitrittsdatum" in inhalt
