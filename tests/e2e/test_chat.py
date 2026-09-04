"""Bildschirmtests des Chatsystems (FB-G1 bis G3): Senden ohne Neuladen, Antwort-Modus,
Zustimmen, Scroll-Gedächtnis über Seitenwechsel hinweg, Gesprächs-Panel von links."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}


def _mitglied(name="demo1"):
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username=name)


def _antrag():
    from verfahren.models import Antrag

    return Antrag.objects.filter(phase="beratung").first() or Antrag.objects.first()


def _ruhe(p):
    p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")


def _faden(demo=None):
    """Ein Wurzelbeitrag mit einer Antwort — die Grundlage für Faden und Gespräch."""
    from verfahren.chat import beitrag_schreiben

    antrag = _antrag()
    wurzel = beitrag_schreiben(antrag, _mitglied("demo2"), "Ich halte den Vorschlag für tragfähig.")
    beitrag_schreiben(antrag, _mitglied("demo1"), "Sehe ich auch so — mit einer Einschränkung.", wurzel)
    return antrag, wurzel


def test_senden_ohne_neuladen_und_antwort_modus(seite, live_server, demo):
    antrag, wurzel = _faden()
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    _ruhe(p)
    p.evaluate("document.querySelector('.antragsseite').dataset.probe = 'unveraendert'")
    vorher = p.locator(".blase").count()

    p.locator(".chatzeile textarea").fill("Ein Beitrag ohne Neuladen.")
    p.wait_for_timeout(300)  # das Feld wächst mit dem Text
    p.locator(".chatzeile button[type=submit]").click()
    p.wait_for_function("(n) => document.querySelectorAll('.blase').length > n", arg=vorher)
    assert p.evaluate("document.querySelector('.antragsseite').dataset.probe") == "unveraendert", "die Seite lädt nicht neu"
    assert p.locator(".chatzeile textarea").input_value() == "", "das Feld leert sich"
    assert "Ein Beitrag ohne Neuladen." in p.locator("#chat-faden").inner_text()

    # Antwort-Modus: Chip erscheint, die Antwort landet eingerückt unter dem Wurzelbeitrag
    _ruhe(p)  # der getauschte Faden blendet ein — erst danach steht der Knopf still
    p.locator(f'#k-{wurzel.pk} .blase-knopf:text("Antworten")').click()
    chip = p.locator(".antwort-chip")
    p.wait_for_selector(".antwort-chip", state="visible")
    assert "Mitglied" in chip.inner_text()
    p.locator(".chatzeile textarea").fill("Meine Antwort im Faden.")
    p.wait_for_timeout(300)
    p.locator(".chatzeile button[type=submit]").click()
    p.wait_for_function("() => document.body.innerText.includes('Meine Antwort im Faden.')")
    _ruhe(p)
    assert "Meine Antwort im Faden." in p.locator(".antworten").inner_text()
    assert not p.locator(".antwort-chip").is_visible(), "der Antwort-Modus endet nach dem Senden"


def test_zustimmen_und_zuruecknehmen(seite, live_server, demo):
    antrag, wurzel = _faden()
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    _ruhe(p)
    knopf = p.locator(f"#k-{wurzel.pk} .blase-knopf.zustimmen")
    assert knopf.get_attribute("aria-pressed") == "false"
    knopf.click()
    p.wait_for_function(
        "(id) => document.querySelector('#k-' + id + ' .blase-knopf.zustimmen')?.getAttribute('aria-pressed') === 'true'",
        arg=wurzel.pk,
    )
    assert "1" in p.locator(f"#k-{wurzel.pk} .blase-knopf.zustimmen").inner_text()
    p.locator(f"#k-{wurzel.pk} .blase-knopf.zustimmen").click()
    p.wait_for_function(
        "(id) => document.querySelector('#k-' + id + ' .blase-knopf.zustimmen')?.getAttribute('aria-pressed') === 'false'",
        arg=wurzel.pk,
    )


def test_scroll_gedaechtnis_ueberlebt_den_seitenwechsel(seite, live_server, demo):
    """FB-G2: Die Leiste steht wieder dort, wo man aufgehört hat zu lesen."""
    from verfahren.chat import beitrag_schreiben

    antrag, _wurzel = _faden()
    for i in range(25):
        beitrag_schreiben(antrag, _mitglied("demo2"), f"Beitrag Nummer {i} mit etwas Text zum Füllen der Seite.")
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    _ruhe(p)
    p.locator(".blase").nth(12).scroll_into_view_if_needed()  # mitten im Faden aufhören zu lesen
    p.wait_for_timeout(2600)  # das Gedächtnis merkt sich gedrosselt alle zwei Sekunden
    gemerkt = p.evaluate(f"JSON.parse(localStorage.getItem('ddoe.chat.{antrag.pk}') || 'null')")
    assert gemerkt and gemerkt["beitrag"], "die Stelle wird gemerkt"

    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_timeout(500)
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    _ruhe(p)
    p.wait_for_timeout(900)  # die Wiederherstellung zieht nach, bis das Layout steht
    oben = p.evaluate(
        "(id) => { const b = document.querySelector('.blase[data-beitrag=\"' + id + '\"]');"
        " return b ? Math.round(b.getBoundingClientRect().top) : null; }",
        gemerkt["beitrag"],
    )
    assert oben is not None and abs(oben - gemerkt["versatz"]) < 40, "die Stelle wird wiederhergestellt"


def test_gespraechspanel_gleitet_von_links(seite, live_server, demo):
    antrag, _wurzel = _faden()
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    griff = p.locator(".g-griff")
    assert griff.is_visible()
    kasten = griff.bounding_box()
    assert kasten["x"] < 30, "der Griff klebt am linken Rand"
    griff.click()
    p.wait_for_selector(".g-panel", state="visible")
    p.wait_for_function("() => document.querySelectorAll('.gz').length > 0")
    panel = p.locator(".g-panel").bounding_box()
    assert panel["x"] < 5, "das Panel kommt von links"
    zeile = p.locator(".gz").first
    assert antrag.titel[:20] in zeile.inner_text()
    assert p.locator(".g-schleier").is_visible()
    p.keyboard.press("Escape")
    p.wait_for_selector(".g-panel", state="hidden")
    assert p.evaluate("document.activeElement.classList.contains('g-griff')"), "der Fokus kehrt zum Griff zurück"


def test_ohne_javascript_bleibt_der_chat_bedienbar(seite, live_server, demo):
    antrag, wurzel = _faden()
    p = seite(js=False, als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    p.wait_for_timeout(600)
    assert p.locator(".blase").count() >= 2
    p.locator(".chatzeile textarea").fill("Auch ohne Skript geschrieben.")
    p.wait_for_timeout(300)
    p.locator(".chatzeile button[type=submit]").click()
    p.wait_for_load_state()
    assert "Auch ohne Skript geschrieben." in p.locator("#chat-faden").inner_text()
    # Der Griff ist ohne Skript ein Link auf die Gesprächsseite
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_timeout(400)
    p.locator(".g-griff").click()
    p.wait_for_load_state()
    assert "/gespraeche/" in p.url
    assert "Meine Gespräche" in p.locator("h1").inner_text()


def test_handy_hat_chats_in_der_tableiste(seite, live_server, demo):
    _faden()
    p = seite(viewport=HANDY, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    assert not p.locator(".g-griff").is_visible(), "am Handy kein Randgriff (D-G3)"
    tabs = p.locator(".tabs a")
    assert tabs.count() == 6
    p.locator(".tabs .tab-chats").click()
    p.wait_for_load_state()
    assert "/gespraeche/" in p.url


def test_panel_laedt_auch_auf_der_gespraechsseite(seite, live_server, demo):
    """Auf /gespraeche/ trug die Seitenliste dieselbe id wie die Liste im Panel; htmx traf
    darum die Seite statt des Panels, und das Panel blieb auf „Wird geladen …" stehen."""
    _faden()
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/gespraeche/")
    _ruhe(p)
    p.locator(".g-griff").click()
    p.wait_for_selector(".g-panel", state="visible")
    p.wait_for_function("() => document.querySelectorAll('.g-panel .gz').length > 0")
    assert "Wird geladen" not in p.locator(".g-panel").inner_text(), "das Panel füllt sich"
    assert p.locator(".g-panel .gz").count() >= 1
