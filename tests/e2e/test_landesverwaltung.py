"""Landesquelle ausdrücklich wählen; ohne JavaScript und auf dem Handy sichtbar."""

import pytest
from playwright.sync_api import expect

from faktenbasis import landesrecht
from faktenbasis.models import Norm, RisImport
from faktenbasis.test_landesrecht import NUMMER, STAND
from faktenbasis.test_landesverwaltung import antwort
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_land_ist_ausdruecklich_waehlbar_und_als_herkunft_sichtbar(
    seite, live_server, sichtpruefung, monkeypatch, kennung, viewport, js, dunkel, sprache,
):
    m = mitglied_anlegen()
    m.ist_admin = True
    m.save(update_fields=["ist_admin"])
    calls = []
    def holen(nummer, stand, bundesland, *, seite):
        calls.append((nummer, stand, bundesland, seite))
        return landesrecht.antwort_parsen(antwort(bundesland), nummer, bundesland, seite=seite)
    monkeypatch.setattr(landesrecht, "abrufen", holen)
    p = seite(als=m, viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(f"{live_server.url}/verwaltung/faktenbasis/")
    p.locator("#id_quelle").select_option("land")
    p.locator("#id_gesetzesnummer").fill(NUMMER)
    p.locator("#id_stand").fill(STAND.isoformat())
    p.locator("#id_seite").fill("2")
    p.locator("form.formular button[type=submit]").click()
    expect(p.locator("#id_bundesland_error")).to_be_visible()
    assert not calls and not RisImport.objects.exists()
    p.locator("#id_bundesland").select_option("Oberoesterreich")
    expect(p.locator("#id_quelle")).to_be_visible()
    expect(p.locator("#id_bundesland")).to_be_visible()
    p.screenshot(path=str(sichtpruefung / f"landesquelle-formular-{kennung}.png"), full_page=True)
    p.locator("form.formular button[type=submit]").click()
    assert calls == [(NUMMER, STAND, "Oberoesterreich", 2)]
    n = Norm.objects.get()
    p.locator(f'a[href="/zukunftswerkstatt/faktenbasis/norm/{n.pk}/"]').click()
    landesquelle = p.locator(".karte").first.locator("p").first
    expect(landesquelle).to_be_visible()
    expect(landesquelle).to_contain_text("Oberösterreich")
    herkunft = p.locator("details").filter(has=p.locator(
        f'a[href="/zukunftswerkstatt/faktenbasis/import/{n.importlauf_id}/antwort.json"]',
    ))
    herkunft.locator("summary").click()
    expect(herkunft.get_by_text("RIS page: 2" if sprache == "en" else "RIS-Seite: 2", exact=True)).to_be_visible()
    assert len(calls) == 1 and p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"landesquelle-herkunft-{kennung}.png"), full_page=True)
