"""Das Handy-Menü zeigt den Hauptschritt der Rolle (GP-080, GAST-08): Die Medienregel, die in der
schmalen Leiste den Knopf ausblendet, traf auch den gleichnamigen Knopf im ausgeklappten Menü."""

import pytest
from playwright.sync_api import expect

from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]

HANDY = {'width': 390, 'height': 844}


@pytest.mark.parametrize('js', [True, False])
@pytest.mark.parametrize('gast', [True, False])
def test_gp080_handy_menue_zeigt_den_hauptschritt(seite, live_server, js, gast):
    p = seite(als=None if gast else mitglied_anlegen(), viewport=HANDY, js=js, reduziert=True)
    p.goto(f'{live_server.url}/parlament/')
    p.locator('details.menue > summary').click()
    panel = p.locator('details.menue .panel')
    expect(panel).to_be_visible()
    ziel = 'Mitglied werden' if gast else 'Antrag einbringen'
    expect(panel.locator('a.cta', has_text=ziel)).to_be_visible()
