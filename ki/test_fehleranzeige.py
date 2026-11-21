"""Öffentliche Fehleranzeige der Zukunftswerkstatt (GP-146): Gäste lesen einen festen, übersetzbaren
Fehlersatz, nie den rohen Ausnahmetext oder einen Klassennamen. Der Rohtext bleibt am Auftrag und im
Lauf-Archiv. Alles ohne Netz (Attrappe)."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import pytest
from django.urls import reverse

from ki.anbieter import AnbieterFehler, AttrappenAnbieter
from ki.models import Auftragsstatus, KIAuftrag, KILauf, oeffentlicher_fehler
from ki.test_folgenauftraege import attrappe, neu  # noqa: F401
from ki.test_kontext import antrag  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

INTERN = 'could not connect to server db-intern.example:5432 in /srv/app/ki/folgenauftraege.py'
NETZ = 'Anbieter nicht erreichbar: <urlopen error [Errno 111] Connection refused intern-host-7:443>'
KLASSEN = ('RuntimeError', 'SteckplatzStumm', 'AnbieterFehler', 'SteckplatzWartet', 'urlopen')


def _sechsmal(job):
    for _ in range(6):
        KIAuftrag.objects.filter(pk=job.pk).update(naechster_versuch=None)
        auftrag_ausfuehren(job.pk)
    job.refresh_from_db()
    return job


def test_interne_ausnahme_steht_nicht_auf_der_gastseite(antrag, attrappe, monkeypatch, client):
    def kaputt(self, auftrag, eingabe):
        raise RuntimeError(INTERN)

    monkeypatch.setattr(AttrappenAnbieter, 'frage', kaputt)
    job = _sechsmal(neu(antrag))
    assert job.status == Auftragsstatus.GESCHEITERT and 'db-intern.example' in job.fehler  # Rohtext bleibt am Auftrag
    html = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert 'db-intern.example' not in html and '/srv/app' not in html
    assert not [k for k in KLASSEN if k in html]
    assert str(oeffentlicher_fehler(job.fehler)) in html


def test_netzfehler_steht_weder_in_der_historie_noch_in_der_zukunftswerkstatt(antrag, attrappe, monkeypatch, client):
    def stumm(self, auftrag, eingabe):
        raise AnbieterFehler(NETZ)

    monkeypatch.setattr(AttrappenAnbieter, 'frage', stumm)
    job = neu(antrag)
    assert auftrag_ausfuehren(job.pk) == 'verschoben'
    lauf = KILauf.objects.get(antrag=antrag, erfolgreich=False)
    assert 'intern-host-7' in lauf.fehler  # das Archiv behält den Rohtext
    for adresse in (reverse('verfahren:antrag', args=[antrag.pk]), reverse('verfahren:zukunftswerkstatt')):
        html = client.get(adresse).content.decode()
        assert 'intern-host-7' not in html and 'Errno' not in html, adresse
        assert not [k for k in KLASSEN if k in html], adresse
        assert str(oeffentlicher_fehler(lauf.fehler)) in html, adresse


def test_englische_oberflaeche_zeigt_keinen_deutschen_rohtext(antrag, attrappe, monkeypatch, client):
    def stumm(self, auftrag, eingabe):
        raise AnbieterFehler('HTTP 503 vom Anbieter')

    monkeypatch.setattr(AttrappenAnbieter, 'frage', stumm)
    _sechsmal(neu(antrag))
    for adresse in (reverse('verfahren:antrag', args=[antrag.pk]), reverse('verfahren:zukunftswerkstatt')):
        html = client.get(adresse, HTTP_ACCEPT_LANGUAGE='en').content.decode()
        assert 'vom Anbieter' not in html and 'nicht geantwortet' not in html, adresse


def test_fehlercodes_sind_fest_und_kennen_den_altbestand():
    """Auch Rohtexte früherer Fassungen (vor GP-146) ergeben einen der festen Sätze."""
    from ki.models import FEHLERSAETZE, fehlercode

    faelle = {
        '': '',
        'SteckplatzStumm: Der Anbieter hat nicht geantwortet (HTTP 503 vom Anbieter).': 'anbieter_http',
        'HTTP 401 vom Anbieter': 'anbieter_http',
        NETZ: 'anbieter_nicht_erreichbar',
        'Antwortformat unerwartet': 'antwortform',
        'Anbieter lieferte nicht je Text einen Vektor': 'antwortform',
        'SteckplatzWartet: Kein KI-Anbieter angeschlossen — der Steckplatz ist leer (Schlüssel fehlt).': 'kein_anbieter',
        'SteckplatzWartet: Das Monats-Tokenbudget des Steckplatzes ist erschöpft — er bleibt stumm.': 'budget',
        'quellenkontext_erfassung': 'vorbereitung',
        'folgenkontext_erfassung': 'vorbereitung',
        'ZeroDivisionError: division by zero': 'intern',
        'RuntimeError: ' + INTERN: 'intern',
    }
    for roh, code in faelle.items():
        assert fehlercode(roh) == code, roh
        if code == 'anbieter_http':
            assert str(oeffentlicher_fehler(roh)).endswith(f'(HTTP {roh.split("HTTP ")[1][:3]}).'), roh
        elif code:
            assert str(oeffentlicher_fehler(roh)) == str(FEHLERSAETZE[code]), roh
        else:
            assert oeffentlicher_fehler(roh) == ''
