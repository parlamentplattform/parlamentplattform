"""Gültige alte Nachrechnung und ausdrücklicher Fehler ohne interne Zusatzdaten."""
# ruff: noqa: F811 -- importierte pytest-Fixture

import copy
import json
from pathlib import Path

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.models import KIAuftrag, KILauf
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.test_korrektur_exportgrenze import PRIVAT, altfall_erzeugen, lauf_kopie
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True), pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache,quellenfassung", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT", 0),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT", 1),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "de-AT", 2),
    ("handy-dunkel-en", {"width": 390, "height": 844}, True, True, "en", 2),
])
def test_alte_nachrechnung_und_ehrlicher_schutz_des_oeffentlichen_archivs(
    a, monkeypatch, seite, live_server, sichtpruefung, kennung, viewport, js, dunkel, sprache, quellenfassung,
):
    a, job = altfall_erzeugen(a, quellenfassung, monkeypatch)
    b = job.beanstandung
    original = job.lauf
    vorher = KILauf.objects.values().get(pk=original.pk)
    p = seite(viewport=viewport, js=js, dunkel=dunkel, sprache=sprache, reduziert=True)
    p.goto(live_server.url + reverse("verfahren:antrag", args=[a.pk]) + f"#beanstandung-{b.pk}")
    karte = p.locator(f"#beanstandung-{b.pk}")
    karte.get_by_text("Read the recalculation response" if sprache == "en" else "Antwort der Nachrechnung lesen", exact=False).click()
    expect(karte).to_contain_text("korrektur-v2" if quellenfassung == 2 else "korrektur-v1")
    karte.get_by_text("Read the correction context" if sprache == "en" else "Korrekturkontext nachlesen", exact=True).click()
    with p.expect_download() as download:
        karte.get_by_role("link").click()
    daten = json.loads(Path(download.value.path()).read_text(encoding="utf-8"))
    assert daten["rechtsbezug"]["korrekturen"][0]["lauf"]["eingabe"] == original.eingabe
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    p.screenshot(path=str(sichtpruefung / f"altkorrektur-gueltig-{kennung}.png"), full_page=True)

    fremd = lauf_kopie(original, {**copy.deepcopy(original.kontext), "privat": PRIVAT})
    KIAuftrag.objects.filter(pk=job.pk).update(lauf=fremd)
    p.reload()
    expect(karte).to_contain_text("The correction reference cannot be verified unambiguously" if sprache == "en" else "Der Korrekturbezug ist nicht eindeutig prüfbar")
    assert PRIVAT not in p.content()
    response = p.request.get(live_server.url + reverse("verfahren:archiv_export", kwargs={"pk": a.pk, "art": "json"}))
    assert response.status == 200 and PRIVAT not in response.text()
    assert daten["rechtsbezug"]["korrekturen"][0]["lauf"]["id"] == original.pk
    assert response.json()["rechtsbezug"]["korrekturen"] == [{"auftrag": job.pk, "zustand": "fehler"}]
    assert KILauf.objects.values().get(pk=original.pk) == vorher
    assert KILauf.objects.get(pk=fremd.pk).kontext["privat"] == PRIVAT
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.evaluate("scrollTo({top: 0, behavior: 'instant'})")
    p.screenshot(path=str(sichtpruefung / f"altkorrektur-geschuetzt-{kennung}.png"), full_page=True)
