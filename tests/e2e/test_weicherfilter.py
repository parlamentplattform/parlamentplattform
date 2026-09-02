"""Bildschirmtests des WeicherFilters (FB-B2, B4, B5): Profil-Leiste mit Pfeil (gemerkt je Gerät),
Overlay von rechts mit Escape und Fokusrückgabe, Live-Vorschau mit „● Ungespeichert“ und
„Warum hier?“, ohne JavaScript bedienbar, am Handy füllt das Overlay das Feld."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _ruhe(p):
    p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")


def test_leiste_faehrt_ein_und_merkt_sich_das(seite, live_server, demo):
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    leiste = p.locator("#filter-leiste")
    assert leiste.bounding_box()["height"] >= 38
    pfeil = p.locator("#feld-filter .pfeil")
    assert pfeil.is_visible() and pfeil.get_attribute("aria-expanded") == "true"
    pfeil.click()
    p.wait_for_timeout(450)
    assert leiste.bounding_box()["height"] <= 16
    assert p.locator("#feld-filter .griff").is_visible()
    assert p.locator("#feld-filter .feld-kopf .bk").is_visible()  # der aktive Name bleibt lesbar
    p.reload()
    _ruhe(p)
    assert p.locator("#filter-leiste").bounding_box()["height"] <= 16  # je Gerät gemerkt
    p.locator("#feld-filter .griff").click()
    p.wait_for_timeout(450)
    assert p.locator("#filter-leiste").bounding_box()["height"] >= 38


def test_overlay_gleitet_von_rechts_und_escape_schliesst(seite, live_server, demo):
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.locator("#feld-filter .regler-klappe > summary").click()
    p.wait_for_timeout(450)
    overlay = p.locator("#feld-filter .regler-feld")
    assert overlay.is_visible() and overlay.get_attribute("role") == "dialog"
    feld = p.locator("#feld-filter").bounding_box()
    kasten = overlay.bounding_box()
    assert abs((kasten["x"] + kasten["width"]) - (feld["x"] + feld["width"])) < 3  # rechts bündig
    assert kasten["width"] <= 342
    assert p.locator("#filter-liste").is_visible()  # der Feed bleibt darunter sichtbar
    assert p.locator('#feld-filter button[name="speichern"]').is_disabled()  # Neutral: nichts zu speichern
    assert p.locator("#feld-filter .regler .regler, #feld-filter label.regler").count() == 9
    p.keyboard.press("Escape")
    p.wait_for_timeout(250)
    assert not overlay.is_visible()
    assert p.evaluate(
        "document.activeElement === document.querySelector('#feld-filter .regler-klappe > summary')"
    )
    # Regler-Symbol im Feldkopf öffnet ebenfalls
    p.locator("#feld-filter .feld-kopf .ikon").click()
    p.wait_for_timeout(450)
    assert overlay.is_visible()


def test_live_vorschau_ordnet_um_und_zeigt_ungespeichert(seite, live_server, demo):
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    vorher = p.locator("#filter-liste .fz .zt").all_inner_texts()
    assert vorher and p.locator("#filter-liste .warum").count() == 0
    p.locator("#feld-filter .regler-klappe > summary").click()
    p.wait_for_timeout(300)
    regler = p.locator('#feld-filter input[name="r_unterstuetzungsphase"]')
    regler.focus()
    p.keyboard.press("End")
    p.wait_for_function("() => document.querySelector('#filter-liste .warum') !== null")
    _ruhe(p)
    nachher = p.locator("#filter-liste .fz .zt").all_inner_texts()
    assert nachher[0] != vorher[0]  # Unterstützungsanträge stehen jetzt vorn
    assert p.locator("#feld-filter .regler-kopf .pkt").is_visible()  # ● Ungespeichert
    assert p.locator("#filter-leiste .chip.still").is_visible()
    p.keyboard.press("Escape")
    p.wait_for_timeout(250)
    p.locator("#filter-liste .warum > summary").first.click()
    p.wait_for_timeout(300)
    aufk = p.locator("#filter-liste .warum .aufk").first
    assert aufk.is_visible() and "Mehr Unterstützungsanträge" in aufk.inner_text()
    from verfahren.models import FilterProfil

    assert not FilterProfil.objects.filter(mitglied=_mitglied()).exists()  # Vorschau speichert nichts


def test_ohne_javascript_bleibt_der_filter_bedienbar(seite, live_server, demo):
    p = seite(js=False, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_timeout(800)
    assert p.locator("#filter-leiste").bounding_box()["height"] >= 38
    assert not p.locator("#feld-filter .pfeil").is_visible()  # nur mit JavaScript
    p.locator("#feld-filter .regler-klappe > summary").click()
    p.wait_for_timeout(500)  # das Overlay gleitet auch ohne Skript herein (CSS-Animation)
    assert p.locator("#feld-filter .regler-feld").is_visible()
    regler = p.locator('#feld-filter input[name="r_abstimmungen"]')
    regler.focus()  # Tastatur ±5 je Schritt — native Bedienung ohne Skript
    for _ in range(12):
        p.keyboard.press("ArrowRight")
    assert regler.input_value() == "60"
    p.wait_for_timeout(300)
    p.locator("#feld-filter .regler-aktionen .neu > summary").click()
    p.locator('#feld-filter input[name="profilname"]').fill("Ohne JS")
    p.locator('#feld-filter button[name="als_neues"]').click()
    p.wait_for_load_state()
    assert "profil: ohne js" in p.locator("#feld-filter .feld-kopf").inner_text().lower()  # Kapitälchen per CSS
    assert p.locator("#filter-liste .warum").count() >= 1


def test_handy_overlay_fuellt_das_feld(seite, live_server, demo):
    p = seite(viewport=HANDY, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/#feld-filter")
    _ruhe(p)
    p.locator("#feld-filter .regler-klappe > summary").click()
    p.wait_for_timeout(450)
    overlay = p.locator("#feld-filter .regler-feld").bounding_box()
    feld = p.locator("#feld-filter").bounding_box()
    assert abs(overlay["width"] - feld["width"]) < 4
