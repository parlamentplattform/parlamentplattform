"""Auswahl-Beschriftungen (TextChoices) sind übersetzbar (Befund #64, F-33).

Bis 0.45 trugen die meisten `TextChoices` nackte Strings: Auf englischen Seiten standen
„Integritätsrat“, „Beleidigung oder Herabwürdigung“ oder „in Prüfung (Gruppe 2)“ auf Deutsch.
Vorbilder waren `parameter.Gruppe` und `anstoss`."""

import pytest
from django.utils.functional import Promise

from gremien.models import (
    Anlass,
    Aussetzung,
    BeschlussStatus,
    Gremium,
    HinweisQuelle,
    HinweisStatus,
    Pruefung,
    Regelpruefung,
)
from ki.models import Zweck
from mandatare.models import Aufgabenstatus
from parameter.models import Status
from verfahren.models import Meldung, Reaktionsart, Vollzugsstatus

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize(
    "auswahl",
    [
        Gremium,
        Anlass,
        BeschlussStatus,
        Aussetzung.Gegenstand,
        Regelpruefung.Ergebnis,
        HinweisQuelle,
        HinweisStatus,
        Pruefung.KoratEntscheid,
        Meldung.Grund,
        Vollzugsstatus,
        Reaktionsart,
        Zweck,
        Status,
        Aufgabenstatus,
    ],
)
def test_die_beschriftungen_sind_uebersetzbar(auswahl):
    for wahl in auswahl:
        assert isinstance(wahl.label, Promise), f"{auswahl.__name__}.{wahl.name} ist nicht übersetzbar"


def test_die_gremiennamen_erscheinen_auf_der_englischen_seite_uebersetzt(client):
    """Die Besetzungsseite baut ihre Überschriften aus `Gremium.choices` — der Katalog kennt
    „Integritätsrat“ und „Koordinationsrat“ längst, nur kam die Beschriftung nie bei ihm an."""
    inhalt = client.get("/gremien/", HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Integrity council" in inhalt and "Coordination council" in inhalt
    assert "Integritätsrat" not in inhalt
