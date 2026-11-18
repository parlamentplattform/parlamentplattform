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


def _register(schluessel, wert):
    from parameter.models import Parameter

    Parameter.objects.update_or_create(schluessel=schluessel, defaults={'wert': str(wert), 'beschreibung': 'x', 'quelle': 'Test'})


def test_platz_zaehlt_keinen_auftrag_im_rueckzug(client, settings, ordnung):  # noqa: F811
    """GP-150 (ZWA-19): Ein älterer Auftrag im Fehlerrückzug wird nicht vor dem jüngeren gerechnet."""
    from datetime import timedelta

    from django.utils import timezone

    settings.DDOE_KI_ANBIETER = 'attrappe'
    aelter = _antrag(ordnung)
    zurueck = einreihen(Zweck.RECHTSBEZUG, aelter, aelter.eingebracht_von)
    type(zurueck).objects.filter(pk=zurueck.pk).update(naechster_versuch=timezone.now() + timedelta(minutes=2), versuche=1)
    juenger = antrag_einbringen(mitglied_anlegen('bert'), 'Radwege in allen Gemeinden', 'Jede Gemeinde baut Radwege.', '', ordnung)
    einreihen(Zweck.RECHTSBEZUG, juenger, juenger.eingebracht_von)
    inhalt = _seite(client, juenger)
    assert 'Warteschlange, Platz 1' in inhalt


def test_aufgebrauchtes_tageskontingent_wird_genannt(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = 'attrappe'
    _register('ki-tageslaeufe', 0)
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    inhalt = _seite(client, antrag)
    assert 'Tageskontingent' in inhalt and 'Monatsbudget' not in inhalt


def test_erschoepftes_monatsbudget_nennt_den_monatswechsel(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = 'attrappe'
    _register('ki-monatstokens', 0)
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    inhalt = _seite(client, antrag)
    assert 'Monatsbudget' in inhalt and 'Monatswechsel' in inhalt


def test_ohne_erschoepfung_kein_wartegrund(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = 'attrappe'
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    inhalt = _seite(client, antrag)
    assert 'Tageskontingent' not in inhalt and 'Monatsbudget' not in inhalt
