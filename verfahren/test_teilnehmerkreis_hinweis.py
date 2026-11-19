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
    # GP-059 (OW-10): Jedes regionale Verfahren ohne Gebietsstand sagt, wer teilnimmt — nicht nur Kandidaturen
    (Ebene.GEMEINDE, Antragsart.SACHE, True),
    (Ebene.BEZIRK, Antragsart.SACHE, True),
    (Ebene.BUND, Antragsart.SACHE, False),
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
        assert a.teilnahmegebiet is None
        kreis = html.split('id="teilnehmerkreis"', 1)[1].split("</p>", 1)[0]
        assert "alle stimmberechtigten Mitglieder; kein örtlicher Kreis" in kreis
        assert html.index('id="teilnehmerkreis"') < html.index('id="zone-text"')
    a.refresh_from_db()
    assert a.policy_snapshot == eingefroren
