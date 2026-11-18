"""Die Rollenübersicht läuft bei 320 Pixel nicht waagrecht über (GP-107): Die Kartenspalte verlangte
mindestens 320 Pixel, breiter als der Inhalt eines 320 Pixel schmalen Fensters."""

import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.django_db(transaction=True)]


@pytest.mark.parametrize('js', [True, False])
def test_gp107_rollenuebersicht_ohne_waagrechten_ueberlauf(seite, live_server, js):
    p = seite(viewport={'width': 320, 'height': 740}, js=js, reduziert=True)
    p.goto(f'{live_server.url}/rollen/')
    breite = p.evaluate('document.documentElement.scrollWidth')
    assert breite <= 320, breite
    ueber = p.evaluate(
        "[...document.querySelectorAll('a, button, input, select, textarea, summary')]"
        ".filter(e => !e.closest('details.menue:not([open])'))"  # das geschlossene Menü liegt außerhalb
        ".filter(e => e.getClientRects().length && e.getBoundingClientRect().right > 320.5)"
        ".map(e => e.outerHTML.slice(0, 120) + ' @' + e.getBoundingClientRect().right)"
    )
    assert not ueber, ueber
