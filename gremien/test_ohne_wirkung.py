"""GP-034, Rest aus dem Gegenlesen: Das Kennzeichen `ohne_wirkung` hing am Wortanfang des Vermerks.

Erkannt wurden nur Vermerke, die mit „Ohne Wirkung“ oder „Nicht “ beginnen. „Beim Integritätsrat läuft
bereits ein Beschluss zur Hervorhebung.“ ist aber ein entschiedener Beschluss, der nichts bewirkt hat —
und ein Satz, der zufällig mit „Nicht“ beginnt, wäre fälschlich gekennzeichnet. Jetzt sagt die Wirkung
selbst, ob sie ausblieb; der Wortlaut entscheidet nichts mehr.

„Ohne Ergebnis zur Frist …“ trägt das Kennzeichen weiterhin nicht: Ohne Ergebnis ist nichts entschieden,
das ohne Wirkung bleiben könnte (Status „ohne Ergebnis“ steht am Beschluss selbst)."""

from __future__ import annotations

import ast
import pathlib

import pytest
from django.urls import reverse

from gremien import models as gm
from gremien.models import Anlass, GremienBeschluss, Gremium
from gremien.test_koordination import abstimmen, korat
from gremien.test_werkstatt import ANTRAG, ordnung  # noqa: F401
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import antrag_einbringen, mitglied_anlegen

pytestmark = pytest.mark.django_db


def _vermerkt(beschluss):
    return [
        e.ereignis for e in AuditEintrag.objects.order_by('pk')
        if e.ereignis.get('typ') == 'gremienbeschluss_vermerkt' and e.ereignis.get('beschluss') == beschluss.pk
    ]


def _anregen(client, leute, antrag):
    client.force_login(leute[0])
    client.post(
        reverse('gremien:koordination_beschluss'),
        {'anlass': 'hervorhebung_anregen', 'antrag': antrag.pk, 'beschreibung': 'Wenig Beteiligung, große Wirkung.'},
    )
    beschluss = GremienBeschluss.objects.filter(anlass=Anlass.HERVORHEBUNG_ANREGEN).order_by('-pk').first()
    return abstimmen(client, leute, beschluss)


def test_eine_zweite_anregung_waehrend_der_erste_beschluss_laeuft_ist_ohne_wirkung(client, ordnung):  # noqa: F811
    leute = korat()
    antrag = antrag_einbringen(mitglied_anlegen('stellerin'), **ANTRAG, ordnung=ordnung)
    erste = _anregen(client, leute, antrag)
    assert [e['ohne_wirkung'] for e in _vermerkt(erste)] == [False]  # eingebracht: mit Wirkung
    zweite = _anregen(client, leute, antrag)
    assert GremienBeschluss.objects.filter(gremium=Gremium.INTEGRITAETSRAT, anlass=Anlass.HERVORHEBUNG).count() == 1
    vermerkt = _vermerkt(zweite)
    assert len(vermerkt) == 1 and 'läuft bereits' in vermerkt[0]['vermerk']
    assert vermerkt[0]['ohne_wirkung'] is True


def test_der_wortlaut_entscheidet_nicht_ueber_das_kennzeichen():
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.KOORDINATIONSRAT, gegenstand='Ob wir uns monatlich treffen', optionen=gm.JA_NEIN,
        angelegt_von=mitglied_anlegen('rat'),
    )
    gm._vermerken(beschluss, 'Nicht nur beschlossen, sondern auch umgesetzt.')
    gm._vermerken(beschluss, 'Eingetragen.', ohne_wirkung=True)
    assert [e['ohne_wirkung'] for e in _vermerkt(beschluss)] == [False, True]
    assert not hasattr(gm, 'OHNE_WIRKUNG_ANFAENGE')


def test_jeder_vermerk_der_eine_ausgebliebene_wirkung_sagt_traegt_das_kennzeichen():
    """Wächter: Ein Vermerk, dessen Text „Ohne Wirkung“ oder „Nicht …“ sagt, setzt das Kennzeichen
    ausdrücklich — sonst stünde er wieder nur am Wortlaut erkennbar in der Kette."""
    quelle = pathlib.Path(gm.__file__).read_text(encoding='utf-8')
    fehlend = []
    for knoten in ast.walk(ast.parse(quelle)):
        if not (isinstance(knoten, ast.Call) and getattr(knoten.func, 'id', None) == '_vermerken'):
            continue
        text = knoten.args[1] if len(knoten.args) > 1 else None
        anfang = ''
        if isinstance(text, ast.Constant) and isinstance(text.value, str):
            anfang = text.value
        elif isinstance(text, ast.JoinedStr) and text.values and isinstance(text.values[0], ast.Constant):
            anfang = str(text.values[0].value)
        gesetzt = any(k.arg == 'ohne_wirkung' for k in knoten.keywords)
        if anfang.startswith(('Ohne Wirkung', 'Nicht ')) and not gesetzt:
            fehlend.append(knoten.lineno)
    assert fehlend == []
