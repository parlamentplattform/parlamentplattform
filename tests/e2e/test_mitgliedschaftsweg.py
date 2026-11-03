"""Gleicher Ablauf auf beiden Einstiegen: Handy, Tastatur, Sprachen, ohne JavaScript."""

import pytest
from playwright.sync_api import expect

from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache,reduziert", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT", False),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT", True),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT", True),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en", True),
])
def test_mitgliedschaft_erklaert_lesbar_ohne_falsche_versprechen(
    seite, live_server, sichtpruefung, ordnung, kennung, viewport, js, dunkel, sprache, reduziert,  # noqa: F811
):
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=reduziert,
              video=(sichtpruefung / "bewegung") if not reduziert else None)
    en = sprache == "en"
    for url, name in [("/mitgliedschaft/", "mitgliedschaft"), ("/", "willkommen")]:
        p.goto(f"{live_server.url}{url}")
        diagramm = p.locator(".ablauf-bildlauf")
        diagramm.focus()
        expect(diagramm).to_be_focused()
        if viewport["width"] < 500:
            diagramm.press("ArrowRight")
            expect(diagramm).not_to_have_js_property("scrollLeft", 0, timeout=3000)
            assert diagramm.evaluate("e => e.scrollWidth > e.clientWidth")
        else:
            assert diagramm.evaluate("e => e.scrollWidth <= e.clientWidth")
        summary = p.locator(".ablauf-text > summary")
        summary.press("Enter")
        expect(p.locator(".ablauf-text ol")).to_be_visible()
        assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
        if name == "mitgliedschaft":
            expect(p.locator(".mitgliedsrechte a")).to_have_count(6)
            expect(p.locator(".werkstatt-mini article")).to_have_count(3)
            expect(p.locator("main")).to_contain_text("Local restrictions have not yet been implemented" if en else "Eine örtliche Begrenzung ist noch nicht umgesetzt")
            if reduziert:
                assert p.locator(".mitgliedsrechte path").first.evaluate("e => getComputedStyle(e).animationName") == "none"
            else:
                p.locator(".mitgliedsrechte").scroll_into_view_if_needed()
                expect(p.locator(".mitgliedsrechte > .karte").first).to_have_class("karte zeichnet")
                assert p.locator(".mitgliedsrechte path").first.evaluate("e => getComputedStyle(e).animationDuration") == "0.4s"
        p.evaluate("scrollTo({top: 0, left: 0, behavior: 'instant'})")
        p.screenshot(path=str(sichtpruefung / f"{name}-{kennung}.png"), full_page=True)
