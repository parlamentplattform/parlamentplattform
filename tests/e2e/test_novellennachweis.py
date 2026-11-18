"""Amtliche Fundstelle sichtbar am konkreten Quellenstand, ohne externe Navigation."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.test_novellenfundstelle import landesnorm_anlegen, normstaende_anlegen
from faktenbasis.testhilfe import abrufuhr  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("handy,sprache", [(True, "de-AT"), (False, "en")])
def test_novelle_ist_sichtbar_und_auch_ohne_js_nachlesbar(
    seite, live_server, sichtpruefung, monkeypatch, abrufuhr, handy, sprache,  # noqa: F811
):
    alt, neu = normstaende_anlegen(monkeypatch)
    p = seite(js=False, dunkel=handy, sprache=sprache, reduziert=True,
              viewport={"width": 390, "height": 844} if handy else None)
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[alt.pk]))
    expect(p.locator("#novellenfundstelle")).to_have_count(0)
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[neu.pk]))
    bereich = p.locator("section[aria-labelledby='novellenfundstelle']")
    titel = "Novelle laut RIS-Metadaten" if handy else "Amendment named in RIS metadata"
    expect(bereich.get_by_role("heading", name=titel)).to_be_visible()
    expect(bereich.get_by_role("link", name="BGBl. I Nr. 70/2024")).to_have_attribute(
        "href", "https://www.ris.bka.gv.at/eli/bgbl/I/2024/70",
    )
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    kennung = "handy-de" if handy else "desktop-en"
    p.screenshot(path=str(sichtpruefung / f"novellenfundstelle-{kennung}.png"), full_page=True)


def test_landeskundmachung_als_fundstelle_anzeigen(seite, live_server, sichtpruefung, monkeypatch, abrufuhr):  # noqa: F811
    norm = landesnorm_anlegen(monkeypatch)
    p = seite(js=False, dunkel=True, sprache="en", reduziert=True, viewport={"width": 390, "height": 844})
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[norm.pk]))
    bereich = p.locator("section[aria-labelledby='novellenfundstelle']")
    expect(bereich.get_by_text("LGBl. Nr. 62/2026", exact=True)).to_be_visible()
    expect(bereich.get_by_text("The gazette publication date needed for a direct link is missing.")).to_be_visible()
    expect(bereich.get_by_role("link", name="LGBl. Nr. 62/2026")).to_have_count(0)
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / "landesnovelle-ooe-handy-en.png"), full_page=True)
