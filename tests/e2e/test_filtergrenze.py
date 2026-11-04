"""Die echte Profilgrenze bleibt im Overlay sichtbar, auch ohne JavaScript."""

import pytest
from playwright.sync_api import expect

from parameter.models import Parameter
from verfahren.models import FilterProfil
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_grenze_aus_dem_register_ist_sichtbar(
    seite, live_server, sichtpruefung, kennung, viewport, js, dunkel, sprache,
):
    Parameter.objects.update_or_create(schluessel="weicherfilter-profile-hoechstzahl", defaults={"wert": "2"})
    m = mitglied_anlegen()
    for i in range(2):
        FilterProfil.objects.create(mitglied=m, name=f"Profil {i}", aktiv=i == 0)
    p = seite(als=m, viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(f"{live_server.url}/parlament/")
    p.locator("#feld-filter .regler-klappe > summary").click()
    grenze = p.get_by_text("2 of 2 — delete or overwrite one" if sprache == "en"
                          else "2 von 2 — eine löschen oder überschreiben", exact=True)
    expect(grenze).to_be_visible()
    grenze.scroll_into_view_if_needed()
    p.screenshot(path=str(sichtpruefung / f"filtergrenze-zwei-{kennung}.png"), full_page=True)
    Parameter.objects.filter(schluessel="weicherfilter-profile-hoechstzahl").update(wert="0")
    p.reload()
    p.locator("#feld-filter .regler-klappe > summary").click()
    gesperrt = p.get_by_text("New configurations are disabled." if sprache == "en"
                            else "Neue Konfigurationen sind gesperrt.", exact=True)
    expect(gesperrt).to_be_visible()
    gesperrt.scroll_into_view_if_needed()
    assert m.filterprofile.count() == 2
    p.screenshot(path=str(sichtpruefung / f"filtergrenze-null-{kennung}.png"), full_page=True)
