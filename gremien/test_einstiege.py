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


def test_ein_gast_erreicht_von_der_gremienseite_jeden_vorhandenen_jahresbericht():
    """Die Übersicht verweist auf den Bericht jedes Jahres, in dem der Integritätsrat beschlossen hat —
    nicht nur auf den des laufenden Jahres (Auflage zu GP-030: „verlinkt auf der Seite Gremien“)."""
    from datetime import datetime

    from django.utils import timezone

    from gremien.models import JA_NEIN, GremienBeschluss, Gremium
    from verfahren.test_views_aktionen import mitglied_anlegen

    frueher = datetime(2024, 6, 1, 12, tzinfo=timezone.get_current_timezone())
    GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT, gegenstand='Ob wir uns monatlich treffen', optionen=JA_NEIN,
        angelegt_von=mitglied_anlegen('rat'), angelegt_am=frueher, frist=frueher,
    )
    html = Client().get(reverse('gremien:uebersicht')).content.decode()
    ziel = reverse('gremien:integritaet_bericht', args=[2024])
    assert f'href="{ziel}"' in html
    assert Client().get(ziel).status_code == 200
