"""Ausdrückliche amtliche Einzelabrufe, auch auf Handy und ohne JavaScript."""

import json

import pytest
from playwright.sync_api import expect

from faktenbasis import importieren, volltext
from faktenbasis.models import Norm
from faktenbasis.ris import antwort_parsen
from faktenbasis.test_ris import NUMMER, STAND, beispiel
from faktenbasis.test_xmltext import RIS_ID, xml_beispiel
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel", [
    ("desktop-hell-js", {"width": 1440, "height": 900}, True, False),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False),
    ("handy-dunkel-js", {"width": 390, "height": 844}, True, True),
])
def test_quelle_ausdruecklich_uebernehmen(seite, live_server, sichtpruefung, monkeypatch, kennung, viewport, js, dunkel):
    person = mitglied_anlegen()
    person.ist_admin = True
    person.save(update_fields=["ist_admin"])
    daten = json.loads(json.dumps(beispiel()).replace("NOR11000363", RIS_ID))
    aufrufe = []
    def meta(*args):
        aufrufe.append(args)
        return antwort_parsen(daten, NUMMER)
    monkeypatch.setattr(importieren, "abrufen", meta)
    monkeypatch.setattr(volltext, "abrufen", lambda *args: xml_beispiel())
    p = seite(als=person, js=js, dunkel=dunkel, viewport=viewport, reduziert=True)
    p.goto(f"{live_server.url}/zukunftswerkstatt/faktenbasis/")
    p.get_by_role("link", name="Amtliche Quelle übernehmen", exact=True).click()
    expect(p.get_by_role("heading", name="Amtliche Quelle übernehmen")).to_be_visible()
    p.get_by_label("Gesetzesnummer", exact=True).fill(NUMMER)
    p.get_by_label("Stichtag", exact=True).fill(STAND.isoformat())
    assert not aufrufe and not Norm.objects.exists()
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.screenshot(path=str(sichtpruefung / f"quellenverwaltung-formular-{kennung}.png"), full_page=True)
    p.get_by_role("button", name="Metadaten einmal abrufen", exact=True).click()
    expect(p.get_by_text("Metadaten übernommen:", exact=False)).to_be_visible()
    assert len(aufrufe) == 1
    p.get_by_role("link", name="Abänderung des Bundes-Verfassungsgesetzes").click()
    p.get_by_role("button", name="Diesen Dokumenttext einmal abrufen", exact=True).click()
    expect(p.locator(".fakten-wortlaut")).to_contain_text("Änderung des B-VG")
    expect(p.get_by_text("Der amtliche Dokumenttext wurde übernommen.", exact=False)).to_be_visible()
    assert p.evaluate("document.documentElement.scrollWidth <= window.innerWidth")
    p.screenshot(path=str(sichtpruefung / f"quellenverwaltung-text-{kennung}.png"), full_page=True)
