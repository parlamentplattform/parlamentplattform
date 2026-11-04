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
    digest = p.locator("#bestands-hash").inner_text()
    with p.expect_download() as down:
        p.locator("#bestandsnachweis a.knopf").click()
    d = json.loads(Path(down.value.path()).read_text(encoding="utf-8"))
    raw = json.dumps(d["inhalt"], sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    assert hashlib.sha256(raw).hexdigest() == digest == d["sha256"]
    assert len(d["inhalt"]["eintraege"]) == 4
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"quellenbestand-{kennung}.png"), full_page=True)
    Parameter.objects.update_or_create(schluessel="faktenbasis-bestandsnachweis-hoechstzahl", defaults={"wert": "3"})
    antwort = p.reload()
    assert antwort.status == 503
    assert p.locator("#bestands-hash").count() == 0
    assert p.locator("#bestandsnachweis a.knopf").count() == 0
    expect(p.get_by_role("status")).to_contain_text("No partial evidence" if sprache == "en" else "kein Teilnachweis")
    assert p.evaluate("document.documentElement.scrollWidth <= innerWidth")
    p.screenshot(path=str(sichtpruefung / f"quellenbestand-grenze-{kennung}.png"), full_page=True)
    assert AuditEintrag.objects.count() == vorher
