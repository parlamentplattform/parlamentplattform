"""GP-172 (ZB-09): Mindestgröße der Tippziele am Handy (WCAG 2.2, 2.5.8 — 24 × 24 CSS-Pixel).

Abnahme: Sonde bei 390 Pixel Breite — kein sichtbarer Knopf auf /parlament/ und /antrag/<pk>/ ist
kleiner als 24 × 24. Als Knopf zählt, was wie ein Knopf bedient wird: button, Eingaben vom Typ
submit/button/checkbox/radio (mit ihrem Etikett, wenn sie darin stehen), summary sowie Verweise in
Knopfgestalt (Stern, Chip, Symbol, Knopf). Verweise im Fließtext nimmt 2.5.8 ausdrücklich aus."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}
MINDEST = 24

SONDE = """(mindest) => {
    const knoepfe = document.querySelectorAll(
        'button, [role=button], input[type=submit], input[type=button], input[type=checkbox], input[type=radio], '
        + 'summary, a.knopf, a.stern, a.chip, a.ikon, a.btn, a.btn-linie, a.btn-still, a.btn-hell');
    const klein = [];
    for (const e of knoepfe) {
        if (e.closest('[inert], [hidden], details:not([open]) > :not(summary)')) continue;
        const s = getComputedStyle(e);
        if (s.display === 'none' || s.visibility === 'hidden') continue;
        // Eine Eingabe im Etikett: Das Etikett gehört zum Tippziel
        const ziel = (e.tagName === 'INPUT' && e.closest('label')) || e;
        const r = ziel.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;  // flächenlos: Sache der Tastatursonde (GP-171)
        if (r.width < mindest - 0.05 || r.height < mindest - 0.05) {
            klein.push(`${e.tagName.toLowerCase()}.${String(e.className).trim().replace(/\\s+/g, '.')} `
                + `„${(e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 16)}“ `
                + `${r.width.toFixed(1)}×${r.height.toFixed(1)}`);
        }
    }
    return [...new Set(klein)];
}"""


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _seiten():
    """Parlament und eine Antragsseite in der Beratung mit Chatbeiträgen (Stimmknöpfe, Melden)."""
    from mitglieder.models import Mitglied
    from verfahren.chat import ChatGesperrt, beitrag_schreiben
    from verfahren.models import Antrag, Kategorie

    for antrag in Antrag.objects.filter(phase="beratung").order_by("pk"):
        try:
            wurzel = beitrag_schreiben(antrag, Mitglied.objects.get(username="demo2"), "Ein Beitrag zum Prüfen.")
        except ChatGesperrt:
            continue  # der Expertenrat arbeitet noch am Vorschlag
        beitrag_schreiben(antrag, _mitglied(), "Eine Antwort darauf.", wurzel)
        kategorie = Kategorie.objects.filter(aktiv=True).order_by("pk").first()
        if kategorie is not None:
            antrag.kategorien.add(kategorie)  # der Lebensbereich steht als Chip-Verweis im Kopf
        return ["/parlament/", f"/antrag/{antrag.pk}/"]
    raise AssertionError("demo_seed legt einen Antrag mit offenem Chat an")


@pytest.mark.parametrize("angemeldet", [False, True], ids=["gast", "mitglied"])
@pytest.mark.parametrize("js", [True, False], ids=["mit-js", "ohne-js"])
def test_gp172_kein_knopf_unter_24_pixel_am_handy(seite, live_server, demo, js, angemeldet):
    pfade = _seiten()
    # Reduzierte Bewegung: Das Einblenden (scale .955) endet sofort — gemessen wird das ruhende Ziel
    p = seite(viewport=HANDY, js=js, reduziert=True, als=_mitglied() if angemeldet else None)
    funde = {}
    for pfad in pfade:
        p.goto(f"{live_server.url}{pfad}")
        p.wait_for_load_state("load")
        p.wait_for_timeout(300)  # ein paar Bilder, bis das 1-ms-Einblenden auch ohne Skript gelaufen ist
        if js:
            p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")
        klein = p.evaluate(SONDE, MINDEST)
        if klein:
            funde[pfad] = klein
    assert funde == {}, f"Tippziele unter {MINDEST} × {MINDEST} Pixel: {funde}"
