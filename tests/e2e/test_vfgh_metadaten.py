"""Vom Quellenindex ohne JavaScript zum VfGH-Metadatenstand."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.test_vfgh_metadaten import AKTENZEICHEN, DOKUMENT, ECLI, QUELLE, original
from faktenbasis.vfgh_import import importieren

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize(("sprache", "breite", "hoehe", "titel"), [
    ("de", 390, 844, "Normangaben laut RIS-Metadaten"),
    ("en", 1440, 900, "Legal provisions listed in the RIS metadata"),
])
def test_vfgh_beleg_ist_nativ_bedienbar(seite, live_server, sichtpruefung, sprache, breite, hoehe, titel):
    stand = importieren(DOKUMENT, original())
    p = seite(sprache=sprache, js=False, dunkel=sprache == "en", reduziert=True,
              viewport={"width": breite, "height": hoehe})
    p.goto(live_server.url + reverse("faktenbasis:index"))
    p.locator(f'a[href="{reverse("faktenbasis:vfgh")}"]').press("Enter")
    p.get_by_role("link", name=AKTENZEICHEN, exact=True).press("Enter")
    expect(p.get_by_role("heading", name=titel, exact=True)).to_be_visible()
    expect(p.get_by_text(ECLI, exact=True)).to_be_visible()
    expect(p.get_by_text(stand.original_sha256, exact=True)).to_be_visible()
    expect(p.locator("main a[href^='https://www.ris.bka.gv.at/']")).to_have_attribute("href", QUELLE)
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.evaluate("window.scrollTo(0, 0)")
    p.screenshot(path=str(sichtpruefung / f"vfgh-metadaten-ohne-js-{sprache}.png"), full_page=True)
