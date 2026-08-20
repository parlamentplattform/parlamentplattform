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


@pytest.fixture(autouse=True)
def _gemeindeverzeichnis(db):
    from django.core.management import call_command

    call_command("gemeinden_laden")


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
    assert m.gemeinde == "St. Marienkirchen an der Polsenz"  # amtlicher Name („Sankt“ toleriert)
    assert m.bundesland == "oberoesterreich"  # automatisch aus dem Gemeindeverzeichnis (F-43)
    assert m.wohnsitz.bezirk == "Eferding"
    assert not m.has_usable_password()  # passwortlos by design
    assert len(mail.outbox) == 1

    antwort = client.get(link_aus_mail(mail.outbox[0]), follow=True)
    m.refresh_from_db()
    assert m.is_active is True
    assert m.beitritt == timezone.now().date()  # Anwartschaft beginnt (§ 4 Abs 4)
    assert antwort.status_code == 200
    assert antwort.request["PATH_INFO"] == "/einfuehrung/1/"  # F-53: erst die Einführung …
    inhalt = client.get(reverse("mitglieder:willkommen")).content.decode()  # … ihr Abschluss: der Beitrag
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
    client.get(link_aus_mail(mail.outbox[0]), follow=True)  # bestätigen (landet in der Einführung)
    inhalt = client.get(reverse("mitglieder:willkommen")).content.decode()
    assert "<svg" in inhalt  # EPC-QR-Code (F-38): Zahlen mit Code, ohne Zahlungsdienstleister
    assert "Zahlen mit Code" in inhalt


# --- Gemeindeverzeichnis (F-43) --------------------------------------------------


def test_unbekannte_gemeinde_wird_abgelehnt(client):
    daten = {**ANMELDUNG, "gemeinde": "Entenhausen", **botschutz()}
    antwort = client.post(reverse("mitglieder:registrieren"), daten)
    assert "amtlichen Gemeindeverzeichnis" in antwort.content.decode()
    assert Mitglied.objects.count() == 0


def test_mehrdeutige_gemeinde_verlangt_praezisierung(client):
    daten = {**ANMELDUNG, "gemeinde": "Krumbach", **botschutz()}
    antwort = client.post(reverse("mitglieder:registrieren"), daten)
    inhalt = antwort.content.decode()
    assert "mehrmals" in inhalt and "Bregenz" in inhalt  # beide Kandidaten angeboten
    assert Mitglied.objects.count() == 0

    daten["gemeinde"] = "Krumbach (Bregenz)"
    daten.update(botschutz())
    client.post(reverse("mitglieder:registrieren"), daten)
    m = Mitglied.objects.get()
    assert m.bundesland == "vorarlberg"
    assert m.wohnsitz.kennziffer.startswith("8")


# --- Versandstörung: kein halbes Konto, ehrliche Meldung -------------------------


def _versand_kaputt(monkeypatch):
    def kaputt(*args, **kwargs):
        raise OSError("SMTP nicht erreichbar")

    monkeypatch.setattr("mitglieder.views.send_mail", kaputt)


def test_versandstoerung_rollt_die_registrierung_zurueck(client, monkeypatch):
    _versand_kaputt(monkeypatch)
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz()})
    assert antwort.status_code == 200  # Formular mit Meldung, kein 500
    assert "gestört" in antwort.content.decode()
    assert Mitglied.objects.count() == 0  # nichts halb angelegt — die Adresse bleibt frei

    monkeypatch.undo()  # Versand repariert: derselbe Mensch kann es sofort erneut versuchen
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz()})
    assert Mitglied.objects.filter(email="eva@example.org").exists()
    assert len(mail.outbox) == 1


def test_versandstoerung_beim_anmelden_wird_offen_gemeldet(client, monkeypatch):
    m = Mitglied.objects.create(username="eva@example.org", email="eva@example.org", is_active=True)
    m.set_unusable_password()
    m.save()
    _versand_kaputt(monkeypatch)
    antwort = client.post(reverse("mitglieder:login"), {"email": "eva@example.org", **botschutz()})
    assert antwort.status_code == 200
    assert "gestört" in antwort.content.decode()
    assert "Postfach" not in antwort.content.decode()  # keine falsche „unterwegs“-Seite
