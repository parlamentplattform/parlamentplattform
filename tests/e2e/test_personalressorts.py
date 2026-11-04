"""Amtliche Ressortwerte, leere Felder und Rundungsgrenzen ohne Skriptzwang."""

import copy

import pytest
from playwright.sync_api import expect

from faktenbasis import ressortimport
from faktenbasis.test_ressortimport import DATEN
from faktenbasis.testhilfe import abrufuhr  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_ressortwerte_und_unbekannte_teilspalten(seite, live_server, sichtpruefung, monkeypatch,
    kennung, viewport, js, dunkel, sprache):
    monkeypatch.setattr(ressortimport, "lesen", lambda raw: copy.deepcopy(DATEN))
    lauf = ressortimport.datei_importieren(b"synthetisch")
    monkeypatch.setattr(ressortimport, "_herunterladen", lambda: pytest.fail("Keine Netzabfrage beim Nachlesen"))
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(f"{live_server.url}/zukunftswerkstatt/faktenbasis/personal/ressorts/{lauf.inhalt_id}/")
    karte = p.locator("#personal-ressorts")
    englisch = sprache == "en"
    expect(karte).to_contain_text("Not headcounts, available capacity or staffing forecasts" if englisch else "Keine Kopfzahlen, freien Kapazitäten oder Personalprognosen")
    expect(karte.locator("tbody > tr")).to_have_count(15)
    erste = karte.locator("tbody > tr").first
    expect(erste).to_contain_text("Sonstige oberste Organe")
    expect(erste).to_contain_text("not stated" if englisch else "nicht angegeben")
    expect(karte).to_contain_text("Methodology page" if englisch else "Methodikseite")
    expect(karte.get_by_role("link", name="Download the ministry staff table with provenance as JSON" if englisch else "Ressorttabelle mit Herkunft als JSON herunterladen")).to_have_attribute("href", f"/zukunftswerkstatt/faktenbasis/personal/ressorts/{lauf.inhalt_id}/nachweis.json")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"personalressorts-{kennung}.png"), full_page=True)
