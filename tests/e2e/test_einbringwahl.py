"""Ähnlichkeit und Wahl auf Desktop/Handy, mit und ohne JavaScript."""

import pytest
from playwright.sync_api import expect

from verfahren.models import Antrag, Eigenstaendigkeit, Unterstuetzung, antrag_einbringen
from verfahren.test_einbringen_aehnlichkeit import UMFORMULIERT
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("js", [True, False])
@pytest.mark.parametrize("kennung,viewport", [
    ("desktop", {"width": 1440, "height": 1000}),
    ("handy", {"width": 390, "height": 844}),
])
def test_direkt_unterstuetzen_mit_erhaltenem_entwurf(
    seite, live_server, ordnung, sichtpruefung, js, kennung, viewport,  # noqa: F811
):
    ziel = antrag_einbringen(mitglied_anlegen("anna"), ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    bernd = mitglied_anlegen("bernd")
    p = seite(als=bernd, js=js, viewport=viewport, reduziert=True)
    p.goto(f"{live_server.url}/einbringen/")
    p.get_by_label("Titel", exact=True).fill(UMFORMULIERT["titel"])
    p.get_by_label("Wortlaut des Antrags", exact=True).fill(UMFORMULIERT["wortlaut"])
    if not js:
        p.get_by_role("button", name="Antrag einbringen", exact=True).click()
    wahl = p.get_by_role("button", name="Diesen unterstützen", exact=True)
    expect(wahl).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.screenshot(path=str(sichtpruefung / f"einbringwahl-{kennung}-{'js' if js else 'ohne-js'}.png"), full_page=True)
    p.locator("#aehnliche-inhalt").screenshot(
        path=str(sichtpruefung / f"einbringwahl-auswahl-{kennung}-{'js' if js else 'ohne-js'}.png"),
    )
    wahl.click()
    expect(p.get_by_role("button", name="Ja, diesen unterstützen", exact=True)).to_be_visible()
    assert not Unterstuetzung.objects.filter(antrag=ziel, mitglied=bernd).exists()
    p.get_by_role("button", name="Zurück zu meinem Text", exact=True).click()
    expect(p.get_by_label("Wortlaut des Antrags", exact=True)).to_have_value(UMFORMULIERT["wortlaut"])
    p.get_by_role("button", name="Diesen unterstützen", exact=True).click()
    p.get_by_role("button", name="Ja, diesen unterstützen", exact=True).click()
    expect(p).to_have_url(f"{live_server.url}/antrag/{ziel.pk}/#zone-einschaetzung")
    expect(p.locator("#zone-einschaetzung")).to_be_visible()
    assert Unterstuetzung.gueltige().filter(antrag=ziel, mitglied=bernd).count() == 1
    assert Antrag.objects.count() == 1


def test_eigene_einstufung_ohne_javascript(seite, live_server, ordnung):  # noqa: F811
    ziel = antrag_einbringen(mitglied_anlegen("anna"), ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    p = seite(als=mitglied_anlegen("bernd"), js=False, reduziert=True)
    p.goto(f"{live_server.url}/einbringen/")
    p.get_by_label("Titel", exact=True).fill(UMFORMULIERT["titel"])
    p.get_by_label("Wortlaut des Antrags", exact=True).fill(UMFORMULIERT["wortlaut"])
    p.get_by_role("button", name="Antrag einbringen", exact=True).click()
    p.get_by_role("button", name="Mein Antrag ist etwas anderes — einbringen", exact=True).click()
    neu = Antrag.objects.latest("pk")
    assert Eigenstaendigkeit.objects.get(antrag=neu).gegenueber == ziel
    expect(p.get_by_role("heading", name="Beim Einbringen als eigenständig eingestuft gegenüber:")).to_be_visible()
