"""Einzeltexte, erhaltene Fassungen und Abrufgeschichte ohne JS lesbar."""

import json

import pytest
from playwright.sync_api import expect

from faktenbasis import importieren as meta
from faktenbasis import volltext
from faktenbasis.models import Norm
from faktenbasis.ris import RisFehler, antwort_parsen
from faktenbasis.test_ris import STAND, beispiel
from faktenbasis.test_xmltext import NUMMER, RIS_ID, xml_beispiel
from faktenbasis.testhilfe import abrufuhr  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel", [
    ("desktop-hell-js", {"width": 1440, "height": 900}, True, False),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False),
    ("handy-dunkel-js", {"width": 390, "height": 844}, True, True),
])
def test_amtliche_einzeltexte_und_abrufe_lesen(
    seite, live_server, sichtpruefung, monkeypatch, kennung, viewport, js, dunkel,
):
    daten = json.loads(json.dumps(beispiel()).replace("NOR11000363", RIS_ID))
    daten["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]["Metadaten"]["Bundesrecht"]["BrKons"]["ArtikelParagraphAnlage"] = "Art. 1"
    monkeypatch.setattr(meta, "abrufen", lambda *args: antwort_parsen(daten, NUMMER))
    meta.importieren(NUMMER, STAND)
    norm = Norm.objects.get()
    monkeypatch.setattr(volltext, "abrufen", lambda *args: xml_beispiel())
    lauf = volltext.importieren(norm)
    volltext.importieren(norm)
    def kaputt(*args):
        raise RisFehler("abruf")
    monkeypatch.setattr(volltext, "abrufen", kaputt)
    with pytest.raises(RisFehler):
        volltext.importieren(norm)
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True)
    p.goto(f"{live_server.url}/zukunftswerkstatt/faktenbasis/norm/{norm.pk}/")
    expect(p.get_by_role("heading", name="Amtliche Dokumenttexte", exact=True)).to_be_visible()
    expect(p.get_by_text("Der letzte Dokumenttext-Abruf ist fehlgeschlagen.", exact=False)).to_be_visible()
    expect(p.locator("section .fakten-rohdaten")).to_contain_text("Änderung des B-VG")
    expect(p.get_by_role("link", name="Gespeichertes Original-XML herunterladen")).to_have_attribute(
        "href", f"/zukunftswerkstatt/faktenbasis/text/{lauf.inhalt_id}/original.xml",
    )
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.screenshot(path=str(sichtpruefung / f"dokumenttext-{kennung}.png"), full_page=True)
    p.get_by_text("Dokumenttext-Abrufe nachlesen", exact=True).press("Enter")
    expect(p.get_by_text("Jüngster Abruf zuerst;", exact=False)).to_be_visible()
    expect(p.locator("section li")).to_have_count(3)
    p.screenshot(path=str(sichtpruefung / f"dokumenttext-abrufe-{kennung}.png"), full_page=True)
