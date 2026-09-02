"""Tests für den App-Rahmen (Bauschritt S1): Leiste, Konto-Menü, Bänder, Raster, Tableiste, Anstoß, Alpine.

Jeder Test prüft serverseitig gerendertes Markup — die Grundschicht, die ohne JavaScript gilt.
Layout und Bewegung prüfen die Bildschirmtests unter tests/e2e/.
"""

import pytest
from django.urls import reverse

from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _feld(html: str, feld_id: str) -> str:
    return html.split(f'id="{feld_id}"', 1)[1].split("</section>", 1)[0]


def test_regler_ohne_inline_handler_mit_alpine(client):
    client.force_login(mitglied_anlegen())
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-filter")
    assert "oninput" not in feld
    assert feld.count('type="range"') >= 8
    assert feld.count('x-model.number="wert"') == feld.count('type="range"')
    assert '<output x-text="wert">' in feld


def test_thema_skript_vor_dem_stil_und_html_ohne_serverseitiges_thema(client):
    html = client.get("/").content.decode()
    kopf = html.split("</head>", 1)[0]
    assert kopf.index("verfahren/js/thema.js") < kopf.index("<style>")
    assert "data-theme" not in html.split("<head>", 1)[0]
