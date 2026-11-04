"""Lange Datentexte auf Englisch lesen, auch ohne JavaScript und auf dem Handy."""

import pytest
from playwright.sync_api import expect

from parameter.models import erstbestand_sicherstellen
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False),
    ("handy-dunkel", {"width": 390, "height": 844}, True, True),
])
def test_datentexte_englisch_lesbar(
    seite, live_server, sichtpruefung, kennung, viewport, js, dunkel,
):
    erstbestand_sicherstellen()
    admin = mitglied_anlegen("datentexte-admin")
    admin.ist_admin = True
    admin.save(update_fields=["ist_admin"])
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True, sprache="en", als=admin)

    p.goto(f"{live_server.url}/rollen/")
    expect(p.locator("#rolle-mitglied")).to_contain_text("Member (confirmed, active)")
    expect(p.locator("#rolle-mitglied")).to_contain_text("after the qualifying period")
    expect(p.locator("#rolle-schiedsgericht")).to_contain_text("not currently maintain this list")
    expect(p.get_by_text("The German original texts remain authoritative", exact=False)).to_be_visible()
    assert p.locator(".rk").count() == 14
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    # Bei einer langen Elementaufnahme würden feste Navigation und Feedbackknopf
    # mitten im Bild landen. Nur für diese isolierte Kartenaufnahme ausblenden.
    p.locator("#rolle-mitglied").screenshot(
        path=str(sichtpruefung / f"datentexte-rolle-{kennung}.png"),
        style=".leiste,.anstoss-ecke,.gespraeche-griff{visibility:hidden!important}",
    )

    p.goto(f"{live_server.url}/regeln/")
    regel = p.locator("#regel-eligibility")
    expect(regel).to_contain_text("three months for substantive questions")
    expect(regel).to_contain_text("twelve months for elections of persons")
    expect(regel).to_contain_text("last day")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    regel.screenshot(path=str(sichtpruefung / f"datentexte-regel-{kennung}.png"))

    p.goto(f"{live_server.url}/parameter/")
    expect(p.get_by_text("four weeks also give time", exact=False)).to_be_visible()
    expect(p.get_by_text("all other values act as 0", exact=False).first).to_be_attached()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")

    p.goto(f"{live_server.url}/parameter/verfahren-abstimmung-tage/")
    expect(p.get_by_text("The statutes require at least seven days", exact=False)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"datentexte-parameter-{kennung}.png"), full_page=True)

    p.goto(f"{live_server.url}/verwaltung/parameter/")
    expect(p.get_by_text("Protects the monthly budget from a single account", exact=False)).to_be_attached()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"datentexte-verwaltung-{kennung}.png"))
