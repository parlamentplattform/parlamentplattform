"""Öffentliche Nachlese von Herkunft und erhaltenen RIS-Ständen, ohne externe Abrufe."""

import pytest
from playwright.sync_api import expect

from faktenbasis import importieren as modul
from faktenbasis.importieren import importieren
from faktenbasis.ris import antwort_parsen
from faktenbasis.test_ris import NUMMER, STAND, beispiel

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel", [
    ("desktop-hell-js", {"width": 1440, "height": 900}, True, False),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False),
    ("handy-dunkel-js", {"width": 390, "height": 844}, True, True),
])
def test_amtliche_metadaten_und_herkunft_oeffentlich_lesen(
    seite, live_server, sichtpruefung, monkeypatch, kennung, viewport, js, dunkel,
):
    daten = beispiel()
    monkeypatch.setattr(modul, "abrufen", lambda *args: antwort_parsen(daten, NUMMER))
    importieren(NUMMER, STAND)
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True)
    p.goto(f"{live_server.url}/zukunftswerkstatt/faktenbasis/")
    expect(p.get_by_role("heading", name="Faktenbasis", exact=True)).to_be_visible()
    expect(p.get_by_text("1 Dokument · 1 Schnappschuss")).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.screenshot(path=str(sichtpruefung / f"faktenbasis-{kennung}.png"), full_page=True)
    p.get_by_role("link", name="Abänderung des Bundes-Verfassungsgesetzes").click()
    expect(p.get_by_text("Metadaten, kein vollständiger Gesetzestext", exact=True)).to_be_visible()
    p.get_by_text("Herkunft und Prüfsumme", exact=True).click()
    expect(p.locator(".fakten-rohdaten")).to_be_visible()
    expect(p.get_by_role("link", name="Amtliches Dokument im RIS öffnen")).to_have_attribute(
        "href", "https://ogd.ris.bka.gv.at/eli/bgbl/1962/215/P0/NOR11000363",
    )
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.screenshot(path=str(sichtpruefung / f"faktenbasis-norm-{kennung}.png"), full_page=True)
