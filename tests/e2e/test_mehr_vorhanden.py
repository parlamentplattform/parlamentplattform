"""Bildschirmtests für „mehr vorhanden" (FB-A5) und die Regionsbänder (FB-E1): die Pille zählt,
was unter bzw. hinter der Sichtkante liegt, rollt beim Klick weiter und verschwindet am Ende."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _ruhe(p):
    p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")


def test_pille_zaehlt_verborgene_zeilen_und_rollt_weiter(seite, live_server, demo):
    p = seite()
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    pille = p.locator("#feld-filter .feld-mehr")
    pille.wait_for(state="visible")
    assert "weitere" in pille.inner_text() or "mehr" in pille.inner_text()
    assert "mehr-da" in (p.locator("#feld-filter").get_attribute("class") or "")
    vorher = p.evaluate("document.querySelector('#feld-filter .feld-korpus').scrollTop")
    pille.click()
    p.wait_for_function("(v) => document.querySelector('#feld-filter .feld-korpus').scrollTop > v", arg=vorher)
    # Bis ans Ende rollen: die Pille verschwindet
    p.evaluate("(() => { const k = document.querySelector('#feld-filter .feld-korpus'); k.scrollTop = k.scrollHeight; })()")
    pille.wait_for(state="hidden")
    # Das Favoriten-Feld hat keine Pille, die drei anderen Felder ohne Überlauf zeigen keine
    assert p.locator("#feld-favoriten .feld-mehr").count() == 0


def test_regionsband_wischt_ab_der_vierten_kachel(seite, live_server, demo):
    from verfahren.models import Verfahrensordnung, antrag_einbringen

    demo1 = _mitglied()
    ordnung = Verfahrensordnung.objects.filter(aktiv=True).first()
    vorhanden = demo1.wohnsitz.name if demo1.wohnsitz else "St. Marienkirchen an der Polsenz"
    for i in range(3):
        antrag_einbringen(demo1, f"Gemeindesache {i}", "Wortlaut.", "", ordnung, ebene="gemeinde", gebiet=vorhanden)
    p = seite(als=demo1)
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    band = p.locator("#feld-region .rband.r1")
    spur = band.locator(".spur")
    assert spur.locator(":scope > .kachel").count() >= 4
    masse = p.evaluate(
        "(() => { const s = document.querySelector('#feld-region .rband.r1 .spur'); return [s.scrollWidth, s.clientWidth]; })()"
    )
    assert masse[0] > masse[1]
    pille = band.locator(".spur-mehr")
    pille.wait_for(state="visible")
    assert "weitere" in pille.inner_text()
    pille.click()
    p.wait_for_function("() => document.querySelector('#feld-region .rband.r1 .spur').scrollLeft > 0")
    # Alle drei Bänder sind auf 1440×900 ohne senkrechtes Rollen sichtbar
    korpus = p.evaluate(
        "(() => { const k = document.querySelector('#feld-region .feld-korpus'); return [k.scrollHeight, k.clientHeight]; })()"
    )
    assert korpus[0] <= korpus[1] + 1
    for i in (1, 2, 3):
        assert p.locator(f"#feld-region .rband.r{i} .rkopf").is_visible()
