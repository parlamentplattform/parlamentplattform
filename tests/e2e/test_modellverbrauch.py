"""Verbrauch ist öffentlich nachlesbar, kein erfundener Kostenbetrag und keine internen Texte."""

import re

import pytest
from playwright.sync_api import expect

from ki.models import KILauf, Zweck
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell-js", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_verbrauchstabelle_bleibt_ohne_js_lesbar(
    seite, live_server, sichtpruefung, settings, ordnung, kennung, viewport, js, dunkel, sprache,  # noqa: F811
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    m = mitglied_anlegen("verbrauch-browser")
    antrag = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    for zweck, erfolg, ein, aus in [(Zweck.RECHTSBEZUG, True, 125, 25),
                                    (Zweck.RECHTSBEZUG, False, 0, 0), (Zweck.EINSCHAETZUNG, True, 450, 50)]:
        KILauf.objects.create(zweck=zweck, antrag=antrag, angefordert_von=m,
                              eingabe="NICHT_OEFFENTLICHER_TESTTEXT", anbieter="attrappe", modell="Testmodell",
                              erfolgreich=erfolg, tokens_ein=ein, tokens_aus=aus)
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True, sprache=sprache)
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/#zone-einschaetzung")
    k = p.locator("#modellverbrauch")
    k.locator(":scope > summary").press("Enter")
    englisch = sprache == "en"
    expect(k.get_by_role("table")).to_be_visible()
    expect(k).to_contain_text("No monetary cost recorded" if englisch else "Kostenbetrag nicht erfasst")
    expect(k).to_contain_text("not billing evidence" if englisch else "kein Abrechnungsnachweis")
    expect(k.get_by_role("cell", name=re.compile(r"(?:^|\s)125$"))).to_be_visible()
    expect(k).to_contain_text("575")
    assert "NICHT_OEFFENTLICHER_TESTTEXT" not in k.inner_text()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"modellverbrauch-{kennung}.png"), full_page=True)
