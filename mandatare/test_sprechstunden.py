"""Ort, Rechte, Zeitzone und nachvollziehbare Absage von veröffentlichten Terminen."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Mandat, Sprechstunde
from mitglieder.models import Gemeinde
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


@pytest.fixture
def mandat():
    ort = Gemeinde.objects.create(kennziffer="40510", name="Gleichort", bezirk="Eferding", bundesland="oberoesterreich")
    return Mandat.objects.create(mitglied=mitglied_anlegen("ratsmitglied"), bezeichnung="Gemeinderat", gemeinde=ort)


def _formular():
    beginn = timezone.localtime() + timedelta(days=2)
    return {"beginn": beginn.strftime("%Y-%m-%dT%H:%M"), "ende": (beginn + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "treffpunkt": "Öffentlicher Raum A"}


def test_mandatar_veroeffentlicht_nur_am_zugeordneten_ort_und_sagt_nachvollziehbar_ab(client, mandat):
    gleichort = Gemeinde.objects.create(kennziffer="41419", name=mandat.gemeinde.name, bezirk="Schärding", bundesland="oberoesterreich")
    client.force_login(mandat.mitglied)
    url = reverse("mandatare:sprechstunden", args=[mandat.pk])
    antwort = client.post(url, _formular())
    assert antwort.status_code == 302
    termin = Sprechstunde.objects.get()
    oeffentlich = reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer])
    gast = Client()
    assert "Öffentlicher Raum A" in gast.get(oeffentlich).content.decode()
    assert "Öffentlicher Raum A" not in gast.get(reverse("gemeinde:ort", args=[gleichort.kennziffer])).content.decode()
    assert "private" in client.get(url).headers["Cache-Control"]

    absage = reverse("mandatare:sprechstunde_absagen", args=[mandat.pk, termin.pk])
    assert client.get(absage).status_code == 405
    for _ in range(2):
        assert client.post(absage).status_code == 302
    termin.refresh_from_db()
    assert termin.abgesagt_am is not None
    assert "Abgesagt" in gast.get(oeffentlich).content.decode()
    audit = AuditEintrag.objects.filter(ereignis__typ__startswith="sprechstunde_")
    assert sorted(e.ereignis["typ"] for e in audit) == ["sprechstunde_abgesagt", "sprechstunde_veroeffentlicht"]


def test_fremde_paused_und_mandatsende_sperren_veroeffentlichung(client, mandat):
    url = reverse("mandatare:sprechstunden", args=[mandat.pk])
    client.force_login(mitglied_anlegen("fremd"))
    assert client.post(url, _formular()).status_code == 404
    client.force_login(mandat.mitglied)
    mandat.mitglied.status = "pausiert"
    mandat.mitglied.save(update_fields=["status"])
    assert client.post(url, _formular()).status_code == 403
    mandat.mitglied.status = "aktiv"
    mandat.mitglied.save(update_fields=["status"])
    mandat.vertretung_beendet_am = timezone.localdate()
    mandat.save(update_fields=["vertretung_beendet_am"])
    assert client.post(url, _formular()).status_code == 404
    assert not Sprechstunde.objects.exists()


def test_falsche_datumsfolgen_doppelung_und_csrf(client, mandat):
    url = reverse("mandatare:sprechstunden", args=[mandat.pk])
    client.force_login(mandat.mitglied)
    daten = _formular()
    assert client.post(url, {**daten, "ende": daten["beginn"]}).status_code == 200
    assert client.post(url, {**daten, "beginn": daten["beginn"] + "+05:00"}).status_code == 200
    assert client.post(url, {**daten, "beginn": "a"}).status_code == 200
    assert not Sprechstunde.objects.exists()
    assert client.post(url, daten).status_code == 302
    assert client.post(url, daten).status_code == 200
    assert Sprechstunde.objects.count() == 1
    abgesichert = Client(enforce_csrf_checks=True)
    abgesichert.force_login(mandat.mitglied)
    assert abgesichert.post(url, daten).status_code == 403
