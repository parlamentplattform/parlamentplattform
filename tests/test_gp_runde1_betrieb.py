"""Betrieb und Nachweis, erste Behebungsrunde nach der Gesamtprüfung (0.113.0)."""

import pytest
from django.urls import reverse

from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


# --- GP-154: Persönliche Antworten landen in keinem Zwischenspeicher --------------------------------


@pytest.mark.parametrize('name', ['mitglieder:profil', 'mitglieder:profil_export', 'verfahren:audit'])
def test_jede_antwort_an_ein_angemeldetes_konto_traegt_no_store(client, name):
    client.force_login(mitglied_anlegen('cache'))
    antwort = client.get(reverse(name))
    assert antwort.status_code == 200
    assert 'no-store' in antwort['Cache-Control'] and 'private' in antwort['Cache-Control']


def test_gastantworten_bleiben_unveraendert(client):
    antwort = client.get(reverse('verfahren:audit'))
    assert antwort.status_code == 200
    assert 'Cache-Control' not in antwort


def test_eine_eigene_festlegung_der_ansicht_bleibt():
    from django.contrib.auth.models import AnonymousUser
    from django.http import HttpResponse
    from django.test import RequestFactory

    from config.sicherheitsheader import PersoenlichesNichtSpeichern

    anfrage = RequestFactory().get('/')
    anfrage.user = type('Angemeldet', (AnonymousUser,), {'is_authenticated': True})()
    eigene = HttpResponse('x')
    eigene['Cache-Control'] = 'max-age=60, public'
    assert PersoenlichesNichtSpeichern(lambda r: eigene)(anfrage)['Cache-Control'] == 'max-age=60, public'


# --- GP-160: Ohne eigenen Schlüssel startet der Dienst nicht ---------------------------------------


def _einstellungen_laden(**umgebung):
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {k: v for k, v in os.environ.items() if k != 'DDOE_SECRET_KEY'}
    env.update(umgebung)
    return subprocess.run(
        [sys.executable, '-c', 'import config.settings'],
        cwd=Path(__file__).resolve().parent.parent, env=env, capture_output=True, text=True, timeout=120,
    )


@pytest.mark.parametrize('schluessel', [
    None, '', 'nur-fuer-entwicklung-niemals-produktiv', 'hier-einen-langen-zufaelligen-schluessel-eintragen',
])
def test_ohne_eigenen_schluessel_verweigert_die_produktion_den_start(schluessel):
    umgebung = {'DDOE_DEBUG': '0'}
    if schluessel is not None:
        umgebung['DDOE_SECRET_KEY'] = schluessel
    lauf = _einstellungen_laden(**umgebung)
    assert lauf.returncode != 0
    assert 'ImproperlyConfigured' in lauf.stderr


def test_mit_zufaelligem_schluessel_startet_die_produktion():
    import secrets

    lauf = _einstellungen_laden(DDOE_DEBUG='0', DDOE_SECRET_KEY=secrets.token_urlsafe(50))
    assert lauf.returncode == 0, lauf.stderr


def test_die_entwicklung_braucht_keinen_schluessel():
    assert _einstellungen_laden(DDOE_DEBUG='1').returncode == 0


def test_die_musterdatei_traegt_keinen_platzhalter_als_schluessel():
    from pathlib import Path

    muster = Path(__file__).resolve().parent.parent / 'docs' / 'partner' / 'instanz' / 'env.example'
    zeilen = [z for z in muster.read_text(encoding='utf-8').splitlines() if z.startswith('DDOE_SECRET_KEY=')]
    assert zeilen == ['DDOE_SECRET_KEY=']


# --- GP-211: Fällige Adresswechsel werden ohne Seitenaufruf wirksam ---------------------------------


def test_der_hintergrundlauf_macht_faellige_adresswechsel_wirksam():
    from datetime import timedelta

    from django.utils import timezone

    from mitglieder.models import Adresswechsel
    from verfahren.hintergrund import faellige_ausfuehren

    mitglied, admin = mitglied_anlegen('wechsel'), mitglied_anlegen('zweite')
    wechsel = Adresswechsel.objects.create(
        mitglied=mitglied, neue_email='wechsel-neu@example.org', frist_bis=timezone.now() - timedelta(hours=1),
        einspruch_hash='y' * 64, bestaetigt_von=admin, bestaetigt_am=timezone.now() - timedelta(days=1),
    )
    assert 'adresswechsel' in faellige_ausfuehren()
    wechsel.refresh_from_db()
    mitglied.refresh_from_db()
    assert wechsel.status == Adresswechsel.Status.WIRKSAM
    assert mitglied.email == 'wechsel-neu@example.org'


# --- GP-209: Der Demo-Bestand vergibt keine vorbehaltenen Anzeigenamen ------------------------------


def _profil_mit_anfangswerten_gueltig(client, mitglied):
    from django.urls import reverse

    from mitglieder.profil import ProfilFormular

    client.force_login(mitglied)
    anfang = client.get(reverse('mitglieder:profil')).context['form'].initial
    daten = {k: v for k, v in anfang.items() if v not in (None, False)}
    formular = ProfilFormular(daten, mitglied=mitglied)
    return formular.is_valid(), formular.errors


def test_nach_demo_seed_laesst_sich_das_profil_von_demo1_unveraendert_speichern(client):
    from django.core.management import call_command

    from mitglieder.models import Mitglied

    call_command('demo_seed', '--erzwingen', verbosity=0)
    for i in range(1, 6):
        gueltig, fehler = _profil_mit_anfangswerten_gueltig(client, Mitglied.objects.get(username=f'demo{i}'))
        assert gueltig, fehler


def test_ein_bestehender_demo_bestand_wird_beim_naechsten_lauf_berichtigt(client):
    from django.core.management import call_command

    from mitglieder.models import Mitglied

    call_command('demo_seed', '--erzwingen', verbosity=0)
    Mitglied.objects.filter(username='demo1').update(pseudonym_oeffentlich='Mitglied 1')
    call_command('demo_seed', '--erzwingen', verbosity=0)
    gueltig, fehler = _profil_mit_anfangswerten_gueltig(client, Mitglied.objects.get(username='demo1'))
    assert gueltig, fehler


# --- GP-159 (Teil): Die Drossel hält Verbindungsadressen rund zwei Stunden, auch ohne neuen Verkehr --


def test_der_hintergrundlauf_loescht_alte_drosselzaehler():
    import time

    from mitglieder.models import Drosselzaehler
    from verfahren.hintergrund import faellige_ausfuehren

    jetzt = int(time.time() // 3600)
    Drosselzaehler.objects.create(zweck='anstoss', kennung='203.0.113.7', stunde=jetzt - 240, anzahl=1)
    Drosselzaehler.objects.create(zweck='anstoss', kennung='203.0.113.8', stunde=jetzt - 2, anzahl=1)
    Drosselzaehler.objects.create(zweck='anmeldung', kennung='203.0.113.9', stunde=jetzt - 1, anzahl=1)
    Drosselzaehler.objects.create(zweck='anmeldung', kennung='203.0.113.10', stunde=jetzt, anzahl=1)
    assert 'drossel' in faellige_ausfuehren()
    assert sorted(Drosselzaehler.objects.values_list('stunde', flat=True)) == [jetzt - 1, jetzt]
