"""Selbstregistrierung (F-37), Double-Opt-in und passwortloser Login (F-02).

Die Tests fahren die echten HTTP-Flüsse über den Test-Client und lesen die
Tokens aus dem Mail-Postausgang — genau wie eine echte Nutzerin."""

import base64
import json
import re
import time
from datetime import date, timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from mitglieder.botschutz import SITZUNGSSCHLUESSEL
from mitglieder.models import Drosselzaehler, Identitaetsstufe, Mitglied

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _gemeindeverzeichnis(db):
    from django.core.management import call_command

    call_command("gemeinden_laden")


def botschutz(client, alter=10.0, antwort=None, honigtopf="", url=None):
    """Gültige (oder gezielt ungültige) Menschlichkeitsprüfungs-Felder (F-49).

    Holt ein frisches Formular und beantwortet dessen Aufgabe — wie ein Mensch, nur mit
    Blick in die Sitzung statt aufs Bild (die Seite selbst verrät die Lösung nicht mehr,
    Befund #68). `alter` datiert die Aufgabe zurück, damit die Mindestzeit erfüllt ist."""
    client.get(url or reverse("mitglieder:registrieren"))
    sitzung = client.session
    aufgaben = sitzung[SITZUNGSSCHLUESSEL]
    kennung = max(aufgaben, key=lambda k: aufgaben[k]["t"])
    aufgaben[kennung]["t"] = time.time() - alter
    sitzung[SITZUNGSSCHLUESSEL] = aufgaben
    sitzung.save()
    a, b = aufgaben[kennung]["a"], aufgaben[kennung]["b"]
    return {"pruefung": kennung, "rechenfrage": antwort if antwort is not None else a + b, "website": honigtopf}


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
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
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
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    link = link_aus_mail(mail.outbox[0])
    assert client.get(link, follow=True).status_code == 200
    client.post(reverse("mitglieder:abmelden"))
    assert client.get(link).status_code == 400  # verbraucht


def test_unter_sechzehn_wird_abgelehnt(client):
    daten = {**ANMELDUNG, "geburtsjahr": timezone.now().year - 15}
    antwort = client.post(reverse("mitglieder:registrieren"), {**daten, **botschutz(client)})
    assert antwort.status_code == 200
    assert "16. Lebensjahr" in antwort.content.decode()
    assert Mitglied.objects.count() == 0
    assert mail.outbox == []


def test_doppelte_adresse_wird_abgelehnt(client):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    antwort = client.post(
        reverse("mitglieder:registrieren"), {**ANMELDUNG, "vorname": "Zwilling", **botschutz(client)}
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
    client.post(reverse("mitglieder:login"), {"email": "EVA@example.org", **botschutz(client)})  # Groß/klein egal
    assert len(mail.outbox) == 1
    link = link_aus_mail(mail.outbox[0])

    antwort = client.get(link)
    assert antwort.status_code == 302
    assert int(client.session["_auth_user_id"]) == m.pk

    client.post(reverse("mitglieder:abmelden"))
    assert client.get(link).status_code == 400  # Einmal-Token


def test_login_verraet_nicht_ob_ein_konto_existiert(client):
    antwort = client.post(reverse("mitglieder:login"), {"email": "niemand@example.org", **botschutz(client)})
    assert antwort.status_code == 200  # identische Antwortseite …
    assert "Postfach" in antwort.content.decode()
    assert mail.outbox == []  # … aber keine Mail


def test_abmelden_verlangt_post(client):
    assert client.get(reverse("mitglieder:abmelden")).status_code == 405
    antwort = client.post(reverse("mitglieder:abmelden"))
    assert antwort.status_code == 302


# --- Unbestätigte Konten sperren die Adresse nicht auf Dauer (Befund #21) -----------------


def test_unbestaetigtes_konto_sperrt_die_adresse_nicht_dauerhaft(client):
    """Link nie geklickt, 48 Stunden um: Der echte Inhaber bekommt am Login einen neuen
    Bestätigungslink (Selbsthilfe), und eine erneute Registrierung überschreibt die Zeile,
    statt sie abzulehnen — gelöscht wird nichts (das Audit verweist auf die pk)."""
    from mitglieder.auth_flows import EinmalToken

    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    m = Mitglied.objects.get(email="eva@example.org")
    EinmalToken.objects.filter(mitglied=m).update(gueltig_bis=timezone.now() - timedelta(hours=1))
    mail.outbox.clear()

    login = reverse("mitglieder:login")
    antwort = client.post(login, {"email": "eva@example.org", **botschutz(client, url=login)})
    assert "Postfach" in antwort.content.decode()  # dieselbe Seite wie sonst
    assert len(mail.outbox) == 1
    bestaetigen_pfad = reverse("mitglieder:bestaetigen", args=["x"]).rsplit("x", 1)[0]
    assert bestaetigen_pfad in mail.outbox[0].body  # ein Bestätigungs-, kein Anmeldelink

    EinmalToken.objects.filter(mitglied=m).update(gueltig_bis=timezone.now() - timedelta(hours=1))
    mail.outbox.clear()
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, "vorname": "Evamaria", **botschutz(client)})
    assert Mitglied.objects.count() == 1  # überschrieben, nicht verdoppelt
    m.refresh_from_db()
    assert m.first_name == "Evamaria" and m.is_active is False
    client.get(link_aus_mail(mail.outbox[0]), follow=True)
    m.refresh_from_db()
    assert m.is_active is True and m.beitritt == timezone.localdate()


def test_solange_der_link_gilt_bleibt_die_adresse_belegt_und_der_login_hilft(client):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    mail.outbox.clear()
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    assert "existiert bereits" in antwort.content.decode() and Mitglied.objects.count() == 1
    login = reverse("mitglieder:login")
    client.post(login, {"email": "eva@example.org", **botschutz(client, url=login)})
    assert len(mail.outbox) == 1  # der Login hilft sofort mit einem frischen Bestätigungslink


def test_ausgeschlossene_bleiben_zu(client):
    """Ausgeschlossene sind ebenfalls inaktiv — sie bekommen weder Link noch neue Registrierung."""
    from mitglieder.models import Mitgliedsstatus

    Mitglied.objects.create(
        username="eva@example.org", email="eva@example.org", is_active=False, status=Mitgliedsstatus.AUSGESCHLOSSEN
    )
    login = reverse("mitglieder:login")
    client.post(login, {"email": "eva@example.org", **botschutz(client, url=login)})
    assert mail.outbox == []
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    assert "existiert bereits" in antwort.content.decode() and Mitglied.objects.count() == 1


# --- Menschlichkeitsprüfung (F-49) ---------------------------------------------


def test_honigtopf_faengt_bots(client):
    antwort = client.post(
        reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client, honigtopf="http://spam")}
    )
    assert antwort.status_code == 200
    assert Mitglied.objects.count() == 0
    assert mail.outbox == []


def test_zu_schnelles_absenden_wird_abgewiesen(client):
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client, alter=0.5)})
    assert antwort.status_code == 200
    assert Mitglied.objects.count() == 0


def test_falsche_rechenantwort_wird_abgewiesen(client):
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client, antwort=99)})
    assert "Sicherheitsfrage" in antwort.content.decode()
    assert Mitglied.objects.count() == 0


def test_ip_drossel_stoppt_massenregistrierung(client):
    for i in range(5):
        client.post(
            reverse("mitglieder:registrieren"),
            {**ANMELDUNG, "email": f"eva{i}@example.org", **botschutz(client)},
        )
    antwort = client.post(
        reverse("mitglieder:registrieren"), {**ANMELDUNG, "email": "eva99@example.org", **botschutz(client)}
    )
    assert "Zu viele Versuche" in antwort.content.decode()
    assert not Mitglied.objects.filter(email="eva99@example.org").exists()


# --- Drossel: die Verbindung zählt, nicht der Kopf (Befunde #19, #66) --------------------


def test_drossel_liest_nie_x_forwarded_for(client):
    """XFF[0] ist vom Client frei wählbar (Cloudflare und Render hängen nur an) — wer je
    Versuch eine andere Adresse hineinschreibt, darf die Drossel nicht umgehen."""
    login = reverse("mitglieder:login")
    for i in range(10):
        client.post(login, {"email": "eva@example.org", **botschutz(client, url=login)}, HTTP_X_FORWARDED_FOR=f"10.0.0.{i}")
    antwort = client.post(
        login, {"email": "eva@example.org", **botschutz(client, url=login)}, HTTP_X_FORWARDED_FOR="10.0.0.99"
    )
    assert "Zu viele Versuche" in antwort.content.decode()


def test_proxy_kopfzeile_zaehlt_nur_wenn_sie_konfiguriert_ist(client, settings):
    """Ohne DDOE_CLIENT_IP_KOPFZEILE (Partner-Instanz ohne Proxy) könnte ein Client
    CF-Connecting-IP selbst setzen — dann gilt ausschließlich REMOTE_ADDR."""
    login = reverse("mitglieder:login")
    settings.DDOE_CLIENT_IP_KOPFZEILE = ""
    for i in range(10):
        client.post(login, {"email": "eva@example.org", **botschutz(client, url=login)}, HTTP_CF_CONNECTING_IP=f"10.0.0.{i}")
    antwort = client.post(
        login, {"email": "eva@example.org", **botschutz(client, url=login)}, HTTP_CF_CONNECTING_IP="10.0.0.99"
    )
    assert "Zu viele Versuche" in antwort.content.decode()  # REMOTE_ADDR war immer dieselbe

    settings.DDOE_CLIENT_IP_KOPFZEILE = "HTTP_CF_CONNECTING_IP"  # Render hinter Cloudflare
    antwort = client.post(
        login, {"email": "eva@example.org", **botschutz(client, url=login)}, HTTP_CF_CONNECTING_IP="198.51.100.7"
    )
    assert "Zu viele Versuche" not in antwort.content.decode()  # jetzt zählt die Kopfzeile: neuer Eimer


def test_klienten_ip_kennt_nur_remote_addr_und_die_konfigurierte_kopfzeile(rf, settings):
    from mitglieder.botschutz import klienten_ip

    anfrage = rf.get(
        "/",
        REMOTE_ADDR="203.0.113.5",
        HTTP_X_FORWARDED_FOR="10.0.0.1, 203.0.113.5",
        HTTP_CF_CONNECTING_IP="198.51.100.7",
    )
    settings.DDOE_CLIENT_IP_KOPFZEILE = ""
    assert klienten_ip(anfrage) == "203.0.113.5"
    settings.DDOE_CLIENT_IP_KOPFZEILE = "HTTP_CF_CONNECTING_IP"
    assert klienten_ip(anfrage) == "198.51.100.7"


def test_drossel_zaehlt_in_der_datenbank_nicht_im_prozesscache(client):
    """Zwei gunicorn-Worker, ein Neustart: Ein LocMemCache je Prozess verdoppelt das Limit
    und vergisst es beim Neustart. Der Zähler muss den Cache-Verlust überstehen."""
    from django.core.cache import cache

    for i in range(5):
        client.post(
            reverse("mitglieder:registrieren"),
            {**ANMELDUNG, "email": f"eva{i}@example.org", **botschutz(client)},
        )
    cache.clear()  # als hätte ein anderer Worker übernommen
    antwort = client.post(
        reverse("mitglieder:registrieren"), {**ANMELDUNG, "email": "eva99@example.org", **botschutz(client)}
    )
    assert "Zu viele Versuche" in antwort.content.decode()
    assert Drosselzaehler.objects.get(zweck="registrierung").anzahl == 5


# --- Rechenfrage: Lösung bleibt am Server, gelöst heißt verbraucht (Befund #68) --------


def test_die_seite_verraet_die_loesung_der_rechenfrage_nicht(client):
    """Ein signiertes Token war lesbar (base64-JSON mit a und b). Jetzt trägt die Seite
    nur eine zufällige Kennung; die Summanden liegen in der Sitzung."""
    seite = client.get(reverse("mitglieder:registrieren")).content.decode()
    kennung = re.search(r'name="pruefung" value="([^"]+)"', seite).group(1)
    aufgabe = client.session[SITZUNGSSCHLUESSEL][kennung]
    roh = base64.urlsafe_b64decode(kennung + "=" * (-len(kennung) % 4))
    try:
        nutzlast = json.loads(roh.decode("utf-8"))  # so war das alte Token lesbar
    except (UnicodeDecodeError, ValueError):
        nutzlast = None
    assert not (isinstance(nutzlast, dict) and "a" in nutzlast)
    assert f"= {aufgabe['a'] + aufgabe['b']}" not in seite  # das Bild zeigt „= ?“, nie die Lösung


def test_eine_geloeste_aufgabe_traegt_kein_zweites_absenden(client):
    login = reverse("mitglieder:login")
    felder = botschutz(client, url=login)
    erste = client.post(login, {"email": "eva@example.org", **felder})
    assert "Postfach" in erste.content.decode()  # gültig
    zweite = client.post(login, {"email": "eva@example.org", **felder})  # dieselbe Kennung und Antwort
    assert "Sicherheitsfrage wurde nicht richtig" in zweite.content.decode()


def test_nach_einem_tippfehler_bleibt_dieselbe_aufgabe_stehen(client):
    """Wer sich in der Gemeinde vertippt, muss nicht neu rechnen — die Aufgabe ist erst
    verbraucht, wenn das ganze Formular trägt."""
    felder = botschutz(client)
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, "gemeinde": "Entenhausen", **felder})
    inhalt = antwort.content.decode()
    assert "amtlichen Gemeindeverzeichnis" in inhalt
    assert f'value="{felder["pruefung"]}"' in inhalt  # dieselbe Kennung wird erneut gerendert
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **felder})
    assert Mitglied.objects.filter(email="eva@example.org").exists()


def test_willkommensseite_zeigt_beitrags_qr(client):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    client.get(link_aus_mail(mail.outbox[0]), follow=True)  # bestätigen (landet in der Einführung)
    inhalt = client.get(reverse("mitglieder:willkommen")).content.decode()
    assert "<svg" in inhalt  # EPC-QR-Code (F-38): Zahlen mit Code, ohne Zahlungsdienstleister
    assert "Zahlen mit Code" in inhalt


# --- Mitgliedschaftsseite sagt, was der Code tut (Befunde #15, #51, #55) ----------------


def test_mitgliedschaftsseite_verspricht_keinen_schutz_den_es_nicht_gibt(client):
    """Geprüft wird heute die E-Mail-Adresse, „geprüft“ setzt der Beitragseingang; es gibt
    keine regionale Stimmberechtigung (§ 5 Abs 6 verbietet den Ausschluss); die Durchrechnung
    der Werkstatt ist im Aufbau. Die Seite darf nichts anderes behaupten."""
    inhalt = client.get(reverse("mitglieder:mitgliedschaft")).content.decode()
    assert "gekauften Mehrheiten" not in inhalt and "mit geprüfter Identität" not in inhalt
    assert "Beitragseingang schaltet die Mitwirkung" in inhalt and "Frage des Vertrauens" in inhalt
    assert "Ihre Gemeinde stimmt" not in inhalt
    assert "schließt niemanden von einer Abstimmung aus (§ 5 Abs 6)" in inhalt
    assert "rechnet durch, welche Gesetze" not in inhalt
    assert "ist im Aufbau" in inhalt
    assert Identitaetsstufe.GEPRUEFT.label == "geprüft (Beitragseingang verbucht)"  # kein „Einladungscode“


# --- Gemeindeverzeichnis (F-43) --------------------------------------------------


def test_unbekannte_gemeinde_wird_abgelehnt(client):
    daten = {**ANMELDUNG, "gemeinde": "Entenhausen", **botschutz(client)}
    antwort = client.post(reverse("mitglieder:registrieren"), daten)
    assert "amtlichen Gemeindeverzeichnis" in antwort.content.decode()
    assert Mitglied.objects.count() == 0


def test_mehrdeutige_gemeinde_verlangt_praezisierung(client):
    daten = {**ANMELDUNG, "gemeinde": "Krumbach", **botschutz(client)}
    antwort = client.post(reverse("mitglieder:registrieren"), daten)
    inhalt = antwort.content.decode()
    assert "mehrmals" in inhalt and "Bregenz" in inhalt  # beide Kandidaten angeboten
    assert Mitglied.objects.count() == 0

    daten["gemeinde"] = "Krumbach (Bregenz)"
    daten.update(botschutz(client))
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
    antwort = client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    assert antwort.status_code == 200  # Formular mit Meldung, kein 500
    assert "gestört" in antwort.content.decode()
    assert Mitglied.objects.count() == 0  # nichts halb angelegt — die Adresse bleibt frei

    monkeypatch.undo()  # Versand repariert: derselbe Mensch kann es sofort erneut versuchen
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    assert Mitglied.objects.filter(email="eva@example.org").exists()
    assert len(mail.outbox) == 1


def test_versandstoerung_beim_anmelden_wird_offen_gemeldet(client, monkeypatch):
    m = Mitglied.objects.create(username="eva@example.org", email="eva@example.org", is_active=True)
    m.set_unusable_password()
    m.save()
    _versand_kaputt(monkeypatch)
    antwort = client.post(reverse("mitglieder:login"), {"email": "eva@example.org", **botschutz(client)})
    assert antwort.status_code == 200
    assert "gestört" in antwort.content.decode()
    assert "Postfach" not in antwort.content.decode()  # keine falsche „unterwegs“-Seite
