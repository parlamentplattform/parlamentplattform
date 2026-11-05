"""Persönliche Profilwechsel bleiben atomar; fremde Profile und CSRF bleiben geschützt."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event
from time import monotonic, sleep

import pytest
from django.db import connection, connections
from django.test import Client
from django.urls import reverse

from parameter.models import Parameter
from verfahren import views_aktionen
from verfahren.models import FilterProfil
from verfahren.test_views_aktionen import mitglied_anlegen


@pytest.mark.django_db(transaction=True)
@pytest.mark.parametrize("aktion", ["waehlen", "neutral", "umbenennen"])
def test_schreiben_nach_begonnener_neuanlage_bleibt_konsistent(monkeypatch, aktion):
    if connection.vendor != "postgresql":
        pytest.skip("Zeilensperren werden auf PostgreSQL geprüft.")
    Parameter.objects.update_or_create(schluessel="weicherfilter-profile-hoechstzahl", defaults={"wert": "2"})
    m = mitglied_anlegen()
    alt = FilterProfil.objects.create(mitglied=m, name="Bisher", aktiv=True)
    clients = [Client(), Client()]
    for client in clients:
        client.force_login(m)
    angelegt, auswahl_begonnen, freigeben = Event(), Event(), Event()
    original = views_aktionen._zurueck_zum_parlament
    backend = {}

    def antwort(request, *args, **kwargs):
        if request.POST.get("profilname") == "Neu":
            angelegt.set()
            assert freigeben.wait(timeout=10)
        return original(request, *args, **kwargs)

    monkeypatch.setattr(views_aktionen, "_zurueck_zum_parlament", antwort)

    def anlegen():
        connections.close_all()
        try:
            return clients[0].post(reverse("verfahren:filter_anwenden"), {
                "als_neues": "1", "profilname": "Neu", "r_chronologisch": "40",
            }).status_code
        finally:
            connections.close_all()

    def waehlen():
        connections.close_all()
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_backend_pid()")
                backend["pid"] = cursor.fetchone()[0]
            auswahl_begonnen.set()
            url = reverse(f"verfahren:filter_{aktion}", args=[] if aktion == "neutral" else [alt.pk])
            return clients[1].post(url, {"name": "Neu"} if aktion == "umbenennen" else {}).status_code
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        neu = pool.submit(anlegen)
        try:
            assert angelegt.wait(timeout=10)
            wahl = pool.submit(waehlen)
            assert auswahl_begonnen.wait(timeout=10)
            wartet = False
            bis = monotonic() + 5
            while monotonic() < bis:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT wait_event_type FROM pg_stat_activity WHERE pid = %s", [backend["pid"]])
                    zeile = cursor.fetchone()
                if zeile and zeile[0] == "Lock":
                    wartet = True
                    break
                sleep(0.02)
            assert wartet, "Die Auswahl muss den laufenden Schreibvorgang abwarten."
        finally:
            freigeben.set()
        assert neu.result(timeout=15) == 302 and wahl.result(timeout=15) == 302

    assert m.filterprofile.count() == 2
    aktive = list(m.filterprofile.filter(aktiv=True).values_list("name", flat=True))
    assert aktive == {"waehlen": ["Bisher"], "neutral": [], "umbenennen": ["Neu"]}[aktion]
    assert list(m.filterprofile.order_by("pk").values_list("name", flat=True)) == ["Bisher", "Neu"]


AKTIONEN = ("anwenden", "favoriten", "waehlen", "neutral", "umbenennen", "loeschen")


def adresse(aktion, profil):
    args = [profil.pk] if aktion in {"waehlen", "umbenennen", "loeschen"} else []
    return reverse(f"verfahren:filter_{aktion}", args=args)


@pytest.mark.django_db
@pytest.mark.parametrize("aktion", AKTIONEN)
@pytest.mark.parametrize("schutz", ["gast", "csrf"])
def test_jeder_profilschreibweg_braucht_anmeldung_und_csrf(aktion, schutz):
    m = mitglied_anlegen()
    profil = FilterProfil.objects.create(mitglied=m, name="Unverändert", aktiv=True)
    # Anmeldung und CSRF unabhängig prüfen: sonst sperrt die Middleware
    # bereits den Gast-POST, bevor der Anmeldeschutz erreicht wird.
    client = Client(enforce_csrf_checks=schutz == "csrf")
    if schutz == "csrf":
        client.force_login(m)
    vorher = list(m.filterprofile.values())
    r = client.post(adresse(aktion, profil), {
        "name": "Anders", "profilname": "Neu", "als_neues": "1", "r_chronologisch": "70",
    })
    assert r.status_code == (403 if schutz == "csrf" else 302)
    assert list(m.filterprofile.values()) == vorher


@pytest.mark.django_db
@pytest.mark.parametrize("aktion", ["waehlen", "umbenennen", "loeschen"])
def test_fremde_profile_sind_auch_unter_der_sperre_nicht_beschreibbar(client, aktion):
    eigenes = mitglied_anlegen()
    fremdes = mitglied_anlegen("andere")
    profil = FilterProfil.objects.create(mitglied=fremdes, name="Privat", aktiv=True)
    client.force_login(eigenes)
    vorher = list(FilterProfil.objects.values())
    r = client.post(adresse(aktion, profil), {"name": "Anders"})
    assert r.status_code == 404 and list(FilterProfil.objects.values()) == vorher
