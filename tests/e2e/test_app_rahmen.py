"""Bildschirmtests des App-Rahmens (FB-A1 Abnahmen 1–4, Design-Spezifikation 8).

Geprüft wird, was sich nur im Browser zeigt: Höhen, Einrasten, Bewegung, Erscheinungsbild —
jeweils mit und ohne JavaScript, hell und dunkel, auf 1440×900 und 390×844.

Ohne JavaScript kann Playwright kein `evaluate` ausführen; solche Prüfungen laufen dort
über gemessene Kästen (`bounding_box`), was für die Abnahmen genügt.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}
TABLET = {"width": 900, "height": 1200}


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _hervorgehobener_antrag() -> int:
    from verfahren.models import Antrag

    return Antrag.objects.filter(hervorgehoben=True).first().pk


def _ruhe(p, js: bool = True) -> None:
    """Wartet, bis die Auftauch-Bewegung der Felder vorbei ist — erst dann stimmen die Maße."""
    if js:
        p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")
    else:
        p.wait_for_timeout(800)


def _felder(p) -> list[dict]:
    return [p.locator(f"#feld-{name}").bounding_box() for name in ("filter", "favoriten", "wichtig", "region")]


# ── Abnahme 1: Desktop ohne Seiten-Scroll, vier gleich große Felder ─────────────


@pytest.mark.parametrize("js", [True, False], ids=["mit-js", "ohne-js"])
@pytest.mark.parametrize("gast", [True, False], ids=["gast", "mitglied"])
def test_desktop_kein_seitenscroll_vier_gleiche_felder(seite, live_server, demo, js, gast):
    p = seite(js=js, als=None if gast else _mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p, js)
    kaesten = _felder(p)
    breiten = {round(k["width"]) for k in kaesten}
    hoehen = {round(k["height"]) for k in kaesten}
    assert max(breiten) - min(breiten) <= 1 and max(hoehen) - min(hoehen) <= 1, "Die vier Felder sind nicht gleich groß"
    assert max(k["y"] + k["height"] for k in kaesten) <= 900 + 1, "Das Raster reicht über den Bildschirm (FB-A1 Abnahme 1)"
    assert round(p.locator("header.leiste").bounding_box()["height"]) == 56
    if gast:
        assert round(p.locator(".band.gast").bounding_box()["height"]) == 32, "Gastband ist 32 px hoch (FB-A6)"
    else:
        assert p.locator(".band").count() == 0
    if js:
        assert p.evaluate("document.documentElement.scrollHeight <= window.innerHeight + 1")
        assert p.evaluate("getComputedStyle(document.body).overflow") == "hidden"


def test_tablet_bleibt_zweispaltig(seite, live_server, demo):
    p = seite(viewport=TABLET)
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    spalten = p.evaluate("getComputedStyle(document.querySelector('.parlament')).gridTemplateColumns")
    assert len(spalten.split()) == 2, "Auf dem Tablet bleiben zwei Spalten (Spec 3.2)"
    assert min(k["height"] for k in _felder(p)) >= 380 - 1


# ── Abnahme 2: Handy mit Einrasten und Tableiste ───────────────────────────────


@pytest.mark.parametrize("js", [True, False], ids=["mit-js", "ohne-js"])
def test_handy_snap_und_tableiste(seite, live_server, demo, js):
    p = seite(viewport=HANDY, js=js)
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p, js)
    tabs = p.locator("nav.tabs").bounding_box()
    assert round(tabs["height"]) == 60 and round(tabs["y"] + tabs["height"]) == 844, "Tableiste klebt unten (60 px)"
    plus = p.locator("nav.tabs a.plus span").bounding_box()
    assert abs((plus["x"] + plus["width"] / 2) - 195) <= 3, "Das ＋ sitzt mittig"
    assert round(plus["width"]) == 48 and plus["y"] < tabs["y"], "＋ ragt über die Leiste"
    assert round(p.locator("header.leiste").bounding_box()["height"]) == 52
    raster = p.locator(".parlament").bounding_box()
    erstes = p.locator("#feld-filter").bounding_box()
    # Das Feld füllt den Bildschirm bis auf den 8-px-Rand des Rasters
    assert erstes["height"] >= raster["height"] - 18, "Jedes Feld füllt den Bildschirm (Snap-Ansicht)"
    if js:
        assert "mandatory" in p.evaluate("getComputedStyle(document.querySelector('.parlament')).scrollSnapType")
        p.locator("nav.tabs a[href='#feld-favoriten']").click()
        p.wait_for_timeout(700)
        abstand = p.evaluate(
            "Math.abs(document.getElementById('feld-favoriten').getBoundingClientRect().top"
            " - document.querySelector('.parlament').getBoundingClientRect().top)"
        )
        assert abstand <= 10, "Das Feld rastet nicht bündig ein"


# ── Abnahme 3: Fußzeile nur außerhalb des Parlaments ───────────────────────────


@pytest.mark.parametrize("js", [True, False], ids=["mit-js", "ohne-js"])
def test_fusszeile_nur_ausserhalb_des_parlaments(seite, live_server, demo, js):
    antrag = _hervorgehobener_antrag()
    p = seite(js=js)
    p.goto(f"{live_server.url}/parlament/")
    assert p.locator("footer").count() == 0, "Das Parlament hat keine Fußzeile (FB-A1 Abnahme 3)"
    p.goto(f"{live_server.url}/antrag/{antrag}/")
    assert p.locator("footer").count() == 1
    p.goto(f"{live_server.url}/")
    assert p.locator("footer").count() == 1


# ── Menüs, Anstoß, Erscheinungsbild ────────────────────────────────────────────


def test_konto_popover_mit_escape_und_fokusrueckgabe(seite, live_server, demo):
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.locator(".konto > summary").click()
    pop = p.locator(".konto > .pop")
    assert pop.is_visible()
    p.wait_for_timeout(300)
    kasten = pop.bounding_box()
    assert kasten["y"] >= 56, "Das Popover öffnet unterhalb der Leiste"
    assert round(kasten["width"]) == 240
    p.keyboard.press("Escape")
    assert not pop.is_visible()
    assert p.evaluate("document.activeElement.classList.contains('avatar')"), "Fokus kehrt zum Avatar zurück"
    p.locator(".konto > summary").click()
    p.locator(".parlament").click(position={"x": 5, "y": 5})
    assert not pop.is_visible(), "Außenklick schließt das Popover"


def test_konto_popover_auch_ohne_javascript(seite, live_server, demo):
    p = seite(js=False, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.locator(".konto > summary").click()
    assert p.locator(".konto > .pop").is_visible(), "Ohne JavaScript öffnet das native details"
    assert p.locator(".konto .pop a[href='/beitrag/']").is_visible()
    assert p.locator(".konto form[action='/abmelden/'] button").is_visible()


def test_anstoss_popover_unter_der_leiste(seite, live_server, demo):
    p = seite()
    p.goto(f"{live_server.url}/parlament/")
    p.locator(".anstoss-leiste .anstoss-fleck > summary").click()
    karte = p.locator(".anstoss-karte")
    p.wait_for_timeout(300)
    kasten = karte.bounding_box()
    assert kasten["y"] >= 56 and round(kasten["width"]) == 340
    p.fill(".anstoss-karte textarea", "Aus dem Bildschirmtest.")
    p.click(".anstoss-karte button[type=submit]")
    p.wait_for_timeout(600)
    assert not karte.is_visible(), "Nach dem Senden schließt die Karte (HX-Trigger)"
    assert p.locator("#anstoss-blase").is_visible()


def test_anstoss_ohne_javascript_leitet_um(seite, live_server, demo):
    p = seite(js=False)
    p.goto(f"{live_server.url}/parlament/")
    p.locator(".anstoss-leiste .anstoss-fleck > summary").click()
    p.wait_for_timeout(800)  # die Karte blendet ein; ohne JavaScript kann nicht darauf gewartet werden
    p.fill(".anstoss-karte textarea", "Ohne JavaScript gesendet.")
    p.click(".anstoss-karte button[type=submit]")
    p.wait_for_load_state()
    assert "anstoss=danke" in p.url
    assert p.locator("#anstoss-blase").is_visible()


def test_burger_panel_gleitet_von_rechts(seite, live_server, demo):
    p = seite(viewport=HANDY)
    p.goto(f"{live_server.url}/parlament/")
    p.locator(".menue > summary").click()
    panel = p.locator(".panel")
    p.wait_for_timeout(500)  # das Panel gleitet in 320 ms herein
    kasten = panel.bounding_box()
    assert round(kasten["width"]) == round(390 * 0.84), "Panel ist 84 % breit"
    assert round(kasten["x"] + kasten["width"]) == 390, "Panel liegt am rechten Rand an"
    assert p.locator(".scrim").is_visible()
    assert p.locator(".panel nav.panel-nav a[href='/parlament/']").is_visible()
    p.keyboard.press("Escape")
    assert not panel.is_visible()


def test_thema_schalter_merkt_sich_die_wahl(seite, live_server, demo):
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.locator(".konto > summary").click()
    assert p.locator(".konto .thema").is_visible(), "Mit JavaScript erscheint die Schaltergruppe"
    p.locator(".konto .thema button", has_text="Dunkel").click()
    assert p.evaluate("document.documentElement.dataset.theme") == "dark"
    assert p.evaluate("localStorage.getItem('ddoe.thema')") == "dark"
    p.reload()
    assert p.evaluate("document.documentElement.dataset.theme") == "dark", "Die Wahl überlebt das Neuladen"
    assert p.evaluate("getComputedStyle(document.body).backgroundColor") == "rgb(12, 21, 30)"
    p.locator(".konto > summary").click()
    p.locator(".konto .thema button", has_text="System").click()
    assert p.evaluate("document.documentElement.dataset.theme") is None


def test_thema_schalter_ohne_javascript_verborgen(seite, live_server, demo):
    p = seite(js=False, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.locator(".konto > summary").click()
    assert not p.locator(".konto .thema").is_visible(), "Ohne JavaScript kein wirkungsloser Schalter"


def test_dunkles_thema_ohne_helle_flaechen(seite, live_server, demo):
    p = seite(dunkel=True)
    p.goto(f"{live_server.url}/parlament/")
    grund = p.evaluate("getComputedStyle(document.body).backgroundColor")
    assert grund == "rgb(12, 21, 30)", f"Dunkler Seitengrund erwartet, war {grund}"
    hell = p.evaluate(
        "[...document.querySelectorAll('.feld, .kachel, .leiste, .tabs, .band, .badge')]"
        ".map(e => getComputedStyle(e).backgroundColor)"
        ".filter(f => f === 'rgb(255, 255, 255)')"
    )
    assert not hell, "Im dunklen Thema bleibt keine Fläche weiß"


def test_reduzierte_bewegung_schaltet_animationen_ab(seite, live_server, demo):
    p = seite(reduziert=True)
    p.goto(f"{live_server.url}/parlament/")
    dauern = p.evaluate(
        "[...document.querySelectorAll('.feld, .kachel, .leiste, .band')].flatMap(e => "
        "[getComputedStyle(e).animationDuration, getComputedStyle(e).transitionDuration])"
        ".flatMap(w => w.split(',').map(x => parseFloat(x)))"
    )
    assert max(dauern) <= 0.001, f"Bewegung trotz reduzierter Einstellung: {dauern}"
    assert p.evaluate("getComputedStyle(document.documentElement).scrollBehavior") == "auto"


def _kontrast(a: list[float], b: list[float]) -> float:
    """Kontrastverhältnis nach WCAG 2.x aus zwei sRGB-Farben (0–255)."""
    def hell(rgb):
        lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in (x / 255 for x in rgb[:3])]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]
    x, y = hell(a), hell(b)
    return (max(x, y) + 0.05) / (min(x, y) + 0.05)


def _farbe(wert: str) -> list[float]:
    """„rgb(14, 76, 92)“ oder „#0E4C5C“ als Zahlen."""
    import re

    wert = wert.strip()
    if wert.startswith("#"):
        return [int(wert[i:i + 2], 16) for i in (1, 3, 5)]
    return [float(x) for x in re.findall(r"[\d.]+", wert)][:3]


_FOKUS_JS = """() => { const a = document.activeElement, s = getComputedStyle(a);
  return {fv: a.matches(':focus-visible'), ring: s.outlineColor, stil: s.outlineStyle}; }"""
_NACHT_JS = "['--night-1', '--night-2', '--night-3'].map(n => getComputedStyle(document.documentElement).getPropertyValue(n))"


@pytest.mark.parametrize("dunkel", [False, True], ids=["hell", "dunkel"])
def test_fokusring_auf_leiste_buehne_und_menue_mindestens_3_zu_1(seite, live_server, demo, dunkel):
    """WCAG 1.4.11: Die App-Leiste und die Bühne sind auch im hellen Modus nachtdunkel — dort trägt der
    Fokusring Gold; in den hellen Aufklappflächen der Leiste (Konto-Menü) bleibt er Petrol. Gemessen
    wird gegen den tatsächlichen Hintergrund (Verlauf der Nachttöne bzw. Fläche des Menüs)."""
    p = seite(als=_mitglied(), dunkel=dunkel)
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    nacht = [_farbe(n) for n in p.evaluate(_NACHT_JS)]
    p.locator(".leiste nav.haupt a").first.focus()
    p.keyboard.press("Tab")
    leiste = p.evaluate(_FOKUS_JS)
    assert leiste["fv"] and leiste["stil"] == "solid", leiste
    werte = [round(_kontrast(_farbe(leiste["ring"]), n), 2) for n in nacht]
    assert min(werte) >= 3, f"Fokusring in der Leiste: {leiste['ring']} gegen die Nachttöne {werte}"
    # Konto-Menü per Tastatur öffnen: der erste Link im hellen Popover
    p.locator(".konto > summary").focus()
    p.keyboard.press("Enter")
    p.keyboard.press("Tab")
    menue = p.evaluate(_FOKUS_JS)
    assert menue["fv"] and p.evaluate("!!document.activeElement.closest('.konto .pop')"), menue
    flaeche = p.evaluate("getComputedStyle(document.querySelector('.konto .pop')).backgroundColor")
    wert = round(_kontrast(_farbe(menue["ring"]), _farbe(flaeche)), 2)
    assert wert >= 3, f"Fokusring im Konto-Menü: {menue['ring']} gegen {flaeche} = {wert}"
    # Bühne der Startseite (Gäste)
    g = seite(dunkel=dunkel)
    g.goto(f"{live_server.url}/")
    _ruhe(g)
    g.locator(".held .wege a").first.focus()
    g.keyboard.press("Tab")
    held = g.evaluate(_FOKUS_JS)
    assert held["fv"] and g.evaluate("!!document.activeElement.closest('.held')"), held
    werte = [round(_kontrast(_farbe(held["ring"]), n), 2) for n in nacht]
    assert min(werte) >= 3, f"Fokusring auf der Bühne: {held['ring']} gegen die Nachttöne {werte}"


# ── Hauptnavigation zwischen 760 und 1279 px (Befund #48) ─────────────────────


@pytest.mark.parametrize("breite", [768, 1024, 1100, 1180, 1280])
@pytest.mark.parametrize("gast", [True, False], ids=["gast", "mitglied"])
def test_hauptnavigation_vollstaendig_oder_burger(seite, live_server, demo, breite, gast):
    """`overflow:hidden` schnitt die sechs Hauptpunkte zwischen 760 und 1279 px stumm ab — auf dem
    iPad hochkant sah ein Gast nur „Parlament“. Jetzt gilt: unter 1024 px der Burger mit allen
    sechs Punkten im Panel (Gäste: unter 1180 px, ihr rechter Block ist breiter), darüber alle
    sechs in der Leiste (lange Punkte in Kurzform)."""
    p = seite(viewport={"width": breite, "height": 900}, als=None if gast else _mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    burger = p.locator(".menue > summary")
    if breite < (1180 if gast else 1024):
        assert burger.is_visible(), "unter der Grenze steht der Burger"
        assert not p.locator("nav.haupt").is_visible()
        burger.click()
        p.wait_for_timeout(500)
        assert p.locator(".panel nav.panel-nav a").count() == 6
        if breite >= 760:
            # Konto bzw. Anmelden bleiben zwischen 760 und 1023 px in der Leiste
            assert p.locator(".leiste .konto, .leiste .anmelden").first.is_visible()
        return
    assert not burger.is_visible()
    nav = p.locator("nav.haupt")
    rahmen = nav.bounding_box()
    links = nav.locator("a")
    assert links.count() == 6
    for i in range(6):
        k = links.nth(i).bounding_box()
        assert k["x"] >= rahmen["x"] - 1 and k["x"] + k["width"] <= rahmen["x"] + rahmen["width"] + 1, (
            f"Punkt {i + 1} ist bei {breite} px abgeschnitten ({'Gast' if gast else 'Mitglied'})"
        )
    assert p.evaluate("(n) => n.scrollWidth <= n.clientWidth + 1", nav.element_handle()), "nichts rollt verborgen"
    kurz = p.locator("nav.haupt .kurz").first
    assert kurz.is_visible() == (breite < 1280), "Kurzformen nur zwischen 1024 und 1279 px"
