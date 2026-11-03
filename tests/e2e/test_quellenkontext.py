"""Tatsächlich übergebenes amtliches Material, Grenzen und Altbestand ohne JavaScript."""

import json

import pytest
from playwright.sync_api import expect

from faktenbasis import volltext
from faktenbasis.test_volltext import norm, xml  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import KIAuftrag, Zweck
from ki.warteschlange import auftrag_ausfuehren, einreihen
from parameter.models import Parameter
from verfahren.models import AntragsFassung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell-js", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_amtlicher_ausschnitt_und_legacy_bleiben_getrennt(
    seite, live_server, sichtpruefung, settings, monkeypatch, ordnung, norm, xml,  # noqa: F811
    kennung, viewport, js, dunkel, sprache,
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    roh = json.dumps({"normen": [], "hinweis": "Testantwort", "unsicherheit": "hoch"})
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(roh, "attrappe-quellen", 10, 20))
    volltext.importieren(norm)
    Parameter.objects.update_or_create(schluessel="quellenkontext-textzeichen", defaults={"wert": "40"})
    m = mitglied_anlegen("quellen-browser")
    antrag = antrag_einbringen(m, norm.kurztitel, ANTRAG["wortlaut"], "", ordnung)
    alt = KIAuftrag.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=antrag, angefordert_von=m, fassung_nummer=1)
    assert auftrag_ausfuehren(alt.pk) == "erledigt"
    AntragsFassung.objects.create(antrag=antrag, nummer=2, wortlaut="Zweite öffentliche Textfassung")
    job = einreihen(Zweck.RECHTSBEZUG, antrag, m)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True, sprache=sprache)
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/#zone-einschaetzung")
    englisch = sprache == "en"
    karte = p.locator("#rechtsbezug")
    jetzt = karte.locator(":scope > .ki-quellenstand")
    jetzt.locator(":scope > summary").press("Enter")
    expect(jetzt).to_contain_text("Official document excerpt" if englisch else "Amtlicher Dokumenttext als Ausschnitt")
    expect(jetzt).to_contain_text("truncated" if englisch else "gekürzt")
    expect(jetzt).to_contain_text(job.quellenkontext["sha256"])
    expect(jetzt.get_by_role("link", name=norm.ris_id, exact=False)).to_have_attribute("href", norm.quelle)
    expect(jetzt).to_contain_text("does not establish legal relevance" if englisch else "beweist keine rechtliche Betroffenheit")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"quellenkontext-{kennung}.png"), full_page=True)
    historie = karte.locator(".ki-historie > details").first
    historie.locator(":scope > summary").press("Enter")
    historie.locator(".ki-quellenstand > summary").press("Enter")
    expect(historie).to_contain_text("not assigned retroactively" if englisch else "nicht nachträglich zugeordnet")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"quellenkontext-altbestand-{kennung}.png"), full_page=True)
