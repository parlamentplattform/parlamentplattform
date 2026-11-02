"""Die Einführung führt zur echten Suche und nennt die geltenden Fristen."""

import pytest
from django.core.management import call_command
from playwright.sync_api import expect

from verfahren.models import Verfahrensordnung
from verfahren.test_views_aktionen import REGELN, mitglied_anlegen

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel", [
    ("desktop-hell-js", {"width": 1440, "height": 900}, True, False),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False),
    ("handy-dunkel-js", {"width": 390, "height": 844}, True, True),
])
def test_einfuehrung_suche_und_fristen(seite, live_server, sichtpruefung, kennung, viewport, js, dunkel):
    call_command("kategorien_laden", verbosity=0)
    person = mitglied_anlegen()
    Verfahrensordnung.objects.create(policy_id="einfuehrung", version=1, aktiv=True,
                                    regeln={**REGELN, "beratung_tage": 35, "abstimmung_tage": 28})
    p = seite(als=person, js=js, dunkel=dunkel, viewport=viewport, reduziert=True)
    p.goto(f"{live_server.url}/einfuehrung/1/")
    p.get_by_role("link", name="Favoriten-Feld des Parlaments", exact=True).click()
    expect(p.locator("#feld-favoriten input[type=search]")).to_be_visible()
    p.goto(f"{live_server.url}/einfuehrung/2/")
    expect(p.get_by_text("Die Dauer steht bei jeder Abstimmung", exact=False)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.screenshot(path=str(sichtpruefung / f"einfuehrung-stimmrecht-{kennung}.png"), full_page=True)
    p.get_by_role("link", name="Weiter: Antrag einbringen", exact=False).click()
    expect(p.get_by_text("35 Tage Beratung und 28 Tage Abstimmung", exact=False)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.screenshot(path=str(sichtpruefung / f"einfuehrung-fristen-{kennung}.png"), full_page=True)
