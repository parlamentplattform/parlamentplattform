"""Die Willkommensseite sagt zum Stimmrecht dasselbe wie der Willkommensbrief (C2, 28.9.2026).

Bis 0.49 nannte die Seite feste Fristen („nach drei Monaten … nach zwölf“), obwohl mit der
Übergangsregel (§ 4 Abs 4 lit d, `DDOE_UEBERGANGSREGEL`, auch live) keine gilt. Jetzt liefert
`stimmrechts_satz` beiden dieselbe Auskunft — mit und ohne Übergangsregel.
"""

from __future__ import annotations

import pytest
from django.core import mail
from django.urls import reverse

from mitglieder.test_views import ANMELDUNG, botschutz, link_aus_mail
from plattform_core.eligibility import monate_addieren

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _gemeindeverzeichnis(db):
    from django.core.management import call_command

    call_command("gemeinden_laden")


def _registrieren_und_bestaetigen(client):
    from mitglieder.models import Mitglied

    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    client.get(link_aus_mail(mail.outbox[0]), follow=True)
    return Mitglied.objects.get(email=ANMELDUNG["email"])


def test_mit_uebergangsregel_nennt_die_seite_keine_wartefrist(client, settings):
    settings.DDOE_UEBERGANGSREGEL = True
    _registrieren_und_bestaetigen(client)
    inhalt = client.get(reverse("mitglieder:willkommen")).content.decode()
    assert "nach drei Monaten" not in inhalt and "nach zwölf" not in inhalt
    assert "ohne zusätzliche Wartefrist abstimmen und wählen" in inhalt
    assert "Aufbauphase" in inhalt


def test_ohne_uebergangsregel_rechnet_die_seite_die_anwartschaft_aus_dem_beitritt(client, settings):
    settings.DDOE_UEBERGANGSREGEL = False
    m = _registrieren_und_bestaetigen(client)
    inhalt = client.get(reverse("mitglieder:willkommen")).content.decode()
    sach = monate_addieren(m.beitritt, 3)
    pers = monate_addieren(m.beitritt, 12)
    assert f"ab {sach:%d.%m.%Y} abstimmen" in inhalt
    assert f"ab {pers:%d.%m.%Y} teilnehmen" in inhalt
    assert "ohne zusätzliche Wartefrist" not in inhalt


def test_gast_wird_zum_login_geschickt(client):
    assert client.get(reverse("mitglieder:willkommen")).status_code == 302
