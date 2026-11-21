'''Bildschirmtests der Folgewelle 0.115.0 (Paket Oberfläche).

GP-068: Der Lesestand des Chats entsteht beim Seitenaufruf am Server — mit JavaScript ruft die Seite
`chat/gelesen` nicht mehr zusätzlich auf, die Linie „neu“ erscheint nach einer fremden Antwort einmal und
beim übernächsten Besuch nicht mehr.
GP-060: Die Fehlerübersicht eines Formulars steht am Handy ohne JavaScript oben im Bild — auch im
Dunkelmodus, mit den Farbtokens der Fehlerbox aus dem dunklen Block.'''

import pytest
from django.urls import reverse
from playwright.sync_api import expect

from mitglieder.models import Mitglied
from verfahren.test_oertliche_teilnahme import menschen  # noqa: F401
from verfahren.test_views_aktionen import ANTRAG, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {'width': 390, 'height': 844}


def _mitglied(name):
    return Mitglied.objects.get(username=name)


def test_gp068_lesestand_ohne_zweiten_aufruf_aus_dem_skript(seite, live_server, demo):
    from verfahren.chat import beitrag_schreiben
    from verfahren.models import Antrag, Lesestand

    antrag = Antrag.objects.filter(phase='beratung').first()
    leser, andere = _mitglied('demo1'), _mitglied('demo2')
    wurzel = beitrag_schreiben(antrag, andere, 'Ein Beitrag zum Mitlesen.')
    p = seite(als=leser)
    aufrufe = []
    p.on('request', lambda anfrage: aufrufe.append(anfrage.url) if '/chat/gelesen/' in anfrage.url else None)
    adresse = f'{live_server.url}/antrag/{antrag.pk}/'

    p.goto(adresse)
    p.wait_for_load_state('networkidle')
    assert Lesestand.objects.filter(mitglied=leser, antrag=antrag).exists(), 'der erste Besuch legt den Stand an'
    assert p.locator('.neulinie').count() == 0

    beitrag_schreiben(antrag, andere, 'Eine fremde Antwort.', wurzel)
    p.goto(adresse)
    p.wait_for_load_state('networkidle')
    expect(p.locator('.neulinie').first).to_be_visible()
    p.wait_for_timeout(4500)  # so lange wartete das Skript bisher, bevor es den Stand vorrückte
    assert aufrufe == [], 'das Skript ruft chat/gelesen nicht mehr auf'

    p.goto(adresse)
    p.wait_for_load_state('networkidle')
    assert p.locator('.neulinie').count() == 0, 'beim übernächsten Besuch ist die Linie weg'


def test_gp060_fehleruebersicht_im_dunkelmodus_am_handy_ohne_javascript(seite, live_server, menschen, ordnung, sichtpruefung):  # noqa: F811
    leute, _ort, fremdort = menschen
    p = seite(als=leute['autor'], js=False, viewport=HANDY, reduziert=True, dunkel=True)
    p.goto(live_server.url + reverse('verfahren:einbringen'))
    p.fill('#id_titel', ANTRAG['titel'])
    p.fill('#id_wortlaut', ANTRAG['wortlaut'])
    p.locator('input[name="ebene"][value="gemeinde"]').check()
    Mitglied.objects.filter(pk=leute['autor'].pk).update(wohnsitz=fremdort)
    p.locator('#einbringen-form button[type=submit]').first.click()
    p.wait_for_load_state()
    meldung = p.locator('[role=alert]').first
    expect(meldung).to_be_visible()
    expect(meldung.locator('a[href="#id_ebene"]')).to_have_count(1)
    kasten = meldung.bounding_box()
    assert kasten is not None and 0 <= kasten['y'] and kasten['y'] + min(kasten['height'], 80) <= HANDY['height']
    # Die Tokens der Fehlerbox kommen im Dunkelmodus aus dem dunklen Block, nicht aus dem hellen
    tokens = p.evaluate(
        '''() => { const s = getComputedStyle(document.documentElement);
        return ['--warn-grund', '--warn-rand', '--warn-text', '--warn-bg', '--warn'].map(n => s.getPropertyValue(n).trim()); }'''
    )
    grund, rand, text, warn_bg, warn = tokens
    assert all(tokens), tokens
    assert (grund, rand, text) == (warn_bg, warn, warn)
    assert warn_bg.upper() == '#2E1616' and warn.upper() == '#E08A8A', tokens
    farbe = meldung.evaluate('el => getComputedStyle(el).backgroundColor')
    assert farbe == 'rgb(46, 22, 22)', farbe
    p.screenshot(path=str(sichtpruefung / 'formularfehler-einbringen-handy-dunkel-ohne-js.png'))
