"""Bildschirmtests des App-Gefühls im Desktop-Browser (Teil 7): Fokus-Modus je Feld (⤢/⤡, Esc,
sessionStorage, ohne JavaScript ?fokus=), keine Tastenkürzel außer Esc, keine Seiten-Scrollbalken mit
klebenden Feldköpfen, App-Manifest samt Symbolen erreichbar."""

from __future__ import annotations

import json

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

FELDER = ("filter", "favoriten", "wichtig", "region")


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _ruhe(p):
    p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")


def _sichtbare(p) -> list[str]:
    return [f for f in FELDER if p.locator(f"#feld-{f}").is_visible()]


def test_fokus_knopf_dehnt_ein_feld_esc_stellt_das_raster_wieder_her(seite, live_server, demo):
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    assert _sichtbare(p) == list(FELDER)
    raster = p.locator(".parlament").bounding_box()
    p.locator("#feld-filter .fokus-knopf").click()
    _ruhe(p)
    assert _sichtbare(p) == ["filter"]
    assert "fokus-filter" in (p.locator(".parlament").get_attribute("class") or "")
    feld = p.locator("#feld-filter").bounding_box()
    assert feld["width"] >= raster["width"] - 26 and feld["height"] >= raster["height"] - 26, "das Feld füllt das Raster"
    knopf = p.locator("#feld-filter .fokus-knopf")
    assert knopf.get_attribute("aria-label") == "Alle Felder zeigen" and knopf.inner_text().strip() == "⤡"
    assert p.evaluate("document.documentElement.scrollHeight <= window.innerHeight + 1"), "kein Seiten-Scroll"
    assert p.evaluate("sessionStorage.getItem('ddoe.fokus')") == "filter"
    # Der Zustand überlebt ein Neuladen (sessionStorage je Sitzung)
    p.reload()
    _ruhe(p)
    assert _sichtbare(p) == ["filter"]
    p.keyboard.press("Escape")
    _ruhe(p)
    assert _sichtbare(p) == list(FELDER)
    assert p.evaluate("sessionStorage.getItem('ddoe.fokus')") is None
    assert p.locator("#feld-filter .fokus-knopf").get_attribute("aria-label") == "Feld vergrößern"
    # Der Knopf ⤡ führt ebenfalls zurück
    p.locator("#feld-favoriten .fokus-knopf").click()
    _ruhe(p)
    assert _sichtbare(p) == ["favoriten"]
    p.locator("#feld-favoriten .fokus-knopf").click()
    _ruhe(p)
    assert _sichtbare(p) == list(FELDER)
    assert "/parlament/" in p.url and "fokus=" not in p.url


@pytest.mark.parametrize("weg", ["esc", "knopf"])
def test_fokus_aus_der_adresse_mit_javascript_verlassen_stellt_das_raster_her(seite, live_server, demo, weg):
    """?fokus= rendert die Klassen serverseitig; Esc oder ⤡ muss sie wieder abnehmen (Lesezeichen,
    geteilter Link, ⤢ in neuem Tab — jeweils mit JavaScript)."""
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/?fokus=wichtig")
    _ruhe(p)
    assert _sichtbare(p) == ["wichtig"]
    if weg == "esc":
        p.locator("#feld-wichtig .feld-korpus").focus()
        p.keyboard.press("Escape")
    else:
        p.locator("#feld-wichtig .fokus-knopf").click()
    _ruhe(p)
    assert _sichtbare(p) == list(FELDER)
    klasse = p.locator(".parlament").get_attribute("class").split()
    assert "fokus" not in klasse and "fokus-wichtig" not in klasse, klasse
    spalten = p.evaluate("getComputedStyle(document.querySelector('.parlament')).gridTemplateColumns")
    assert len(spalten.split()) == 2, spalten
    assert p.locator("#feld-filter").bounding_box()["height"] > 100


def test_am_handy_gibt_es_keinen_fokus_modus(seite, live_server, demo):
    """Unter 760 px ist jedes Feld ein Bildschirm und der Knopf ⤢/⤡ fehlt: Wer auf dem Desktop fokussiert
    und dann dreht oder verkleinert, sieht wieder alle Felder; ohne JavaScript wirkt ?fokus= dort nicht."""
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.locator("#feld-filter .fokus-knopf").click()
    _ruhe(p)
    assert _sichtbare(p) == ["filter"]
    p.set_viewport_size({"width": 390, "height": 844})
    p.wait_for_function("() => !document.querySelector('.parlament').classList.contains('fokus')")
    assert _sichtbare(p) == list(FELDER)
    assert p.evaluate("sessionStorage.getItem('ddoe.fokus')") is None
    g = seite(js=False, viewport={"width": 390, "height": 844})
    g.goto(f"{live_server.url}/parlament/?fokus=wichtig")
    g.wait_for_timeout(600)
    assert _sichtbare(g) == list(FELDER)


def test_ohne_javascript_rendert_fokus_ein_feld_und_der_link_fuehrt_zurueck(seite, live_server, demo):
    p = seite(js=False)
    p.goto(f"{live_server.url}/parlament/?fokus=wichtig")
    p.wait_for_timeout(800)
    assert _sichtbare(p) == ["wichtig"]
    raster = p.locator(".parlament").bounding_box()
    feld = p.locator("#feld-wichtig").bounding_box()
    assert feld["width"] >= raster["width"] - 26
    assert p.locator("#feld-wichtig .fokus-knopf").get_attribute("href") == "/parlament/#feld-wichtig"
    with p.expect_navigation():
        p.locator("#feld-wichtig .fokus-knopf").click()
    assert "fokus=" not in p.url
    assert _sichtbare(p) == list(FELDER)
    # und hinein per Link
    assert p.locator("#feld-region .fokus-knopf").get_attribute("href") == "/parlament/?fokus=region"
    p.goto(f"{live_server.url}/parlament/?fokus=region")
    p.wait_for_timeout(500)
    assert _sichtbare(p) == ["region"]


def test_keine_tastenkuerzel_alt_ziffer_und_fragezeichen_bleiben_beim_tippen(seite, live_server, demo):
    """Entscheidung des Gründers 29.9.2026: keine Tastenkürzel im Fokus-Modus. Alt+Ziffer (am Mac ⌥2 = “,
    unter Windows Alt-Codes) und „?“ gehören dem Browser und dem Textfeld; Esc bleibt."""
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    assert p.locator("#tastenhilfe").count() == 0
    feld = p.locator("#feld-favoriten .feld-suche input")
    feld.focus()
    p.keyboard.type("abc")
    p.keyboard.press("Alt+2")
    p.wait_for_timeout(100)
    assert p.evaluate("document.activeElement.tagName") == "INPUT"
    abgefangen = p.evaluate("""() => {
      const i = document.querySelector('#feld-favoriten .feld-suche input'), k = document.querySelector('#feld-wichtig .feld-korpus');
      const mac = new KeyboardEvent('keydown', {key: '\u201c', code: 'Digit2', altKey: true, cancelable: true, bubbles: true});
      i.focus(); i.dispatchEvent(mac);
      const frage = new KeyboardEvent('keydown', {key: '?', cancelable: true, bubbles: true});
      k.focus(); k.dispatchEvent(frage);
      return [mac.defaultPrevented, frage.defaultPrevented, document.activeElement === k]; }""")
    assert abgefangen == [False, False, True], abgefangen
    assert _sichtbare(p) == list(FELDER)


def test_feldkoepfe_bleiben_beim_rollen_stehen_ohne_seiten_scroll(seite, live_server, demo):
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    kopf_vorher = p.locator("#feld-filter .feld-kopf").bounding_box()
    p.evaluate("document.querySelector('#feld-filter .feld-korpus').scrollTop = 400")
    p.wait_for_timeout(100)
    kopf_nachher = p.locator("#feld-filter .feld-kopf").bounding_box()
    assert kopf_vorher["y"] == kopf_nachher["y"], "der Feldkopf bleibt stehen, nur der Körper rollt"
    assert p.evaluate("getComputedStyle(document.body).overflow") == "hidden"
    assert p.evaluate("getComputedStyle(document.querySelector('#feld-filter .feld-korpus')).scrollbarWidth") == "thin"
    assert p.evaluate("document.documentElement.scrollHeight <= window.innerHeight + 1")


def test_app_manifest_und_symbole_erreichbar(seite, live_server, demo):
    p = seite()
    p.goto(f"{live_server.url}/parlament/")
    href = p.locator('link[rel="manifest"]').get_attribute("href")
    assert href == "/static/verfahren/app.webmanifest"
    antwort = p.request.get(f"{live_server.url}{href}")
    assert antwort.status == 200
    assert antwort.headers.get("content-type", "").startswith("application/manifest+json")
    manifest = json.loads(antwort.text())
    assert manifest["start_url"] == "/parlament/" and manifest["display"] == "standalone"
    for symbol in manifest["icons"]:
        bild = p.request.get(f"{live_server.url}{symbol['src']}")
        assert bild.status == 200 and bild.headers.get("content-type", "").startswith("image/png"), symbol
    assert p.locator('meta[name="theme-color"]').count() == 2
    assert p.evaluate("'serviceWorker' in navigator && navigator.serviceWorker.controller") in (None, False)
