"""GP-069 (ASR-20): „Mitreden“ in Kachel und Zeile führt auf die Chat-Zone der Antragsseite.

Abnahme: In vier Varianten (Desktop 1440×900 und Handy 390×844, je mit und ohne JavaScript) liegt
#zone-chat nach dem Klick auf „Mitreden“ im sichtbaren Fenster — und zwar so, dass ihre Überschrift
nicht unter der klebenden Kopfleiste oder der Zonenleiste liegt."""

from __future__ import annotations

import time

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

DESKTOP = {"width": 1440, "height": 900}
HANDY = {"width": 390, "height": 844}


def _beratung_hervorheben():
    """Ein Antrag in der Beratung als Kachel im Feld „Wichtige Abstimmungen“ — dort steht „Mitreden“."""
    from verfahren.models import Antrag

    antrag = Antrag.objects.filter(phase="beratung").order_by("pk").first()
    assert antrag is not None, "demo_seed legt einen Antrag in der Beratung an"
    Antrag.objects.filter(pk=antrag.pk).update(hervorgehoben=True, hervorhebung_begruendung="Test GP-069")
    return antrag


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _scrollruhe(p, frist=6.0):
    """Wartet, bis das weiche Scrollen (scroll-behavior: smooth) zur Ruhe kommt — von außen gemessen,
    damit es auch ohne JavaScript der Seite geht."""
    vorher, ende = None, time.monotonic() + frist
    while time.monotonic() < ende:
        jetzt = p.evaluate("() => [window.scrollY, ...[...document.querySelectorAll('*')]"
                           ".filter(e => e.scrollTop).map(e => e.scrollTop)].join(',')")
        if jetzt == vorher:
            return
        vorher = jetzt
        p.wait_for_timeout(250)


def _ueberschrift_frei(p, selektor: str) -> dict:
    """Liegt die Überschrift der Zone im Fenster und trifft ein Tippen auf ihre Mitte sie selbst?"""
    return p.evaluate(
        """(sel) => {
            const zone = document.querySelector(sel);
            if (!zone) return {grund: 'fehlt'};
            const h = zone.querySelector('h2') || zone;
            const r = h.getBoundingClientRect();
            if (r.width === 0 || r.height === 0) return {grund: 'ohne Fläche'};
            if (r.top < 0 || r.bottom > window.innerHeight) return {grund: 'außerhalb', top: r.top, bottom: r.bottom};
            const x = r.left + Math.min(r.width, 40) / 2, y = r.top + r.height / 2;
            const oben = document.elementFromPoint(x, y);
            return {frei: !!oben && h.contains(oben), oben: oben ? oben.tagName + '.' + oben.className : null,
                    top: r.top};
        }""",
        selektor,
    )


@pytest.mark.parametrize("js", [True, False], ids=["mit-js", "ohne-js"])
@pytest.mark.parametrize("viewport", [DESKTOP, HANDY], ids=["desktop", "handy"])
def test_gp069_mitreden_zeigt_die_chat_zone(seite, live_server, demo, viewport, js):
    antrag = _beratung_hervorheben()
    p = seite(viewport=viewport, js=js, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    link = p.locator(f'#feld-wichtig a[href="/antrag/{antrag.pk}/#zone-chat"]')
    assert link.count() == 1, "die Kachel bietet „Mitreden“"
    # Das Parlament am Handy rastet feldweise ein; der Verweis wird sofort ins Bild geholt, nicht weich
    link.evaluate("a => a.scrollIntoView({block: 'center', behavior: 'instant'})")
    link.click()
    p.wait_for_url(f"**/antrag/{antrag.pk}/#zone-chat")
    p.wait_for_load_state("load")
    _scrollruhe(p)
    lage = _ueberschrift_frei(p, "#zone-chat")
    assert lage.get("frei"), f"nach „Mitreden“ liegt #zone-chat frei im Fenster: {lage}"
    if js:
        # Der Reiter folgt dem Sprung: „Chat“ ist die gewählte Zone, nicht der Text darüber
        assert p.locator('.zreiter[href="#zone-chat"]').get_attribute("aria-current") == "true"
