"""Herkunft bleibt von Zuständigkeit getrennt, historische Quellenfassung1 erhalten."""

import json

import pytest
from playwright.sync_api import expect

from faktenbasis.kontext import festhalten as quellen_festhalten
from faktenbasis.test_landesxml import landnorm, textquelle  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from faktenbasis.volltext import importieren
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.kontext import festhalten as text_festhalten
from ki.models import KIAuftrag, Zweck
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import AntragsFassung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_landherkunft_und_alter_quellenvertrag(seite, live_server, sichtpruefung, settings, monkeypatch,
    landnorm, textquelle, ordnung, kennung, viewport, js, dunkel, sprache):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    def frage(self, prompt, text):
        return Antwort(json.dumps({"normen": [{"titel": "Ungeprüfte Modellbehauptung", "kennung": landnorm.ris_id,
            "ebene": "Land", "aenderung": "beruehrt", "begruendung": "Ungeprüfte Deutung"}],
            "hinweis": "Keine bestätigte Zuständigkeit", "unsicherheit": "hoch"}), "test-land", 10, 20)
    monkeypatch.setattr(AttrappenAnbieter, "frage", frage)
    importieren(landnorm)
    m = mitglied_anlegen("landeskontext-browser")
    a = antrag_einbringen(m, landnorm.kurztitel, ANTRAG["wortlaut"], "", ordnung)
    text = text_festhalten(a)
    alt = KIAuftrag.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=m, fassung_nummer=1,
        kontext=text, quellenkontext=quellen_festhalten([], hoechstzahl=3, textzeichen=30,
            text_sha256=text["sha256"], fassung=1))
    assert auftrag_ausfuehren(alt.pk) == "erledigt"
    AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut="Zweite synthetische Textfassung")
    job = einreihen(Zweck.RECHTSBEZUG, a, m)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(f"{live_server.url}/antrag/{a.pk}/#zone-einschaetzung")
    englisch = sprache == "en"
    karte = p.locator("#rechtsbezug")
    jetzt = karte.locator(":scope > .ki-quellenstand")
    jetzt.locator(":scope > summary").press("Enter")
    expect(jetzt.locator(".quellenumfang")).to_contain_text("without geographical jurisdiction checks" if englisch else "ohne räumliche Zuständigkeitsprüfung")
    expect(jetzt.locator(".quellenherkunft")).to_contain_text("Oberösterreich")
    expect(jetzt).to_contain_text("Official document excerpt" if englisch else "Amtlicher Dokumenttext als Ausschnitt")
    expect(karte).to_contain_text("rechtsbezug-v3")
    expect(karte.locator(":scope > .normen .kennungsabgleich")).to_contain_text("Oberösterreich")
    historie = karte.locator(".ki-historie > details").first
    historie.locator(":scope > summary").press("Enter")
    historie.locator(".ki-quellenstand > summary").press("Enter")
    expect(historie).to_contain_text("rechtsbezug-v2")
    expect(historie.locator(".quellenumfang")).to_have_count(0)
    expect(historie.locator(".quellenherkunft")).to_have_count(0)
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"landeskontext-{kennung}.png"), full_page=True)
