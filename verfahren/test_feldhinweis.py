"""Der Feldhinweis des Parlaments erscheint nur nach einer eigenen Handlung (Z-1, R1-8)."""

import pytest
from django.urls import reverse

from mitglieder.models import Identitaetsstufe
from verfahren.hinweise import hinweis_lage
from verfahren.test_direkt_handlung import _feld, _lage
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

FREMD = '/parlament/?hinweis=erfasst&feld=filter'


def test_z1_fremder_link_zeigt_keine_erfolgsmeldung(client, ordnung):  # noqa: F811
    """Ein fremder Link mit ?hinweis=…&feld=… zeigte Gästen, Gemeindekonten und Mitgliedern
    „Unterstützung erfasst.“, ohne dass sie etwas getan hatten."""
    leute, _sammelnd, _ = _lage(ordnung)
    assert 'Unterstützung erfasst.' not in _feld(client, 'filter', FREMD)  # Gast
    client.force_login(mitglied_anlegen('neu', stufe=Identitaetsstufe.UNGEPRUEFT))
    assert 'Unterstützung erfasst.' not in _feld(client, 'filter', FREMD)
    client.force_login(leute[2])
    assert 'Unterstützung erfasst.' not in _feld(client, 'filter', FREMD)


def test_z1_nur_die_eigene_letzte_handlung_zeigt_ihren_hinweis(client, ordnung, rf):  # noqa: F811
    leute, sammelnd, _ = _lage(ordnung)
    client.force_login(leute[2])
    antwort = client.post(
        reverse('verfahren:unterstuetzen', args=[sammelnd.pk]), {'weiter': '/parlament/', 'feld': 'filter'}
    )
    assert antwort.url == '/parlament/?hinweis=erfasst&feld=filter#feld-filter'
    assert 'Unterstützung erfasst.' in _feld(client, 'filter', antwort.url.split('#')[0])
    # Ein anderer Code oder ein anderes Feld in der Adresse gehört zu keiner eigenen Handlung
    assert 'Unterstützung zurückgezogen.' not in _feld(client, 'filter', '/parlament/?hinweis=zurueckgezogen&feld=filter')
    assert 'Unterstützung erfasst.' not in _feld(client, 'region', '/parlament/?hinweis=erfasst&feld=region')
    # Ohne Sitzung (etwa ein nackter Abruf) gibt es keinen Hinweis
    assert hinweis_lage(rf.get(FREMD)) is None
