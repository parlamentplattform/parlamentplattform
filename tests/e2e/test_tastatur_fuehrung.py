"""E-43 Zeile 3 (GP-171, Variante a): Tastaturführung im Parlament.

(i) Rollt Enter auf der „mehr“-Pille das Feld weiter, springt der Fokus auf das erste neu sichtbare Ziel
statt mit der Pille zu verschwinden. (ii) Im Fächer folgen die Unterknoten eines Asts in der Tab-Folge direkt
auf ihren Ast — jeder Unterknoten ist per Tab erreichbar. Ohne JavaScript bleibt alles wie bisher bedienbar."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

DESKTOP = {"width": 1440, "height": 900}

FOKUS_IM_FELD = """(feld) => {
  const e = document.activeElement, k = document.querySelector(feld + ' .feld-korpus');
  if (!e || !k.contains(e)) return null;
  const r = e.getBoundingClientRect(), kr = k.getBoundingClientRect();
  return {sichtbar: r.top >= kr.top - 0.5 && r.bottom <= kr.top + k.clientHeight + 0.5 && r.width > 0 && r.height > 0,
          oben: r.top - kr.top + k.scrollTop};
}"""


def _bild(p):
    p.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


@pytest.mark.parametrize("reduziert", [True, False], ids=["reduziert", "bewegt"])
def test_e43_enter_auf_mehr_fuehrt_den_fokus_auf_das_erste_neu_sichtbare_ziel(seite, live_server, demo, reduziert):
    p = seite(viewport=DESKTOP, reduziert=reduziert)
    p.goto(f"{live_server.url}/parlament/")
    pille = p.locator("#feld-filter .feld-mehr")
    pille.wait_for(state="visible")
    kante = p.evaluate("(() => { const k = document.querySelector('#feld-filter .feld-korpus');"
                       " return k.scrollTop + k.clientHeight; })()")
    pille.focus()
    p.keyboard.press("Enter")
    p.wait_for_function("() => document.querySelector('#feld-filter .feld-korpus').scrollTop > 0")
    p.wait_for_timeout(900)  # die weiche Bewegung läuft aus
    fokus = p.evaluate(FOKUS_IM_FELD, "#feld-filter")
    assert fokus is not None, "der Fokus bleibt im Feld"
    assert fokus["sichtbar"], fokus
    assert fokus["oben"] >= kante - 2, (fokus, kante)  # vorher unter der Sichtkante

    # Am Ende des Feldes verschwindet die Pille — der Fokus geht mit ihr nicht verloren
    p.evaluate("(() => { const k = document.querySelector('#feld-filter .feld-korpus');"
               " k.scrollTop = k.scrollHeight - 1.5 * k.clientHeight; })()")
    pille.wait_for(state="visible")
    pille.focus()
    p.keyboard.press("Enter")
    pille.wait_for(state="hidden")
    p.wait_for_timeout(900)
    fokus = p.evaluate(FOKUS_IM_FELD, "#feld-filter")
    assert fokus is not None and fokus["sichtbar"], fokus
    # Tab geht von dort aus weiter durch das Feld
    p.keyboard.press("Tab")
    assert p.evaluate("document.activeElement !== document.body")


def _fknoten_per_tab(p, js: bool) -> set[str]:
    p.evaluate("document.querySelector('#feld-favoriten .fknoten.anker .stern, #feld-favoriten .fknoten.anker a')?.focus()")
    erreicht: set[str] = set()
    for _ in range(400):
        p.keyboard.press("Tab")
        if js:
            _bild(p)  # menschliches Tempo: Alpine zeigt den entfalteten Ast im nächsten Bild
        slug = p.evaluate("(() => { const k = document.activeElement?.closest('#feld-favoriten .fknoten');"
                          " return k ? k.dataset.slug : null; })()")
        if slug is None:
            break
        erreicht.add(slug)
    return erreicht


def test_e43_jeder_unterknoten_des_faechers_ist_per_tab_erreichbar(seite, live_server, demo):
    p = seite(viewport=DESKTOP, reduziert=True)
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_load_state("load")
    p.wait_for_timeout(300)
    alle = set(p.evaluate("Array.from(document.querySelectorAll('#feld-favoriten .fknoten')).map(k => k.dataset.slug)"))
    ast_knoten = set(p.evaluate(
        "Array.from(document.querySelectorAll('#feld-favoriten .fknoten[data-ast]')).map(k => k.dataset.slug)"
    ))
    aeste = set(p.evaluate(
        "Array.from(document.querySelectorAll('#feld-favoriten .fknoten[data-ast]')).map(k => k.dataset.ast)"
    ))
    assert len(aeste) >= 2 and ast_knoten, "die Demo-Daten haben mehrere entfaltbare Äste"
    anker = p.evaluate("document.querySelector('#feld-favoriten .fknoten.anker').dataset.slug")
    erreicht = _fknoten_per_tab(p, js=True) | {anker}
    assert ast_knoten <= erreicht, f"per Tab nicht erreichbar: {sorted(ast_knoten - erreicht)[:10]}"
    assert alle <= erreicht, f"per Tab nicht erreichbar: {sorted(alle - erreicht)[:10]}"


def test_e43_ohne_javascript_bleibt_der_faecher_wie_bisher_bedienbar(seite, live_server, demo):
    """Ohne JavaScript ist nur der Ruhe-Ast sichtbar; jeder sichtbare Knoten ist ein Link und per Tab erreichbar."""
    p = seite(viewport=DESKTOP, js=False)
    p.goto(f"{live_server.url}/parlament/")
    sichtbar = set(p.evaluate(
        "Array.from(document.querySelectorAll('#feld-favoriten .fknoten')).filter(k => k.offsetParent !== null)"
        ".filter(k => k.querySelector('a, button')).map(k => k.dataset.slug)"
    ))
    anker = p.evaluate("document.querySelector('#feld-favoriten .fknoten.anker').dataset.slug")
    erreicht = _fknoten_per_tab(p, js=False) | {anker}
    assert sichtbar and sichtbar <= erreicht, sorted(sichtbar - erreicht)[:10]
