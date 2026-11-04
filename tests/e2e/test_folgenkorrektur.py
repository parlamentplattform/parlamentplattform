"""Qualitative Folgen-Nachrechnung, mit und ohne JS, ohne erfundene Personalspanne."""
# ruff: noqa: F811 -- importierte pytest-Fixture

from datetime import timedelta

import pytest
from django.utils import timezone
from playwright.sync_api import expect

from gremien.models import Gremium, Rolle
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import KIAuftrag, Zweck
from ki.test_folgenauftraege import ANTWORT
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
def test_qualitative_folgenkorrektur_behaelt_original_und_unbekannte_personalfolgen(
    seite, live_server, sichtpruefung, settings, monkeypatch, ordnung,
    kennung, viewport, js, dunkel, sprache,
):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(ANTWORT, "test-folgen", 10, 20))
    m = mitglied_anlegen("folgenkorrektur-browser")
    a = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    Rolle.objects.create(mitglied=m, gremium=Gremium.EXPERTENRAT_1, antrag=a,
        endet_am=timezone.localdate() + timedelta(days=30), bestaetigt=True)
    alt = einreihen(Zweck.RECHTSFOLGEN, a, m, hoechstzeichen=50000)
    assert auftrag_ausfuehren(alt.pk) == "erledigt"
    alt.refresh_from_db()
    b = Beanstandung.objects.create(antrag=a, lauf=alt.lauf, mitglied=m, text="Die qualitative Folgenbasis ist ungeklärt.")
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True, als=m)
    p.goto(f"{live_server.url}/antrag/{a.pk}/#zone-einschaetzung")
    en = sprache == "en"
    p.get_by_role("button", name="Request recalculation" if en else "Nachrechnung anfordern", exact=True).click()
    job = KIAuftrag.objects.get(beanstandung=b)
    assert job.versuche == 0 and job.korrekturkontext["version"] == 2
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    p.reload()
    karte = p.locator(f"#beanstandung-{b.pk}")
    karte.get_by_text("Read the recalculation response" if en else "Antwort der Nachrechnung lesen", exact=False).click()
    expect(karte).to_contain_text("Effects on the judiciary" if en else "Folgen für Judikatur")
    expect(karte).to_contain_text("Effects on the executive" if en else "Folgen für Exekutive")
    expect(karte).to_contain_text("Unknown values do not mean zero demand" if en else "Unbekannte Werte bedeuten keinen Nullbedarf")
    expect(karte).to_contain_text("Original and note remain unchanged" if en else "Original und Vermerk bleiben unverändert")
    expect(karte.locator(".ki-folgenabschnitte svg")).to_have_count(0)
    b.refresh_from_db()
    assert b.erledigt_am is None
    expect(karte).to_be_visible()
    expect(karte.locator(".ki-folgenabschnitte")).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    p.screenshot(path=str(sichtpruefung / f"folgenkorrektur-{kennung}.png"), full_page=True)
