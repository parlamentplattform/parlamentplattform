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


def test_antragstitel_mit_hochkomma_wird_auf_der_uebersicht_kein_markup(client, ordnung):  # noqa: F811
    """Befund #0 (gespeichertes XSS): Der Titel ist frei wählbar und fließt in das aria-label des
    Ergebnisbalkens, den die Seite mit |safe rendert. Ein Hochkomma darf dort nie ein Attribut
    beenden — sonst feuert `onload` bei jedem Besucher der anmeldefreien Seite."""
    from html import unescape

    leute = [mitglied_anlegen(f"x{i}") for i in range(3)]
    titel = "x' onload='alert(1)' data-x='"
    antrag = in_abstimmung_bringen(
        antrag_einbringen(leute[0], **{**ANTRAG, "titel": titel}, ordnung=ordnung), leute[1:]
    )
    stimme_abgeben(antrag, leute[1], "ja")
    inhalt = client.get(reverse("uebersicht:index")).content.decode()
    import xml.etree.ElementTree as ET

    assert "onload='alert(1)'" not in inhalt and 'onload="alert(1)"' not in inhalt
    balken = [s[: s.index("</svg>") + 6] for s in inhalt.split("<svg")[1:] if "aria-label='Ergebnis" in s]
    assert balken, "der Ergebnisbalken fehlt auf der Seite"
    for svg in balken:
        wurzel = ET.fromstring("<svg" + svg)  # wohlgeformt — der Titel hat die Struktur nicht verändert
        assert all("onload" not in e.attrib for e in wurzel.iter())
        assert "alert(1)" in unescape(wurzel.get("aria-label"))  # der Titel steht drin — als Text
