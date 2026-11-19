"""Sitzungsunterlagen sind ohne JavaScript veröffentlich- und auffindbar."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect

from mandatare.models import Sitzung
from mandatare.test_gemeindesitzungsquellen import BESCHLUSS_URL, ERSTE_URL, aufgabe  # noqa: F401
from mandatare.test_sprechstunden import mandat as gemeindemandat  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("art,adresse,de,en,bild", [
    ("einladung", ERSTE_URL, "Einladung und Tagesordnung", "Meeting notice and agenda", "sitzungsquelle"),
    ("ratsbeschluesse", BESCHLUSS_URL, "Veröffentlichte Ratsbeschlüsse", "Published council decisions", "beschlussquelle"),
])
def test_unterlage_auf_der_oeffentlichen_ortsseite(
    seite, live_server, sichtpruefung, aufgabe, art, adresse, de, en, bild,  # noqa: F811
):
    mandat = aufgabe.mandat
    if art == "ratsbeschluesse":
        aufgabe.frist = timezone.now() - timedelta(days=1)
        aufgabe.save(update_fields=["frist"])
    p = seite(als=mandat.mitglied, viewport={"width": 390, "height": 844}, js=False, reduziert=True)
    p.goto(live_server.url + reverse("mandatare:mein_mandat", args=[mandat.pk]))
    p.get_by_role("link", name="Sitzungsunterlage verlinken", exact=True).press("Enter")
    p.get_by_role("combobox", name="Unterlage").select_option(art)
    p.get_by_role("textbox", name="Öffentlicher HTTPS-Link").fill(adresse)
    p.get_by_role("checkbox", name="Diese Unterlage ist öffentlich und gehört zu dieser Gemeinderatssitzung.").check()
    p.screenshot(path=str(sichtpruefung / f"{bild}-formular-handy-ohne-js-de.png"), full_page=True)
    p.get_by_role("button", name="Link veröffentlichen", exact=True).press("Enter")
    expect(p.get_by_role("link", name=de)).to_have_attribute("href", adresse)

    gast = seite(sprache="en", dunkel=True, js=False, reduziert=True)
    gast.goto(live_server.url + reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer]))
    gast.get_by_role("link", name="Public meeting documents").press("Enter")
    expect(gast.get_by_role("heading", name="Public meeting documents")).to_be_visible()
    expect(gast.get_by_role("link", name=en)).to_have_attribute("href", adresse)
    assert gast.evaluate("document.documentElement.scrollWidth <= innerWidth")
    gast.screenshot(path=str(sichtpruefung / f"{bild}-oeffentlich-ohne-js-en.png"), full_page=True)

    sitzung = Sitzung.objects.create(mandat=mandat, aufgabe=aufgabe)
    live_url = live_server.url + reverse("mandatare:live", args=[mandat.pk]) + f"?sitzung={sitzung.pk}&schreiben=1"
    gast.goto(live_url)
    quellen = gast.locator("#live-unterlagen")
    expect(quellen.get_by_role("heading", name="Public meeting documents")).to_be_visible()
    expect(quellen.get_by_role("link", name=en)).to_have_attribute("href", adresse)
    assert gast.evaluate("document.documentElement.scrollWidth <= innerWidth")
    quellen.screenshot(path=str(sichtpruefung / f"{bild}-live-ohne-js-en.png"))

    p.goto(live_url)
    quellen = p.locator("#live-unterlagen")
    expect(quellen.get_by_role("link", name=de)).to_have_attribute("href", adresse)
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    quellen.screenshot(path=str(sichtpruefung / f"{bild}-live-ohne-js-de.png"))
