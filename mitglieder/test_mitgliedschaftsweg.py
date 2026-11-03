"""Einstieg: echte Regeln, gleiche Darstellung und keine fingierten Ergebnisse."""

import re
from copy import deepcopy

import pytest

from parameter.models import Parameter
from verfahren.models import AuditEintrag, Verfahrensordnung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def grafik(html):
    return html.split('<svg class="ablauf"', 1)[1].split('</svg>', 1)[0]


def test_beide_einstiege_zeigen_die_gleiche_beschlossene_ordnung(client, ordnung):  # noqa: F811
    regeln = {**ordnung.regeln, "beratung_tage": 35, "abstimmung_tage": 17, "hoechstrunden": 2}
    Verfahrensordnung.objects.filter(pk=ordnung.pk).update(regeln=regeln)
    Parameter.objects.update_or_create(schluessel="verfahren-abstimmung-tage", defaults={"wert": "99"})
    Parameter.objects.update_or_create(schluessel="gremien-hoechstrunden", defaults={"wert": "9"})
    start = client.get("/").content.decode()
    mitgliedschaft = client.get("/mitgliedschaft/").content.decode()
    assert grafik(start) == grafik(mitgliedschaft)
    for s in [start, mitgliedschaft]:
        assert "35 Tage" in s and "17 Tage · pseudonym" in s and "höchstens 2 Runden" in s
        assert "99 Tage" not in s and "höchstens 9 Runden" not in s


def test_ohne_aktive_ordnung_werden_keine_registerwerte_als_fristeingabe_ausgegeben(client):
    Verfahrensordnung.objects.update(aktiv=False)
    for url in ["/", "/mitgliedschaft/"]:
        s = client.get(url).content.decode()
        assert "Noch keine aktive Verfahrensordnung" in s
        assert grafik(s).count("nicht festgelegt") == 3
        assert not re.search(r"\d+ Tage", grafik(s))


def test_lesende_einstiegsseiten_aendern_keine_laufenden_regeln(client, ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    stand, kette = deepcopy(antrag.policy_snapshot), list(AuditEintrag.objects.values_list("hash", flat=True))
    for url in ["/", "/mitgliedschaft/"]:
        assert client.get(url).status_code == 200
    antrag.refresh_from_db()
    assert antrag.policy_snapshot == stand
    assert list(AuditEintrag.objects.values_list("hash", flat=True)) == kette


@pytest.mark.parametrize("aufbau", [True, False])
def test_freischaltung_und_anwartschaft_folgen_der_tatsaechlichen_einstellung(client, settings, aufbau):
    settings.DDOE_UEBERGANGSREGEL = aufbau
    s = client.get("/mitgliedschaft/").content.decode()
    assert ("Während der Aufbauphase" in s) is aufbau
    assert ("bei Sachfragen nach drei Monaten" in s) is not aufbau
    assert "Ein Beitragseingang allein bestätigt noch nicht Ihre Identität" in s
    assert "ohne festen Wohnsitz" in s and "Wohnsitz im Ausland" in s
    assert "Eine örtliche Begrenzung ist noch nicht umgesetzt" in s
    assert "keine Daten eines echten Antrags" in s and "noch keine vollständige Durchrechnung" in s
    assert "Ein Parteibeschluss ist noch kein staatliches Gesetz" in s


def test_rechte_links_fuehren_auf_vorhandene_bereiche_ohne_ausgedachte_antraege(client):
    s = client.get("/mitgliedschaft/").content.decode()
    karten = s.split('<div class="kat-grid mitgliedsrechte">', 1)[1].split('<h2 id="weg">', 1)[0]
    links = re.findall(r'href="([^"]+)"', karten)
    assert len(links) == 6
    for ziel in links:
        pfad, _, anker = ziel.partition("#")
        r = client.get(pfad)
        assert r.status_code in (200, 302)
        if anker:
            assert f'id="{anker}"' in r.content.decode()
