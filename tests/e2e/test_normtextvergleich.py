"""Archivierte Wortlaute sind am Handy und Desktop lesbar und nativ auswählbar."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.test_textvergleich import text_anlegen

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("sprache,breite,hoehe", [("de", 390, 844), ("en", 1440, 900)])
def test_archivierte_dokumenttexte_nativ_gegenueberstellen(seite, live_server, sichtpruefung, sprache, breite, hoehe):
    alt = text_anlegen("Synthetischer Ausgangstext." + " X" * 12)
    neu = text_anlegen("Synthetischer Vergleichstext." + "Z" * 100, tage=1, parser=2)
    p = seite(sprache=sprache, js=False, dunkel=(sprache == "en"), reduziert=True,
              viewport={"width": breite, "height": hoehe})
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[alt.norm_id]))
    p.locator(f'#dokumenttext-{alt.pk} a[href$="vergleich/"]').press("Enter")
    auswahl = reverse("faktenbasis:textvergleich", args=[alt.pk, neu.pk])
    p.locator(f'a[href="{auswahl}"]').press("Enter")
    expect(p.locator(".fakten-wortlaut").first).to_have_text(alt.text)
    expect(p.locator(".fakten-wortlaut").last).to_have_text(neu.text)
    # Beide Gitterpositionen aus demselben Layout lesen. Bildschirmkoordinaten
    # aus zwei Browseraufrufen können sich durch Scrollen oder den Aufbau verschieben.
    erste, zweite = p.locator(".fakten-textvergleich section").evaluate_all(
        "karten => karten.map(karte => ({x: karte.offsetLeft, y: karte.offsetTop}))",
    )
    if sprache == "de":
        assert erste["y"] < zweite["y"]
    else:
        assert erste["x"] < zweite["x"] and erste["y"] == zweite["y"]
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"normtextvergleich-ohne-js-{sprache}.png"), full_page=True)
