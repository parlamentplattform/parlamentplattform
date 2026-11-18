"""Zone 2 der Antragsseite: Die Leerkarte und die Karte „Betroffene Gesetze“ widersprechen einander nicht,
und die Wartelage nennt den Grund des Wartens (GP-150, GP-151). Nie Netz."""

import pytest
from django.urls import reverse

from ki.models import Zweck
from ki.warteschlange import einreihen
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

BERATUNGSSATZ = 'sie entsteht mit dem Eintritt in die Beratung'
OHNE_ANBIETER = 'Kein Anbieter angeschlossen — es wird nichts gerechnet.'


def _antrag(ordnung):  # noqa: F811
    return antrag_einbringen(mitglied_anlegen('anna'), ANTRAG['titel'], ANTRAG['wortlaut'], '', ordnung)


def _seite(client, antrag):
    return client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()


def test_wartender_auftrag_steht_nie_neben_dem_beratungssatz(client, settings, ordnung):  # noqa: F811
    """GP-151 (ZWB-11): Der Auftrag läuft seit dem Einbringen; die Leerkarte sagt nicht, die Einschätzung
    entstehe erst mit der Beratung."""
    settings.DDOE_KI_ANBIETER = 'attrappe'
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    inhalt = _seite(client, antrag)
    assert 'Warteschlange, Platz' in inhalt
    assert BERATUNGSSATZ not in inhalt


def test_satz_zum_fehlenden_anbieter_steht_hoechstens_einmal(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = 'mistral'
    settings.DDOE_KI_SCHLUESSEL = ''
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    inhalt = _seite(client, antrag)
    assert inhalt.count(OHNE_ANBIETER) == 1
    assert BERATUNGSSATZ not in inhalt
