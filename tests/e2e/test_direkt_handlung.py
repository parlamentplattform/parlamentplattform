"""Bildschirmtests der Direkt-Handlung aus der Feed-Zeile (Befunde B1/B2, FB-A2).

Mit JavaScript: Klick „Unterstützen“ tauscht nur das Feld — das Feld bleibt, der Knopf zeigt
„✓ Unterstützt“, der Gold-Haken „Erfasst“ erscheint, der Hinweis steht im Feldkopf und der
Fokus liegt wieder auf dem Knopf. Ohne JavaScript: derselbe Klick führt ins Parlament mit dem
Hinweis im Feld. Fokusring und Auswahl sind unterscheidbar (WCAG 1.4.1), auch bei
reduzierter Bewegung bleibt der Haken sichtbar."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


def _mitglied(name="demo3"):
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username=name)


def _sammelnder_antrag():
    from verfahren.models import Antrag

    return Antrag.objects.filter(phase="unterstuetzung").order_by("pk").first()


def _ruhe(p):
    p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")


def test_unterstuetzen_mit_javascript_tauscht_nur_das_feld(seite, live_server, demo):
    antrag = _sammelnder_antrag()
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.evaluate("document.querySelector('.parlament').dataset.probe = 'unveraendert'")
    knopf = p.locator(f"#u-filter-{antrag.pk}")
    assert knopf.inner_text().strip() == "Unterstützen"
    knopf.click()
    p.wait_for_selector(f"#u-filter-{antrag.pk}.gewaehlt")
    assert p.evaluate("document.querySelector('.parlament').dataset.probe") == "unveraendert", "die Seite lädt nicht neu"
    assert p.locator("#feld-filter").count() == 1, "das Feld bleibt stehen"
    assert "Unterstützt" in p.locator(f"#u-filter-{antrag.pk}").inner_text()
    assert p.locator(f"#u-filter-{antrag.pk}").get_attribute("aria-pressed") == "true"
    hinweis = p.locator("#feld-filter .feld-hinweis")
    assert hinweis.is_visible() and "Unterstützung erfasst." in hinweis.inner_text()
    assert hinweis.get_attribute("role") == "status"
    # Gold-Haken „Erfasst“ in der neuen Zeile desselben Antrags (FB-A2)
    p.wait_for_selector(f'.fz[data-antrag="{antrag.pk}"].erfasst', timeout=2000)
    assert p.locator(f'.fz[data-antrag="{antrag.pk}"] .k-erfasst').is_visible()
    # Fokus liegt wieder auf dem Knopf
    assert p.evaluate("document.activeElement && document.activeElement.id") == f"u-filter-{antrag.pk}"
    assert "/parlament/" in p.url and "hinweis=" not in p.url  # htmx schreibt keine Adresse
    assert p.locator(".meldung").count() == 0, "keine Flash-Meldung"

    # Zurückziehen — der Hinweis wechselt, der Haken erscheint erneut
    p.locator(f"#u-filter-{antrag.pk}").click()
    p.wait_for_selector(f"#u-filter-{antrag.pk}:not(.gewaehlt)")
    assert "Unterstützung zurückgezogen." in p.locator("#feld-filter .feld-hinweis").inner_text()


def test_unterstuetzen_ohne_javascript_landet_im_feld_mit_hinweis(seite, live_server, demo):
    antrag = _sammelnder_antrag()
    p = seite(js=False, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_timeout(800)  # ohne JavaScript kein getAnimations() — die Auftauch-Bewegung abwarten
    p.locator(f"#u-filter-{antrag.pk}").click()
    p.wait_for_load_state()
    assert p.url.endswith("/parlament/?hinweis=erfasst&feld=filter#feld-filter")
    hinweis = p.locator("#feld-filter .feld-hinweis")
    assert hinweis.is_visible() and "Unterstützung erfasst." in hinweis.inner_text()
    assert "Unterstützt" in p.locator(f"#u-filter-{antrag.pk}").inner_text()
    assert p.locator(".meldung").count() == 0


def test_gesperrtes_mitglied_sieht_zustand_statt_knoepfen(seite, live_server, demo):
    from mitglieder.models import Mitgliedsstatus

    antrag = _sammelnder_antrag()
    person = _mitglied("demo4")
    person.status = Mitgliedsstatus.PAUSIERT
    person.save(update_fields=["status"])
    p = seite(als=person)
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    assert p.locator(f"#u-filter-{antrag.pk}").count() == 0
    zeile = p.locator(f'#feld-filter .fz[data-antrag="{antrag.pk}"] .sperre')
    assert zeile.is_visible() and "Mitwirkung ruht" in zeile.inner_text()
    assert zeile.locator("a").get_attribute("href").endswith("/willkommen/")


@pytest.mark.parametrize("dunkel", [False, True], ids=["hell", "dunkel"])
def test_fokusring_und_auswahl_sind_unterscheidbar(seite, live_server, demo, dunkel):
    antrag = _sammelnder_antrag()
    p = seite(als=_mitglied(), dunkel=dunkel)
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    knopf = p.locator(f"#u-filter-{antrag.pk}")
    knopf.focus()
    p.keyboard.press("Tab")
    p.keyboard.press("Shift+Tab")  # Tastaturfokus → :focus-visible
    ring = p.evaluate(
        "(id) => { const s = getComputedStyle(document.getElementById(id)); return s.outlineStyle + ' ' + s.outlineWidth + ' ' + s.outlineColor; }",
        f"u-filter-{antrag.pk}",
    )
    fokus, deep, gold = p.evaluate(
        "['--fokus', '--deep', '--gold'].map(n => getComputedStyle(document.documentElement).getPropertyValue(n).trim())"
    )
    assert ring.startswith("solid 2px"), ring
    assert fokus == (gold if dunkel else deep), (fokus, deep, gold)  # Petrol auf Hell, Gold auf Dunkel
    # Auswahl: gefüllter Knopf, kein Outline — Fokus und Auswahl sehen verschieden aus
    knopf.click()
    p.wait_for_selector(f"#u-filter-{antrag.pk}.gewaehlt")
    p.locator("#h-filter").click()  # Fokus weg
    stil = p.evaluate(
        "(id) => { const s = getComputedStyle(document.getElementById(id)); return [s.outlineStyle, s.backgroundColor]; }",
        f"u-filter-{antrag.pk}",
    )
    assert stil[0] == "none" and stil[1] not in ("rgba(0, 0, 0, 0)", "transparent"), stil


def test_haken_bleibt_bei_reduzierter_bewegung_sichtbar(seite, live_server, demo):
    antrag = _sammelnder_antrag()
    p = seite(als=_mitglied(), reduziert=True)
    p.goto(f"{live_server.url}/parlament/")
    p.locator(f"#u-filter-{antrag.pk}").click()
    p.wait_for_selector(f'.fz[data-antrag="{antrag.pk}"].erfasst', timeout=2000)
    haken = p.locator(f'.fz[data-antrag="{antrag.pk}"] .k-erfasst')
    assert haken.is_visible()
    assert p.evaluate("(el) => getComputedStyle(el).opacity", haken.element_handle()) == "1"
