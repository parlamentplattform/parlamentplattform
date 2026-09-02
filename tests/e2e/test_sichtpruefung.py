"""Erzeugt die Bilder für die Sichtprüfung des Gründers (FB-P5, Definition of Done 5).

Lauf mit Ablage unter docs/sichtpruefung/<version>/:

    DDOE_SICHTPRUEFUNG=1 python -m pytest tests/e2e/test_sichtpruefung.py -q

Ohne die Umgebungsvariable landen die Bilder in einem flüchtigen Ordner; der Test prüft
dann nur, dass sie entstehen.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _ruhe(p, js: bool = True) -> None:
    if js:
        p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")
    else:
        p.wait_for_timeout(800)


def test_screenshots_fuer_die_sichtpruefung(seite, live_server, demo, sichtpruefung):
    bilder = []

    def halte_fest(p, name, js=True):
        _ruhe(p, js)
        ziel = sichtpruefung / f"{name}.png"
        p.screenshot(path=str(ziel))
        bilder.append(ziel)

    # Desktop 1440×900 — hell und dunkel, als Gast und als Mitglied
    p = seite()
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-desktop-hell-gast")

    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-desktop-hell-mitglied")

    p = seite(dunkel=True, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-desktop-dunkel-mitglied")

    # Der Favoriten-Fächer (FB-C1–C4): Wurzel mit fünf Ebenen, entfalteter Ast beim Hover,
    # Mitte-Modus mit Rückweg und Brotkrume, Handy-Variante
    def halte_feld(p, name, feld="#feld-favoriten"):
        _ruhe(p)
        ziel = sichtpruefung / f"{name}.png"
        p.locator(feld).screenshot(path=str(ziel))
        bilder.append(ziel)

    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_feld(p, "faecher-wurzel")
    p.locator("#feld-favoriten .fknoten.enkel").nth(6).hover()
    p.wait_for_timeout(300)
    halte_feld(p, "faecher-hover-ast")
    p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first.click()
    p.wait_for_timeout(900)
    p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first.click()
    p.wait_for_timeout(900)
    halte_feld(p, "faecher-mitte")

    p = seite(viewport=HANDY, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/#feld-favoriten")
    p.wait_for_timeout(500)
    halte_feld(p, "faecher-handy")

    # Der WeicherFilter (FB-B1–B5): Overlay von rechts, Live-Vorschau mit „Warum hier?", eingefahrene Leiste
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.locator("#feld-filter .regler-klappe > summary").click()
    p.wait_for_timeout(450)
    halte_feld(p, "filter-overlay", "#feld-filter")
    p.locator('#feld-filter input[name="r_unterstuetzungsphase"]').focus()
    p.keyboard.press("End")
    p.wait_for_function("() => document.querySelector('#filter-liste .warum') !== null")
    p.keyboard.press("Escape")
    p.wait_for_timeout(250)
    p.locator("#filter-liste .warum > summary").first.click()
    p.wait_for_timeout(300)
    halte_feld(p, "filter-vorschau-warum", "#feld-filter")
    p.locator("#feld-filter .pfeil").click()
    p.wait_for_timeout(450)
    halte_feld(p, "filter-leiste-zu", "#feld-filter")

    # Konto-Menü und Anstoß-Popover geöffnet
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.locator(".konto > summary").click()
    halte_fest(p, "konto-menue")
    p.keyboard.press("Escape")
    p.locator(".anstoss-leiste .anstoss-fleck > summary").click()
    halte_fest(p, "anstoss-popover")

    # Handy 390×844 — hell und dunkel, dazu das Burger-Panel
    p = seite(viewport=HANDY, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-handy-hell")
    p.locator(".menue > summary").click()
    p.wait_for_timeout(500)
    halte_fest(p, "handy-menue")

    p = seite(viewport=HANDY, dunkel=True, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-handy-dunkel")

    # Ohne JavaScript (Grundschicht) und eine Seite mit Fußzeile zum Vergleich
    p = seite(js=False)
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-ohne-javascript", js=False)

    from verfahren.models import Antrag

    antrag = Antrag.objects.filter(hervorgehoben=True).first().pk
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag}/")
    halte_fest(p, "antragsseite-mit-fusszeile")

    assert len(bilder) == 17
    for bild in bilder:
        assert bild.exists() and bild.stat().st_size > 5000, bild
