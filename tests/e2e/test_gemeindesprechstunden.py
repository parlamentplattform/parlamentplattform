"""Öffentliche Terminbekanntgabe und Absage ohne JavaScript."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from mandatare.test_sprechstunden import _formular, mandat  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def test_termin_veroeffentlichen_und_absagen(seite, live_server, sichtpruefung, mandat):  # noqa: F811
    p = seite(als=mandat.mitglied, viewport={"width": 390, "height": 844}, js=False, reduziert=True)
    p.goto(live_server.url + reverse("mandatare:mein_mandat", args=[mandat.pk]))
    p.get_by_role("link", name="Sprechstunden", exact=True).press("Enter")
    daten = _formular()
    for feld in daten:
        p.locator(f"#id_{feld}").fill(daten[feld])
    p.get_by_role("button", name="Veröffentlichen", exact=True).press("Enter")
    expect(p.get_by_text("Die Sprechstunde ist veröffentlicht.")).to_be_visible()

    ort = live_server.url + reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer])
    gast = seite(sprache="en", dunkel=True, js=False, reduziert=True)
    gast.goto(ort)
    termin = gast.locator("#sprechstunden")
    expect(termin).to_contain_text(daten["treffpunkt"])
    expect(termin.get_by_role("heading", name="Office hours")).to_be_visible()
    gast.screenshot(path=str(sichtpruefung / "sprechstunde-oeffentlich-en.png"), full_page=True)

    p.get_by_role("button", name="Sprechstunde absagen", exact=True).press("Enter")
    expect(p.get_by_text("Abgesagt", exact=True)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / "sprechstunde-absage-handy-ohne-js-de.png"), full_page=True)
    gast.reload()
    expect(termin.get_by_text("Cancelled", exact=True)).to_be_visible()
