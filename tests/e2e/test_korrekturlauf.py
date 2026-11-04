"""Explizite Nachrechnung ohne JS; Original und Beanstandung bleiben sichtbar."""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone
from playwright.sync_api import expect

from gremien.models import Gremium, Rolle
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import KIAuftrag, Zweck
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import Beanstandung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_nachrechnung_explizit_anfordern_und_nachlesen(seite, live_server, sichtpruefung,
    settings, monkeypatch, ordnung, kennung, viewport, js, dunkel, sprache):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    antwort = json.dumps({"normen": [], "hinweis": "Technische Prüfantwort ohne Rechtsurteil", "unsicherheit": "hoch"})
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(antwort, "test-nachrechnung", 10, 20))
    m = mitglied_anlegen("korrektur-browser")
    a = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    Rolle.objects.create(mitglied=m, gremium=Gremium.EXPERTENRAT_1, antrag=a,
        endet_am=timezone.localdate()+timedelta(days=30), bestaetigt=True)
    alt = einreihen(Zweck.RECHTSBEZUG, a, m)
    assert auftrag_ausfuehren(alt.pk) == "erledigt"
    alt.refresh_from_db()
    b = Beanstandung.objects.create(antrag=a, lauf=alt.lauf, mitglied=m, text="Dieser Quellenbezug bleibt für mich ungeklärt.")
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True, als=m)
    p.goto(f"{live_server.url}/antrag/{a.pk}/#zone-einschaetzung")
    en = sprache == "en"
    p.get_by_role("button", name="Request recalculation" if en else "Nachrechnung anfordern", exact=True).click()
    expect(p.locator(f"#beanstandung-{b.pk}")).to_contain_text("queue" if en else "Warteschlange")
    j = KIAuftrag.objects.get(beanstandung=b)
    assert j.versuche == 0
    assert auftrag_ausfuehren(j.pk) == "erledigt"
    p.reload()
    karte = p.locator(f"#beanstandung-{b.pk}")
    karte.get_by_text("Read the recalculation response" if en else "Antwort der Nachrechnung lesen", exact=False).click()
    expect(karte).to_contain_text("Original and note remain unchanged" if en else "Original und Vermerk bleiben unverändert")
    expect(karte).to_contain_text("Technische Prüfantwort ohne Rechtsurteil")
    karte.get_by_text("Read the correction context" if en else "Korrekturkontext nachlesen", exact=True).click()
    expect(karte.get_by_role("link", name="Download the complete record from the motion archive" if en else "Vollständigen Nachweis im Antragsarchiv herunterladen")).to_have_attribute("href", reverse("verfahren:archiv_export", kwargs={"pk":a.pk,"art":"json"}))
    b.refresh_from_db()
    assert b.erledigt_am is None
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"korrekturlauf-{kennung}.png"), full_page=True)
