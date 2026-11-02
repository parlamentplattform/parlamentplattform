"""Neue wartende Vorschlagsfassung und altes Ergebnis koexistieren lesbar."""

import pytest
from playwright.sync_api import expect

from gremien.models import Entwurf, EntwurfsFassung
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import KIAuftrag, Zweck
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import antrag_einbringen
from verfahren.test_rechtsbezug_anzeige import JSON_ANTWORT
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel", [
    ("desktop-hell-js", {"width": 1440, "height": 900}, True, False),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False),
    ("handy-dunkel-js", {"width": 390, "height": 844}, True, True),
])
def test_textquelle_wartestatus_und_fruehere_antwort_lesen(
    seite, live_server, sichtpruefung, settings, monkeypatch, ordnung, kennung, viewport, js, dunkel,  # noqa: F811
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(JSON_ANTWORT, "attrappe-1", 10, 20))
    m = mitglied_anlegen("kontext-browser")
    antrag = antrag_einbringen(m, ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    alt = einreihen(Zweck.RECHTSBEZUG, antrag, m)
    auftrag_ausfuehren(alt.pk)
    antrag.phase = "beratung"
    antrag.save(update_fields=["phase"])
    e = Entwurf.objects.create(antrag=antrag)
    EntwurfsFassung.objects.create(
        entwurf=e, nummer=1, wortlaut="Überarbeiteter öffentlicher Wortlaut des Expertenrats.", verfasst_von=m,
    )
    assert e.einreichen()
    neu = KIAuftrag.objects.get(antrag=antrag, quellenart="vorschlag")
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True)
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/#zone-einschaetzung")
    bereich = p.locator("#rechtsbezug")
    expect(bereich.get_by_text("Vorschlag des Expertenrats · Fassung 1", exact=True)).to_be_visible()
    expect(bereich.get_by_text("Die Zukunftswerkstatt prüft, welche Gesetze betroffen sind.", exact=False)).to_be_visible()
    bereich.locator(".ki-historie > details > summary").first.press("Enter")
    expect(bereich.locator(".ki-historie .ki-textstand")).to_contain_text(alt.kontext["sha256"])
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    p.screenshot(path=str(sichtpruefung / f"textkontext-wartet-{kennung}.png"), full_page=True)
    assert auftrag_ausfuehren(neu.pk) == "erledigt"
    p.reload()
    expect(bereich.locator(":scope > .ki-textstand")).to_contain_text("Vorschlag des Expertenrats")
    expect(bereich.locator(":scope > .ki-textstand")).to_contain_text(neu.kontext["sha256"])
    bereich.locator(":scope > .ki-textstand summary").press("Enter")
    expect(bereich.locator(":scope > .ki-textstand pre")).to_contain_text("Überarbeiteter öffentlicher Wortlaut")
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.evaluate("window.scrollTo({top:0,behavior:'instant'})")
    p.screenshot(path=str(sichtpruefung / f"textkontext-erledigt-{kennung}.png"), full_page=True)
