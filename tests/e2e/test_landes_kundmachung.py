"""Die direkte Landes-Kundmachung erscheint mit ihrem archivierten Datumsnachweis."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.kundmachung import zuordnen
from faktenbasis.test_kundmachungsbeleg import ELI, rohbytes
from faktenbasis.test_novellenfundstelle import landesnorm_anlegen
from faktenbasis.testhilfe import abrufuhr  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("sprache,breite,hoehe", [("de", 390, 844), ("en", 1440, 900)])
def test_oberoesterreichischer_beleg_ist_nativ_lesbar(
    seite, live_server, sichtpruefung, monkeypatch, abrufuhr, sprache, breite, hoehe,  # noqa: F811
):
    norm = landesnorm_anlegen(monkeypatch)
    beleg = zuordnen(norm.pk, rohbytes())
    p = seite(sprache=sprache, js=False, dunkel=sprache == "en", reduziert=True,
              viewport={"width": breite, "height": hoehe})
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[norm.pk]))
    bereich = p.locator("#novellenfundstelle").locator("..")
    expect(bereich.get_by_role("link", name="LGBl. Nr. 62/2026")).to_have_attribute("href", ELI)
    expect(bereich.get_by_text(beleg.original_sha256, exact=True)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"landeskundmachung-ohne-js-{sprache}.png"), full_page=True)
