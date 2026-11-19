"""Die Rollenverwaltung im Audit (GP-048): Wer beruft, bestätigt und beendet, steht in der Kette.

Die Verwaltung besetzt die Räte von Hand, auch das Aufsichtsorgan. Welches Konto das getan hat, muss
nachvollziehbar sein — in der Kette vollständig, öffentlich geschwärzt wie jede Mitgliedskennung."""

import json

import pytest
from django.urls import reverse

from gremien.models import Gremium, Rolle, standard_ende
from gremien.test_werkstatt import mitglied_anlegen
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


def test_jede_rollenhandlung_nennt_im_audit_das_handelnde_konto(client):
    admin = mitglied_anlegen('verwaltung')
    admin.ist_admin = True
    admin.save()
    wer = mitglied_anlegen('berufene')
    client.force_login(admin)
    aktion = reverse('gremien:rollen_aktion')
    client.post(
        aktion,
        {'aktion': 'berufen', 'mitglied': wer.pk, 'gremium': Gremium.EXPERTENRAT_1, 'endet_am': standard_ende().isoformat()},
    )
    rolle = Rolle.objects.get(mitglied=wer)
    client.post(aktion, {'aktion': 'bestaetigen', 'rolle': rolle.pk})
    client.post(aktion, {'aktion': 'beenden', 'rolle': rolle.pk, 'grund': 'Rücktritt'})
    eintraege = {
        e.ereignis['typ']: e.ereignis
        for e in AuditEintrag.objects.all()
        if e.ereignis['typ'] in ('rolle_berufen', 'rolle_bestaetigt', 'rolle_beendet')
    }
    assert set(eintraege) == {'rolle_berufen', 'rolle_bestaetigt', 'rolle_beendet'}
    assert all(e['durch'] == admin.pk and e['rolle'] == rolle.pk for e in eintraege.values())
    # Öffentlich steht dafür nur die Schwärzung — in der Liste wie im Export.
    client.logout()
    export = json.loads(client.get('/audit.json').content)
    liste = export['eintraege'] if isinstance(export, dict) and 'eintraege' in export else export
    oeffentlich = [e for e in liste if e.get('typ') in eintraege]
    assert len(oeffentlich) == 3
    for e in oeffentlich:
        assert e['geschwaerzt'] is True and e['ereignis']['durch'] == '•'
    seite = client.get('/audit/').content.decode()
    assert f'"durch": {admin.pk}' not in seite and f'durch: {admin.pk}' not in seite
