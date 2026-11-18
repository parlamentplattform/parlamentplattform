"""Sitzungsunterlagen sind ohne JavaScript veröffentlich- und auffindbar."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from mandatare.test_gemeindesitzungsquellen import ERSTE_URL, aufgabe  # noqa: F401
from mandatare.test_sprechstunden import mandat as gemeindemandat  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def test_einladung_auf_der_oeffentlichen_ortsseite(seite, live_server, sichtpruefung, aufgabe):  # noqa: F811
    mandat = aufgabe.mandat
    p = seite(als=mandat.mitglied, viewport={"width": 390, "height": 844}, js=False, reduziert=True)
    p.goto(live_server.url + reverse("mandatare:mein_mandat", args=[mandat.pk]))
    p.get_by_role("link", name="Sitzungsunterlage verlinken", exact=True).press("Enter")
    p.get_by_role("textbox", name="Öffentlicher HTTPS-Link").fill(ERSTE_URL)
    p.get_by_role("checkbox", name="Diese Unterlage ist öffentlich und gehört zu dieser Gemeinderatssitzung.").check()
    p.screenshot(path=str(sichtpruefung / "sitzungsquelle-formular-handy-ohne-js-de.png"), full_page=True)
    p.get_by_role("button", name="Link veröffentlichen", exact=True).press("Enter")
    expect(p.get_by_role("link", name="Einladung und Tagesordnung")).to_have_attribute("href", ERSTE_URL)

    gast = seite(sprache="en", dunkel=True, js=False, reduziert=True)
    gast.goto(live_server.url + reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer]))
    gast.get_by_role("link", name="Public meeting documents").press("Enter")
    expect(gast.get_by_role("heading", name="Public meeting documents")).to_be_visible()
    expect(gast.get_by_role("link", name="Meeting notice and agenda")).to_have_attribute("href", ERSTE_URL)
    assert gast.evaluate("document.documentElement.scrollWidth <= innerWidth")
    gast.screenshot(path=str(sichtpruefung / "sitzungsquelle-oeffentlich-ohne-js-en.png"), full_page=True)
