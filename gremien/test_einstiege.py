"""GP-030: Protokolle, Jahresbericht, Beschlüsse und Fachliste der Räte hatten für Gäste keinen Einstieg.

Gebaut und öffentlich waren sie, auffindbar aber nur über die Adresse (Protokoll, Jahresbericht) oder über
Umwege. Jetzt nennt die Übersicht /gremien/ je Rat die öffentlichen Unterlagen."""

from __future__ import annotations

import re

import pytest
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

HREF = re.compile(r'href="(/[^"#]*)')


def _erreichbar(start: str, klicks: int) -> set[str]:
    """Alle Adressen, die ein Gast von `start` aus in höchstens `klicks` Klicks erreicht."""
    gast = Client()
    gesehen, rand = {start}, [start]
    for _schritt in range(klicks):
        naechste = []
        for seite in rand:
            antwort = gast.get(seite)
            if antwort.status_code != 200 or 'text/html' not in antwort.get('Content-Type', ''):
                continue
            for ziel in set(HREF.findall(antwort.content.decode())):
                ziel = ziel.replace('&amp;', '&')
                if ziel not in gesehen and not ziel.startswith(('/static/', '/abmelden', '/i18n')):
                    gesehen.add(ziel)
                    naechste.append(ziel)
        rand = naechste
    return gesehen


def test_ein_gast_erreicht_von_der_startseite_die_unterlagen_der_raete():
    erreicht = _erreichbar('/', 2)
    # Das Jahr nimmt die Seite selbst; der Test hängt nicht vom heutigen Datum ab.
    muster = {
        'Beschlüsse': re.escape(reverse('gremien:beschluesse')) + r'(\?gremium=integritaetsrat)?$',
        'Fachliste': re.escape(reverse('gremien:fachliste')) + '$',
        'Jahresbericht': re.escape(reverse('gremien:integritaet_bericht', args=[2000])).replace('2000', r'\d{4}') + '$',
        'Protokoll IR': re.escape(reverse('gremien:protokoll', args=['integritaetsrat', 2000])).replace('2000', r'\d{4}') + '$',
        'Protokoll KR': re.escape(reverse('gremien:protokoll', args=['koordinationsrat', 2000])).replace('2000', r'\d{4}') + '$',
    }
    for name, ausdruck in muster.items():
        treffer = [z for z in erreicht if re.match(ausdruck, z)]
        assert treffer, name
        assert Client().get(treffer[0]).status_code == 200, treffer[0]
