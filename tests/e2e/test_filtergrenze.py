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


@pytest.mark.parametrize('breite', [390, 320])
def test_gp061_regler_ohne_javascript_wieder_schliessen(seite, live_server, breite):
    """GP-061 (ZB-04): Ohne JavaScript ließ sich das geöffnete Regler-Overlay nicht mehr schließen;
    es lag über dem Auslöser und der Filterliste."""
    m = mitglied_anlegen()
    FilterProfil.objects.create(mitglied=m, name='Profil', aktiv=True)
    p = seite(als=m, viewport={'width': breite, 'height': 844}, js=False, reduziert=True)
    p.goto(f'{live_server.url}/parlament/')
    klappe = p.locator('#feld-filter details.regler-klappe')
    klappe.locator('> summary').click()
    expect(klappe).to_have_attribute('open', '')
    schliessen = klappe.get_by_role('link', name='Schließen')
    expect(schliessen).to_be_visible()
    schliessen.click()
    p.wait_for_load_state()
    klappe = p.locator('#feld-filter details.regler-klappe')
    expect(klappe).not_to_have_attribute('open', '')
    p.locator('#filter-liste').click(trial=True, timeout=3000)


def test_gp061_mit_javascript_nur_ein_schliessen(seite, live_server):
    m = mitglied_anlegen()
    FilterProfil.objects.create(mitglied=m, name='Profil', aktiv=True)
    p = seite(als=m, viewport={'width': 390, 'height': 844}, js=True, reduziert=True)
    p.goto(f'{live_server.url}/parlament/')
    klappe = p.locator('#feld-filter details.regler-klappe')
    klappe.locator('> summary').click()
    expect(klappe.get_by_role('button', name='Schließen')).to_be_visible()
    expect(klappe.get_by_role('link', name='Schließen')).to_be_hidden()
