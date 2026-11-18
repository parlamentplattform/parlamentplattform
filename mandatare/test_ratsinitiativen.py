"""Einbringung ist ein eigener dokumentierter Schritt, geschützt durch das Mandat."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Ratsinitiative, Ratsmeldung
from mandatare.test_sprechstunden import mandat  # noqa: F401
from mitglieder.models import Gemeinde
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db
INITIATIVE = {"titel": "Öffentlicher Gegenstand", "text": "Arbeitsstand des Mandatars.", "art": "anfrage"}


def test_verlauf_bleibt_oeffentlich_in_der_urspruenglichen_gemeinde(client, mandat):  # noqa: F811
    client.force_login(mandat.mitglied)
    erstellt = client.post(reverse("mandatare:ratsinitiative_anlegen", args=[mandat.pk]), INITIATIVE)
    assert erstellt.status_code == 302
    initiative = Ratsinitiative.objects.get()
    detail = erstellt.url
    melden = reverse("mandatare:ratsinitiative_melden", args=[mandat.pk, initiative.pk])
    heute = timezone.localdate()
    daten = {"text": "Beim Gemeindeamt übergeben", "datum": heute.isoformat()}
    assert client.post(melden, {**daten, "art": "antwort"}).status_code == 200
    assert client.post(melden, {**daten, "art": "eingebracht"}).status_code == 302
    assert client.post(melden, {**daten, "art": "eingebracht"}).status_code == 200
    assert client.post(melden, {**daten, "art": "antwort", "datum": (heute - timedelta(days=1)).isoformat()}).status_code == 200
    antwort = client.post(melden, {**daten, "art": "antwort", "text": "Öffentliche Antwort"}, follow=True)
    assert "Öffentliche Antwort" in antwort.content.decode()
    assert list(initiative.meldungen.values_list("art", flat=True)) == ["eingebracht", "antwort"]

    falscher_ort = Gemeinde.objects.create(kennziffer="41419", name=mandat.gemeinde.name, bezirk="Schärding", bundesland="oberoesterreich")
    mandat.gemeinde = falscher_ort
    mandat.save(update_fields=["gemeinde"])
    mandat.beendet = heute
    mandat.save(update_fields=["beendet"])
    assert client.post(melden, {**daten, "art": "nachtrag"}).status_code == 404
    gast = Client()
    assert "Öffentliche Antwort" in gast.get(detail).content.decode()
    assert gast.get(reverse("gemeinde:ratsinitiative", args=[falscher_ort.kennziffer, initiative.pk])).status_code == 404


def test_fremde_und_unbestaetigte_mandate_koennen_nicht_veroeffentlichen(client, mandat):  # noqa: F811
    anlegen = reverse("mandatare:ratsinitiative_anlegen", args=[mandat.pk])
    client.force_login(mitglied_anlegen("fremd"))
    assert client.post(anlegen, INITIATIVE).status_code == 404
    client.force_login(mandat.mitglied)
    mandat.mitglied.identitaetsstufe = "ungeprueft"
    mandat.mitglied.save(update_fields=["identitaetsstufe"])
    assert client.post(anlegen, INITIATIVE).status_code == 403
    assert not Ratsinitiative.objects.exists() and not Ratsmeldung.objects.exists()
