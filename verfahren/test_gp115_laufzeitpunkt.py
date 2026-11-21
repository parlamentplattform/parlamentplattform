'''Der Lauf, der das Ergebnis einer Vertrauensfrage feststellt, wird ausdrücklich übergeben (GP-106).

`Antrag.fortschreiben` nannte dem Fachmodul nur die Sollzeit; den Zeitpunkt der Veröffentlichung las
`mandatare` selbst von der Uhr. Im Betrieb ist das dasselbe — ausdrücklich ist es erst, wenn der Lauf
seinen eigenen Zeitpunkt weitergibt. Alle Zeitpunkte hängen an EINEM Ausgangswert.'''

from datetime import timedelta

import pytest
from django.utils import timezone

from mandatare.models import Vertrauensfrage
from verfahren.test_vertrauensfrage import (  # noqa: F401
    abstimmen,
    altmandat,
    einbringen,
    tage,
    unterstuetzen,
)
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _abgestimmt(ordnung, altmandat, kuerzel):  # noqa: F811
    '''Eine Vertrauensfrage, deren Abstimmung am Tag 14 endet (Sollzeit); noch nicht fortgeschrieben.'''
    leute = [mitglied_anlegen(f'{kuerzel}{i}') for i in range(5)]
    t0 = timezone.now()
    antrag = einbringen(leute[0], altmandat, ordnung, jetzt=t0)
    unterstuetzen(antrag, leute[1:2], t0 + tage(1))
    antrag.fortschreiben(t0 + tage(7))
    abstimmen(antrag, leute, 'nein', t0 + tage(8))
    return antrag, t0


def test_der_lauf_uebergibt_seinen_zeitpunkt_als_veroeffentlichung(ordnung, altmandat):  # noqa: F811
    '''Ohne gestellte Uhr: Der Zeitpunkt kommt aus dem Aufruf, nicht aus `timezone.now()`.'''
    antrag, t0 = _abgestimmt(ordnung, altmandat, 'lauf')
    lauf = t0 + tage(120)
    assert antrag.fortschreiben(lauf)
    vf = Vertrauensfrage.objects.get(antrag=antrag)
    assert vf.ergebnis_am == t0 + tage(14)  # die Sollzeit bleibt, was sie war
    assert vf.ergebnis_veroeffentlicht_am == lauf
    assert vf.anfechtungsfrist_ende == lauf + tage(7)


def test_im_regelbetrieb_aendert_sich_nichts(ordnung, altmandat, monkeypatch):  # noqa: F811
    '''Lauf und Uhr stimmen überein — veröffentlicht ist zum Lauf, zwei Minuten nach der Sollzeit.'''
    antrag, t0 = _abgestimmt(ordnung, altmandat, 'regel')
    lauf = t0 + tage(14) + timedelta(minutes=2)
    monkeypatch.setattr(timezone, 'now', lambda: lauf)
    assert antrag.fortschreiben()
    vf = Vertrauensfrage.objects.get(antrag=antrag)
    assert vf.ergebnis_veroeffentlicht_am == lauf and vf.ergebnis_am == t0 + tage(14)


def test_ein_vorlauf_vor_einem_gremienbeschluss_datiert_die_veroeffentlichung_nicht_zurueck(ordnung, altmandat):  # noqa: F811
    '''Reiht sich der Übergang vor der Frist eines Gremienbeschlusses ein (GP-004), rechnet `_schritt`
    auf diese Frist zurück. Veröffentlicht ist trotzdem erst mit dem Lauf selbst.'''
    antrag, t0 = _abgestimmt(ordnung, altmandat, 'vorlauf')
    beschlussfrist, lauf = t0 + tage(20), t0 + tage(120)
    antrag._phasenfelder_lesen()
    assert antrag._schritt(beschlussfrist, vorlauf=True, lauf=lauf)
    vf = Vertrauensfrage.objects.get(antrag=antrag)
    assert vf.ergebnis_am == t0 + tage(14)
    assert vf.ergebnis_veroeffentlicht_am == lauf


def test_die_fortschreibung_reicht_ihren_zeitpunkt_an_den_vorlauf_weiter(ordnung, altmandat, monkeypatch):  # noqa: F811
    '''Die Aufrufstelle selbst: Liegt ein fälliger Gremienbeschluss zum Antrag vor, rechnet
    `fortschreiben` auf dessen Frist zurück und nennt dem Vorlauf den eigenen Zeitpunkt. Ohne diese
    Weitergabe gälte das Ergebnis als zur Beschlussfrist veröffentlicht — die Anfechtungsfrist (lit h)
    liefe dann schon, bevor es jemand lesen konnte.'''
    from gremien.models import GremienBeschluss

    antrag, t0 = _abgestimmt(ordnung, altmandat, 'reihe')
    beschlussfrist, lauf = t0 + tage(20), t0 + tage(120)
    monkeypatch.setattr(
        GremienBeschluss, 'faellige_zu_antrag', classmethod(lambda cls, antrag_id, jetzt: [(0, beschlussfrist)])
    )
    assert antrag.fortschreiben(lauf)
    vf = Vertrauensfrage.objects.get(antrag=antrag)
    assert vf.ergebnis_am == t0 + tage(14)
    assert vf.ergebnis_veroeffentlicht_am == lauf
    assert vf.anfechtungsfrist_ende == lauf + tage(7)
