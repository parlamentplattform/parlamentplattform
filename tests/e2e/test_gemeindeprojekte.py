"""Projektstand im Mandatsbereich erfassen und in der Ortsansicht lesen."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from mandatare.test_gemeindeprojekte import QUELLE, TITEL, projekt_daten
from mandatare.test_sprechstunden import mandat as gemeindemandat  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def test_projektquelle_ohne_javascript_veroeffentlichen(seite, live_server, sichtpruefung, gemeindemandat):  # noqa: F811
    p = seite(als=gemeindemandat.mitglied, js=False, reduziert=True, viewport={"width": 390, "height": 844})
    p.goto(live_server.url + reverse("mandatare:mein_mandat", args=[gemeindemandat.pk]))
    p.get_by_role("link", name="Gemeindeprojekt aufnehmen").press("Enter")
    p.get_by_label("Projekttitel").fill(TITEL)
    p.get_by_role("combobox", name="Belegter Projektstand").select_option("vorgestellt")
    p.get_by_label("Datum des belegten Stands").fill(projekt_daten()["stand_am"])
    p.get_by_label("Öffentlicher HTTPS-Link").fill(QUELLE)
    p.get_by_role("checkbox", name="Diese Quelle und diese Angaben sind öffentlich.").check()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / "gemeindeprojekt-eingabe-handy-de.png"), full_page=True)
    p.get_by_role("button", name="Veröffentlichen", exact=True).press("Enter")
    expect(p.get_by_role("link", name="Öffentliche Quelle zum Projektstand")).to_have_attribute("href", QUELLE)

    gast = seite(sprache="en", dunkel=True, js=False, reduziert=True)
    gast.goto(live_server.url + reverse("gemeinde:ort", args=[gemeindemandat.gemeinde.kennziffer]))
    gast.get_by_role("link", name="Municipal projects").press("Enter")
    gast.get_by_role("link", name=TITEL).press("Enter")
    expect(gast.get_by_role("heading", name="Current project status")).to_be_visible()
    expect(gast.get_by_role("link", name="Public source for this project status")).to_have_attribute("href", QUELLE)
    gast.screenshot(path=str(sichtpruefung / "gemeindeprojekt-oeffentlich-en.png"), full_page=True)

    p.get_by_role("link", name="Projektstand ergänzen").press("Enter")
    p.get_by_role("combobox", name="Belegter Projektstand").select_option("umsetzung")
    p.get_by_role("checkbox", name="Diese Quelle und diese Angaben sind öffentlich.").check()
    p.get_by_role("button", name="Veröffentlichen", exact=True).press("Enter")
    expect(p.get_by_text("In Umsetzung", exact=True)).to_be_visible()
    p.get_by_role("link", name="Projektstand ergänzen").press("Enter")
    p.get_by_role("button", name="Projektveröffentlichung zurückziehen").press("Enter")
    expect(p.get_by_role("heading", name="Veröffentlichung zurückgezogen")).to_be_visible()
    gast.reload()
    expect(gast.get_by_role("heading", name="Publication withdrawn")).to_be_visible()
    expect(gast.get_by_role("link", name="Public source for this project status")).to_have_count(0)
