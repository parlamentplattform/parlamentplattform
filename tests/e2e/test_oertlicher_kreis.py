"""Der örtliche Teilnehmerkreis ist sichtbar und der native Schreibweg nutzbar."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from verfahren.test_oertliche_teilnahme import _einbringen, menschen  # noqa: F401
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("js,handy,sprache", [(False, True, "de-AT"), (True, False, "en")])
def test_tatstaechliche_teilnahme_ueber_native_formulare(
    seite, live_server, client, menschen, ordnung, sichtpruefung, js, handy, sprache,  # noqa: F811
):
    leute, _, _ = menschen
    a = _einbringen(client, leute["autor"])
    url = live_server.url + reverse("verfahren:antrag", args=[a.pk])
    aktion = reverse("verfahren:unterstuetzen", args=[a.pk])
    viewport = {"width": 390, "height": 844} if handy else {"width": 1440, "height": 900}
    name = "handy-ohne-js-de" if handy else "desktop-js-en"
    for personalie in ("fremd", "ort"):
        p = seite(als=leute[personalie], js=js, viewport=viewport, sprache=sprache, reduziert=True, dunkel=handy)
        p.goto(url)
        kreis = p.locator("#teilnehmerkreis")
        expect(kreis).to_be_visible()
        expect(kreis).to_contain_text("gemeinde:40510")
        assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
        formular = p.locator(f'form[action="{aktion}"]')
        if personalie == "fremd":
            expect(formular).to_have_count(0)
        else:
            formular.get_by_role("button").press("Enter")
            assert a.unterstuetzungen.get().mitglied_id == leute[personalie].pk
        p.screenshot(path=str(sichtpruefung / f"teilnehmerkreis-{name}-{personalie}.png"), full_page=True)
