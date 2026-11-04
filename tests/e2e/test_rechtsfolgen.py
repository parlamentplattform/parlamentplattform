"""Qualitative Hauptanzeige und genaue Beanstandungsbindung ohne Pflicht-JavaScript."""
# ruff: noqa: F811 -- importierte pytest-Fixture

import pytest
from playwright.sync_api import expect

from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import Zweck
from ki.test_folgenauftraege import ANTWORT
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import Beanstandung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_folgenbericht_zeigt_unbekannte_personalfolgen_und_bindet_beanstandung(
    seite, live_server, sichtpruefung, settings, monkeypatch, ordnung,
    kennung, viewport, js, dunkel, sprache,
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort(ANTWORT, "test-rechtsfolgen", 10, 20))
    m = mitglied_anlegen("rechtsfolgen-browser")
    a = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    job = einreihen(Zweck.RECHTSFOLGEN, a, m, hoechstzeichen=50000)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True, als=m)
    p.goto(f"{live_server.url}/antrag/{a.pk}/#zone-einschaetzung")
    en = sprache == "en"
    karte = p.locator("#rechtsbezug")
    expect(karte).to_contain_text("Effects on the judiciary" if en else "Folgen für Judikatur")
    expect(karte).to_contain_text("Effects on the executive" if en else "Folgen für Exekutive")
    expect(karte).to_contain_text("Unknown values do not mean zero demand" if en else "Unbekannte Werte bedeuten keinen Nullbedarf")
    expect(karte.locator(".ki-folgenabschnitte svg")).to_have_count(0)
    expect(karte.locator(".ki-folgenabschnitte")).to_be_visible()
    expect(p.locator(".kopfkarte")).to_contain_text("test-rechtsfolgen")
    p.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    p.screenshot(path=str(sichtpruefung / f"rechtsfolgen-vor-beanstandung-{kennung}.png"), full_page=True)
    p.locator(".kopfkarte .beanstanden summary").click()
    p.locator("#id_beanstandung").fill("Ich beanstande genau den sichtbaren Folgenbericht.")
    p.get_by_role("button", name="Publish objection" if en else "Beanstandung veröffentlichen", exact=True).click()
    assert Beanstandung.objects.get(antrag=a).lauf_id == job.lauf_id
    # Der Formular-Redirect beginnt mobil wieder im Textreiter. Den tatsächlichen
    # Bedienweg wählen; versteckter DOM-Text ist kein sichtbarer Bildnachweis.
    if js and viewport["width"] < 768:
        p.locator('.zreiter[href="#zone-einschaetzung"]').click()
    expect(p.locator(".kommentar")).to_contain_text("genau den sichtbaren Folgenbericht")
    expect(p.locator(".kommentar").filter(has_text="genau den sichtbaren Folgenbericht")).to_be_visible()
    expect(karte).to_be_visible()
    expect(karte.locator(".ki-folgenabschnitte")).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    p.screenshot(path=str(sichtpruefung / f"rechtsfolgen-{kennung}.png"), full_page=True)
