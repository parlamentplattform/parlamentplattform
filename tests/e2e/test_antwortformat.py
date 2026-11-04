"""Formwarnung, Originalnachlese und historische Antworten ohne JavaScript."""

import json

import pytest
from playwright.sync_api import expect

from gremien.models import Entwurf, EntwurfsFassung
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import KIAuftrag, Zweck
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell-js", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_formabweichung_und_historischer_befund_bleiben_nachlesbar(
    seite, live_server, sichtpruefung, settings, monkeypatch, ordnung, kennung, viewport, js, dunkel, sprache,  # noqa: F811
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    roh = json.dumps({"normen": [{"titel": "Testnorm", "aenderung": "unbekannt"}], "unsicherheit": "extrem"})
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(roh, "attrappe-format", 10, 20))
    m = mitglied_anlegen("format-browser")
    antrag = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    alt = einreihen(Zweck.RECHTSBEZUG, antrag, m)
    auftrag_ausfuehren(alt.pk)
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True, sprache=sprache)
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/#zone-einschaetzung")
    karte = p.locator("#rechtsbezug")
    englisch = sprache == "en"
    warnung = "The model response differs" if englisch else "Die Modellantwort weicht"
    expect(karte.get_by_text(warnung, exact=False)).to_be_visible()
    expect(karte.get_by_text("unclear" if englisch else "unklar", exact=True)).to_be_visible()
    karte.locator(":scope > .ki-formatstand > summary").press("Enter")
    expect(karte.locator(":scope > .ki-formatstand")).to_contain_text("Current format check" if englisch else "Aktuelle Formprüfung")
    link = karte.get_by_role("link", name="Download response schema" if englisch else "Antwortschema herunterladen")
    with p.expect_download() as download:
        link.click()
    assert download.value.suggested_filename == "rechtsbezug-schema-v1.json"
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"antwortformat-warnung-{kennung}.png"), full_page=True)
    antrag.phase = "beratung"
    antrag.save(update_fields=["phase"])
    entwurf = Entwurf.objects.create(antrag=antrag)
    EntwurfsFassung.objects.create(entwurf=entwurf, nummer=1, wortlaut="Geänderter Testwortlaut.", verfasst_von=m)
    assert entwurf.einreichen()
    roh = json.dumps({"normen": [], "judikatur": {"text": "Ohne vollständige Belege offen."},
        "exekutive": {"text": "Vollzugsbedarf bleibt unbestimmt."}, "personal": [], "unsicherheit": "hoch", "quellen": []})
    neu = KIAuftrag.objects.get(antrag=antrag, quellenart="vorschlag")
    assert neu.zweck == Zweck.RECHTSFOLGEN and alt.zweck == Zweck.RECHTSBEZUG
    assert auftrag_ausfuehren(neu.pk) == "erledigt"
    p.reload()
    expect(karte.get_by_text("empty list of provisions" if englisch else "leere Normenliste", exact=False)).to_be_visible()
    karte.locator(".ki-historie > details > summary").first.press("Enter")
    expect(karte.locator(".ki-historie").get_by_text(warnung, exact=False)).to_be_visible()
    expect(karte.locator(".ki-historie").get_by_text("unclear" if englisch else "unklar", exact=True)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"antwortformat-historie-{kennung}.png"), full_page=True)
