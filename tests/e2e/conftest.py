"""Gemeinsame Vorrichtungen der Bildschirmtests (Design-Spezifikation 8, FB-P5).

Die Tests laufen gegen einen echten Server (`live_server`) mit den Demo-Daten aus
`demo_seed` und steuern Chromium über Playwright. Fehlt Playwright, überspringt sich
die ganze Datei — die CI bleibt damit ohne Browser grün.

Screenshots landen unter `docs/sichtpruefung/<version>/`, sobald `DDOE_SICHTPRUEFUNG=1`
gesetzt ist; sonst in einem temporären Ordner.
"""

from __future__ import annotations

import os
from pathlib import Path

import pytest

# Playwrights Treiber hält eine Ereignisschleife im selben Faden; ohne diese Testvariable
# verweigert Django jeden ORM-Zugriff (SynchronousOnlyOperation). Gilt nur für Tests.
os.environ.setdefault("DJANGO_ALLOW_ASYNC_UNSAFE", "1")

playwright_api = pytest.importorskip("playwright.sync_api", reason="Playwright ist nicht installiert")

from django.core.management import call_command  # noqa: E402
from django.test import Client  # noqa: E402

from plattform_core import __version__  # noqa: E402

WURZEL = Path(__file__).resolve().parent.parent.parent
DESKTOP = {"width": 1440, "height": 900}
HANDY = {"width": 390, "height": 844}
TABLET = {"width": 900, "height": 1200}


@pytest.fixture(scope="session")
def browser():
    with playwright_api.sync_playwright() as p:
        browser = p.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def demo(db):
    """Die Demo-Daten des Alpha-Betriebs: demo1…demo5, Anträge je Phase, Gremien-Rollen."""
    call_command("demo_seed", verbosity=0)


@pytest.fixture
def sichtpruefung() -> Path:
    ziel = WURZEL / "docs" / "sichtpruefung" / __version__
    if os.environ.get("DDOE_SICHTPRUEFUNG") == "1":
        ziel.mkdir(parents=True, exist_ok=True)
        return ziel
    fluechtig = WURZEL / ".sichtpruefung-fluechtig"
    fluechtig.mkdir(exist_ok=True)
    return fluechtig


@pytest.fixture
def seite(browser, live_server):
    """Fabrik für Browser-Seiten: Maße, Erscheinungsbild, Bewegung, JavaScript, Anmeldung."""
    kontexte = []

    def erzeuge(*, viewport=None, dunkel=False, js=True, reduziert=False, als=None, video=None,
                sprache="de-AT"):
        # Die Sprache steht ausdrücklich hier: Sonst erbt der Browser die des Rechners, und
        # dieselben Tests prüften auf einem englischen System eine andere Oberfläche.
        kontext = browser.new_context(
            viewport=viewport or DESKTOP,
            locale=sprache,
            color_scheme="dark" if dunkel else "light",
            reduced_motion="reduce" if reduziert else "no-preference",
            java_script_enabled=js,
            record_video_dir=str(video) if video else None,
            record_video_size=viewport or DESKTOP,
        )
        if als is not None:
            # Demo-Konten haben kein Passwort (Anmeldung per E-Mail-Link) — Sitzung direkt setzen
            c = Client()
            c.force_login(als)
            kontext.add_cookies([{
                "name": "sessionid",
                "value": c.cookies["sessionid"].value,
                "url": live_server.url,
            }])
        kontexte.append(kontext)
        return kontext.new_page()

    yield erzeuge
    for kontext in kontexte:
        kontext.close()
