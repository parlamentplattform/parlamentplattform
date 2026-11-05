"""Anzeige, Speichern und Rückmeldungen verwenden dieselbe vorhandene Stellgröße."""

import pytest
from django.db import connection, connections
from django.test import Client
from django.urls import reverse

from parameter.models import Parameter
from verfahren.models import FilterProfil
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


def grenze(wert):
    Parameter.objects.update_or_create(schluessel="weicherfilter-profile-hoechstzahl", defaults={"wert": str(wert)})


def neu(client, name, **extra):
    return client.post(reverse("verfahren:filter_anwenden"), {
        "als_neues": "1", "profilname": name, "r_chronologisch": "40", **extra,
    }, follow=True)


@pytest.mark.parametrize("limit", [2, 7])
def test_anzeige_und_beide_rueckmeldungswege_nennen_die_tatsaechliche_grenze(client, limit):
    grenze(limit)
    m = mitglied_anlegen()
    client.force_login(m)
    for i in range(limit):
        neu(client, f"Profil {i}")
    r = client.get(reverse("verfahren:parlament"))
    assert r.context["filter_lage"]["hoechstzahl"] == limit and r.context["filter_lage"]["voll"]
    assert f"{limit} von {limit} — eine löschen oder überschreiben" in r.content.decode()
    flash = neu(client, "Zuviel")
    assert f"Höchstens {limit} Konfigurationen" in flash.content.decode()
    feld = neu(client, "Auch zuviel", feld="filter", weiter="/parlament/")
    assert f"Höchstens {limit} Konfigurationen" in feld.context["hinweis"]["text"]
    assert FilterProfil.objects.filter(mitglied=m).count() == limit


@pytest.mark.parametrize("limit", [0, -1])
def test_null_sperrt_nur_neue_profile_ohne_unmoeglichen_loeschauftrag(client, limit):
    grenze(limit)
    m = mitglied_anlegen()
    client.force_login(m)
    r = neu(client, "Neu", feld="filter", weiter="/parlament/")
    assert not FilterProfil.objects.filter(mitglied=m).exists()
    assert r.context["filter_lage"]["hoechstzahl"] == 0
    assert "Neue Konfigurationen sind gesperrt." in r.content.decode()


def test_gesenkte_grenze_erhaelt_alten_bestand_und_erlaubt_ueberschreiben(client):
    m = mitglied_anlegen()
    client.force_login(m)
    grenze(7)
    for i in range(7):
        neu(client, f"Profil {i}")
    ids = list(m.filterprofile.order_by("pk").values_list("pk", flat=True))
    grenze(2)
    neu(client, "Profil 1")
    neu(client, "Neues darf nicht verdrängen")
    assert list(m.filterprofile.order_by("pk").values_list("pk", flat=True)) == ids
    assert m.filterprofile.get(name="Profil 1").aktiv
    grenze(0)
    r = client.post(reverse("verfahren:filter_anwenden"), {"r_chronologisch": "70"})
    assert r.status_code == 302 and m.filterprofile.get(name="Profil 1").regler["chronologisch"] == 70
    assert list(m.filterprofile.order_by("pk").values_list("pk", flat=True)) == ids


def test_hoehere_grenze_bietet_auch_nach_fuenf_profilen_neuanlage_an(client):
    grenze(7)
    m = mitglied_anlegen()
    client.force_login(m)
    for i in range(5):
        neu(client, f"Profil {i}")
    r = client.get(reverse("verfahren:parlament"))
    assert not r.context["filter_lage"]["voll"]
    assert "Als neue Konfiguration speichern" in r.content.decode()


@pytest.mark.django_db(transaction=True)
def test_gleichzeitige_neuanlagen_ueberschreiten_die_grenze_nicht():
    if connection.vendor != "postgresql":
        pytest.skip("Zeilensperren werden auf PostgreSQL geprüft.")
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    grenze(1)
    m = mitglied_anlegen()
    clients = [Client(), Client()]
    for client in clients:
        client.force_login(m)
    start = Barrier(2)
    def anlegen(i):
        connections.close_all()
        try:
            start.wait(timeout=10)
            return clients[i].post(reverse("verfahren:filter_anwenden"), {
                "als_neues": "1", "profilname": f"Parallel {i}", "r_chronologisch": "40",
            }).status_code
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=2) as pool:
        ergebnisse = [pool.submit(anlegen, i) for i in range(2)]
        assert [e.result(timeout=30) for e in ergebnisse] == [302, 302]
    assert m.filterprofile.count() == 1 and m.filterprofile.filter(aktiv=True).count() == 1
