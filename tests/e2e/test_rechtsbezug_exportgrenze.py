"""Gültige alte Rechtsbezüge und geschützte öffentliche Downloads im Browser."""
# ruff: noqa: F811 -- importierte pytest-Fixture

import copy
import json
from pathlib import Path

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.models import KIAuftrag
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.test_korrektur_exportgrenze import lauf_kopie
from ki.test_rechtsbezug_exportgrenze import PRIVAT, altfall_erzeugen
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache,quellenfassung", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT", 0),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT", 1),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT", 2),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en", 2),
])
def test_oeffentlicher_altbezug_bleibt_lesbar_und_fremder_beifang_geschuetzt(
    a, monkeypatch, seite, live_server, sichtpruefung, kennung, viewport, js, dunkel, sprache, quellenfassung,
):
    a, job = altfall_erzeugen(a, quellenfassung, monkeypatch)
    original = job.lauf
    vorher = copy.deepcopy(original.kontext)
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(live_server.url + reverse("verfahren:antrag", args=[a.pk]))
    mobil_mit_js = js and viewport["width"] < 768
    if mobil_mit_js:
        p.locator('.zreiter[href="#zone-archiv"]').click()
        expect(p.locator("#zone-archiv")).to_be_visible()
    expect(p.locator("body")).to_contain_text(f"rechtsbezug-v{quellenfassung + 1}")
    with p.expect_download() as download:
        p.get_by_role("link", name="As JSON" if sprache == "en" else "Als JSON", exact=True).click()
    daten = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
    assert daten["rechtsbezug"]["laeufe"][0]["eingabe"] == original.eingabe
    if mobil_mit_js:
        p.locator('.zreiter[href="#zone-einschaetzung"]').click()
        expect(p.locator("#zone-einschaetzung")).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    p.screenshot(path=str(sichtpruefung / f"rechtsbezug-gueltig-{kennung}.png"), full_page=True)

    fremd = lauf_kopie(original, {**copy.deepcopy(original.kontext), "intern": PRIVAT})
    KIAuftrag.objects.filter(pk=job.pk).update(lauf=fremd)
    p.reload()
    if mobil_mit_js:
        p.locator('.zreiter[href="#zone-einschaetzung"]').click()
        expect(p.locator("#zone-einschaetzung")).to_be_visible()
    expect(p.get_by_text("The stored run is not clearly bound" if sprache == "en" else "Der gespeicherte Lauf ist nicht eindeutig an den öffentlichen Auftrag gebunden", exact=False)).to_be_visible()
    assert PRIVAT not in p.content()
    for art in ("json", "md"):
        r = p.request.get(live_server.url + reverse("verfahren:archiv_export", kwargs={"pk": a.pk, "art": art}))
        assert r.status == 200 and PRIVAT not in r.text()
        if art == "json":
            assert r.json()["rechtsbezug"]["laeufe"][-1] == {"id": fremd.pk, "zweck": "rechtsbezug", "kontextstatus": "fehler"}
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    assert original.__class__.objects.get(pk=original.pk).kontext == vorher
    assert original.__class__.objects.get(pk=fremd.pk).kontext["intern"] == PRIVAT
    p.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    p.screenshot(path=str(sichtpruefung / f"rechtsbezug-geschuetzt-{kennung}.png"), full_page=True)
