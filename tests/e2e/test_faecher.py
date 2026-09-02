"""Bildschirmtests des Favoriten-Fächers (FB-C1–C4): fünf Ebenen ohne Überlappung, Hover
entfaltet den Ast und färbt den Faden, Klick zoomt hinein, ab Tiefe 3 sitzt der Anker in der
Mitte, ohne JavaScript bleibt alles bedienbar, am Handy rollt der Fächer waagrecht, der Stern
tauscht nur sich selbst."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}
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


def test_klick_zoomt_hinein_und_ab_tiefe_drei_sitzt_der_anker_in_der_mitte(seite, live_server, demo):
    p = seite()
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    saeule = p.locator("#feld-favoriten .fknoten.kind a").first
    name = saeule.get_attribute("title")
    saeule.click()
    _anker_heisst(p, name)
    _ruhe(p)
    assert p.locator("#feld-favoriten .brot").inner_text().startswith("Lebensbereiche")
    bereich = p.locator("#feld-favoriten .fknoten.kind a").first
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
    saeule = fach.locator(".fknoten.kind a").first
    name = saeule.get_attribute("title")
    saeule.click()
    p.wait_for_load_state()
    assert "?fach=" in p.url
    assert p.locator("#feld-favoriten .fknoten.anker .fname").inner_text().strip() == name


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
