import pytest
from playwright.sync_api import expect

from ki.anbieter import AttrappenAnbieter

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_zugangsgrenze_wird_ohne_modellaufruf_nachgelesen(seite, live_server, sichtpruefung, settings, monkeypatch,
    kennung, viewport, js, dunkel, sprache):
    settings.DDOE_KI_ANBIETER = "attrappe"
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: pytest.fail("Kein Anbieter beim Nachlesen"))
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(f"{live_server.url}/zukunftswerkstatt/")
    englisch = sprache == "en"
    expect(p.get_by_text("Model requests share one operational access slot" if englisch else "Modellanfragen teilen sich einen betrieblichen Zugang", exact=False)).to_be_visible()
    expect(p.get_by_text("This is not a guaranteed spending cap" if englisch else "Das ist keine garantierte Geldobergrenze", exact=False)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.get_by_text("Model requests share one operational access slot" if englisch else "Modellanfragen teilen sich einen betrieblichen Zugang", exact=False).scroll_into_view_if_needed()
    p.screenshot(path=str(sichtpruefung / f"ki-zugang-{kennung}.png"))
