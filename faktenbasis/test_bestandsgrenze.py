"""Bestandsnachweis an der Grenze (GP-147): Die Verwaltung wird an der Grenze gewarnt, die Meldung nach
einem Import darüber nennt den Ausfall, die Gastseite nennt Bestand, Grenze und Zuständige. Ohne Netz."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import pytest
from django.urls import reverse

from faktenbasis.bestandsnachweis import bestandszahl
from faktenbasis.models import Norm
from faktenbasis.test_bestandsnachweis import bestand, grenze  # noqa: F401
from faktenbasis.test_verwaltung import abrufe, admin, anfrage  # noqa: F401
from faktenbasis.test_volltext import norm  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures('abrufuhr')]

WARNUNG = 'Nachweisgrenze erreicht'


def test_bestandszahl_zaehlt_alle_sieben_sammlungen(bestand):
    assert bestandszahl() == 7  # Norm, Text, Personal, Ressorts, Kundmachung, VfGH, RIS-Änderungsseite


def test_verwaltung_warnt_bei_bestand_gleich_grenze(client, bestand):
    admin(client)
    grenze(8)
    html = client.get(reverse('faktenbasis:verwaltung')).content.decode()
    assert WARNUNG not in html and 'Bestandsnachweis: 7 von höchstens 8 Schnappschüssen' in html
    grenze(7)
    html = client.get(reverse('faktenbasis:verwaltung')).content.decode()
    assert WARNUNG in html


def test_meldung_nach_import_ueber_die_grenze_nennt_den_ausfall(client, abrufe):
    import copy

    from faktenbasis.models import PersonalAggregat
    from faktenbasis.test_personalimport import DATEN

    PersonalAggregat.objects.create(**copy.deepcopy(DATEN))
    admin(client)
    vorher = bestandszahl()
    grenze(vorher)
    antwort = anfrage(client)
    assert Norm.objects.count() >= 1 and bestandszahl() > vorher
    meldungen = [str(m) for m in antwort.wsgi_request._messages]
    assert any('Bestandsnachweis' in m and 'fällt aus' in m for m in meldungen), meldungen


def test_gastseite_nennt_bestand_grenze_und_zustaendige(client, bestand):
    grenze(5)
    antwort = client.get(reverse('faktenbasis:bestand'))
    html = antwort.content.decode()
    assert antwort.status_code == 503
    assert 'Gespeicherter Bestand: 7 Schnappschüsse, Nachweisgrenze: 5.' in html
    assert 'Die Grenze stellt die Verwaltung im Parameterregister ein' in html
    assert reverse('parameter:liste') in html
    json_antwort = client.get(reverse('faktenbasis:bestand_json'))
    assert json_antwort.status_code == 503 and 'Verwaltung' in json_antwort.json()['meldung']


def test_altbestand_ohne_registerzeile_und_ohne_daten(client):
    from parameter.models import Parameter

    Parameter.objects.filter(schluessel='faktenbasis-bestandsnachweis-hoechstzahl').delete()
    assert bestandszahl() == 0
    admin(client)
    assert WARNUNG not in client.get(reverse('faktenbasis:verwaltung')).content.decode()
