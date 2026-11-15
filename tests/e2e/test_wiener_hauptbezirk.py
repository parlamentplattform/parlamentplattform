"""Privaten Hauptwohnsitzbezirk auswählen und beim Einbringen wiederfinden."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from mitglieder.models import Gemeinde
from verfahren.test_teilnahme_fundament import mit_ort
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("sprache,breite,hoehe,speichern,bezirksoption", [
    ("de", 390, 844, "Speichern", "Mein Bezirk (Wien 22., Donaustadt)"),
    ("en", 1440, 900, "Save", "My district (Wien 22., Donaustadt)"),
])
def test_hauptbezirk_aus_dem_profil_ist_im_antragsformular_verfuegbar(
    seite, live_server, sichtpruefung, ordnung, sprache, breite, hoehe, speichern, bezirksoption,  # noqa: F811
):
    wien, _ = Gemeinde.objects.get_or_create(
        kennziffer="90001", defaults={"name": "Wien", "bezirk": "Wien", "bundesland": "wien"},
    )
    m = mit_ort("wiener", wien)
    p = seite(als=m, sprache=sprache, js=False, dunkel=sprache == "en", reduziert=True,
              viewport={"width": breite, "height": hoehe})
    einbringen = live_server.url + reverse("verfahren:einbringen")
    profil = reverse("mitglieder:profil")

    p.goto(einbringen)
    expect(p.locator('input[name="ebene"][value="bezirk"]')).to_have_count(0)
    p.locator(f'a[href="{profil}#wohnsitz"]').press("Enter")
    wohnsitz = p.locator("#wohnsitz")
    wohnsitz.locator("#id_wiener_bezirk").select_option("922")
    wohnsitz.get_by_role("button", name=speichern, exact=True).press("Enter")
    expect(wohnsitz.locator("#id_wiener_bezirk")).to_have_value("922")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    wohnsitz.screenshot(path=str(sichtpruefung / f"wiener-hauptbezirk-profil-ohne-js-{sprache}.png"))

    p.goto(einbringen)
    p.get_by_role("radio", name=bezirksoption, exact=True).check()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"wiener-hauptbezirk-einbringen-ohne-js-{sprache}.png"), full_page=True)
