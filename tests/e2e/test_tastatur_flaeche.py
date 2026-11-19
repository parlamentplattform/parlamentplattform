"""GP-171 (ZB-08): Tastatursonde gegen flächenlose Tab-Halte im Parlament.

Abnahme: Mit der Tabulatortaste durch /parlament/ — kein Tab-Halt hat Breite oder Höhe 0, in Desktop
(1440×900) und Handy (390×844). Geprüft je mit und ohne JavaScript, als Gast und als Mitglied. Ein
Halt ohne Fläche zeigt keinen Fokus, Enter löst dort eine Handlung an einem unsichtbaren Element aus."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

DESKTOP = {"width": 1440, "height": 900}
HANDY = {"width": 390, "height": 844}
HOECHSTENS = 500  # Tab-Schritte; das Parlament der Demo-Daten hat deutlich weniger Halte

HALT = """() => {
    const e = document.activeElement;
    if (!e || e === document.body || e === document.documentElement) return null;
    const r = e.getBoundingClientRect();
    const s = getComputedStyle(e);
    const name = e.tagName.toLowerCase() + (e.id ? '#' + e.id : '') + '.' + String(e.className).trim().split(/\\s+/).join('.');
    const text = (e.textContent || e.getAttribute('aria-label') || '').trim().slice(0, 24);
    // Eine stabile Kennung je Element, um den Rundlauf zu erkennen
    if (!e.dataset.sondeNr) e.dataset.sondeNr = String(++window.__sondeZaehler || (window.__sondeZaehler = 1));
    return {nr: e.dataset.sondeNr, name, text, b: r.width, h: r.height,
            unsichtbar: s.visibility === 'hidden' || s.display === 'none'};
}"""


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _flaechenlose_halte(p, js: bool) -> list[str]:
    funde, gesehen = [], set()
    for _ in range(HOECHSTENS):
        p.keyboard.press("Tab")
        if js:
            # Menschliches Tempo: Alpine zeigt und verbirgt (x-show) erst im nächsten Bild — kein Mensch
            # drückt zweimal Tab, bevor ein Bild gezeichnet ist
            p.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")
        halt = p.evaluate(HALT)
        if halt is None:
            continue  # zurück auf der Seite selbst (Adressleiste) — weiter, bis der Rundlauf schließt
        if halt["nr"] in gesehen:
            break  # einmal rundherum
        gesehen.add(halt["nr"])
        if halt["b"] == 0 or halt["h"] == 0 or halt["unsichtbar"]:
            funde.append(f'{halt["name"]} „{halt["text"]}“ {halt["b"]:.1f}×{halt["h"]:.1f}')
    else:
        pytest.fail(f"Der Rundlauf schloss nicht nach {HOECHSTENS} Tab-Schritten")
    assert gesehen, "die Seite hat Tab-Halte"
    return funde


@pytest.mark.parametrize("angemeldet", [False, True], ids=["gast", "mitglied"])
@pytest.mark.parametrize("js", [True, False], ids=["mit-js", "ohne-js"])
@pytest.mark.parametrize("viewport", [DESKTOP, HANDY], ids=["desktop", "handy"])
def test_gp171_kein_tab_halt_ohne_flaeche_im_parlament(seite, live_server, demo, viewport, js, angemeldet):
    p = seite(viewport=viewport, js=js, reduziert=True, als=_mitglied() if angemeldet else None)
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_load_state("load")
    p.wait_for_timeout(300)
    funde = _flaechenlose_halte(p, js)
    assert funde == [], f"Tab-Halte ohne Fläche: {funde}"
