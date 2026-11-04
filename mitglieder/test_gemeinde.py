"""Gemeindeanmeldung ist weder Parteibeitritt noch ein zweiter Parteizugang."""

import re
from datetime import date, timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mitglieder.ausweis import ausweis_moeglich
from mitglieder.auth_flows import EinmalToken, beitragsreferenz
from mitglieder.models import (
    Gemeinde,
    Gemeindezugang,
    Mitglied,
    Postauftrag,
    Wohnsitzart,
    stimmberechtigte_zaehlen,
)
from mitglieder.nummern import sicherstellen
from mitglieder.post import freischaltung_senden, willkommen_senden
from mitglieder.postausgang import beauftragen
from mitglieder.test_views import botschutz, link_aus_mail
from plattform_core import Gegenstand
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


@pytest.fixture
def ort():
    return Gemeinde.objects.create(
        kennziffer="40510", name="St. Marienkirchen an der Polsenz", bezirk="Eferding", bundesland="oberoesterreich"
    )


@pytest.fixture
def buerger(ort):
    m = Mitglied.objects.create_user(
        "einwohner@example.org", email="einwohner@example.org", parteikonto=False,
        wohnsitz=ort, wohnsitz_art=Wohnsitzart.OESTERREICH, klarname_oeffentlich=False,
    )
    jetzt = timezone.now()
    Gemeindezugang.objects.create(konto=m, angemeldet_am=jetzt, alter_erklaert_am=jetzt, bestaetigt_am=jetzt)
    return m


def daten(ort, **extra):
    return {
        "email": "neu@example.org", "anzeigename": "Einwohnerin",
        "geburtsdatum": "1990-11-01", "wohnsitz_art": "oesterreich",
        "gemeinde": ort.anzeige, "meldung": "on", "datenschutz": "on", **extra,
    }


def anmelden(client, ort, **extra):
    url = reverse("gemeinde:anmelden")
    return client.post(url, {**daten(ort, **extra), **botschutz(client, url=url)})


def test_anmeldung_bestaetigung_und_login_ohne_parteifolgen(client, ort):
    vorher = AuditEintrag.objects.count()
    r = anmelden(client, ort, parteikonto="True", post_einwilligung="on", grundsaetze="on")
    assert r.status_code == 200
    m = Mitglied.objects.get(email="neu@example.org")
    assert not m.parteikonto and not m.is_active and not m.has_usable_password()
    assert m.beitritt is None and m.mitgliedsnummer is None and not m.post_einwilligung
    assert m.wohnsitz == ort and not m.klarname_oeffentlich
    assert len(mail.outbox) == 1 and not mail.outbox[0].attachments
    assert "keiner Partei" in mail.outbox[0].body
    link = link_aus_mail(mail.outbox[0])
    assert link.startswith("/gemeinde/bestaetigen/")
    assert "geburtsdatum" not in {f.name for f in Gemeindezugang._meta.fields}
    assert "geburtsdatum" not in client.session
    assert client.get(link).url == reverse("gemeinde:konto")
    m.refresh_from_db()
    assert m.is_active and m.beitritt is None and m.mitgliedsnummer is None
    assert not m.ist_stimmberechtigt(Gegenstand.SACHFRAGE, timezone.localdate(), uebergang=True)
    assert not m.darf_mitwirken and not m.hat_adminrechte and not m.ist_mandatar
    assert m.gemeindezugang.bestaetigt_am is not None
    assert AuditEintrag.objects.count() == vorher  # keine privaten Wohnsitzdaten im Verfahrensaudit
    assert not Postauftrag.objects.filter(mitglied=m).exists()
    assert client.get(link).status_code == 400
    client.post(reverse("mitglieder:abmelden"))
    url = reverse("mitglieder:login")
    client.post(url, {"email": m.email, **botschutz(client, url=url)})
    assert client.get(link_aus_mail(mail.outbox[-1])).url == reverse("gemeinde:konto")
    assert len(mail.outbox) == 2


@pytest.mark.parametrize("extra", [
    {"geburtsdatum": "2100-01-01"}, {"meldung": ""}, {"datenschutz": ""},
    {"wohnsitz_art": "ausland"}, {"wohnsitz_art": "ohne_festen_wohnsitz"},
    {"gemeinde": "Erfundene Gemeinde"}, {"gemeinde": ""},
])
def test_unpassende_selbstauskunft_legt_kein_konto_an(client, ort, extra):
    assert anmelden(client, ort, **extra).status_code == 200
    assert not Mitglied.objects.exists()
    assert not Gemeindezugang.objects.exists()
    assert len(mail.outbox) == 0


def test_altersgrenze_taggenau(client, ort, monkeypatch):
    monkeypatch.setattr("mitglieder.gemeinde.timezone.localdate", lambda: date(2026, 11, 4))
    anmelden(client, ort, geburtsdatum="2010-11-05")
    assert not Mitglied.objects.exists()
    anmelden(client, ort, geburtsdatum="2010-11-04")
    assert Mitglied.objects.count() == 1


def test_versandfehler_rollt_konto_zuordnung_und_token_zurueck(client, ort):
    with patch("mitglieder.gemeinde.send_mail", side_effect=OSError("Testversand")):
        r = anmelden(client, ort)
    assert "nicht gespeichert" in r.content.decode()
    assert not Mitglied.objects.exists() and not Gemeindezugang.objects.exists() and not EinmalToken.objects.exists()


def test_gemeinde_token_und_parteibestaetigung_sind_getrennt(client, buerger):
    buerger.is_active = False
    buerger.save(update_fields=["is_active"])
    token = EinmalToken.ausstellen(buerger, EinmalToken.Zweck.GEMEINDE)
    assert client.get(reverse("mitglieder:bestaetigen", args=[token])).status_code == 400
    assert client.get(reverse("gemeinde:bestaetigen", args=[token])).status_code == 400  # bereits bestätigt
    buerger.refresh_from_db()
    assert not buerger.is_active and buerger.beitritt is None
    token = EinmalToken.ausstellen(buerger, EinmalToken.Zweck.BESTAETIGUNG)
    assert client.get(reverse("mitglieder:bestaetigen", args=[token])).status_code == 400


def test_erneuter_link_fuer_noch_unbestaetigtes_gemeindekonto(client, ort):
    anmelden(client, ort)
    m = Mitglied.objects.get()
    url = reverse("mitglieder:login")
    client.post(url, {"email": m.email, **botschutz(client, url=url)})
    assert "/gemeinde/bestaetigen/" in mail.outbox[-1].body
    assert client.get(link_aus_mail(mail.outbox[-1])).status_code == 302
    m.refresh_from_db()
    assert m.beitritt is None and not m.parteikonto


def test_parteiregistrierung_ueberschreibt_keinen_unbestaetigten_gemeindezugang(client, ort):
    from mitglieder.test_views import ANMELDUNG

    anmelden(client, ort)
    EinmalToken.objects.update(gueltig_bis=timezone.now() - timedelta(days=1))
    m = Mitglied.objects.get()
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, "email": m.email, **botschutz(client)})
    m.refresh_from_db()
    assert not m.parteikonto and m.beitritt is None and not m.is_active
    assert Mitglied.objects.count() == 1


def test_bestehendes_konto_ergaenzt_gemeindezugang_ohne_neues_mitglied(client, ort):
    m = Mitglied.objects.create_user("partei", email="partei@example.org", beitritt=date(2025, 1, 1))
    client.force_login(m)
    assert client.get(reverse("gemeinde:anmelden")).url == reverse("gemeinde:konto")
    assert client.post(reverse("gemeinde:konto"), daten(ort)).status_code == 302
    m.refresh_from_db()
    assert m.parteikonto and m.beitritt == date(2025, 1, 1) and m.wohnsitz == ort
    assert Mitglied.objects.count() == 1 and Gemeindezugang.objects.filter(konto=m, bestaetigt_am__isnull=False).exists()


@pytest.mark.parametrize("url", [
    "/einbringen/", "/einbringen/vorschau/", "/antrag/999/unterstuetzen/", "/antrag/999/abstimmen/",
    "/antrag/999/bewerben/", "/antrag/999/kommentieren/", "/verwaltung/1/", "/mandatare/mein/aktion/",
    "/profil/ausweis/mail/", "/beitrag/gemeldet/", "/profil/austritt/", "/filter/anwenden/",
])
def test_gemeindekonto_kann_keine_parteischreibwege_benutzen(client, buerger, url):
    client.force_login(buerger)
    assert client.post(url, {"parteikonto": "True"}).status_code == 403
    buerger.refresh_from_db()
    assert buerger.beitritt is None and not buerger.parteikonto


@pytest.mark.parametrize("url", ["/verwaltung/", "/profil/", "/beitrag/", "/einbringen/", "/profil/ausweis.pdf"])
def test_partei_private_leseseiten_bleiben_wie_fuer_gaeste_gesperrt(client, buerger, url):
    client.force_login(buerger)
    r = client.get(url)
    assert r.status_code in (302, 403)


def test_oeffentlich_lesen_mit_gemeindekontomenue_und_privater_export(client, buerger):
    client.force_login(buerger)
    r = client.get(reverse("verfahren:parlament"))
    assert r.status_code == 200
    html = r.content.decode()
    assert reverse("gemeinde:konto") in html
    leiste = html.partition("</header>")[0]
    assert 'href="/beitrag/"' not in leiste and 'href="/profil/"' not in leiste
    assert 'href="/einbringen/"' not in leiste
    assert buerger.email not in html and buerger.wohnsitz.name not in html
    r = client.get(reverse("gemeinde:export"))
    assert r.json()["konto"]["parteikonto"] is False
    assert r.json()["hauptwohnsitz"]["gemeinde"] == "40510"
    assert "no-store" in r["Cache-Control"]
    assert Client().get(reverse("gemeinde:export")).status_code == 302


def test_gemeindekonto_bekommt_keine_nummer_karte_post_oder_zaehlung(buerger):
    assert sicherstellen(buerger) is None
    assert not ausweis_moeglich(buerger)
    assert not willkommen_senden(buerger) and not freischaltung_senden(buerger)
    assert not beauftragen(buerger, "beitragserinnerung", bezug="jahr:2026")
    with pytest.raises(ValueError, match="keine Mitgliedsbeitragsreferenz"):
        beitragsreferenz(buerger)
    assert not Mitglied.parteikonten.exists()
    assert stimmberechtigte_zaehlen(Gegenstand.SACHFRAGE, timezone.localdate(), uebergang=True) == 0
    assert not Postauftrag.objects.exists()
    assert not getattr(mail, "outbox", [])
    buerger.refresh_from_db()
    assert buerger.mitgliedsnummer is None and not buerger.beitragsreferenz_stamm and not buerger.ausweis_code


@pytest.mark.parametrize("werte", [
    {"beitritt": date(2026, 1, 1)}, {"mitgliedsnummer": 1}, {"post_einwilligung": True},
    {"identitaetsstufe": "geprueft"}, {"ist_admin": True}, {"is_superuser": True},
    {"ausweis_code": "0123456789"}, {"beitragsreferenz_stamm": "ABCDEF"},
])
def test_datenbank_verhindert_parteidaten_am_gemeindekonto(buerger, werte):
    with pytest.raises(IntegrityError), transaction.atomic():
        Mitglied.objects.filter(pk=buerger.pk).update(**werte)


def test_kontotyp_laesst_sich_nicht_ueber_gewoehnliche_schreibwege_aendern(buerger):
    with pytest.raises(ValueError):
        Mitglied.objects.filter(pk=buerger.pk).update(parteikonto=True)
    buerger.parteikonto = True
    with pytest.raises(ValidationError):
        buerger.save()
    with pytest.raises(ValueError):
        Mitglied.objects.bulk_update([buerger], ["parteikonto"])
    with pytest.raises(ValueError):
        Mitglied.objects.bulk_create([buerger], update_conflicts=True, unique_fields=["username"], update_fields=["parteikonto"])
    kopie = Mitglied(pk=buerger.pk, username=buerger.username, parteikonto=True)
    with pytest.raises(ValidationError):
        kopie.save()


def test_umzug_ohne_festen_wohnsitz_entfernt_nur_aktuelle_zuordnung(client, buerger):
    client.force_login(buerger)
    r = client.post(reverse("gemeinde:konto"), {"wohnsitz_art": "ohne_festen_wohnsitz", "gemeinde": "alter Ort", "meldung": "on"})
    assert r.status_code == 302
    buerger.refresh_from_db()
    assert buerger.wohnsitz_id is None and not buerger.gemeinde and not buerger.bundesland
    assert buerger.is_active and not buerger.parteikonto
    assert "Keine aktuelle Hauptgemeinde" in client.get(reverse("gemeinde:konto")).content.decode()


def test_csrf_und_botschutz_bleiben_erforderlich(client, ort):
    assert Client(enforce_csrf_checks=True).post(reverse("gemeinde:anmelden"), daten(ort)).status_code == 403
    client.post(reverse("gemeinde:anmelden"), daten(ort))
    assert not Mitglied.objects.exists()
    for _ in range(5):
        client.post(reverse("gemeinde:anmelden"), {})
    assert "Zu viele Versuche" in anmelden(client, ort).content.decode()


def test_bestaetigungslink_enthaelt_keine_geburts_oder_wohnortdaten(client, ort):
    anmelden(client, ort)
    body = mail.outbox[0].body
    assert ort.name not in body and "1990" not in body and "Einwohnerin" not in body
    assert re.search(r"/gemeinde/bestaetigen/[A-Za-z0-9_-]+/", body)


def test_alle_oeffentlichen_parteizaehler_und_verwaltung_lassen_gemeindekonto_aus(client, buerger):
    from parameter.kennzahlen import werte

    m = Mitglied.objects.create_user("admin", email="admin@example.org", ist_admin=True)
    assert werte()["members.active"] == 1
    assert client.get(reverse("verfahren:index")).context["buehne"]["mitglieder"] == 1
    assert client.get(reverse("uebersicht:index")).context["mitglieder_gesamt"] == 1
    client.force_login(m)
    r = client.get(reverse("mitglieder:verwaltung"))
    assert r.context["zahlen"]["gesamt"] == 1
    assert buerger.email not in r.content.decode()
    assert client.get(reverse("mitglieder:verwaltung_mitglied", args=[buerger.pk])).status_code == 404


def test_gemeindezuordnung_wird_nicht_zum_oertlichen_parteikreis(buerger, ort):
    from plattform_core.teilnehmerkreis import gebiet_fuer
    from verfahren.models import Antrag
    from verfahren.teilnahme import gemeindestand, kreis_festhalten, oertlich_zulaessig
    from verfahren.test_views_aktionen import REGELN

    autor = Mitglied.objects.create_user("autor", wohnsitz=ort, wohnsitz_art="oesterreich")
    gebiet = gebiet_fuer("gemeinde", gemeindestand(ort), [gemeindestand(ort)])
    a = Antrag.objects.create(titel="Örtliche Parteifrage", eingebracht_von=autor,
                             ebene="gemeinde", gebiet=ort.name, policy_snapshot=REGELN, teilnahmegebiet=gebiet.als_dict())
    kreis_festhalten(a)
    assert a.oertlicher_kreis.filter(mitglied=autor).exists()
    assert not a.oertlicher_kreis.filter(mitglied=buerger).exists()
    assert not oertlich_zulaessig(a, buerger)


def test_gemeindekonto_kann_die_oeffentliche_rueckmeldung_wie_ein_gast_nutzen(client, buerger):
    from anstoss.models import Anstoss

    client.force_login(buerger)
    r = client.post(reverse("anstoss:senden"), {"text": "Örtliche Bedienfrage", "seite": "/gemeinde/konto/"})
    assert r.status_code in (200, 302)
    assert Anstoss.objects.get().nutzer_id is None
