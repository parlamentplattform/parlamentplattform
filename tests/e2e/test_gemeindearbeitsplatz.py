"""Eigener Gemeindearbeitsplatz und native Navigation zu laufenden Arbeiten."""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect

from mandatare.test_sprechstunden import mandat as gemeindemandat  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("sprache,breite,hoehe", [("de", 390, 844), ("en", 1440, 900)])
def test_gemeindearbeitsplatz_oeffnen_und_weiterarbeiten(
    seite, live_server, sichtpruefung, gemeindemandat, sprache, breite, hoehe,  # noqa: F811
):
    beginn = timezone.now() + timedelta(days=2)
    gemeindemandat.sprechstunden.create(
        gemeinde=gemeindemandat.gemeinde, beginn=beginn, ende=beginn + timedelta(hours=1),
        treffpunkt="Öffentlicher Treffpunkt",
    )
    p = seite(als=gemeindemandat.mitglied, sprache=sprache, js=False, dunkel=sprache == "en",
              reduziert=True, viewport={"width": breite, "height": hoehe})
    p.goto(live_server.url + reverse("mandatare:mein_mandat", args=[gemeindemandat.pk]))
    name = "Gemeindearbeitsplatz" if sprache == "de" else "Municipal workspace"
    p.get_by_role("link", name=name, exact=True).press("Enter")
    expect(p.get_by_role("heading", name=name, exact=True)).to_be_visible()
    expect(p.get_by_text("Öffentlicher Treffpunkt", exact=False)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"gemeindearbeitsplatz-ohne-js-{sprache}.png"), full_page=True)
    aktion = "Sprechstunde ankündigen" if sprache == "de" else "Announce office hours"
    p.get_by_role("link", name=aktion, exact=True).press("Enter")
    expect(p).to_have_url(live_server.url + reverse("mandatare:sprechstunden", args=[gemeindemandat.pk]))

    p.goto(live_server.url + reverse("mitglieder:profil"))
    karte = p.locator("#datenexport")
    hinweis = "Mandate samt Gemeindearbeit" if sprache == "de" else "mandates and municipal work"
    expect(karte.get_by_text(hinweis, exact=False)).to_be_visible()
    karte.evaluate("el => el.scrollIntoView({block: 'center', behavior: 'instant'})")
    karte.screenshot(path=str(sichtpruefung / f"gemeindearbeit-datenexport-{sprache}.png"))
    with p.expect_download() as herunterladen:
        karte.get_by_role("link").press("Enter")
    download = herunterladen.value
    assert download.suggested_filename == "meine-daten.json"
    daten = json.loads(download.path().read_text(encoding="utf-8"))
    export = daten["mandate"][0]["gemeindearbeit"]
    assert export["gemeindekennziffer"] == gemeindemandat.gemeinde.kennziffer
    assert export["sprechstunden"][0]["treffpunkt"] == "Öffentlicher Treffpunkt"
