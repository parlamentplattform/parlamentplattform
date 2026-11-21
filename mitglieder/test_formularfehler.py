"""GP-060: Ein Baustein für die Fehlerübersicht eines Formulars — der aus verfahren.

Profil, Gemeindezugang, Anmeldung zum Gemeindekonto und Registrierung zeigen nach falscher Gemeinde
oben im Hauptteil, vor dem ersten Formular, eine Meldung mit role=alert und Sprungverweis auf das
Feld; der Seitentitel beginnt mit „Fehler:“. Alles ohne JavaScript, im Testclient geprüft."""

import pytest
from django.template import TemplateDoesNotExist
from django.template.loader import get_template
from django.urls import reverse

from mitglieder.test_gemeinde import buerger, daten, ort  # noqa: F401
from mitglieder.test_views import ANMELDUNG, botschutz
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db

FALSCH = 'Entenhausen an der Gans'


def _pruefen(antwort):
    assert antwort.status_code == 200
    html = antwort.content.decode()
    assert html.split('<title>', 1)[1].startswith('Fehler:')
    hauptteil = html.split('<main id="inhalt"', 1)[1]
    vor, alarm = hauptteil.split('role="alert"', 1)
    assert '<form' not in vor  # oben im Hauptteil, vor dem ersten Formular
    assert vor.rsplit('<div', 1)[1].startswith(' class="formularfehler"')  # der gemeinsame Baustein
    assert 'href="#id_gemeinde"' in alarm.split('</div>', 1)[0]
    assert hauptteil.count('id="formularfehler"') == 1


def test_mitglieder_hat_keinen_eigenen_baustein_mehr():
    with pytest.raises(TemplateDoesNotExist):
        get_template('mitglieder/_formularfehler.html')


def test_profil(client):
    client.force_login(mitglied_anlegen('anna'))
    _pruefen(client.post(reverse('mitglieder:profil'), {
        'anzeigename': '', 'wohnsitz_art': 'oesterreich', 'gemeinde': FALSCH, 'nebenwohnsitz': '',
    }))


def test_gemeindezugang(client, buerger):  # noqa: F811
    client.force_login(buerger)
    _pruefen(client.post(reverse('gemeinde:konto'), {
        'wohnsitz_art': 'oesterreich', 'gemeinde': FALSCH, 'meldung': 'on',
    }))


def test_anmeldung_zum_gemeindekonto(client, ort):  # noqa: F811
    url = reverse('gemeinde:anmelden')
    _pruefen(client.post(url, {**daten(ort, gemeinde=FALSCH), **botschutz(client, url=url)}))


def test_registrierung(client):
    _pruefen(client.post(reverse('mitglieder:registrieren'), {**ANMELDUNG, 'gemeinde': FALSCH, **botschutz(client)}))
