"""Regionale Anzeige verspricht keine noch nicht gebaute Wahlkreisbegrenzung."""

import copy

import pytest
from django.urls import reverse

from verfahren.models import Antragsart, Ebene, antrag_einbringen
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize("angemeldet", [False, True])
@pytest.mark.parametrize("ebene,art,hinweis", [
    (Ebene.GEMEINDE, Antragsart.MANDAT, True),
    (Ebene.LAND, Antragsart.MANDAT, True),
    (Ebene.BUND, Antragsart.MANDAT, False),
    (Ebene.GEMEINDE, Antragsart.SACHE, False),
])
def test_tatsaechlicher_teilnehmerkreis_ist_vor_der_aktion_sichtbar_ohne_regelaenderung(
    client, ordnung, angemeldet, ebene, art, hinweis,  # noqa: F811
):
    m = mitglied_anlegen()
    a = antrag_einbringen(m, "Kandidatur im Testgebiet", "Interne Kandidatur für ein Testmandat.", "", ordnung,
                         ebene=ebene, gebiet="Testgebiet" if ebene != Ebene.BUND else "", art=art)
    eingefroren = copy.deepcopy(a.policy_snapshot)
    if angemeldet:
        client.force_login(m)
    antwort = client.get(reverse("verfahren:antrag", args=[a.pk]))
    assert antwort.status_code == 200
    html = antwort.content.decode()
    assert ('id="teilnehmerkreis"' in html) == hinweis
    if hinweis:
        assert "parteiweit geprüft" in html and "noch nicht" in html
        assert html.index('id="teilnehmerkreis"') < html.index('id="zone-text"')
    a.refresh_from_db()
    assert a.policy_snapshot == eingefroren
