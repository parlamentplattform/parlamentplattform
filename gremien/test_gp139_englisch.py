'''GP-139 (Rest außerhalb des Pakets verfahren): Fachliste, Verwaltung der Fachliste und Einführung zeigten
die Lebensbereiche auf der englischen Oberfläche deutsch.

Geprüft wird mit der Pseudo-Übersetzung aus verfahren/test_gp139_englisch.py: Jeder Name des Erstbestands
erscheint als „EN[…]“; ein frei gepflegter Name bleibt, wie er ist. Gespeichert wird weiter der Bereich.'''

from __future__ import annotations

import pytest
from django.urls import reverse
from django.utils import translation

from gremien.test_fachliste import _verwaltung, eintragen
from verfahren.models import Kategorie
from verfahren.test_gp139_englisch import pseudo  # noqa: F401
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


def _bereiche():
    wurzel = Kategorie.objects.create(slug='gesellschaftliches-zusammenleben', name='Das gesellschaftliche Zusammenleben')
    energie = Kategorie.objects.create(slug='energie', name='Energie', eltern=wurzel, reihenfolge=1)
    eigen = Kategorie.objects.create(slug='energiewende-ort', name='Energiewende in unserer Gemeinde', eltern=wurzel, reihenfolge=2)
    return energie, eigen


def test_die_oeffentliche_fachliste_nennt_die_fachgebiete_englisch(client, pseudo):  # noqa: F811
    energie, eigen = _bereiche()
    eintrag = eintragen('fachfrau')
    eintrag.fachgebiete.add(energie, eigen)
    seite = client.get(reverse('gremien:fachliste'), HTTP_ACCEPT_LANGUAGE='en').content.decode()
    assert 'EN[Energie]' in seite
    assert 'Energiewende in unserer Gemeinde' in seite  # frei gepflegt: unverändert
    assert 'Energie,' not in seite and ' Energie<' not in seite


def test_die_verwaltung_der_fachliste_nennt_die_fachgebiete_englisch(client, pseudo):  # noqa: F811
    energie, _eigen = _bereiche()
    _verwaltung(client)
    eintrag = eintragen('fachmann')
    eintrag.fachgebiete.add(energie)
    seite = client.get(reverse('gremien:fachliste_verwaltung'), HTTP_ACCEPT_LANGUAGE='en').content.decode()
    assert f'<option value="{energie.pk}">EN[Energie]</option>' in seite  # Auswahl im Formular
    assert '>Energie<' not in seite
    assert 'EN[Energie]</span>' in seite  # Liste der Einträge


def test_die_auswahl_speichert_weiter_den_bereich(client):
    from gremien.models import Fachliste

    energie, _eigen = _bereiche()
    _verwaltung(client)
    neu = mitglied_anlegen('neue')
    with translation.override('en'):
        client.post(reverse('gremien:fachliste_aktion'), {
            'aktion': 'eintragen', 'mitglied': neu.pk, 'einwilligung': 'on', 'fachgebiete': [energie.pk],
        }, HTTP_ACCEPT_LANGUAGE='en')
    assert list(Fachliste.objects.get(mitglied=neu).fachgebiete.all()) == [energie]


def test_die_einfuehrung_nennt_die_lebensbereiche_englisch(client, pseudo):  # noqa: F811
    _bereiche()
    client.force_login(mitglied_anlegen('neuling'))
    seite = client.get(reverse('mitglieder:einfuehrung', args=[1]), HTTP_ACCEPT_LANGUAGE='en').content.decode()
    assert 'EN[Energie]</a>' in seite
    assert 'Energiewende in unserer Gemeinde</a>' in seite
    assert '>Energie</a>' not in seite
