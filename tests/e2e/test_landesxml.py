"""Ein einzelner Landeswortlaut ist auch ohne JavaScript mit Herkunft nachlesbar."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis import volltext
from faktenbasis.test_landesxml import landnorm, textquelle  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_landeseinzeltext_mit_original_hash_und_parserfassung(
    seite, live_server, sichtpruefung, landnorm, textquelle, kennung, viewport, js, dunkel, sprache,  # noqa: F811
):
    lauf = volltext.importieren(landnorm)
    p = seite(js=js, dunkel=dunkel, viewport=viewport, sprache=sprache, reduziert=True)
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[landnorm.pk]))
    expect(p.get_by_text("State law · Oberösterreich" if sprache == "en" else "Landesrecht · Oberösterreich", exact=True)).to_be_visible()
    expect(p.locator(".fakten-wortlaut")).to_have_text("Synthetischer Landeswortlaut\nZweite Zeile\tFeld")
    expect(p.get_by_text("New model requests can use existing state sources as context candidates" if sprache == "en" else "Neue Modellaufträge können vorhandene Landesquellen als Kontextkandidaten", exact=False)).to_be_visible()
    expect(p.locator('a[href="' + reverse("faktenbasis:textxml", args=[lauf.inhalt_id]) + '"]')).to_be_visible()
    expect(p.get_by_text(lauf.inhalt.xml_hash, exact=True)).to_be_visible()
    assert len(textquelle[1]) == 1
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"landesdokument-{kennung}.png"), full_page=True)
