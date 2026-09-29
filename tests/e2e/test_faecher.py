"""Bildschirmtests des Favoriten-Fächers (FB-C1–C4, Teil 7): fünf Ebenen ohne Überlappung, Hover
entfaltet den Ast und färbt den Faden, ein Klick lässt den Knoten zum Anker gleiten (FLIP) und
fächert seine Kinder auf, ab Tiefe 3 sitzt der Anker in der Mitte, der Fächer passt ins Feld
(zoom), reduzierte Bewegung tauscht sofort, ohne JavaScript bleibt alles bedienbar, am Handy
rollt der Fächer waagrecht, der Stern tauscht nur sich selbst."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}
KLEINER_DESKTOP = {"width": 1280, "height": 720}
FLIP_LAEUFT = "() => document.getAnimations().some(a => a.id === 'faecher-flip')"
KEIN_FLIP = "document.getAnimations().filter(a => a.id === 'faecher-flip').length"
FAECHER_MASSE = (
    "(() => { const k = document.querySelector('#feld-favoriten .feld-korpus'); const f = k.querySelector('.faecher');"
    " const kr = k.getBoundingClientRect(), fr = f.getBoundingClientRect();"
    " const pillen = Array.from(f.querySelectorAll('.fknoten:not(.geist)')).filter(e => e.offsetParent !== null)"
    "   .map(e => e.getBoundingClientRect());"
    " return { korpusOben: kr.top, korpusUnten: kr.bottom, faecherOben: fr.top, faecherUnten: fr.bottom,"
    "   rollt: k.scrollHeight > k.clientHeight + 1, zoom: f.style.zoom || '',"
    "   pillenOben: Math.min(...pillen.map(r => r.top)), pillenUnten: Math.max(...pillen.map(r => r.bottom)) }; })()"
)


def _fehler_sammeln(p) -> list[str]:
    fehler: list[str] = []
    p.on("console", lambda m: fehler.append(m.text) if m.type == "error" else None)
    p.on("pageerror", lambda e: fehler.append(str(e)))
    return fehler
SICHTBARE_KAESTEN = (
    "Array.from(document.querySelectorAll('#feld-favoriten .fknoten'))"
    ".filter(e => e.offsetParent !== null)"
    ".map(e => { const r = e.getBoundingClientRect(); return [r.left, r.top, r.right, r.bottom]; })"
)
SICHTBARE_ROLLEN = (
    "Array.from(document.querySelectorAll('#feld-favoriten .fknoten'))"
    ".filter(e => e.offsetParent !== null).map(e => e.className.split(' ')[1])"
)


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _ruhe(p):
    p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")


def _anker_heisst(p, name):
    p.wait_for_function(
        "(name) => (document.querySelector('#feld-favoriten .fknoten.anker .fname')?.textContent || '').trim() === name",
        arg=name,
    )


def test_fuenf_ebenen_ohne_ueberlappung_und_hover_faerbt_den_faden(seite, live_server, demo):
    p = seite()
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    fach = p.locator("#feld-favoriten .faecher")
    assert fach.locator(".fknoten.anker .fname").inner_text().strip() == "Lebensbereiche"
    assert fach.locator(".fknoten.kind").count() == 4
    assert fach.locator(".fknoten.enkel").count() == 12
    assert {"anker", "kind", "enkel", "urenkel", "ururenkel"} <= set(p.evaluate(SICHTBARE_ROLLEN))
    # Bildschirmprobe zur Rechenprobe (tests/test_faecher_layout.py): keine zwei sichtbaren Pillen überlappen
    kaesten = p.evaluate(SICHTBARE_KAESTEN)
    assert len(kaesten) >= 20
    for i in range(len(kaesten)):
        for j in range(i + 1, len(kaesten)):
            a, b = kaesten[i], kaesten[j]
            frei = a[2] <= b[0] + 1 or b[2] <= a[0] + 1 or a[3] <= b[1] + 1 or b[3] <= a[1] + 1
            assert frei, (a, b)
    # Der Fächer füllt das Feld, ohne dass es rollt
    masse = p.evaluate(
        "(() => { const k = document.querySelector('#feld-favoriten .feld-korpus');"
        " return [k.scrollHeight, k.clientHeight]; })()"
    )
    assert masse[0] <= masse[1] + 1
    # Hover auf einen Bereich: sein Ast entfaltet sich, der Faden bis zur Wurzel wird gold
    ziel = fach.locator(".fknoten.enkel").nth(6)
    slug = ziel.get_attribute("data-slug")
    ziel.hover()
    p.wait_for_timeout(250)
    assert fach.locator(".faden.an").count() >= 2
    assert fach.locator(f'.fknoten[data-ast="{slug}"]').first.is_visible()
    assert p.evaluate("Alpine.$data(document.querySelector('#feld-favoriten .faecher')).ast") == slug


def test_klick_laesst_den_knoten_zum_anker_gleiten_und_ab_tiefe_drei_sitzt_der_anker_in_der_mitte(seite, live_server, demo):
    p = seite()
    fehler = _fehler_sammeln(p)
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.evaluate("document.querySelector('.parlament').dataset.probe = 'unveraendert'")
    saeule = p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first
    name = saeule.get_attribute("title")
    slug = saeule.locator("..").get_attribute("data-slug")
    vorher = saeule.locator("..").bounding_box()
    saeule.click()
    # FLIP (Teil 7): der geklickte Knoten gleitet als gemeinsamer Knoten an seine neue Stelle — der Anker unten
    p.wait_for_function(FLIP_LAEUFT)
    _anker_heisst(p, name)
    assert p.locator("#feld-favoriten .faecher.getauscht").count() == 1, "keine zweite Eingangsbewegung"
    _ruhe(p)
    assert p.evaluate("document.querySelector('.parlament').dataset.probe") == "unveraendert", "nur das Feld tauscht"
    anker = p.locator(f'#feld-favoriten .fknoten.anker[data-slug="{slug}"]')
    assert anker.count() == 1
    nachher = anker.bounding_box()
    assert nachher["y"] > vorher["y"] + 40 and nachher["height"] > vorher["height"], "der Knoten steht nun unten als Anker, größer"
    assert p.locator("#feld-favoriten .fknoten.geist").count() == 0, "Geister der alten Knoten sind wieder weg"
    assert p.locator("#feld-favoriten .fknoten.htmx-request").count() == 0
    assert p.evaluate(KEIN_FLIP) == 0
    assert not fehler, fehler
    assert p.locator("#feld-favoriten .brot").inner_text().startswith("Lebensbereiche")
    bereich = p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first
    name2 = bereich.get_attribute("title")
    bereich.click()
    _anker_heisst(p, name2)
    _ruhe(p)
    fach = p.locator("#feld-favoriten .faecher")
    assert "mitte" in (fach.get_attribute("class") or "")
    weg = fach.locator(".fknoten.weg")
    assert weg.count() == 2  # Säule und Wurzel — der vollständige Rückweg
    anker = fach.locator(".fknoten.anker").bounding_box()
    assert all(weg.nth(i).bounding_box()["y"] > anker["y"] for i in range(2))
    korpus = p.locator("#feld-favoriten .feld-korpus").bounding_box()
    assert korpus["y"] < anker["y"] < korpus["y"] + korpus["height"]
    p.locator("#feld-favoriten .brot a").first.click()
    _anker_heisst(p, "Lebensbereiche")


def test_das_feld_blitzt_nach_dem_wechsel_nicht_neu_auf(seite, live_server, demo):
    """Nach der FLIP-Bewegung darf die Eingangsbewegung des Felds (CSS „auftauchen“, ab Deckkraft 0) nicht
    neu anlaufen — sonst verschwindet „Meine Favoriten“ eine halbe Sekunde nach jedem Wechsel und blendet neu ein."""
    p = seite()
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.evaluate(
        "() => { window.__deckkraft = []; const t0 = performance.now(); const mess = () => {"
        " const f = document.getElementById('feld-favoriten'); if (f) window.__deckkraft.push(+getComputedStyle(f).opacity);"
        " if (performance.now() - t0 < 1600) requestAnimationFrame(mess); }; requestAnimationFrame(mess); }"
    )
    p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first.click()
    p.wait_for_function(FLIP_LAEUFT)
    p.wait_for_timeout(1700)
    tiefst = p.evaluate("Math.min(...window.__deckkraft)")
    assert tiefst > 0.95, f"das Feld verschwand kurz (Deckkraft {tiefst})"


def test_ohne_javascript_bleibt_der_ruhe_ast_und_jeder_knoten_ein_link(seite, live_server, demo):
    p = seite(js=False)
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_timeout(800)
    fach = p.locator("#feld-favoriten .faecher")
    standard = (fach.get_attribute("x-data") or "").split("'")[1]
    assert standard and fach.locator(f'.fknoten[data-ast="{standard}"]').first.is_visible()
    andere = fach.locator(".fknoten[x-cloak]")
    assert andere.count() > 0 and not andere.first.is_visible()
    assert {"anker", "kind", "enkel", "urenkel", "ururenkel"} <= set(p.evaluate(SICHTBARE_ROLLEN))
    saeule = fach.locator(".fknoten.kind a[href^='?fach=']").first
    name = saeule.get_attribute("title")
    saeule.click()
    p.wait_for_load_state()
    assert "?fach=" in p.url
    assert p.locator("#feld-favoriten .fknoten.anker .fname").inner_text().strip() == name


def test_reduzierte_bewegung_tauscht_sofort_ohne_animation(seite, live_server, demo):
    p = seite(reduziert=True)
    fehler = _fehler_sammeln(p)
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_timeout(300)
    saeule = p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first
    name = saeule.get_attribute("title")
    saeule.click()
    _anker_heisst(p, name)
    assert p.evaluate(KEIN_FLIP) == 0, "reduzierte Bewegung: kein Gleiten"
    assert p.locator("#feld-favoriten .fknoten.geist").count() == 0
    p.wait_for_timeout(60)  # CSS-Bewegungen dauern bei reduzierter Bewegung 1 ms — danach ruht alles
    assert p.evaluate("document.getAnimations().every(a => a.playState !== 'running')")
    assert p.evaluate(KEIN_FLIP) == 0
    assert p.locator("#feld-favoriten .faecher.getauscht").count() == 1
    assert not fehler, fehler


@pytest.mark.parametrize("dunkel", [False, True], ids=["hell", "dunkel"])
def test_faecher_passt_ins_feld_auf_dem_desktop(seite, live_server, demo, dunkel):
    """Teil 7 (Einpassen): alle fünf Ebenen sichtbar, der Körper rollt nicht, die oberste Pille liegt im Feld —
    auf 1440×900 ohne Verkleinerung, auf 1280×720 mit `zoom` (nie unter 0,72)."""
    p = seite(dunkel=dunkel)
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    masse = p.evaluate(FAECHER_MASSE)
    assert not masse["rollt"] and masse["pillenOben"] >= masse["korpusOben"] - 0.5
    assert masse["pillenUnten"] <= masse["korpusUnten"] + 0.5
    assert {"anker", "kind", "enkel", "urenkel", "ururenkel"} <= set(p.evaluate(SICHTBARE_ROLLEN))

    klein = seite(viewport=KLEINER_DESKTOP, dunkel=dunkel)
    klein.goto(f"{live_server.url}/parlament/")
    _ruhe(klein)
    masse = klein.evaluate(FAECHER_MASSE)
    assert masse["zoom"] and 0.72 <= float(masse["zoom"]) < 1, masse
    assert not masse["rollt"], "der Fächer ist auf die Feldhöhe verkleinert, nichts ist abgeschnitten"
    assert masse["pillenOben"] >= masse["korpusOben"] - 0.5 and masse["pillenUnten"] <= masse["korpusUnten"] + 0.5
    assert masse["faecherOben"] >= masse["korpusOben"] - 0.5 and masse["faecherUnten"] <= masse["korpusUnten"] + 0.5
    assert {"anker", "kind", "enkel", "urenkel", "ururenkel"} <= set(klein.evaluate(SICHTBARE_ROLLEN))
    # keine zwei sichtbaren Pillen überlappen — auch verkleinert
    kaesten = klein.evaluate(SICHTBARE_KAESTEN)
    for i in range(len(kaesten)):
        for j in range(i + 1, len(kaesten)):
            a, b = kaesten[i], kaesten[j]
            assert a[2] <= b[0] + 1 or b[2] <= a[0] + 1 or a[3] <= b[1] + 1 or b[3] <= a[1] + 1, (a, b)
    # nach einem Wechsel in die Tiefe (Modus mitte, höherer Fächer) passt er weiterhin
    for _ in range(2):
        link = klein.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first
        name = link.get_attribute("title")
        link.click()
        _anker_heisst(klein, name)
        _ruhe(klein)
    masse = klein.evaluate(FAECHER_MASSE)
    assert "mitte" in (klein.locator("#feld-favoriten .faecher").get_attribute("class") or "")
    assert masse["zoom"] and float(masse["zoom"]) >= 0.72
    if float(masse["zoom"]) > 0.72:
        assert not masse["rollt"] and masse["pillenOben"] >= masse["korpusOben"] - 0.5
    else:
        # An der Untergrenze (Schrift bleibt lesbar) rollt der Körper von unten: Anker und Rückweg sichtbar
        anker = klein.locator("#feld-favoriten .fknoten.anker").bounding_box()
        assert masse["korpusOben"] < anker["y"] < anker["y"] + anker["height"] < masse["korpusUnten"]
        assert klein.locator("#feld-favoriten .fknoten.weg").last.is_visible()
    # Ohne JavaScript bleibt das heutige Rollen von unten (Anker zuerst sichtbar)
    ohne = seite(viewport=KLEINER_DESKTOP, js=False)
    ohne.goto(f"{live_server.url}/parlament/")
    ohne.wait_for_timeout(800)
    anker = ohne.locator("#feld-favoriten .fknoten.anker").bounding_box()
    korpus = ohne.locator("#feld-favoriten .feld-korpus").bounding_box()
    assert korpus["y"] < anker["y"] < korpus["y"] + korpus["height"]


def test_einpassen_nur_im_zwei_mal_zwei_raster(seite, live_server, demo):
    """Unter 1024 px (auch 1440×900 bei 200 % Browser-Zoom = 720×450) rollt der Feldkörper; der Fächer
    wird nicht verkleinert — sonst nähme das Einpassen die Vergrößerung teilweise zurück (WCAG 1.4.4)."""
    p = seite(viewport={"width": 720, "height": 450})
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.wait_for_timeout(200)
    assert p.evaluate("document.querySelector('#feld-favoriten .faecher').style.zoom") == ""
    p.set_viewport_size(KLEINER_DESKTOP)  # im 2×2-Raster wird eingepasst …
    p.wait_for_function("() => document.querySelector('#feld-favoriten .faecher').style.zoom !== ''")
    p.set_viewport_size({"width": 720, "height": 450})  # … und darunter wieder nicht
    p.wait_for_function("() => document.querySelector('#feld-favoriten .faecher').style.zoom === ''")


def test_handy_rollt_den_faecher_waagrecht(seite, live_server, demo):
    p = seite(viewport=HANDY)
    p.goto(f"{live_server.url}/parlament/#feld-favoriten")
    _ruhe(p)
    breite = p.evaluate(
        "(() => { const k = document.querySelector('#feld-favoriten .feld-korpus');"
        " return [k.scrollWidth, k.clientWidth]; })()"
    )
    assert breite[0] > breite[1] >= 300
    assert p.evaluate("getComputedStyle(document.querySelector('#feld-favoriten .fknoten.anker .fname')).fontSize") == "20px"


def test_stern_tauscht_nur_sich_selbst(seite, live_server, demo):
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.evaluate("document.querySelector('#feld-favoriten').dataset.probe = 'unveraendert'")
    stern = p.locator("#feld-favoriten .fknoten.kind .stern").first
    vorher = stern.get_attribute("aria-pressed")
    stern.click()
    p.wait_for_function(
        "(v) => document.querySelector('#feld-favoriten .fknoten.kind .stern')?.getAttribute('aria-pressed') !== v",
        arg=vorher,
    )
    assert p.evaluate("document.querySelector('#feld-favoriten').dataset.probe") == "unveraendert"  # kein Feldtausch
    assert "ist jetzt Favorit" not in p.content()  # keine Flash-Meldung


def test_fokus_bleibt_nach_faecher_und_brotkrumen_link_im_faecher(seite, live_server, demo):
    """Fächer- und Brotkrumen-Links tragen keine id, und der geklickte Knoten wird zum Anker (kein Link):
    Per Tastatur ausgelöst, landet der Fokus danach im neuen Fächer statt auf <body> (Befund B2)."""
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    im_faecher = "() => { const a = document.activeElement; return a !== document.body && !!a.closest('#feld-favoriten'); }"
    link = p.locator("#feld-favoriten .fknoten.kind > a[href^='?fach=']").first
    name = link.get_attribute("title")
    link.focus()
    p.keyboard.press("Enter")
    _anker_heisst(p, name)
    _ruhe(p)
    assert p.evaluate(im_faecher), p.evaluate("document.activeElement.tagName + '.' + document.activeElement.className")
    p.locator("#feld-favoriten .brot a").first.focus()
    p.keyboard.press("Enter")
    _anker_heisst(p, "Lebensbereiche")
    _ruhe(p)
    assert p.evaluate(im_faecher), p.evaluate("document.activeElement.tagName + '.' + document.activeElement.className")
