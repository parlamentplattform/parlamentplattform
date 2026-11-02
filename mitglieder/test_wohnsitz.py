"""Registrierung ohne erzwungene Gemeinde; Pflege, Rechte und private Daten bleiben konsistent."""

import importlib
import json
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.core.management import call_command
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Gemeinde, Identitaetsstufe, Mitglied, Wohnsitzart
from mitglieder.profil import austreten
from mitglieder.test_verwaltung import admin_anlegen, detail
from mitglieder.test_views import ANMELDUNG, botschutz
from plattform_core import Gegenstand
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db
OHNE_ORT = [Wohnsitzart.OHNE_FESTEN_WOHNSITZ, Wohnsitzart.AUSLAND]


@pytest.fixture(autouse=True)
def gemeinden(db):
    call_command("gemeinden_laden")


@pytest.mark.parametrize("art", OHNE_ORT)
def test_registrierung_ohne_gemeinde_erzeugt_keine_region_und_keine_freischaltung(client, art):
    daten = {**ANMELDUNG, "wohnsitz_art": art, "gemeinde": "", **botschutz(client)}
    antwort = client.post(reverse("mitglieder:registrieren"), daten)
    assert antwort.status_code == 200
    person = Mitglied.objects.get(email=ANMELDUNG["email"])
    assert person.wohnsitz_art == art
    assert (person.gemeinde, person.bundesland, person.wohnsitz_id) == ("", "", None)
    assert not person.is_active and person.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT
    assert not person.ist_stimmberechtigt(Gegenstand.SACHFRAGE, timezone.localdate(), uebergang=True)


@pytest.mark.parametrize("art", OHNE_ORT)
def test_versteckte_alte_gemeinde_wird_beim_wechsel_nicht_uebernommen(client, art):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, "wohnsitz_art": art, **botschutz(client)})
    person = Mitglied.objects.get(email=ANMELDUNG["email"])
    assert person.wohnsitz_art == art and not person.gemeinde and person.wohnsitz_id is None


@pytest.mark.parametrize("art", [Wohnsitzart.OESTERREICH, "unbekannt"])
def test_oesterreich_braucht_gemeinde_und_fremde_kennungen_werden_abgelehnt(client, art):
    antwort = client.post(reverse("mitglieder:registrieren"), {
        **ANMELDUNG, "wohnsitz_art": art, "gemeinde": "", **botschutz(client),
    })
    assert antwort.status_code == 200 and not Mitglied.objects.filter(email=ANMELDUNG["email"]).exists()
    assert antwort.context["form"].errors


def test_altes_geoeffnetes_registrierungsformular_funktioniert_weiter(client):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    person = Mitglied.objects.get(email=ANMELDUNG["email"])
    assert person.wohnsitz_art == Wohnsitzart.OESTERREICH and person.wohnsitz_id


def test_profilwechsel_ist_auditiert_ohne_die_private_angabe_zu_veroeffentlichen(client):
    person = mitglied_anlegen()
    person.wohnsitz = Gemeinde.objects.get(name="Graz")
    person.gemeinde, person.bundesland = "Graz", "steiermark"
    person.wohnsitz_art = Wohnsitzart.OESTERREICH
    person.save()
    client.force_login(person)
    for art in [*OHNE_ORT, Wohnsitzart.OESTERREICH]:
        antwort = client.post(reverse("mitglieder:profil"), {
            "wohnsitz_art": art, "gemeinde": "Graz", "nebenwohnsitz": "", "klarname_oeffentlich": "on",
        })
        assert antwort.status_code == 302
        person.refresh_from_db()
        assert person.wohnsitz_art == art
        assert bool(person.wohnsitz_id) == (art == Wohnsitzart.OESTERREICH)
        assert person.identitaetsstufe == Identitaetsstufe.GEPRUEFT
    ereignisse = list(AuditEintrag.objects.filter(ereignis__typ="profil").values_list("ereignis", flat=True))
    assert len(ereignisse) == 3 and all(e["felder"] == ["wohnsitz"] for e in ereignisse)
    assert all(wert not in json.dumps(ereignisse) for wert in [*OHNE_ORT, "Graz", "steiermark"])


@pytest.mark.parametrize("art", OHNE_ORT)
def test_persoenlicher_export_und_anwartschaft_bleiben_auch_ohne_region_bedienbar(client, art, ordnung):  # noqa: F811
    person = mitglied_anlegen(gemeinde="", bundesland="")
    person.wohnsitz_art = art
    person.save()
    client.force_login(person)
    daten = client.get(reverse("mitglieder:profil_export")).json()
    assert daten["wohnsitz_art"] == art and daten["wohnsitz"] is None
    assert person.ist_stimmberechtigt(Gegenstand.SACHFRAGE, timezone.localdate(), uebergang=True)
    html = client.get(reverse("verfahren:einbringen")).content.decode()
    assert 'value="bund"' in html and 'value="gemeinde"' not in html
    assert 'value="land"' not in html and 'value="bezirk"' not in html


def test_verwaltung_speichert_die_angabe_und_loescht_ueberholte_region(client):
    person = mitglied_anlegen()
    client.force_login(admin_anlegen())
    antwort = client.post(detail(person.pk), {
        "aktion": "stammdaten", "vorname": person.first_name, "nachname": person.last_name,
        "email": person.email, "anzeigename": "", "wohnsitz_art": Wohnsitzart.AUSLAND,
        "gemeinde": "Graz", "identitaetsstufe": person.identitaetsstufe, "beitrag_zuletzt_am": "",
    })
    assert antwort.status_code == 302
    person.refresh_from_db()
    assert person.wohnsitz_art == Wohnsitzart.AUSLAND
    assert not person.gemeinde and not person.bundesland and person.wohnsitz_id is None


def test_austritt_entfernt_auch_die_wohnsitzangabe():
    person = mitglied_anlegen(gemeinde="", bundesland="")
    person.wohnsitz_art = Wohnsitzart.OHNE_FESTEN_WOHNSITZ
    person.save()
    austreten(person)
    person.refresh_from_db()
    assert not person.wohnsitz_art


def test_bestandsmigration_erfindet_keine_wohnungslosigkeit_und_ueberschreibt_keine_wahl():
    bekannt = mitglied_anlegen("bekannt")
    unbekannt = mitglied_anlegen("unbekannt", gemeinde="", bundesland="")
    ausland = mitglied_anlegen("ausland", gemeinde="", bundesland="")
    ausland.wohnsitz_art = Wohnsitzart.AUSLAND
    ausland.save()
    migration = importlib.import_module("mitglieder.migrations.0023_wohnsitzangabe")
    editor = SimpleNamespace(connection=SimpleNamespace(alias="default"))
    assert migration.bestand_zuordnen(apps, editor) == 1
    assert migration.bestand_zuordnen(apps, editor) == 0
    for person in (bekannt, unbekannt, ausland):
        person.refresh_from_db()
    assert bekannt.wohnsitz_art == Wohnsitzart.OESTERREICH
    assert unbekannt.wohnsitz_art == "" and ausland.wohnsitz_art == Wohnsitzart.AUSLAND
