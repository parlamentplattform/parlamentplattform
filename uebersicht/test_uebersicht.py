"""Übersichtsseite (F-50) und datensparsame Besuchszählung (F-52)."""

import pytest
from django.urls import reverse

from uebersicht.models import AntragAufruf, TagesBesucher, TagesZahl
from verfahren.models import antrag_einbringen, stimme_abgeben
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

BROWSER = {"HTTP_USER_AGENT": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}


def test_besuche_werden_als_tagessummen_gezaehlt(client):
    client.get("/", **BROWSER)
    client.get("/", **BROWSER)
    assert TagesZahl.objects.get().aufrufe == 2
    assert TagesBesucher.objects.count() == 1  # gleiche Person, gleiche Tageskennung
    client.get("/", HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1")
    assert TagesBesucher.objects.count() == 2  # anderes Gerät, neue Kennung — nie eine IP gespeichert


def test_maschinen_und_technikpfade_zaehlen_nicht(client):
    client.get("/", HTTP_USER_AGENT="Mozilla/5.0 (compatible; Googlebot/2.1)")
    client.get("/", HTTP_USER_AGENT="python-requests/2.32")
    client.get("/")  # ohne Browserkennung
    client.get("/gesund/", **BROWSER)
    assert TagesZahl.objects.count() == 0


def test_aufrufe_je_antrag(client, ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    client.get(f"/antrag/{antrag.pk}/", **BROWSER)
    client.get(f"/antrag/{antrag.pk}/", **BROWSER)
    eintrag = AntragAufruf.objects.get()
    assert (eintrag.antrag_id, eintrag.aufrufe) == (antrag.pk, 2)


def test_uebersichtsseite_zeigt_kennzahlen_ergebnisse_und_diagramme(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    for person, wahl in zip(leute, ["ja", "ja", "nein"], strict=True):
        stimme_abgeben(antrag, person, wahl)
    client.get(f"/antrag/{antrag.pk}/", **BROWSER)

    antwort = client.get(reverse("uebersicht:index"))
    inhalt = antwort.content.decode()
    assert antwort.status_code == 200
    assert antwort.context["mitglieder_gesamt"] == 3
    assert antwort.context["antraege_aktiv"] == 1
    assert "Abstimmung läuft" in inhalt
    assert "Ja 2" in inhalt and "Nein 1" in inhalt  # Summen je Abstimmung — nie Einzelstimmen
    assert "3 von 3 Stimmberechtigten" in inhalt and "100 % Beteiligung" in inhalt
    assert inhalt.count("<svg") >= 3  # Ergebnisbalken + Verlaufs- und Balkendiagramme
    assert ANTRAG["titel"] in inhalt  # meistgelesener Antrag mit Aufrufzahl
    assert "ohne Speicherung" in inhalt  # Datenschutz-Erklärung der Zählung


def test_uebersichtsseite_funktioniert_auch_leer(client):
    antwort = client.get(reverse("uebersicht:index"))
    assert antwort.status_code == 200
    assert "Noch keine Abstimmungen" in antwort.content.decode()
