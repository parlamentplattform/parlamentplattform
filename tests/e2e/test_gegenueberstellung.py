"""Optionale private Gegenüberstellung, gleichwertige Wahl, Handy und ohne JS."""

import json
import re

import pytest
from playwright.sync_api import expect

from ki.anbieter import Antwort, AttrappenAnbieter
from ki.models import KILauf, Vergleichsanfrage, Zweck
from verfahren.models import Antrag, Eigenstaendigkeit, antrag_einbringen
from verfahren.test_einbringen_aehnlichkeit import UMFORMULIERT
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 1000}, True, False, "de-AT"),
    ("handy-dunkel", {"width": 390, "height": 844}, True, True, "de-AT"),
    ("desktop-ohne-js", {"width": 1440, "height": 1000}, False, True, "de-AT"),
    ("handy-en-ohne-js", {"width": 390, "height": 844}, False, False, "en-GB"),
])
def test_freiwilliger_vergleich_belaesst_die_menschliche_wahl(
    seite, live_server, ordnung, sichtpruefung, monkeypatch, settings,  # noqa: F811
    kennung, viewport, js, dunkel, sprache,
):
    ziel = antrag_einbringen(mitglied_anlegen("vorhanden"), ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    settings.DDOE_KI_ANBIETER = "attrappe"
    aufrufe = []

    def antwort(self, auftrag, eingabe, zeitgrenze=None):
        aufrufe.append(eingabe)
        d = json.loads(eingabe)
        return Antwort(json.dumps({"vergleiche": [
            {"antrag": p["antrag"], "fassung": p["fassung"], "gemeinsamkeit": "Beide Texte nennen Sitzungsprotokolle.",
             "unterschied": "Die Formulierungen unterscheiden sich."} for p in d["gegenueber"]
        ]}), "browser-attrappe-1", 8, 7)

    monkeypatch.setattr(AttrappenAnbieter, "frage", antwort)
    p = seite(als=mitglied_anlegen("vergleichender"), viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(f"{live_server.url}/einbringen/")
    en = sprache.startswith("en")
    p.get_by_label("Title" if en else "Titel", exact=True).fill(UMFORMULIERT["titel"])
    p.get_by_label("Text of the motion" if en else "Wortlaut des Antrags", exact=True).fill(UMFORMULIERT["wortlaut"])
    p.get_by_role("button", name="Submit a motion" if en else "Antrag einbringen", exact=True).click()
    assert not aufrufe
    p.locator("summary").filter(has_text="Ask AI to compare the texts" if en else "Texte durch KI gegenüberstellen lassen").click()
    p.get_by_role("button", name="Compare these texts now" if en else "Diese Texte jetzt gegenüberstellen lassen", exact=True).click()
    abschnitt = p.get_by_role("region", name="AI text comparison" if en else "KI-Textgegenüberstellung")
    expect(abschnitt).to_be_visible()
    expect(abschnitt).to_contain_text("Beide Texte nennen Sitzungsprotokolle.")
    expect(p.get_by_label("Text of the motion" if en else "Wortlaut des Antrags", exact=True)).to_have_value(UMFORMULIERT["wortlaut"])
    expect(p.get_by_role("button", name="Support this motion" if en else "Diesen unterstützen", exact=True)).to_be_visible()
    eigen = p.get_by_role("button", name="My motion is different — submit it" if en else "Mein Antrag ist etwas anderes — einbringen", exact=True)
    expect(eigen).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.screenshot(path=str(sichtpruefung / f"gegenueberstellung-{kennung}.png"), full_page=True)
    assert len(aufrufe) == 1 and Vergleichsanfrage.objects.count() == 1
    assert KILauf.objects.filter(zweck=Zweck.GEGENUEBERSTELLUNG).count() == 1
    eigen.click()
    expect(p).to_have_url(re.compile(r"/antrag/\d+/\?neu=1$"))
    neu = Antrag.objects.latest("pk")
    assert Eigenstaendigkeit.objects.get(antrag=neu).gegenueber_id == ziel.pk
    assert len(aufrufe) == 1
