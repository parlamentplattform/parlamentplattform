"""Bildschirmtests der Antragsseite in drei Zonen (FB-F1, FB-F2): Layout 58/42 mit klebender
Einschätzung, Reiterleiste mit Scroll-Spy, am Handy eine Zone mit Umschalten und Wischen,
ohne JavaScript alles untereinander."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _antrag(phase="beratung"):
    from verfahren.models import Antrag

    return Antrag.objects.filter(phase=phase).first() or Antrag.objects.first()


def _ruhe(p):
    p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")


def test_desktop_zwei_spalten_mit_klebender_einschaetzung(seite, live_server, demo):
    p = seite()
    p.goto(f"{live_server.url}/antrag/{_antrag().pk}/")
    _ruhe(p)
    text = p.locator(".z-text").bounding_box()
    schaetzung = p.locator(".z-einschaetzung").bounding_box()
    assert text["x"] < schaetzung["x"], "Text links, Einschätzung rechts"
    anteil = text["width"] / (text["width"] + schaetzung["width"])
    assert 0.54 < anteil < 0.62, f"58/42 erwartet, ist {anteil:.2f}"
    chat = p.locator(".z-chat").bounding_box()
    assert chat["y"] > text["y"] and chat["width"] > schaetzung["width"], "Chat unten über die volle Breite"
    # Beim Scrollen bleiben Reiterleiste und Einschätzung stehen
    vorher = p.locator(".z-einschaetzung").bounding_box()["y"]
    p.mouse.wheel(0, 600)
    p.wait_for_timeout(500)
    assert p.evaluate("window.scrollY") > 300
    leiste = p.locator(".zonenleiste").bounding_box()
    assert leiste["y"] < 100, "die Reiterleiste klebt unter der App-Leiste"
    nachher = p.locator(".z-einschaetzung").bounding_box()["y"]
    assert nachher > vorher - 600, "die Einschätzung klebt statt wegzuscrollen"


def test_scroll_spy_markiert_die_zone(seite, live_server, demo):
    p = seite()
    p.goto(f"{live_server.url}/antrag/{_antrag().pk}/")
    _ruhe(p)
    assert p.locator(".zreiter.an").inner_text().strip() == "Text"
    p.keyboard.press("End")  # ans Seitenende — dort liest man den Chat
    p.wait_for_function("() => (document.querySelector('.zreiter.an')?.textContent || '').indexOf('Chat') === 0")
    assert p.locator(".zreiter.an").inner_text().startswith("Chat")
    p.keyboard.press("Home")
    p.wait_for_function("() => (document.querySelector('.zreiter.an')?.textContent || '').trim() === 'Text'")


def test_handy_zeigt_eine_zone_und_schaltet_um(seite, live_server, demo):
    p = seite(viewport=HANDY)
    p.goto(f"{live_server.url}/antrag/{_antrag().pk}/")
    _ruhe(p)
    assert p.locator(".z-text").is_visible()
    assert not p.locator(".z-chat").is_visible(), "am Handy ist nur eine Zone sichtbar"
    breite = p.evaluate("[document.documentElement.scrollWidth, document.documentElement.clientWidth]")
    assert breite[0] <= breite[1] + 1, "kein waagrechter Überlauf"
    p.locator('.zreiter[href="#zone-chat"]').click()
    p.wait_for_timeout(300)
    assert p.locator(".z-chat").is_visible() and not p.locator(".z-text").is_visible()
    assert p.locator(".zreiter.an").inner_text().startswith("Chat")


def test_ohne_javascript_stehen_alle_zonen_untereinander(seite, live_server, demo):
    p = seite(js=False, viewport=HANDY)
    p.goto(f"{live_server.url}/antrag/{_antrag().pk}/")
    p.wait_for_timeout(600)
    for zone in (".z-text", ".z-einschaetzung", ".z-chat"):
        assert p.locator(zone).is_visible(), zone
    reiter = p.locator('.zreiter[href="#zone-chat"]')
    assert reiter.is_visible()
    reiter.click()  # gewöhnlicher Ankersprung
    p.wait_for_timeout(400)
    assert "#zone-chat" in p.url


def test_einschaetzung_zeigt_kennzeichnung_und_skelette(seite, live_server, demo):
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{_antrag().pk}/")
    _ruhe(p)
    kopf = p.locator(".kopfkarte")
    assert "Modellrechnung" in kopf.inner_text()
    assert p.locator(".skelett-karte").count() == 5
    p.locator(".beanstanden > summary").click()
    p.wait_for_timeout(200)
    assert p.locator('.beanstanden textarea[name="text"]').is_visible()
