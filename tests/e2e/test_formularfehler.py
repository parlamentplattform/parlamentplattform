"""GP-060 (ZB-02): Ein Formularfehler steht am Handy oben im Bild, als Meldung mit Verweis auf das Feld.

Abnahme: Bei 390 Pixel Breite ohne JavaScript liegt nach dem fehlerhaften Absenden ein Element mit
role=alert im sichtbaren Ausschnitt und verweist auf das betroffene Feld; der Seitentitel beginnt
mit „Fehler:“. Hier am Einbringen eines örtlichen Antrags, dessen Gebiet sich zwischen Anzeigen
und Absenden geändert hat (GP-170) — ein Fehler, den erst der Server erkennt."""

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from mitglieder.models import Mitglied
from verfahren.test_oertliche_teilnahme import menschen  # noqa: F401
from verfahren.test_views_aktionen import ANTRAG, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}


def test_gp060_fehler_beim_einbringen_steht_oben_im_bild(seite, live_server, menschen, ordnung, sichtpruefung):  # noqa: F811
    """Ohne JavaScript, wie die Abnahme es verlangt — mit JavaScript liefe die Vorschau ähnlicher Anträge
    gleichzeitig mit dem Umzug in der Datenbank, und SQLite sperrte die Tabelle."""
    leute, _ort, fremdort = menschen
    p = seite(als=leute["autor"], js=False, viewport=HANDY, reduziert=True)
    p.goto(live_server.url + reverse("verfahren:einbringen"))
    p.fill("#id_titel", ANTRAG["titel"])
    p.fill("#id_wortlaut", ANTRAG["wortlaut"])
    p.locator('input[name="ebene"][value="gemeinde"]').check()
    # Zwischen Anzeigen und Absenden zieht die Person um: Das Gebiet des Formulars gilt nicht mehr
    Mitglied.objects.filter(pk=leute["autor"].pk).update(wohnsitz=fremdort)
    p.locator("#einbringen-form button[type=submit]").first.click()
    p.wait_for_load_state()
    meldung = p.locator("[role=alert]").first
    expect(meldung).to_be_visible()
    expect(meldung.locator('a[href="#id_ebene"]')).to_have_count(1)
    kasten = meldung.bounding_box()
    assert kasten is not None and 0 <= kasten["y"] and kasten["y"] + min(kasten["height"], 80) <= HANDY["height"]
    assert p.title().startswith("Fehler:")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert p.locator("#id_ebene").count() == 1  # das Sprungziel gibt es
    p.screenshot(path=str(sichtpruefung / "formularfehler-einbringen-handy-ohne-js.png"))
