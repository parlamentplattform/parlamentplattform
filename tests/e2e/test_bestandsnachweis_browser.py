"""Öffentliche Nachlese ohne JS und reproduzierbarer, an die Anzeige gebundener Download."""

import hashlib
import json
from pathlib import Path

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from faktenbasis.test_bestandsnachweis import bestand  # noqa: F401
from faktenbasis.test_volltext import norm  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from parameter.models import Parameter
from verfahren.models import AuditEintrag

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("kennung,viewport,js,dunkel,sprache", [
    ("desktop-hell", {"width": 1440, "height": 900}, True, False, "de-AT"),
    ("desktop-dunkel-ohne-js", {"width": 1440, "height": 900}, False, True, "de-AT"),
    ("handy-hell-ohne-js-en", {"width": 390, "height": 844}, False, False, "en"),
    ("handy-dunkel", {"width": 390, "height": 844}, True, True, "de-AT"),
])
def test_bestandsnachweis_und_ehrlicher_ausfall(
    bestand, seite, live_server, sichtpruefung, kennung, viewport, js, dunkel, sprache,  # noqa: F811
):
    vorher = AuditEintrag.objects.count()
    p = seite(js=js, dunkel=dunkel, viewport=viewport, reduziert=True, sprache=sprache)
    p.goto(live_server.url + reverse("faktenbasis:index"))
    p.locator(f'a[href="{reverse("faktenbasis:bestand")}"]').click()
    titel = "Evidence of the stored source inventory" if sprache == "en" else "Nachweis des gespeicherten Quellenbestands"
    expect(p.get_by_role("heading", name=titel, exact=True)).to_be_visible()
    sammlung = "Gazette records" if sprache == "en" else "Kundmachungsbelege"
    expect(p.locator("#bestandsnachweis").get_by_text(sammlung, exact=True)).to_be_visible()
    sammlung = "Constitutional Court metadata records" if sprache == "en" else "VfGH-Metadatenbelege"
    expect(p.locator("#bestandsnachweis").get_by_text(sammlung, exact=True)).to_be_visible()
    sammlung = "Archived RIS change pages" if sprache == "en" else "Archivierte RIS-Änderungsseiten"
    expect(p.locator("#bestandsnachweis").get_by_text(sammlung, exact=True)).to_be_visible()
    digest = p.locator("#bestands-hash").inner_text()
    if viewport["width"] <= 560:
        assert p.locator("#bestands-hash").bounding_box()["width"] > viewport["width"] * 0.65
    with p.expect_download() as down:
        p.locator("#bestandsnachweis a.knopf").click()
    d = json.loads(Path(down.value.path()).read_text(encoding="utf-8"))
    raw = json.dumps(d["inhalt"], sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    assert hashlib.sha256(raw).hexdigest() == digest == d["sha256"]
    assert d["inhalt"]["fassung"] == 4 and len(d["inhalt"]["eintraege"]) == 7
    assert d["inhalt"]["eintraege"][0]["pruefsumme"] == bestand[4].original_sha256
    assert d["inhalt"]["eintraege"][-1] == {
        "sammlung": "vfgh_metadaten", "nummer": bestand[5].pk, "pruefsumme": bestand[5].original_sha256,
    }
    assert d["inhalt"]["eintraege"][-2] == {
        "sammlung": "ris_aenderungsseite", "nummer": bestand[6].pk, "pruefsumme": bestand[6].original_sha256,
    }
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"quellenbestand-{kennung}.png"), full_page=True)
    Parameter.objects.update_or_create(schluessel="faktenbasis-bestandsnachweis-hoechstzahl", defaults={"wert": "6"})
    antwort = p.reload()
    assert antwort.status == 503
    assert p.locator("#bestands-hash").count() == 0
    assert p.locator("#bestandsnachweis a.knopf").count() == 0
    expect(p.get_by_role("status")).to_contain_text("No partial evidence" if sprache == "en" else "kein Teilnachweis")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"quellenbestand-grenze-{kennung}.png"), full_page=True)
    assert AuditEintrag.objects.count() == vorher
