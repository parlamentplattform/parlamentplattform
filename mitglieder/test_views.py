"""Selbstregistrierung (F-37), Double-Opt-in und passwortloser Login (F-02).

Die Tests fahren die echten HTTP-Flüsse über den Test-Client und lesen die
Tokens aus dem Mail-Postausgang — genau wie eine echte Nutzerin."""

import re
import time
from datetime import date, timedelta

import pytest
from django.core import mail, signing
from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from mitglieder.botschutz import SALZ
from mitglieder.models import Identitaetsstufe, Mitglied

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _drossel_zuruecksetzen():
    cache.clear()  # IP-Drossel zwischen Tests zurücksetzen


def botschutz(a=3, b=4, alter=10.0, antwort=None, honigtopf=""):
    """Gültige (oder gezielt ungültige) Menschlichkeitsprüfungs-Felder (F-49)."""
    token = signing.dumps({"a": a, "b": b, "t": time.time() - alter}, salt=SALZ)
    return {"pruefung": token, "rechenfrage": antwort if antwort is not None else a + b, "website": honigtopf}


ANMELDUNG = {
    "vorname": "Eva",
    "nachname": "Muster",
    "email": "eva@example.org",
    "geburtsjahr": 1990,
    "gemeinde": "Sankt Marienkirchen an der Polsenz",
    "bundesland": "oberoesterreich",
    "grundsaetze": "on",
}


def link_aus_mail(nachricht) -> str:
    treffer = re.search(r"http://testserver(/\S+)", nachricht.body)
    assert treffer, "kein Link in der E-Mail"
    return treffer.group(1)


def test_registrierung_legt_inaktives_konto_an_und_bestaetigung_aktiviert(client):
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz()})
    assert antwort.status_code == 200
    m = Mitglied.objects.get(email="eva@example.org")
    assert m.is_active is False  # Double-Opt-in: erst Mail bestätigen
    assert m.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT
    assert m.gemeinde == ANMELDUNG["gemeinde"]
    assert m.bundesland == "oberoesterreich"  # Wohnsitz für regionale Anträge (F-43)
    assert not m.has_usable_password()  # passwortlos by design
    assert len(mail.outbox) == 1

    antwort = client.get(link_aus_mail(mail.outbox[0]), follow=True)
    m.refresh_from_db()
    assert m.is_active is True
    assert m.beitritt == timezone.now().date()  # Anwartschaft beginnt (§ 4 Abs 4)
    assert antwort.status_code == 200
    inhalt = antwort.content.decode()
    assert "AT57 2033 0000 0006 9435" in inhalt  # Beitragsdaten auf der Willkommensseite
    assert f"DDOE-{m.pk:04d}-" in inhalt  # persönliche Beitragsreferenz (F-38)


def test_bestaetigungslink_ist_nur_einmal_gueltig(client):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz()})
    link = link_aus_mail(mail.outbox[0])
    assert client.get(link, follow=True).status_code == 200
    client.post(reverse("mitglieder:abmelden"))
    assert client.get(link).status_code == 400  # verbraucht


def test_unter_sechzehn_wird_abgelehnt(client):
    daten = {**ANMELDUNG, "geburtsjahr": timezone.now().year - 15}
    antwort = client.post(reverse("mitglieder:registrieren"), {**daten, **botschutz()})
    assert antwort.status_code == 200
    assert "16. Lebensjahr" in antwort.content.decode()
    assert Mitglied.objects.count() == 0
    assert mail.outbox == []


def test_doppelte_adresse_wird_abgelehnt(client):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz()})
    antwort = client.post(
        reverse("mitglieder:registrieren"), {**ANMELDUNG, "vorname": "Zwilling", **botschutz()}
    )
    assert Mitglied.objects.count() == 1
    assert "existiert bereits" in antwort.content.decode()


def test_login_per_magic_link_funktioniert_genau_einmal(client):
    m = Mitglied.objects.create(
        username="eva@example.org",
        email="eva@example.org",
        is_active=True,
        beitritt=date.today() - timedelta(days=100),
    )
    m.set_unusable_password()
    m.save()
    client.post(reverse("mitglieder:login"), {"email": "EVA@example.org", **botschutz()})  # Groß/klein egal
    assert len(mail.outbox) == 1
    link = link_aus_mail(mail.outbox[0])

    antwort = client.get(link)
    assert antwort.status_code == 302
    assert int(client.session["_auth_user_id"]) == m.pk

    client.post(reverse("mitglieder:abmelden"))
    assert client.get(link).status_code == 400  # Einmal-Token


def test_login_verraet_nicht_ob_ein_konto_existiert(client):
    antwort = client.post(reverse("mitglieder:login"), {"email": "niemand@example.org", **botschutz()})
    assert antwort.status_code == 200  # identische Antwortseite …
    assert "Postfach" in antwort.content.decode()
    assert mail.outbox == []  # … aber keine Mail


def test_abmelden_verlangt_post(client):
    assert client.get(reverse("mitglieder:abmelden")).status_code == 405
    antwort = client.post(reverse("mitglieder:abmelden"))
    assert antwort.status_code == 302


# --- Menschlichkeitsprüfung (F-49) ---------------------------------------------


def test_honigtopf_faengt_bots(client):
    antwort = client.post(
        reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(honigtopf="http://spam")}
    )
    assert antwort.status_code == 200
    assert Mitglied.objects.count() == 0
    assert mail.outbox == []


def test_zu_schnelles_absenden_wird_abgewiesen(client):
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(alter=0.5)})
    assert antwort.status_code == 200
    assert Mitglied.objects.count() == 0


def test_falsche_rechenantwort_wird_abgewiesen(client):
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(antwort=99)})
    assert "Sicherheitsfrage" in antwort.content.decode()
    assert Mitglied.objects.count() == 0


def test_ip_drossel_stoppt_massenregistrierung(client):
    for i in range(5):
        client.post(
            reverse("mitglieder:registrieren"),
            {**ANMELDUNG, "email": f"eva{i}@example.org", **botschutz()},
        )
    antwort = client.post(
        reverse("mitglieder:registrieren"), {**ANMELDUNG, "email": "eva99@example.org", **botschutz()}
    )
    assert "Zu viele Versuche" in antwort.content.decode()
    assert not Mitglied.objects.filter(email="eva99@example.org").exists()


def test_willkommensseite_zeigt_beitrags_qr(client):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz()})
    antwort = client.get(link_aus_mail(mail.outbox[0]), follow=True)
    inhalt = antwort.content.decode()
    assert "<svg" in inhalt  # EPC-QR-Code (F-38): Zahlen mit Code, ohne Zahlungsdienstleister
    assert "Zahlen mit Code" in inhalt
