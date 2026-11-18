"""Gesamtprüfung 18.11.2026, erste Behebungsrunde: Befunde am Verfahrensmodell, die keine eigene
Testdatei im Gremienpaket haben (das Modell `verfahren/models.py` gehört zu diesem Paket)."""

import pytest

from gremien.test_integritaet import antrag_in_abstimmung
from gremien.test_werkstatt import mitglied_anlegen, ordnung  # noqa: F401
from verfahren.models import AuditEintrag, Stimmabgabe, stimme_abgeben

pytestmark = pytest.mark.django_db


def _stimm_ereignisse(antrag):
    return [
        e.ereignis['typ']
        for e in AuditEintrag.objects.order_by('lfd')
        if e.ereignis['typ'] in ('stimme', 'stimme_geaendert') and e.ereignis.get('antrag') == antrag.pk
    ]


def test_dieselbe_stimme_noch_einmal_ist_keine_aenderung(ordnung):  # noqa: F811
    """GP-164: Ein zweites „ja“ schrieb das öffentliche Ereignis „Stimme geändert“, obwohl sich nichts
    geändert hatte. Jetzt entsteht kein Ereignis, und die Stimmzeile bleibt, wie sie war."""
    antrag = antrag_in_abstimmung(ordnung)
    mitglied = mitglied_anlegen('waehlerin')
    erste = stimme_abgeben(antrag, mitglied, 'ja')
    zeitpunkt = erste.abgegeben_am
    zweite = stimme_abgeben(antrag, mitglied, 'ja')
    assert _stimm_ereignisse(antrag) == ['stimme']
    assert zweite.pk == erste.pk and Stimmabgabe.objects.filter(antrag=antrag).count() == 1
    assert Stimmabgabe.objects.get(pk=erste.pk).abgegeben_am == zeitpunkt


def test_eine_wirklich_geaenderte_stimme_bleibt_eine_aenderung(ordnung):  # noqa: F811
    """Gegenprobe: Das Überschreiben bei einem anderen Wert bleibt — eine Zeile, ein Ereignis mehr."""
    antrag = antrag_in_abstimmung(ordnung)
    mitglied = mitglied_anlegen('waehlerin')
    stimme_abgeben(antrag, mitglied, 'ja')
    stimme_abgeben(antrag, mitglied, 'ja')
    geaendert = stimme_abgeben(antrag, mitglied, 'nein')
    assert _stimm_ereignisse(antrag) == ['stimme', 'stimme_geaendert']
    assert geaendert.stimme == 'nein' and Stimmabgabe.objects.filter(antrag=antrag).count() == 1
