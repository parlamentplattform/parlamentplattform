"""Ring 0b — das Parameterregister (F-68): öffentlich, mit Herkunft,
Änderungen nur mit veröffentlichtem Grund; der Code liest von hier."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import standard_ende
from gremien.test_werkstatt import (  # noqa: F401
    einreichen,
    mitglied_anlegen,
    ordnung,
    werkstatt_lage,
)
from ki.models import KILauf
from parameter.models import ERSTBESTAND, Parameter, erstbestand_sicherstellen, zahl
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


def test_erstbestand_wird_angelegt_und_nie_ueberschrieben():
    assert erstbestand_sicherstellen() == len(ERSTBESTAND)
    eintrag = Parameter.objects.get(schluessel="gremien-hoechstrunden")
    eintrag.wert = "5"
    eintrag.save()
    assert erstbestand_sicherstellen() == 0  # idempotent
    eintrag.refresh_from_db()
    assert eintrag.wert == "5"  # das Register gehört den Menschen, nicht dem Code


def test_zahl_liest_register_mit_ehrlichem_rueckfall():
    assert zahl("gremien-review-tage", 99) == 99  # noch kein Eintrag -> Zielwert
    Parameter.objects.create(
        schluessel="gremien-review-tage", wert="7", beschreibung="x", quelle="Test"
    )
    assert zahl("gremien-review-tage", 99) == 7
    Parameter.objects.create(schluessel="kaputt", wert="viele", beschreibung="x", quelle="Test")
    assert zahl("kaputt", 42) == 42  # unlesbarer Wert -> Zielwert


def test_oeffentliche_seite_und_json_export(client):
    antwort = client.get(reverse("parameter:liste"))
    inhalt = antwort.content.decode()
    assert "gremien-review-tage" in inhalt and "§ 5 Abs 12" in inhalt  # Erstbestand + Quelle
    daten = client.get(reverse("parameter:export")).json()
    schluessel = {p["schluessel"] for p in daten["parameter"]}
    assert {"gremien-hoechstrunden", "ki-monatstokens"} <= schluessel


def test_verwaltung_aendert_nur_mit_grund(client):
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    client.get(reverse("parameter:verwaltung"))  # legt Erstbestand an
    eintrag = Parameter.objects.get(schluessel="gremien-review-tage")
    client.post(
        reverse("parameter:verwaltung_aktion"), {"parameter": eintrag.pk, "wert": "7", "grund": ""}
    )
    eintrag.refresh_from_db()
    assert eintrag.wert == "14"  # ohne Grund keine Änderung
    client.post(
        reverse("parameter:verwaltung_aktion"),
        {"parameter": eintrag.pk, "wert": "7", "grund": "Alpha-Erprobung: kürzere Schleife."},
    )
    eintrag.refresh_from_db()
    assert eintrag.wert == "7"
    audit = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "parameter_geaendert"]
    assert audit and audit[0]["alt"] == "14" and audit[0]["neu"] == "7"


def test_gaeste_sehen_das_register_aber_nicht_die_verwaltung(client):
    assert client.get(reverse("parameter:liste")).status_code == 200
    antwort = client.get(reverse("parameter:verwaltung"))
    assert antwort.status_code in (302, 403)  # Login-Umleitung bzw. kein Zugang


def test_schleife_liest_ihre_frist_aus_dem_register(client, ordnung):  # noqa: F811
    Parameter.objects.create(
        schluessel="gremien-review-tage", wert="3", beschreibung="x", quelle="Test"
    )
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    rest = entwurf.review_frist - timezone.now()
    assert timedelta(days=2, hours=23) < rest <= timedelta(days=3)


def test_rollen_dauer_aus_dem_register():
    Parameter.objects.create(
        schluessel="gremien-rollen-dauer-tage", wert="10", beschreibung="x", quelle="Test"
    )
    assert standard_ende() == timezone.localdate() + timedelta(days=10)


def test_ki_budget_aus_dem_register(settings):
    settings.DDOE_KI_MONATSTOKENS = 555
    assert KILauf.monatsbudget() == 555  # Rückfall auf die Umgebung
    Parameter.objects.create(schluessel="ki-monatstokens", wert="777", beschreibung="x", quelle="Test")
    assert KILauf.monatsbudget() == 777  # das Register führt
