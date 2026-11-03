"""Der tatsächliche regionale Teilnehmerkreis ist auch am Handy ohne JS lesbar."""

import pytest
from playwright.sync_api import expect

from verfahren.models import Antragsart, Ebene, antrag_einbringen
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell-js", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_regionaler_teilnehmerkreis_wird_nicht_als_oertliche_sperre_versprochen(
    seite, live_server, sichtpruefung, ordnung, kennung, viewport, js, dunkel, sprache,  # noqa: F811
):
    a = antrag_einbringen(mitglied_anlegen(), "Kandidatur im Testgebiet", "Interne Kandidatur für ein Testmandat.", "",
                         ordnung, ebene=Ebene.GEMEINDE, gebiet="Testgebiet", art=Antragsart.MANDAT)
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True, sprache=sprache)
    p.goto(f"{live_server.url}/antrag/{a.pk}/")
    expect(p.locator("#teilnehmerkreis")).to_be_visible()
    expect(p.locator("#teilnehmerkreis")).to_contain_text("party-wide" if sprache == "en" else "parteiweit geprüft")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"teilnehmerkreis-{kennung}.png"), full_page=True)
