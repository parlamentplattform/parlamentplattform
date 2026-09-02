"""FB-E1 (3×3-Bänder in „Meine Region"), FB-E3 (kurze Leerzustände) und FB-A5 („mehr vorhanden")."""

import pytest

from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

ORT = "St. Marienkirchen an der Polsenz"


def _region(client):
    return client.get("/parlament/").content.decode().split('id="feld-region"')[1].split("</section>")[0]


def test_region_ist_ein_drei_mal_drei_raster_aus_baendern(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    for i in range(4):
        antrag_einbringen(anna, f"Gemeindesache {i}", "W.", "", ordnung, ebene="gemeinde", gebiet=ORT)
    client.force_login(anna)
    feld = _region(client)
    assert 'class="baender"' in feld
    assert feld.count('class="rband ') == 3 and 'class="rband r1"' in feld and 'class="rband r3"' in feld
    assert feld.count('class="rkopf"') == 3 and f"Gemeinde · {ORT}" in feld
    assert feld.count('<article class="kachel"') == 4  # alle vier in der Spur — die vierte per Wischen
    assert 'class="spur" x-ref="spur"' in feld and 'x-data="spur"' in feld
    assert 'class="spur-mehr" x-cloak' in feld  # „› n weitere“ nur mit JavaScript
    assert "kacheln dreier" not in feld


def test_leerzustaende_sind_kurz_und_haben_eine_handlung(client, ordnung):  # noqa: F811
    client.force_login(mitglied_anlegen("anna"))
    feld = _region(client)
    for satz in ("Noch nichts in Ihrer Gemeinde.", "Noch nichts in Ihrem Bezirk.", "Noch nichts in Ihrem Land."):
        assert satz in feld and len(satz.split()) <= 8
    assert feld.count('href="/einbringen/"') == 3  # je Band eine Handlung
    assert "Kein laufender Antrag" not in feld
    assert feld.count('class="spur leer"') == 3


def test_mehr_vorhanden_pille_an_drei_feldern_ohne_javascript_verborgen(client):
    html = client.get("/parlament/").content.decode()
    assert html.count('class="feld-mehr" x-cloak x-show="sichtbar"') == 3
    for feld in ("filter", "wichtig", "region"):
        assert f'id="feld-{feld}" aria-labelledby="h-{feld}" x-data="feldmehr"' in html
    favoriten = html.split('id="feld-favoriten"')[1].split("</section>")[0]
    assert "feld-mehr" not in favoriten  # der Fächer zeigt zuerst den Anker — kein Pfeil nach unten
