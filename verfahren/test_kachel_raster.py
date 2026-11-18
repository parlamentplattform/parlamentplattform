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
    assert f'href="/antrag/{antrag.pk}/#zone-chat">Mitreden</a>' in feld


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
    assert '<div class="parlament" id="parlament" x-data="parlament(\'\')"' in html
    assert '<span class="k-erfasst" role="status">✓ Erfasst</span>' in _feld(html, "feld-wichtig")


def test_ring_filter_rechnet_den_versatz():
    from verfahren.templatetags.phasen import rest_ring

    assert rest_ring(0) == "50.3" and rest_ring(100) == "0.0" and rest_ring(50) == "25.1"
    assert rest_ring("kaputt") == "50.3"


def test_gp069_jeder_anker_der_parlament_vorlagen_steht_auf_der_antragsseite():
    """GP-069 (ASR-20): „Mitreden“ zielte auf #beratung — eine id, die es auf der Antragsseite nicht
    gibt. Wächter: Jeder feste Anker, mit dem Kachel und Zeile auf die Antragsseite springen, steht
    dort als id."""
    import re
    from pathlib import Path

    ordner = Path(__file__).parent / 'templates' / 'verfahren'
    ziel = (ordner / 'antrag.html').read_text(encoding='utf-8')
    ziel += ''.join(p.read_text(encoding='utf-8') for p in ordner.glob('_chat*.html'))
    anker = set()
    for name in ('_kachel.html', '_filter_zeile.html', '_filter_liste.html', 'parlament.html'):
        anker |= set(re.findall(r"verfahren:antrag' [\w.]+ %\}#([a-z][a-z0-9-]*)", (ordner / name).read_text(encoding='utf-8')))
    assert 'zone-chat' in anker
    fehlend = sorted(a for a in anker if f'id="{a}"' not in ziel)
    assert fehlend == []


def test_gp175_resttage_zaehlen_wiener_kalendertage(ordnung):  # noqa: F811
    """GP-175 (OCR-14): `(frist - jetzt).days` rundete ab — „Frist endet heute“ stand schon am Vortag
    und noch nach dem Fristende. Kachel und Zeile zählen jetzt Wiener Kalendertage."""
    from datetime import datetime, timedelta
    from zoneinfo import ZoneInfo

    from django.utils import timezone

    from verfahren.views import _kachel, resttage

    wien = ZoneInfo('Europe/Vienna')
    frist = datetime(2026, 11, 19, 12, 41, tzinfo=wien)
    assert resttage(frist, datetime(2026, 11, 18, 13, 41, tzinfo=wien)) == 1  # 23 Stunden, aber morgen
    assert resttage(frist, datetime(2026, 11, 19, 0, 5, tzinfo=wien)) == 0
    assert resttage(frist, datetime(2026, 11, 17, 23, 59, tzinfo=wien)) == 2
    assert resttage(frist, frist + timedelta(minutes=1)) is None  # verstrichen: kein „endet heute“
    assert resttage(None, frist) is None

    antrag = antrag_einbringen(mitglied_anlegen('anna'), **ANTRAG, ordnung=ordnung)
    ende = _kachel(antrag, timezone.now())['frist']
    vortag = datetime.combine(timezone.localdate(ende) - timedelta(days=1), datetime.max.time(), tzinfo=wien)
    assert _kachel(antrag, vortag)['resttage'] == 1
    assert _kachel(antrag, ende + timedelta(minutes=1))['resttage'] is None
