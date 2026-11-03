"""Herkunft, Teilmenge und offene Dokumenttexte bleiben auf jeder Oberfläche sichtbar."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.importieren import importieren
from faktenbasis.models import Norm
from faktenbasis.test_landesrecht import NUMMER, STAND, antwort  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("antwort")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_landesherkunft_ist_keine_rechtliche_oder_modellbestaetigung(
    seite, live_server, sichtpruefung, kennung, viewport, js, dunkel, sprache,
):
    importieren(NUMMER, STAND, bundesland="Oberoesterreich")
    n = Norm.objects.get()
    p = seite(js=js, dunkel=dunkel, viewport=viewport, sprache=sprache, reduziert=True)
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[n.pk]))
    expect(p.get_by_role("heading", name="Synthetisches Beispiel", exact=True)).to_be_visible()
    expect(p.get_by_text("State law · Oberösterreich" if sprache == "en" else "Landesrecht · Oberösterreich", exact=True)).to_be_visible()
    expect(p.get_by_text("State-law document texts and their use in model context" if sprache == "en" else "Landes-Dokumenttexte und ihre Verwendung im Modellkontext", exact=False)).to_be_visible()
    expect(p.get_by_role("button", name="Diesen Dokumenttext einmal abrufen")).to_have_count(0)
    p.get_by_text("Provenance and checksum" if sprache == "en" else "Herkunft und Prüfsumme", exact=True).click()
    expect(p.get_by_text("1 of 147" if sprache == "en" else "1 von 147", exact=False)).to_be_visible()
    expect(p.get_by_role("link", name="Download the stored metadata response" if sprache == "en" else "Gespeicherte Metadatenantwort herunterladen")).to_have_attribute("href", reverse("faktenbasis:importantwort", args=[n.importlauf_id]))
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"landesrecht-{kennung}.png"), full_page=True)
