"""Die verwendeten Auftragstexte sind ohne Anmeldung und ohne JavaScript nachlesbar."""

import pytest
from playwright.sync_api import expect

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport", [
    ("desktop", {"width": 1440, "height": 900}),
    ("handy", {"width": 390, "height": 844}),
])
@pytest.mark.parametrize("zweck,inhalt", [
    ("einschaetzung", "jede Entscheidung treffen Menschen"),
    ("parametervorschlag", "entschieden wird vom Koordinationsrat"),
])
def test_werkstatt_auftrag_oeffentlich_ohne_js(seite, live_server, sichtpruefung, kennung, viewport, zweck, inhalt):
    p = seite(js=False, viewport=viewport, reduziert=True)
    p.goto(f"{live_server.url}/zukunftswerkstatt/#steckplatz")
    p.locator("summary").filter(has_text=f"{zweck}-v1").click()
    text = p.locator("details[open] .auftragstext")
    expect(text).to_be_visible()
    expect(text).to_contain_text(inhalt)
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    text.locator("..").screenshot(path=str(sichtpruefung / f"{zweck}-auftrag-{kennung}-ohne-js.png"))
