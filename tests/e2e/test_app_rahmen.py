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
