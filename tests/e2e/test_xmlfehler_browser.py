"""Kodierungsfehler sind sichtbar; alte Originale und Parserstände bleiben erhalten."""

import hashlib
from pathlib import Path

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.models import NormText, NormTextAbruf
from faktenbasis.test_volltext import norm, xml  # noqa: F401
from faktenbasis.test_xmlkodierung import dokument
from faktenbasis.test_xmltext import NUMMER, RIS_ID, xml_beispiel
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from faktenbasis.xmltext import xmltext_parsen
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,kodierung", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "UTF-16LE"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "UTF-16BE"),
    ("handy-hell-ohne-js", {"width": 390, "height": 844}, False, False, "UTF-16LE"),
    ("handy-dunkel", {"width": 390, "height": 844}, True, True, "UTF-16BE"),
])
def test_fehler_laesst_altstand_lesbar_und_utf8_erhaelt_zusaetzliche_fassung(
    norm, xml, seite, live_server, sichtpruefung, kennung, viewport, js, dunkel, kodierung,  # noqa: F811
):
    person = mitglied_anlegen()
    person.ist_admin = True
    person.save(update_fields=["ist_admin"])
    raw = xml_beispiel()
    daten = xmltext_parsen(raw, RIS_ID, NUMMER)
    alt = NormText.objects.create(norm=norm, quelle=norm.quelle, xml=raw, text=daten.text,
                                 xml_hash=daten.xml_hash, parser_fassung=2)
    altzeit = alt.erfasst_am
    xml[0] = dokument(kodierung, "&lokal;", '<!DOCTYPE risdok [<!ENTITY lokal "Lokaler Test">]>').encode(kodierung)
    p = seite(als=person, js=js, dunkel=dunkel, viewport=viewport, reduziert=True)
    p.goto(live_server.url + reverse("faktenbasis:norm", args=[norm.pk]))
    p.get_by_role("button", name="Diesen Dokumenttext einmal abrufen", exact=True).click()
    expect(p.get_by_text("Der letzte Dokumenttext-Abruf ist fehlgeschlagen.", exact=False)).to_be_visible()
    expect(p.locator(".fakten-wortlaut")).to_contain_text("Änderung des B-VG")
    expect(p.locator("section .fakten-hash")).to_have_text(hashlib.sha256(raw).hexdigest())
    assert NormText.objects.count() == NormTextAbruf.objects.count() == 1
    assert NormTextAbruf.objects.get().fehlercode == "volltextformat"
    with p.expect_download() as download:
        p.locator(f'a[href="{reverse("faktenbasis:textxml", args=[alt.pk])}"]').click()
    assert Path(download.value.path()).read_bytes() == raw
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"xmlfehler-altstand-{kennung}.png"), full_page=True)

    # Ausschließlich expliziter neuer guter Einzelimport; keine automatische Reparatur.
    xml[0] = raw
    p.get_by_role("button", name="Diesen Dokumenttext einmal abrufen", exact=True).click()
    expect(p.get_by_text("Der amtliche Dokumenttext wurde übernommen.", exact=False)).to_be_visible()
    neu = NormText.objects.exclude(pk=alt.pk).get()
    assert neu.parser_fassung == 3 and bytes(neu.xml) == raw and neu.xml_hash == alt.xml_hash
    assert NormText.objects.count() == NormTextAbruf.objects.count() == 2
    alt.refresh_from_db()
    assert alt.parser_fassung == 2 and bytes(alt.xml) == raw and alt.text == daten.text
    assert alt.erfasst_am == altzeit and alt.xml_hash == daten.xml_hash
    expect(p.locator(".fakten-wortlaut").first).to_contain_text("Änderung des B-VG")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"xmlfehler-neuer-stand-{kennung}.png"), full_page=True)
