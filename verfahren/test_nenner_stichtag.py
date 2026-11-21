"""Der Nenner hängt am Stichtag, nicht am Tag der Verarbeitung (GP-094, § 4 Abs 4 lit a)."""

from datetime import timedelta

import pytest
from django.utils import timezone

from mitglieder.models import Mitgliedsstatus
from plattform_core import Gegenstand
from verfahren.models import Antrag, antrag_einbringen
from verfahren.teilnahme import berechtigte_zaehlen, kreis_festhalten, stimmrecht_im_neuen_kreis
from verfahren.test_teilnahme_fundament import mit_ort, orte, vorbereiten  # noqa: F401
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _fall(ordnung, spaet):  # noqa: F811
    """Zehn Stimmberechtigte; die Beratung endete vor drei Tagen. Zwei Mitglieder werden NACH dem
    Stichtag pausiert. Pünktlich: Der Wächter schrieb fünf Minuten nach Fristende fort. Verspätet:
    Er stand, und erst der heutige Aufruf stellt den Nenner fest."""
    jetzt = timezone.now()
    leute = [mitglied_anlegen(f'm{i}') for i in range(10)]
    antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    for u in leute[1:3]:
        antrag.unterstuetzungen.create(mitglied=u)
    antrag.fortschreiben()
    assert antrag.phase == 'beratung'
    frist = timedelta(days=antrag.policy_snapshot['beratung_tage'])
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=jetzt - frist - timedelta(days=3))
    antrag.refresh_from_db()
    if not spaet:
        antrag.fortschreiben(jetzt - timedelta(days=3) + timedelta(minutes=5))
    for konto in leute[8:]:
        konto.save(update_fields=konto.status_setzen(Mitgliedsstatus.PAUSIERT, 'Beitrag ausständig'))
    antrag.refresh_from_db()
    antrag.fortschreiben(jetzt)
    antrag.refresh_from_db()
    assert antrag.phase == 'abstimmung'
    return antrag, timezone.localdate(jetzt - timedelta(days=3))


@pytest.mark.parametrize('spaet', [False, True])
def test_puenktliche_und_verspaetete_verarbeitung_liefern_denselben_nenner(ordnung, spaet):  # noqa: F811
    antrag, stichtag = _fall(ordnung, spaet)
    assert antrag.stimmberechtigung_stichtag == stichtag
    assert antrag.stimmberechtigte_anzahl == 10


def test_festgehaltener_nenner_wird_nicht_neu_gerechnet(ordnung):  # noqa: F811
    """Altbestand: Eine vor dieser Fassung festgestellte Zahl bleibt, was sie war."""
    antrag, _stichtag = _fall(ordnung, spaet=False)
    Antrag._base_manager.filter(pk=antrag.pk).update(stimmberechtigte_anzahl=8)
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.stimmberechtigte_anzahl == 8


def test_oertlicher_kreis_zaehlt_wie_die_bundesebene_am_stichtag(ordnung, orte):  # noqa: F811
    heute = timezone.localdate()
    stichtag = heute - timedelta(days=3)
    autor, zweite = mit_ort('autor', orte[0]), mit_ort('zweite', orte[0])
    antrag = vorbereiten(ordnung, autor)
    kreis_festhalten(antrag)
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, stichtag) == 2
    zweite.save(update_fields=zweite.status_setzen(Mitgliedsstatus.PAUSIERT, 'Beitrag ausständig'))
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, stichtag) == 2
    assert berechtigte_zaehlen(antrag, Gegenstand.SACHFRAGE, zweite.status_seit) == 1
    # Einzelprüfung: während der Pause ruhen die Rechte; danach stimmt mit, wer im Nenner stand.
    Antrag.objects.filter(pk=antrag.pk).update(stimmberechtigung_stichtag=stichtag, stimmberechtigte_anzahl=2)
    antrag.refresh_from_db()
    assert not stimmrecht_im_neuen_kreis(antrag, zweite, frisch=True)
    zweite.save(update_fields=zweite.status_setzen(Mitgliedsstatus.AKTIV, ''))
    assert stimmrecht_im_neuen_kreis(antrag, zweite, frisch=True)


def test_altbestand_ohne_stichtag_laeuft_regulaer_zu_ende_und_behaelt_seinen_nenner(ordnung):  # noqa: F811
    """Altbestand von vor dem Stichtagsfeld: Zahl festgestellt, Stichtag leer. Der reguläre Weg bis
    zum Ergebnis schreibt keines der beiden Felder und scheitert nicht am Schreibriegel (GP-028)."""
    antrag, _stichtag = _fall(ordnung, spaet=False)
    Antrag._base_manager.filter(pk=antrag.pk).update(stimmberechtigte_anzahl=8, stimmberechtigung_stichtag=None)
    antrag.refresh_from_db()
    ende = antrag.phase_beginn + timedelta(days=antrag.policy_snapshot['abstimmung_tage'], minutes=1)
    assert antrag.fortschreiben(ende)
    antrag.refresh_from_db()
    assert antrag.phase in ('angenommen', 'abgelehnt')
    assert antrag.stimmberechtigte_anzahl == 8 and antrag.stimmberechtigung_stichtag is None
