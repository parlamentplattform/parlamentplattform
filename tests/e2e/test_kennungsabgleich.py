"""Amtliche Kennung getrennt vom ungeprüften Modelltitel; ohne JavaScript nutzbar."""

import json

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.test_volltext import norm  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import Zweck
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_damalige_kennung_bestaetigt_keine_modellbehauptung(seite, live_server, sichtpruefung,
    settings, monkeypatch, norm, ordnung, kennung, viewport, js, dunkel, sprache):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    n = {"titel": "Ungeprüfter Modelltitel", "kennung": norm.ris_id, "ebene": "Bund", "aenderung": "beruehrt", "begruendung": "Ungeprüfte Modellbegründung"}
    roh = json.dumps({"normen": [n, {**n, "kennung": "NOR99999999"}], "hinweis": "Technische Prüfantwort", "unsicherheit": "hoch"})
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(roh, "test-kennung", 10, 20))
    m = mitglied_anlegen("kennungs-browser")
    a = antrag_einbringen(m, norm.kurztitel, ANTRAG["wortlaut"], "", ordnung)
    j = einreihen(Zweck.RECHTSBEZUG, a, m)
    assert auftrag_ausfuehren(j.pk) == "erledigt"
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(f"{live_server.url}/antrag/{a.pk}/#zone-einschaetzung")
    karte = p.locator("#rechtsbezug")
    z = karte.locator(":scope > .normen > li > .kennungsabgleich")
    expect(z).to_have_count(1)
    expect(z).to_contain_text("Identifier in the original source snapshot:" if sprache == "en" else "Kennung im damaligen Quellenstand:")
    expect(z.get_by_role("link")).to_have_attribute("href", reverse("faktenbasis:norm", args=[norm.pk]))
    expect(z).to_contain_text(norm.kurztitel)
    expect(z).to_contain_text("does not confirm" if sprache == "en" else "nicht bestätigt")
    expect(karte).to_contain_text("not verified" if sprache == "en" else "nicht verifiziert")
    expect(karte).to_contain_text("NOR99999999")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"kennungsabgleich-{kennung}.png"), full_page=True)
