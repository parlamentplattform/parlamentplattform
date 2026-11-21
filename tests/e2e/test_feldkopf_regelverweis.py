"""Regelverweise im Feldkopf am Handy (GP-074; Gesamtprüfung 0.115.0, Fund in oberflaeche).

Die Verweise auf das Regelverzeichnis („nach Phase und Frist“, „Voreinstellung: neutral“ …) standen in
der Brotkrume `.bk`, die sich mit `overflow:hidden` und `white-space:nowrap` kürzt. Bei 390 Pixel Breite
blieben von „nach Phase und Frist“ 21 von 162 Pixel sichtbar, die Verweise waren 15 Pixel hoch.
Abnahme: Jeder sichtbare Verweis im Feldkopf liegt ganz in seiner Brotkrume und im Bild, die Brotkrume
läuft nicht über, und der Verweis ist mindestens 24 Pixel hoch. Am großen Bildschirm bleibt der Feldkopf
44 Pixel hoch."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}
DESKTOP = {"width": 1440, "height": 900}
MINDEST = 24

SONDE = """() => {
    const ergebnis = [];
    for (const a of document.querySelectorAll('.feld-kopf .bk a')) {
        if (a.closest('[hidden], [inert]')) continue;
        const bk = a.closest('.bk');
        const r = a.getBoundingClientRect(), b = bk.getBoundingClientRect();
        if (r.width === 0 || r.height === 0) continue;
        ergebnis.push({
            text: a.textContent.trim(),
            breite: r.width, hoehe: r.height,
            ganz_drin: r.left >= b.left - 0.5 && r.right <= b.right + 0.5 && r.right <= window.innerWidth + 0.5,
            ueberlauf: bk.scrollWidth > bk.clientWidth + 1,
        });
    }
    return ergebnis;
}"""


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


@pytest.mark.parametrize("angemeldet", [False, True], ids=["gast", "mitglied"])
def test_regelverweis_im_feldkopf_ist_am_handy_ganz_lesbar_und_antippbar(
    seite, live_server, demo, sichtpruefung, angemeldet
):
    p = seite(viewport=HANDY, reduziert=True, als=_mitglied() if angemeldet else None)
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_load_state("load")
    p.wait_for_timeout(300)
    for i, kopf in enumerate(p.locator(".feld-kopf").all()):
        if kopf.is_visible():
            kopf.evaluate("k => k.scrollIntoView({block: 'start'})")  # die Tableiste unten verdeckt sonst
            kopf.screenshot(path=str(sichtpruefung / f"feldkopf-handy-{'mitglied' if angemeldet else 'gast'}-{i}.png"))
    verweise = p.evaluate(SONDE)
    assert verweise, "Die Demo-Daten zeigen mindestens einen Regelverweis im Feldkopf"
    mangel = [
        f"„{v['text']}“ {v['breite']:.0f}×{v['hoehe']:.1f}"
        for v in verweise
        if not v["ganz_drin"] or v["ueberlauf"] or v["hoehe"] < MINDEST - 0.05
    ]
    assert mangel == [], f"Regelverweise abgeschnitten oder unter {MINDEST} Pixel hoch: {mangel}"


@pytest.mark.parametrize("angemeldet", [False, True], ids=["gast", "mitglied"])
def test_feldkopf_bleibt_am_grossen_bildschirm_44_pixel_hoch(seite, live_server, demo, angemeldet):
    p = seite(viewport=DESKTOP, reduziert=True, als=_mitglied() if angemeldet else None)
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_load_state("load")
    hoehen = p.evaluate(
        "() => [...document.querySelectorAll('.feld-kopf')].filter(k => !k.closest('[hidden]'))"
        ".map(k => k.getBoundingClientRect().height)"
    )
    assert hoehen and all(abs(h - 44) < 0.5 for h in hoehen), hoehen
