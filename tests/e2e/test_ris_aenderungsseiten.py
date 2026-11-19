"""Nachlese einer ausdrücklich übernommenen RIS-Seite ohne JavaScript."""

from datetime import timedelta

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.ris_historie import importieren
from faktenbasis.test_ris_historie import KENNUNG, TAG, URL, norm_anlegen, original

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("sprache,viewport,titel,umfang", [
    ("de", {"width": 390, "height": 844}, "Archivierte RIS-Änderungsseiten", "1 Dokument auf dieser Seite, 11 Treffer laut RIS."),
    ("en", {"width": 1440, "height": 900}, "Archived RIS change pages", "1 document on this page, 11 results reported by RIS."),
])
def test_ris_aenderungsseite_nativ_lesbar(seite, live_server, sichtpruefung, sprache, viewport, titel, umfang):
    stand = importieren(TAG, 2, original())
    norm = norm_anlegen(TAG - timedelta(days=1))
    page = seite(sprache=sprache, viewport=viewport, js=False, dunkel=sprache == "en", reduziert=True)
    page.goto(live_server.url + reverse("faktenbasis:index"))
    page.get_by_role("link", name=titel, exact=True).press("Enter")
    expect(page.get_by_role("heading", name=titel, exact=True)).to_be_visible()
    expect(page.get_by_text(umfang, exact=True)).to_be_visible()
    expect(page.get_by_role("link", name=KENNUNG)).to_have_attribute("href", URL)
    expect(page.get_by_text(stand.original_sha256, exact=True)).to_be_visible()
    assert "synthetischer Originalinhalt" not in page.locator("main").inner_text()
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(sichtpruefung / f"ris-aenderungsseite-ohne-js-{sprache}.png"), full_page=True)
    liste = page.get_by_role("link", name=f"‹ {titel}", exact=True)
    page.get_by_role("article").get_by_role("heading").get_by_role("link").press("Enter")
    expect(page.get_by_text(umfang, exact=True)).to_be_visible()
    expect(page.get_by_text(stand.original_sha256, exact=True)).to_be_visible()
    expect(liste).to_be_visible()
    lokal = "Jüngster gespeicherter Stichtag" if sprache == "de" else "Latest stored reference date"
    normlink = page.get_by_role("link", name=lokal)
    expect(normlink).to_have_attribute("href", reverse("faktenbasis:norm", args=[norm.pk]))
    assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
    page.screenshot(path=str(sichtpruefung / f"ris-aenderungsabgleich-ohne-js-{sprache}.png"), full_page=True)
    normlink.press("Enter")
    expect(page.get_by_role("heading", name="Testnorm")).to_be_visible()

    page.goto(live_server.url + reverse("parameter:regeln") + "#regel-ris_historie")
    regel = page.locator("#regel-ris_historie")
    expect(regel.get_by_role("heading", name=titel, exact=True)).to_be_visible()
    fassung = "Fassung 7" if sprache == "de" else "Version 7"
    originalpruefung = "Bei der Originalprüfung" if sprache == "de" else "To verify original files"
    expect(regel.get_by_text(fassung, exact=False)).to_be_visible()
    expect(regel.get_by_text(originalpruefung, exact=False)).to_be_visible()
    assert regel.evaluate("r => r.scrollWidth <= r.clientWidth")
    assert regel.evaluate("r => r.getBoundingClientRect().top >= document.querySelector('.leiste').getBoundingClientRect().bottom")
    page.screenshot(path=str(sichtpruefung / f"ris-originalpruefung-regel-{sprache}.png"))
