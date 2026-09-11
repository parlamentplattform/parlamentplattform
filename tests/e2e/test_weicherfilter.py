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


def test_eingefahrene_leiste_hat_keine_unsichtbaren_tab_stopps(seite, live_server, demo):
    """Befund #50: Eingefahren war die Leiste nur `opacity:0` — Neutral-Knopf, Profil-Chips,
    Regler und Pfeil blieben Tab-Stopps ohne sichtbaren Fokus, und Enter auf „Neutral“ stellte
    unbemerkt das Profil um (WCAG 2.4.7). Jetzt nehmen visibility:hidden und inert sie heraus."""
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.evaluate("localStorage.setItem('ddoe.filterleiste', 'zu')")
    p.reload()
    _ruhe(p)
    assert p.locator("#filter-leiste").bounding_box()["height"] <= 16
    innen = "#filter-leiste .innen"
    assert p.locator(innen).get_attribute("inert") is not None
    assert p.evaluate(f"getComputedStyle(document.querySelector('{innen}')).visibility") == "hidden"
    p.locator("#feld-filter .feld-kopf .ikon").focus()
    for _ in range(12):
        p.keyboard.press("Tab")
        assert not p.evaluate(f"!!document.activeElement.closest('{innen}')"), "kein Tab-Stopp in der eingefahrenen Leiste"
    assert p.locator("#feld-filter .griff").is_visible(), "der Griff bleibt der Weg zurück"
    p.locator("#feld-filter .griff").click()
    p.wait_for_timeout(450)
    assert p.locator(innen).get_attribute("inert") is None
    assert p.evaluate(f"getComputedStyle(document.querySelector('{innen}')).visibility") == "visible"


_KONTRAST = r"""(sel) => {
  const e = document.querySelector(sel);
  if (!e) return null;
  // rgb(a)-Tripel oder color(srgb …) aus color-mix — beides auf 0–255 bringen
  const parse = c => { const n = (c.match(/[\d.]+/g) || []).map(Number); return c.startsWith("color(") ? n.map(v => v * 255) : n; };
  const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4); };
  const lum = ([r, g, b]) => 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  let n = e, bg = getComputedStyle(e).backgroundColor;
  while (n && (parse(bg).length === 4 && parse(bg)[3] === 0)) { n = n.parentElement; if (n) bg = getComputedStyle(n).backgroundColor; }
  const l1 = lum(parse(getComputedStyle(e).color)), l2 = lum(parse(bg));
  return (Math.max(l1, l2) + 0.05) / (Math.min(l1, l2) + 0.05);
}"""


@pytest.mark.parametrize("dunkel", [False, True], ids=["hell", "dunkel"])
def test_kontrast_von_badge_unterstuetzt_anker_und_stern(seite, live_server, demo, dunkel):
    """Befund #49: Im Dunkelthema stand --bar-ink (Creme) auf --deep (helles Cyan) — 1,57:1 für
    das Beratungs-Badge und „✓ Unterstützt“. Befund #82: Beitrags-Anker (Link) und leerer Stern
    (Umschalter) lagen unter 2:1. WCAG 1.4.3 verlangt 4,5:1 für Text, 1.4.11 3:1 für Bedienelemente."""
    from verfahren.models import Antrag

    p = seite(dunkel=dunkel, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    assert p.evaluate(_KONTRAST, ".badge.b-beratung") >= 4.5
    assert p.evaluate(_KONTRAST, ".stern.aus") >= 3
    # „✓ Unterstützt“: demo1 unterstützt einen Antrag in der Unterstützungsphase
    antrag = Antrag.objects.filter(phase="unterstuetzung").first()
    antrag.unterstuetzungen.get_or_create(mitglied=_mitglied())
    p.reload()
    _ruhe(p)
    assert p.evaluate(_KONTRAST, ".knopf.gewaehlt") >= 4.5
    p.locator(".knopf").first.hover()
    p.wait_for_timeout(250)
    assert p.evaluate(_KONTRAST, ".knopf:hover") >= 4.5
    mit_chat = Antrag.objects.filter(kommentare__isnull=False).first()
    p.goto(f"{live_server.url}/antrag/{mit_chat.pk}/")
    _ruhe(p)
    assert p.evaluate(_KONTRAST, ".blase:not(.system) .blase-anker") >= 4.5
