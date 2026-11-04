"""Amtliche Aggregate, Herkunft und Datenjahr bleiben ohne JavaScript lesbar."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.personalbeleg import ORIGINAL_SHA256
from faktenbasis.personalimport import datei_importieren
from faktenbasis.test_personalimport import gelesen  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("gelesen")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_aggregat_ist_keine_kapazitaetsprognose(seite, live_server, sichtpruefung,
    kennung, viewport, js, dunkel, sprache):
    a = datei_importieren(b"Synthetischer Browserbeleg").aggregat
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(live_server.url + reverse("faktenbasis:personal_detail", args=[a.pk]))
    karte = p.locator("#personal-aggregat")
    expect(karte).to_contain_text("2025")
    expect(karte).to_contain_text("VBÄ")
    expect(karte).to_contain_text("60312")
    expect(karte).to_contain_text("77788")
    expect(karte).to_contain_text("138100")
    expect(karte.get_by_text("Civil servants" if sprache == "en" else "Beamtinnen und Beamte", exact=True)).to_be_visible()
    expect(karte.get_by_text("Contract staff" if sprache == "en" else "Vertragliches Personal", exact=True)).to_be_visible()
    expect(karte.get_by_text("Total" if sprache == "en" else "Gesamt", exact=True)).to_be_visible()
    expect(karte).to_contain_text(ORIGINAL_SHA256)
    expect(karte).to_contain_text("not a forecast" if sprache == "en" else "keine Prognose")
    expect(karte.get_by_role("link", name="Download the aggregate and provenance as JSON" if sprache == "en" else "Aggregat mit Herkunft als JSON herunterladen")).to_have_attribute("href", reverse("faktenbasis:personal_nachweis", args=[a.pk]))
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"personalaggregat-{kennung}.png"), full_page=True)
