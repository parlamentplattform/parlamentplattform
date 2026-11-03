"""Spätere lokale Texte neben unverändertem alten Quellenrahmen, ohne Neuberechnung."""

import json

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis import volltext
from faktenbasis.test_volltext import norm, xml  # noqa: F401
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
def test_spaetere_quelle_ohne_umschreiben_des_alten_rahmens(
    seite, live_server, sichtpruefung, settings, monkeypatch, ordnung, norm, xml,  # noqa: F811
    kennung, viewport, js, dunkel, sprache,
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    antwort = json.dumps({"normen": [], "hinweis": "Technische Testantwort", "unsicherheit": "hoch"})
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(antwort, "attrappe-nachlese", 10, 20))
    m = mitglied_anlegen("nachlese-browser")
    antrag = antrag_einbringen(m, norm.kurztitel, ANTRAG["wortlaut"], "", ordnung)
    job = einreihen(Zweck.RECHTSBEZUG, antrag, m)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    checksum = job.quellenkontext["sha256"]
    spaeter = volltext.importieren(norm).inhalt
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/#zone-einschaetzung")
    karte = p.locator("#rechtsbezug")
    abgleich = karte.locator(":scope > .ki-quellenabgleich")
    abgleich.locator(":scope > summary").press("Enter")
    en = sprache == "en"
    expect(abgleich).to_contain_text("does not trigger a model run" if en else "löst keinen Modelllauf aus")
    expect(abgleich).to_contain_text("currency of applicable law" if en else "Aktualität des geltenden Rechts")
    expect(abgleich.get_by_role("link", name="Later document text snapshot" if en else "Späterer Dokumenttextstand", exact=False)).to_have_attribute(
        "href", reverse("faktenbasis:textxml", args=[spaeter.pk]),
    )
    alt = karte.locator(":scope > .ki-quellenstand")
    alt.locator(":scope > summary").press("Enter")
    expect(alt).to_contain_text(checksum)
    expect(alt).to_contain_text("Metadata only" if en else "Nur Metadaten")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.evaluate("scrollTo({top:0,left:0,behavior:'instant'})")
    p.screenshot(path=str(sichtpruefung / f"quellennachlese-{kennung}.png"), full_page=True)
