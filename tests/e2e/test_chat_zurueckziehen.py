"""Zurückziehen eines Beitrags braucht eine Bestätigung, auch ohne JavaScript (GP-177, ASR-25):
Vorher zog der erste Klick ohne JavaScript den Beitrag sofort zurück — hx-confirm fragt nur mit htmx."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]


@pytest.mark.parametrize('js', [False, True])
def test_gp177_erst_der_bestaetigende_klick_zieht_zurueck(seite, live_server, js):
    from verfahren.chat import beitrag_schreiben
    from verfahren.models import Kommentar, Verfahrensordnung, antrag_einbringen
    from verfahren.test_views_aktionen import ANTRAG, REGELN, mitglied_anlegen

    ordnung = Verfahrensordnung.objects.create(policy_id='test-ordnung', version=1, regeln=REGELN, aktiv=True)
    anna = mitglied_anlegen('anna')
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    beitrag = beitrag_schreiben(antrag, anna, 'Mein Gedanke zum Antrag.')
    p = seite(als=anna, js=js, reduziert=True)
    p.on('dialog', lambda d: d.accept())
    p.goto(f'{live_server.url}/antrag/{antrag.pk}/')
    blase = p.locator(f'#k-{beitrag.pk}')
    blase.get_by_text('Zurückziehen', exact=True).click()
    p.wait_for_load_state()
    assert not Kommentar.objects.get(pk=beitrag.pk).geloescht, 'der erste Klick zieht noch nicht zurück'
    blase.get_by_role('button', name='Ja, zurückziehen').click()
    p.wait_for_function(
        "(id) => !document.querySelector('#k-' + id + ' .blase-zurueckziehen')", arg=beitrag.pk,
    )
    assert Kommentar.objects.get(pk=beitrag.pk).geloescht
