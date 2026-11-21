'''Der Nenner unter Siegel (Gesamtprüfung GP-028, § 4 Abs 4 lit a).

Die Zahl der Stimmberechtigten und ihr Stichtag entscheiden über die Mindestbeteiligung. Sie stehen im
Ereignis des Abstimmungsbeginns (alle drei Wege), lassen sich nach dem Feststellen nicht mehr ändern, und
das Prüfskript vergleicht den Export mit der Kette. Ereignisse von vor dieser Fassung tragen die Felder
nicht: Sie gelten als „nicht versiegelt“, nie als Fehler.'''

import copy
import json
from datetime import date, timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from verfahren.models import Antrag, AuditEintrag, antrag_einbringen, stimme_abgeben
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    _nachrechnen_laden,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _beginn(antrag):
    '''Die Ereignisse, mit denen die Abstimmung dieses Antrags begann.'''
    return [
        e.ereignis
        for e in AuditEintrag.objects.filter(ereignis__antrag=antrag.pk, ereignis__typ='phasenwechsel').order_by('lfd')
        if e.ereignis.get('neue_phase') == 'abstimmung'
    ]


def _laufende_abstimmung(ordnung, anzahl=4):  # noqa: F811
    leute = [mitglied_anlegen(f'n{i}') for i in range(anzahl)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.refresh_from_db()
    return antrag, leute


def _entschieden(client, antrag, leute):
    for m in leute:
        stimme_abgeben(antrag, m, 'ja')
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))
    daten = json.loads(client.get(reverse('verfahren:export', args=[antrag.pk])).content)
    antrag.refresh_from_db()
    assert antrag.phase == 'angenommen'
    return daten


# --- Das Ereignis des Abstimmungsbeginns trägt Nenner und Stichtag (alle drei Wege) -----------------


def test_der_regeluebergang_haelt_nenner_und_stichtag_im_ereignis_fest(ordnung):  # noqa: F811
    antrag, _leute = _laufende_abstimmung(ordnung)
    (wechsel,) = _beginn(antrag)
    assert antrag.stimmberechtigte_anzahl == 4
    assert wechsel['stimmberechtigte'] == antrag.stimmberechtigte_anzahl
    assert wechsel['stichtag'] == antrag.stimmberechtigung_stichtag.isoformat()


def test_die_mandatsfrage_haelt_nenner_und_stichtag_im_ereignis_fest(ordnung):  # noqa: F811
    from verfahren.test_mandatsfrage import eroeffnen, mandat_mit_report

    leute = [mitglied_anlegen(f'm{i}') for i in range(3)]
    mandat, aufgabe = mandat_mit_report(leute[0])
    antrag = eroeffnen(mandat, aufgabe, ordnung)
    (wechsel,) = _beginn(antrag)
    assert wechsel['stimmberechtigte'] == antrag.stimmberechtigte_anzahl == 3
    assert wechsel['stichtag'] == antrag.stimmberechtigung_stichtag.isoformat()


def test_die_endabstimmung_der_schleife_haelt_nenner_und_stichtag_im_ereignis_fest(client, ordnung):  # noqa: F811
    from gremien.test_werkstatt import einreichen, frist_setzen, reagieren, systembeitrag, werkstatt_lage

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    for u in unterstuetzer:
        reagieren(client, antrag, passt, u)
    frist_setzen(entwurf, timezone.now() - timedelta(days=5))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == 'abstimmung'
    (wechsel,) = _beginn(antrag)
    assert 'entwurfsfassung' in wechsel  # der Weg über die Entwurfsschleife
    assert wechsel['stimmberechtigte'] == antrag.stimmberechtigte_anzahl
    assert wechsel['stichtag'] == antrag.stimmberechtigung_stichtag.isoformat()


def test_das_ereignis_bleibt_oeffentlich_ungeschwaerzt_und_nachrechenbar(client, ordnung):  # noqa: F811
    antrag, leute = _laufende_abstimmung(ordnung)
    daten = _entschieden(client, antrag, leute)
    (eintrag,) = [e for e in daten['audit'] if e['typ'] == 'phasenwechsel' and e['ereignis'].get('neue_phase') == 'abstimmung']
    assert eintrag['geschwaerzt'] is False and eintrag['hash']
    assert eintrag['ereignis']['stimmberechtigte'] == 4


# --- Schreibriegel: Was festgestellt ist, bleibt ------------------------------------------------------


@pytest.mark.parametrize('feld,wert', [
    ('stimmberechtigte_anzahl', 80), ('stimmberechtigte_anzahl', None),
    ('stimmberechtigung_stichtag', date(2020, 1, 1)), ('stimmberechtigung_stichtag', None),
])
@pytest.mark.parametrize('weg', ['save', 'save_ganz', 'update', 'bulk_update'])
def test_festgestellter_nenner_und_stichtag_bleiben_unveraendert(ordnung, feld, wert, weg):  # noqa: F811
    antrag, _leute = _laufende_abstimmung(ordnung)
    vorher = (antrag.stimmberechtigte_anzahl, antrag.stimmberechtigung_stichtag)
    with pytest.raises(ValidationError):
        if weg == 'update':
            Antrag.objects.filter(pk=antrag.pk).update(**{feld: wert})
        else:
            setattr(antrag, feld, wert)
            if weg == 'save':
                antrag.save(update_fields=[feld])
            elif weg == 'save_ganz':
                antrag.save()
            else:
                Antrag.objects.bulk_update([antrag], [feld])
    antrag.refresh_from_db()
    assert (antrag.stimmberechtigte_anzahl, antrag.stimmberechtigung_stichtag) == vorher


def test_die_regulaeren_wege_schreiben_weiter(ordnung):  # noqa: F811
    '''Feststellen beim Übergang, Speichern anderer Felder, Speichern ohne Feldliste mit unveränderten
    Werten und der weitere Lauf bis zum Ergebnis bleiben möglich.'''
    antrag, leute = _laufende_abstimmung(ordnung)
    nenner, stichtag = antrag.stimmberechtigte_anzahl, antrag.stimmberechtigung_stichtag
    antrag.hervorhebung_begruendung = 'Betrifft alle.'
    antrag.save(update_fields=['hervorhebung_begruendung'])
    antrag.save()
    Antrag.objects.filter(pk=antrag.pk).update(titel='Neuer Titel')
    for m in leute:
        stimme_abgeben(antrag, m, 'ja')
    assert antrag.fortschreiben(antrag.phase_beginn + timedelta(days=8)) is True
    antrag.refresh_from_db()
    assert antrag.phase == 'angenommen'
    assert (antrag.stimmberechtigte_anzahl, antrag.stimmberechtigung_stichtag) == (nenner, stichtag)


def test_altbestand_ohne_stichtag_laesst_sich_weiter_speichern(ordnung):  # noqa: F811
    '''Ein entschiedener Antrag von vor Fassung 0.17 trägt einen Nenner, aber keinen Stichtag. Der Riegel
    hält den Nenner und stört das Speichern anderer Felder nicht.'''
    antrag = antrag_einbringen(mitglied_anlegen('alt'), **ANTRAG, ordnung=ordnung)
    Antrag._base_manager.filter(pk=antrag.pk).update(phase='abgelehnt', stimmberechtigte_anzahl=7)
    antrag.refresh_from_db()
    assert antrag.stimmberechtigung_stichtag is None
    antrag.hervorhebung_begruendung = 'Altbestand.'
    antrag.save()
    with pytest.raises(ValidationError):
        Antrag.objects.filter(pk=antrag.pk).update(stimmberechtigte_anzahl=8)
    antrag.refresh_from_db()
    assert antrag.stimmberechtigte_anzahl == 7


# --- Export und Prüfskript -----------------------------------------------------------------------------


def test_der_export_nennt_den_stichtag_und_das_pruefskript_vergleicht_mit_der_kette(client, ordnung):  # noqa: F811
    antrag, leute = _laufende_abstimmung(ordnung)
    daten = _entschieden(client, antrag, leute)
    assert daten['stichtag'] == antrag.stimmberechtigung_stichtag.isoformat()
    nachrechnen = _nachrechnen_laden()
    ergebnis = nachrechnen(copy.deepcopy(daten))
    assert ergebnis['angenommen'] is True and ergebnis['nenner_versiegelt'] is True

    falscher_nenner = {**copy.deepcopy(daten), 'stimmberechtigte': 80}
    with pytest.raises(SystemExit, match='FEHLER.*Stimmberechtigte'):
        nachrechnen(falscher_nenner)
    falscher_stichtag = {**copy.deepcopy(daten), 'stichtag': '2020-01-01'}
    with pytest.raises(SystemExit, match='FEHLER.*Stichtag'):
        nachrechnen(falscher_stichtag)


def test_ein_export_von_vor_dieser_fassung_gilt_als_nicht_versiegelt(client, ordnung):  # noqa: F811
    '''Altbestand: Das Ereignis des Abstimmungsbeginns trägt weder Nenner noch Stichtag, der Export keinen
    Stichtag. Das Prüfskript rechnet wie bisher und meldet „nicht versiegelt“ statt eines Fehlers.'''
    antrag, leute = _laufende_abstimmung(ordnung)
    daten = _entschieden(client, antrag, leute)
    alt = copy.deepcopy(daten)
    alt.pop('stichtag')
    for eintrag in alt['audit']:
        if eintrag['typ'] == 'phasenwechsel':
            eintrag['ereignis'].pop('stimmberechtigte', None)
            eintrag['ereignis'].pop('stichtag', None)
    nachrechnen = _nachrechnen_laden()
    ergebnis = nachrechnen(alt)
    assert ergebnis['angenommen'] is True and ergebnis['nenner_versiegelt'] is False
    ohne_audit = {k: v for k, v in alt.items() if k != 'audit'}
    assert nachrechnen(ohne_audit)['nenner_versiegelt'] is False


def test_ein_altes_ereignis_ohne_die_felder_stoert_seite_und_export_nicht(client, ordnung):  # noqa: F811
    '''Altbestand in der Datenbank: Eine vor dieser Fassung begonnene Abstimmung (Ereignis ohne Nenner)
    läuft zu Ende; Export und Antragsseite arbeiten.'''
    leute = [mitglied_anlegen(f'a{i}') for i in range(4)]
    antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    jetzt = timezone.now()
    Antrag._base_manager.filter(pk=antrag.pk).update(
        phase='abstimmung', phase_beginn=jetzt, stimmberechtigte_anzahl=4, stimmberechtigung_stichtag=timezone.localdate(jetzt),
    )
    AuditEintrag.anhaengen({
        'typ': 'phasenwechsel', 'antrag': antrag.pk, 'neue_phase': 'abstimmung',
        'wirksam_ab': jetzt.isoformat(), 'grund': 'Beratungsphase beendet.', 'chat_archiviert': 0,
    })
    antrag.refresh_from_db()
    daten = _entschieden(client, antrag, leute)
    assert daten['stichtag'] == timezone.localdate(jetzt).isoformat()
    ergebnis = _nachrechnen_laden()(daten)
    assert ergebnis['angenommen'] is True and ergebnis['nenner_versiegelt'] is False
    assert client.get(reverse('verfahren:antrag', args=[antrag.pk])).status_code == 200
