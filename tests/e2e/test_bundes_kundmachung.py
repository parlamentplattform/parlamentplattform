"""Datierter Link und Parlamentsmaterialien ohne JavaScript."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.kundmachung import zuordnen
from faktenbasis.test_bundeskundmachung import ELI, rohbytes
from faktenbasis.test_novellenfundstelle import AUFHEBUNGSFELDER, normstaende_anlegen
from faktenbasis.testhilfe import abrufuhr  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("sprache,breite,hoehe,materialien", [
    ("de", 390, 844, "Parlamentsmaterialien laut RIS-Beleg"),
    ("en", 1440, 900, "Parliamentary papers listed in the RIS record"),
])
def test_bundesbeleg_ist_nativ_lesbar(
    seite, live_server, sichtpruefung, monkeypatch, abrufuhr, sprache, breite, hoehe, materialien,  # noqa: F811
):
    _, norm = normstaende_anlegen(monkeypatch)
    beleg = zuordnen(norm.pk, rohbytes())
    p = seite(sprache=sprache, js=False, dunkel=sprache == "en", reduziert=True,
              viewport={"width": breite, "height": hoehe})
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[norm.pk]))
    bereich = p.locator("#novellenfundstelle").locator("..")
    expect(bereich.get_by_role("link", name="BGBl. I Nr. 70/2024")).to_have_attribute("href", ELI)
    expect(bereich.get_by_role("heading", name=materialien)).to_be_visible()
    expect(bereich.get_by_text("2594", exact=True)).to_be_visible()
    expect(bereich.get_by_text(beleg.original_sha256, exact=True)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    bereich.screenshot(path=str(sichtpruefung / f"bundeskundmachung-ohne-js-{sprache}.png"))
    rueckverweis = reverse("faktenbasis:kundmachung", args=[beleg.pk])
    bereich.locator(f'a[href="{rueckverweis}"]').press("Enter")
    staende = p.locator("#kundmachungsstaende")
    expect(staende.get_by_text(beleg.original_sha256, exact=True)).to_be_visible()
    expect(staende.get_by_role("link")).to_have_attribute("href", reverse("faktenbasis:norm", args=[norm.pk]) + "#novellenfundstelle")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"kundmachung-dokumentstaende-ohne-js-{sprache}.png"), full_page=True)


@pytest.mark.parametrize("sprache,breite,hoehe,titel", [
    ("de", 390, 844, "Aufhebungsfundstelle laut RIS-Metadaten"),
    ("en", 1440, 900, "Repeal reference in the RIS metadata"),
])
def test_aufhebungsfundstelle_zeigt_ausserkraftdatum_und_gebundene_quelle(
    seite, live_server, sichtpruefung, monkeypatch, abrufuhr, sprache, breite, hoehe, titel,  # noqa: F811
):
    _, norm = normstaende_anlegen(monkeypatch, AUFHEBUNGSFELDER)
    beleg = zuordnen(norm.pk, rohbytes())
    p = seite(sprache=sprache, js=False, dunkel=sprache == "en", reduziert=True,
              viewport={"width": breite, "height": hoehe})
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[norm.pk]))
    bereich = p.locator("#novellenfundstelle").locator("..")
    expect(bereich.get_by_role("heading", name=titel)).to_be_visible()
    expect(bereich.locator("time")).to_have_attribute("datetime", "2025-01-01")
    expect(bereich.get_by_role("link", name="BGBl. I Nr. 70/2024")).to_have_attribute("href", ELI)
    expect(bereich.get_by_text(beleg.original_sha256, exact=True)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    bereich.screenshot(path=str(sichtpruefung / f"aufhebungsfundstelle-ohne-js-{sprache}.png"))
