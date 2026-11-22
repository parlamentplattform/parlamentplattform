"""GP-030 (GAST-14, GB-16): Zeilen der Rollenmatrix, die etwas Öffentliches versprechen, führen einen
Gast auf eine öffentliche Seite, nicht in einen geschützten Arbeitsbereich."""

import pytest
from django.urls import reverse

from plattform_core.rollen import GRUPPEN, Stand, alle_rollen


def _zeile(schluessel: str, wort: str):
    rolle = next(r for r in alle_rollen(GRUPPEN) if r.schluessel == schluessel)
    (zeile,) = [f for f in rolle.faehigkeiten if wort in f.titel]
    return zeile


@pytest.mark.django_db
def test_gp030_die_berichtszeile_des_integritaetsrats_fuehrt_einen_gast_zum_oeffentlichen_einstieg(client):
    '''Die Zeile „Mindestens jährlich öffentlich berichten“ verwies auf /gremien/integritaet/, den
    Arbeitsbereich des Rates; ein Gast landete bei der Anmeldung. Sie führt jetzt auf die öffentliche
    Seite „Gremien“, von der aus der Jahresbericht erreichbar ist.'''
    bericht = _zeile('integritaetsrat', 'jährlich öffentlich berichten')
    assert bericht.stand is Stand.VERFUEGBAR
    assert bericht.urlname == 'gremien:uebersicht'
    assert client.get(reverse(bericht.urlname)).status_code == 200
    assert 'eigenen Bereich' not in bericht.ort and 'Seite „Gremien“' in bericht.ort
