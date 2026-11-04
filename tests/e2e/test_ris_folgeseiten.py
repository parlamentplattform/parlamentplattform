"""Explizite Folgeseite: Formfehler, genau ein Abruf und sichtbare Herkunft."""

import pytest
from playwright.sync_api import expect

from faktenbasis import importieren, ris
from faktenbasis.models import Norm, RisImport
from faktenbasis.test_ris import NUMMER, STAND
from faktenbasis.test_ris_seiten import daten
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT"),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en"),
])
def test_gewaehlte_folgeseite_bleibt_nachlesbar(
    seite, live_server, sichtpruefung, monkeypatch, kennung, viewport, js, dunkel, sprache,
):
    m = mitglied_anlegen()
    m.ist_admin = True
    m.save(update_fields=["ist_admin"])
    calls = []
    def holen(nummer, stand, *, seite):
        calls.append((nummer, stand, seite))
        return ris.antwort_parsen(daten("Bund"), nummer, seite=seite)
    monkeypatch.setattr(importieren, "abrufen", holen)
    p = seite(als=m, viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(f"{live_server.url}/verwaltung/faktenbasis/")
    p.locator("#id_gesetzesnummer").fill(NUMMER)
    p.locator("#id_stand").fill(STAND.isoformat())
    p.locator("#id_seite").fill("0")
    # Native HTML-Minimum schützt bereits vor Submit; serverseitige Formprüfung
    # ist separat geprüft. Danach die tatsächlich gewählte positive Seite senden.
    p.locator("form.formular button[type=submit]").click()
    assert not calls and not Norm.objects.exists()
    p.locator("#id_seite").fill("2")
    expect(p.locator("#id_seite")).to_have_value("2")
    expect(p.locator("#id_seite")).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    p.screenshot(path=str(sichtpruefung / f"ris-folgeseite-formular-{kennung}.png"), full_page=True)
    assert p.locator("form.formular").evaluate("f => f.checkValidity()")
    # Der POST muss tatsächlich beendet sein, bevor wir die serverseitigen
    # Schreibwirkungen prüfen — auch ohne JavaScript im mobilen Browser.
    p.locator("form.formular button[type=submit]").evaluate(
        "el => el.scrollIntoView({behavior: 'instant', block: 'center'})",
    )
    with p.expect_response(lambda r: r.request.method == "POST"
                           and r.url == f"{live_server.url}/verwaltung/faktenbasis/") as antwort:
        p.locator("form.formular button[type=submit]").click()
    assert antwort.value.status == 302
    assert calls == [(NUMMER, STAND, 2)] and RisImport.objects.get().seite == 2
    n = Norm.objects.get()
    p.locator(f'a[href="/zukunftswerkstatt/faktenbasis/norm/{n.pk}/"]').click()
    herkunft = p.locator("details").filter(has=p.locator(
        f'a[href="/zukunftswerkstatt/faktenbasis/import/{n.importlauf_id}/antwort.json"]',
    ))
    herkunft.locator("summary").click()
    expect(herkunft.get_by_text("RIS page: 2" if sprache == "en" else "RIS-Seite: 2", exact=True)).to_be_visible()
    assert len(calls) == 1 and p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.evaluate("window.scrollTo({top: 0, behavior: 'instant'})")
    p.screenshot(path=str(sichtpruefung / f"ris-folgeseite-herkunft-{kennung}.png"), full_page=True)
