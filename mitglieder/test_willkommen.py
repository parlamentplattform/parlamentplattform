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


# ── Pausierte und ungeprüfte Konten lesen keinen falschen Stand (Prüfung 0.50.0, P-18) ────────


def _konto(status, stufe=None, tage=900):
    """Ein Bestandsmitglied (Beitritt vor `tage` Tagen) im gegebenen Status seit heute."""
    from django.utils import timezone

    from mitglieder.models import Identitaetsstufe, Mitglied
    from verfahren.test_views_aktionen import mitglied_anlegen

    m = mitglied_anlegen("paula", tage=tage, stufe=stufe or Identitaetsstufe.GEPRUEFT)
    Mitglied.objects.filter(pk=m.pk).update(status=status, status_seit=timezone.localdate())
    return Mitglied.objects.get(pk=m.pk)


def test_die_sperrhinweise_fuehren_auf_die_beitragsseite():
    from verfahren.hinweise import kachel_sperre

    for code in ("gesperrt_pausiert", "gesperrt_ungeprueft"):
        assert kachel_sperre(code)["link"] == reverse("mitglieder:beitrag"), code


@pytest.mark.parametrize("uebergang", [True, False])
def test_pausiertes_bestandsmitglied_liest_keinen_falschen_stand(client, settings, uebergang):
    from mitglieder.models import Mitgliedsstatus

    settings.DDOE_UEBERGANGSREGEL = uebergang
    client.force_login(_konto(Mitgliedsstatus.PAUSIERT))
    inhalt = client.get(reverse("mitglieder:willkommen")).content.decode()
    assert "jetzt Anwärterin beziehungsweise Anwärter" not in inhalt
    assert "ab sofort" not in inhalt and "ohne zusätzliche Wartefrist" not in inhalt
    assert "Ihre Mitgliedschaft ist derzeit pausiert." in inhalt


@pytest.mark.parametrize(
    ("status", "stufe", "erwartet"),
    [
        ("pausiert", "geprueft", "Ihre Mitgliedschaft ist derzeit pausiert."),
        ("ausgeschlossen", "geprueft", "Ihre Mitwirkungsrechte und Ihr Stimmrecht ruhen derzeit."),
        ("aktiv", "ungeprueft", "Über inhaltliche Vorschläge können Sie nach Ihrer Freischaltung abstimmen."),
    ],
)
def test_der_satz_sagt_nie_ab_sofort_ohne_stimmrecht(settings, status, stufe, erwartet):
    """Dieselben Bedingungen wie `ist_stimmberechtigt`: Status und Identitätsstufe."""
    from django.utils import timezone

    from mitglieder.post import stimmrechts_satz
    from plattform_core import Gegenstand

    settings.DDOE_UEBERGANGSREGEL = False
    m = _konto(status, stufe)
    assert not m.ist_stimmberechtigt(Gegenstand.SACHFRAGE, timezone.localdate())
    satz = str(stimmrechts_satz(m))
    assert "ab sofort" not in satz and erwartet in satz


def test_nur_neue_konten_sind_jetzt_anwaerter(client, settings):
    from mitglieder.models import Mitgliedsstatus

    settings.DDOE_UEBERGANGSREGEL = False
    satz = "Sie sind jetzt Anwärterin beziehungsweise Anwärter"
    _registrieren_und_bestaetigen(client)
    assert satz in client.get(reverse("mitglieder:willkommen")).content.decode()

    client.force_login(_konto(Mitgliedsstatus.AKTIV))  # seit Jahren aktiv und geprüft
    inhalt = client.get(reverse("mitglieder:willkommen")).content.decode()
    assert satz not in inhalt and "ab sofort abstimmen" in inhalt
