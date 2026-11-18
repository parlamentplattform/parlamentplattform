"""Eine Initiative vom Arbeitsplatz bis zum öffentlich lesbaren Ratsverlauf."""

import pytest
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect

from mandatare.test_ratsinitiativen import INITIATIVE
from mandatare.test_sprechstunden import mandat  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def test_ratsinitiative_ohne_skript_veroeffentlichen(seite, live_server, sichtpruefung, mandat):  # noqa: F811
    p = seite(als=mandat.mitglied, viewport={"width": 390, "height": 844}, js=False, reduziert=True)
    p.goto(live_server.url + reverse("mandatare:mein_mandat", args=[mandat.pk]))
    p.get_by_role("link", name="Ratsinitiative veröffentlichen", exact=True).press("Enter")
    p.locator("#id_art").select_option(INITIATIVE["art"])
    p.locator("#id_titel").fill(INITIATIVE["titel"])
    p.locator("#id_text").fill(INITIATIVE["text"])
    p.get_by_role("button", name="Veröffentlichen", exact=True).press("Enter")
    expect(p.get_by_role("heading", name=INITIATIVE["titel"], exact=True)).to_be_visible()

    p.get_by_role("link", name="Öffentlichen Verlauf ergänzen").press("Enter")
    p.locator("#id_art").select_option("eingebracht")
    p.locator("#id_datum").fill(timezone.localdate().isoformat())
    p.locator("#id_text").fill("Beim Gemeindeamt übergeben.")
    p.get_by_role("button", name="Veröffentlichen", exact=True).press("Enter")
    expect(p.get_by_text("Beim Gemeindeamt übergeben.", exact=True)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / "ratsinitiative-handy-ohne-js.png"), full_page=True)

    gast = seite(sprache="en", js=False, dunkel=True, reduziert=True)
    gast.goto(live_server.url + reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer]))
    gast.get_by_role("link", name="DDÖ council initiatives").press("Enter")
    gast.get_by_role("link", name=INITIATIVE["titel"]).press("Enter")
    expect(gast.get_by_role("heading", name="Public record", exact=True)).to_be_visible()
    expect(gast.get_by_role("heading", name="Submission recorded", exact=False)).to_be_visible()
    expect(gast.get_by_role("link", name="Add a public update")).to_have_count(0)
    gast.screenshot(path=str(sichtpruefung / "ratsinitiative-oeffentlich-en.png"), full_page=True)
