"""S2 — Kacheln nach FB-D1/D2/D3 und die Rückmeldung in der Kachel (FB-A2)."""

import pytest
from django.urls import reverse

from verfahren.models import Antrag, Kategorie, KategorieAbo, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _feld(html: str, feld_id: str) -> str:
    return html.split(f'id="{feld_id}"', 1)[1].split("</section>", 1)[0]


def _hervorgehoben(ordnung, titel="Wichtig für alle", kategorie=None):  # noqa: F811
    anna = mitglied_anlegen()
    antrag = antrag_einbringen(anna, titel, "Wortlaut.", "", ordnung)
    if kategorie:
        antrag.kategorien.add(kategorie)
    Antrag.objects.filter(pk=antrag.pk).update(hervorgehoben=True, hervorhebung_begruendung="Beschluss IR-2026-11.")
    return anna, antrag


def test_kachel_traegt_thema_mit_eigenem_stern(client, ordnung):  # noqa: F811
    energie = Kategorie.objects.create(slug="energie", name="Energie")
    anna, antrag = _hervorgehoben(ordnung, kategorie=energie)
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-wichtig")
    assert f'<article class="kachel" data-antrag="{antrag.pk}">' in feld
    assert 'class="k-thema-name" title="Energie">Energie</span>' in feld
    assert 'class="stern klein aus gast"' in feld  # Gäste sehen den Stern als Weg zur Anmeldung (FB-C4)
    assert "abonnieren/" not in feld  # aber kein Formular
    client.force_login(anna)
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-wichtig")
    assert 'action="/kategorien/energie/abonnieren/"' in feld
    assert 'class="stern klein aus" aria-pressed="false"' in feld
    KategorieAbo.objects.create(kategorie=energie, mitglied=anna)
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-wichtig")
    assert 'class="stern klein" aria-pressed="true"' in feld


def test_kachel_zeigt_fristring_und_direkt_handlung_je_phase(client, ordnung):  # noqa: F811
    anna, antrag = _hervorgehoben(ordnung)
    client.force_login(anna)
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-wichtig")
    assert 'class="ring"' in feld and "stroke-dashoffset:" in feld
    assert f'action="/antrag/{antrag.pk}/unterstuetzen/"' in feld and ">Unterstützen<" in feld
    antrag.unterstuetzungen.create(mitglied=anna)
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-wichtig")
    assert "✓ Unterstützt" in feld and "gewaehlt" in feld
    # Beratung → „Mitreden“
    Antrag.objects.filter(pk=antrag.pk).update(phase="beratung")
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-wichtig")
    assert f'href="/antrag/{antrag.pk}/#beratung">Mitreden</a>' in feld


def test_kachel_hervorhebungsgrund_gekuerzt_mit_vollem_tooltip(client, ordnung):  # noqa: F811
    lang = "Integritätsrat, 12.08.2026: " + "Betrifft alle Gremien dauerhaft, hat aber bisher wenig Beteiligung. " * 2
    anna, antrag = _hervorgehoben(ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(hervorhebung_begruendung=lang)
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-wichtig")
    grund = feld.split('<p class="erk grund"', 1)[1].split("</p>", 1)[0]
    assert 'title="' + lang in grund and "…" in grund


def test_leerzustand_liegt_ausserhalb_des_rasters(client):
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-wichtig")
    assert '<div class="kacheln">' not in feld and 'class="leer"' in feld


def test_rueckmeldung_in_der_kachel_ist_vorbereitet(client, ordnung):  # noqa: F811
    anna, antrag = _hervorgehoben(ordnung)
    html = client.get(reverse("verfahren:parlament")).content.decode()
    assert '<div class="parlament" id="parlament" x-data="parlament">' in html
    assert '<span class="k-erfasst" role="status">✓ Erfasst</span>' in _feld(html, "feld-wichtig")


def test_ring_filter_rechnet_den_versatz():
    from verfahren.templatetags.phasen import rest_ring

    assert rest_ring(0) == "50.3" and rest_ring(100) == "0.0" and rest_ring(50) == "25.1"
    assert rest_ring("kaputt") == "50.3"
