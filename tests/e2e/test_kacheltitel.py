"""Sichtprüfung 0.113.0: Kacheltitel und Fachliste.

Am Desktop (1440 × 900) schrumpfte der Titel der hervorgehobenen Kachel im Feld „Wichtige Abstimmungen“
auf vier Pixel Höhe: Die Kachel ist dort niedriger als ihr Inhalt, und der Titel gab als Erster nach —
eine Kachel ohne lesbaren Titel (verwandt mit GP-171, dort für das Regionsband behoben). Am Handy ragte
die Mehrfachauswahl der Fachgebiete in der Verwaltung der Fachliste über den Kartenrand (GP-009)."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

DESKTOP = {"width": 1440, "height": 900}
HANDY = {"width": 390, "height": 844}


def _mitglied(name="demo1"):
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username=name)


@pytest.mark.parametrize("js", [True, False], ids=["mit-js", "ohne-js"])
def test_jeder_kacheltitel_am_desktop_hat_seine_zeile(seite, live_server, demo, js):
    p = seite(viewport=DESKTOP, js=js, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_load_state("load")
    titel = p.evaluate(
        """() => [...document.querySelectorAll('.kachel .k-titel')].map(e => {
            const r = e.getBoundingClientRect();
            return {text: e.textContent.trim().slice(0, 40), hoehe: Math.round(r.height)};
        })"""
    )
    assert titel, "das Parlament zeigt Kacheln"
    zu_niedrig = [t for t in titel if t["hoehe"] < 15]
    assert not zu_niedrig, f"Kacheltitel ohne lesbare Zeile: {zu_niedrig}"


def test_die_verwaltung_der_fachliste_laeuft_am_handy_nicht_ueber(seite, live_server, demo):
    verwaltung = _mitglied()
    verwaltung.ist_admin = True
    verwaltung.save(update_fields=["ist_admin"])
    p = seite(viewport=HANDY, als=verwaltung)
    p.goto(f"{live_server.url}/verwaltung/fachliste/")
    p.wait_for_load_state("load")
    assert p.locator("select").count() >= 1, "das Formular bietet die Fachgebiete zur Auswahl"
    breite = p.evaluate("[document.documentElement.scrollWidth, innerWidth]")
    assert breite[0] <= breite[1], f"die Seite läuft am Handy über: {breite}"
    raender = p.evaluate(
        """() => [...document.querySelectorAll('.karte select')].map(s => [s.name,
            Math.round(s.getBoundingClientRect().right), Math.round(s.closest('.karte').getBoundingClientRect().right)])"""
    )
    hinaus = [r for r in raender if r[1] > r[2]]
    assert not hinaus, f"eine Auswahl ragt über die Karte hinaus: {hinaus}"
