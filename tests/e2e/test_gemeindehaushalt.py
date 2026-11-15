"""Öffentliche Planunterlage ohne JavaScript erfassen und am richtigen Ort finden."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from mandatare.test_gemeindehaushalt import QUELLE
from mandatare.test_sprechstunden import mandat as gemeindemandat  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def test_haushaltsquelle_nativ_veroeffentlichen(seite, live_server, sichtpruefung, gemeindemandat):  # noqa: F811
    p = seite(als=gemeindemandat.mitglied, js=False, reduziert=True, viewport={"width": 390, "height": 844})
    p.goto(live_server.url + reverse("mandatare:mein_mandat", args=[gemeindemandat.pk]))
    p.get_by_role("link", name="Haushaltsunterlage verlinken").press("Enter")
    p.get_by_role("combobox", name="Unterlage").select_option("finanzplan")
    p.get_by_label("Haushaltsjahr oder erstes Planjahr").fill("2026")
    p.get_by_label("Letztes Planjahr (nur beim Finanzplan)").fill("2030")
    p.get_by_label("Öffentlicher HTTPS-Link").fill(QUELLE)
    p.get_by_role("checkbox", name="Diese Unterlage ist öffentlich", exact=False).check()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / "haushaltsquelle-eingabe-handy-de.png"), full_page=True)
    p.get_by_role("button", name="Link veröffentlichen").press("Enter")
    expect(p.get_by_role("link", name="Mittelfristiger Ergebnis- und Finanzplan 2026–2030")).to_have_attribute("href", QUELLE)

    gast = seite(sprache="en", dunkel=True, js=False, reduziert=True)
    gast.goto(live_server.url + reverse("gemeinde:ort", args=[gemeindemandat.gemeinde.kennziffer]))
    gast.get_by_role("link", name="Municipal budget").press("Enter")
    expect(gast.get_by_role("heading", name="Municipal budget", exact=True)).to_be_visible()
    expect(gast.get_by_role("link", name="Medium-term operating and financing plan 2026–2030")).to_have_attribute("href", QUELLE)
    gast.screenshot(path=str(sichtpruefung / "haushaltsquelle-oeffentlich-en.png"), full_page=True)
