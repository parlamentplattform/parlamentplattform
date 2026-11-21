'''Wortlaut und eingefrorene Regeln unter Siegel (Gesamtprüfung GP-067, § 5 Abs 3 und Abs 5).

„Append-only-Fassungen“ und „eingefrorene Ordnung je Antrag“ waren Übereinkunft. Jetzt gilt: Eine
bestehende Fassung und die eingefrorenen Regeln lassen sich nicht mehr schreiben; das Ereignis der
Einbringung trägt die Prüfsummen von Wortlaut und Regeln, der Abstimmungsbeginn die Prüfsumme der Fassung,
über die abgestimmt wird; Export und Prüfskript rechnen nach. Ereignisse von vor dieser Fassung gelten
als „nicht versiegelt“, nie als Fehler.'''

import copy
import hashlib
import json
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from verfahren.models import Antrag, AntragsFassung, AuditEintrag, antrag_einbringen, stimme_abgeben
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    _nachrechnen_laden,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _sha(text):
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def _regeln_sha(regeln):
    return _sha(json.dumps(regeln, sort_keys=True, separators=(',', ':'), ensure_ascii=False))


def _ereignis(antrag, typ):
    return AuditEintrag.objects.filter(ereignis__antrag=antrag.pk, ereignis__typ=typ).order_by('lfd').first().ereignis


def _beginn(antrag):
    return AuditEintrag.objects.filter(
        ereignis__antrag=antrag.pk, ereignis__typ='phasenwechsel', ereignis__neue_phase='abstimmung',
    ).order_by('-lfd').first().ereignis


def _entschieden(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f'w{i}') for i in range(4)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    for m in leute:
        stimme_abgeben(antrag, m, 'ja')
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))
    daten = json.loads(client.get(reverse('verfahren:export', args=[antrag.pk])).content)
    antrag.refresh_from_db()
    assert antrag.phase == 'angenommen'
    return antrag, daten


# --- Die Ereignisse tragen die Prüfsummen ---------------------------------------------------------------


def test_antrag_eingebracht_traegt_die_pruefsummen_von_wortlaut_und_regeln(ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    ereignis = _ereignis(antrag, 'antrag_eingebracht')
    assert ereignis['wortlaut_sha256'] == _sha(ANTRAG['wortlaut'])
    # gerechnet über das, was in der Datenbank steht — so, wie der Export es später nennt
    assert ereignis['regeln_sha256'] == _regeln_sha(Antrag.objects.get(pk=antrag.pk).policy_snapshot)


def test_auch_mandatsfrage_und_vertrauensfrage_versiegeln_wortlaut_und_regeln(ordnung, monkeypatch):  # noqa: F811
    from datetime import date

    from mandatare import models as mm
    from mandatare.models import Mandat
    from verfahren.test_mandatsfrage import eroeffnen, mandat_mit_report
    from verfahren.test_vertrauensfrage import einbringen

    mandat, aufgabe = mandat_mit_report(mitglied_anlegen('fragend'))
    frage = eroeffnen(mandat, aufgabe, ordnung)
    eroeffnet = _ereignis(frage, 'mandatsfrage_eroeffnet')
    assert eroeffnet['wortlaut_sha256'] == _sha(frage.aktueller_text().wortlaut)
    assert eroeffnet['regeln_sha256'] == _regeln_sha(Antrag.objects.get(pk=frage.pk).policy_snapshot)

    monkeypatch.setattr(mm, 'INKRAFTTRETEN_ABS_10', date(2025, 1, 1))
    altmandat = Mandat.objects.create(
        mitglied=mitglied_anlegen('mandatar', tage=600), bezeichnung='Gemeinderätin', ebene='gemeinde',
        gebiet='Polsenz', angetreten=date(2025, 1, 1),
    )
    vf = einbringen(mitglied_anlegen('stellerin'), altmandat, ordnung)
    eingebracht = _ereignis(vf, 'vertrauensfrage_eingebracht')
    assert eingebracht['wortlaut_sha256'] == _sha(vf.aktueller_text().wortlaut)
    assert eingebracht['regeln_sha256'] == _regeln_sha(Antrag.objects.get(pk=vf.pk).policy_snapshot)


def test_der_abstimmungsbeginn_versiegelt_die_fassung_ueber_die_abgestimmt_wird(client, ordnung):  # noqa: F811
    from gremien.test_werkstatt import einreichen, frist_setzen, reagieren, systembeitrag, werkstatt_lage

    leute = [mitglied_anlegen(f'r{i}') for i in range(3)]
    regel = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    beginn = _beginn(regel)
    assert (beginn['fassung'], beginn['wortlaut_sha256']) == (1, _sha(ANTRAG['wortlaut']))

    # Über die Entwurfsschleife wird der zustande gekommene Vorschlag die neue, letzte Fassung.
    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    for u in unterstuetzer:
        reagieren(client, antrag, passt, u)
    frist_setzen(entwurf, timezone.now() - timedelta(days=5))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == 'abstimmung' and antrag.fassungen.count() == 2
    beginn = _beginn(antrag)
    letzte = antrag.aktueller_text()
    assert letzte.nummer == 2
    assert (beginn['fassung'], beginn['wortlaut_sha256']) == (2, _sha(letzte.wortlaut))


# --- Schreibriegel ---------------------------------------------------------------------------------------


@pytest.mark.parametrize('weg', ['save', 'save_felder', 'update', 'bulk_update', 'delete', 'query_delete', 'umschreiben'])
def test_eine_bestehende_fassung_laesst_sich_nicht_schreiben(ordnung, weg):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    fassung = antrag.fassungen.get()
    with pytest.raises(ValidationError):
        if weg == 'save':
            fassung.wortlaut = 'Ein anderer Text.'
            fassung.save()
        elif weg == 'save_felder':
            fassung.begruendung = 'Eine andere Begründung.'
            fassung.save(update_fields=['begruendung'])
        elif weg == 'update':
            antrag.fassungen.update(wortlaut='Ein anderer Text.')
        elif weg == 'bulk_update':
            fassung.wortlaut = 'Ein anderer Text.'
            AntragsFassung.objects.bulk_update([fassung], ['wortlaut'])
        elif weg == 'delete':
            fassung.delete()
        elif weg == 'query_delete':
            AntragsFassung.objects.filter(antrag=antrag).delete()
        else:
            AntragsFassung.objects.update_or_create(antrag=antrag, nummer=1, defaults={'wortlaut': 'Ein anderer Text.'})
    assert list(antrag.fassungen.values_list('nummer', 'wortlaut', 'begruendung')) == [
        (1, ANTRAG['wortlaut'], ANTRAG['begruendung'])
    ]


def test_eine_neue_fassung_laesst_sich_weiter_anhaengen(ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    AntragsFassung.objects.create(antrag=antrag, nummer=2, wortlaut='Zweite Fassung.')
    antrag.fassungen.create(nummer=3, wortlaut='Dritte Fassung.')
    AntragsFassung.objects.bulk_create([AntragsFassung(antrag=antrag, nummer=4, wortlaut='Vierte Fassung.')])
    assert antrag.aktueller_text().nummer == 4 and antrag.fassungen.count() == 4


@pytest.mark.parametrize('weg', ['save', 'save_ganz', 'update', 'bulk_update'])
def test_die_eingefrorenen_regeln_lassen_sich_nicht_schreiben(ordnung, weg):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    vorher = copy.deepcopy(Antrag.objects.get(pk=antrag.pk).policy_snapshot)
    neu = {**vorher, 'mindestbeteiligung': 0.5, 'abstimmung_tage': 30}
    with pytest.raises(ValidationError):
        if weg == 'update':
            Antrag.objects.filter(pk=antrag.pk).update(policy_snapshot=neu)
        else:
            antrag.policy_snapshot = neu
            if weg == 'save':
                antrag.save(update_fields=['policy_snapshot'])
            elif weg == 'save_ganz':
                antrag.save()
            else:
                Antrag.objects.bulk_update([antrag], ['policy_snapshot'])
    assert Antrag.objects.get(pk=antrag.pk).policy_snapshot == vorher


def test_speichern_mit_unveraenderten_regeln_bleibt_moeglich(ordnung):  # noqa: F811
    '''Der Riegel vergleicht den Inhalt: Das eben eingebrachte Objekt (Regeln noch als Python-Werte im
    Speicher) und ein aus der Datenbank gelesenes lassen sich ganz speichern, solange die Regeln gleich
    sind — und der Lauf des Verfahrens schreibt weiter.'''
    leute = [mitglied_anlegen(f'u{i}') for i in range(3)]
    antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    antrag.titel = 'Neuer Titel'
    antrag.save()
    gelesen = Antrag.objects.get(pk=antrag.pk)
    gelesen.hervorhebung_begruendung = 'Betrifft alle.'
    gelesen.save()
    gelesen.save(update_fields=['policy_snapshot'])  # dieselben Regeln: kein Schreiben, kein Fehler
    in_abstimmung_bringen(gelesen, leute[1:3])
    assert gelesen.phase == 'abstimmung'


def test_altbestand_mit_alter_ordnung_laeuft_und_speichert_weiter(ordnung):  # noqa: F811
    '''Ein Schnappschuss von vor dieser Fassung (ohne spätere Felder) bleibt, wie er ist: Der Riegel
    prüft keinen Inhalt, er lässt nur keine Änderung zu.'''
    leute = [mitglied_anlegen(f'a{i}') for i in range(3)]
    antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    alt = dict(antrag.policy_snapshot)
    for feld in ('uebergangsregel', 'vorschlag_annahme_anteil', 'beratung_entfaellt'):
        alt.pop(feld, None)
    Antrag._base_manager.filter(pk=antrag.pk).update(policy_snapshot=alt)
    antrag.refresh_from_db()
    antrag.hervorhebung_begruendung = 'Altbestand.'
    antrag.save()
    in_abstimmung_bringen(antrag, leute[1:3])
    antrag.refresh_from_db()
    assert antrag.phase == 'abstimmung' and antrag.policy_snapshot == alt


# --- Export, Archiv und Prüfskript -------------------------------------------------------------------------


def test_der_export_nennt_die_fassungen_und_das_pruefskript_rechnet_wortlaut_und_regeln_nach(client, ordnung):  # noqa: F811
    antrag, daten = _entschieden(client, ordnung)
    assert daten['fassungen'] == [{'nummer': 1, 'wortlaut': ANTRAG['wortlaut']}]
    nachrechnen = _nachrechnen_laden()
    ergebnis = nachrechnen(copy.deepcopy(daten))
    assert ergebnis['angenommen'] is True
    assert ergebnis['regeln_versiegelt'] is True and ergebnis['wortlaut_versiegelt'] is True

    andere_regeln = copy.deepcopy(daten)
    andere_regeln['policy']['mindestbeteiligung'] = 0.5
    with pytest.raises(SystemExit, match='FEHLER.*Regeln'):
        nachrechnen(andere_regeln)
    anderer_text = copy.deepcopy(daten)
    anderer_text['fassungen'][0]['wortlaut'] = 'Noch ein anderer Text, während die Abstimmung läuft.'
    with pytest.raises(SystemExit, match='FEHLER.*Wortlaut'):
        nachrechnen(anderer_text)
    ohne_text = copy.deepcopy(daten)
    ohne_text['fassungen'] = []
    with pytest.raises(SystemExit, match='FEHLER.*Fassung 1'):
        nachrechnen(ohne_text)


def test_ein_export_von_vor_dieser_fassung_gilt_als_nicht_versiegelt(client, ordnung):  # noqa: F811
    '''Altbestand: Die Ereignisse tragen keine Prüfsummen, der Export keine Fassungen. Das Prüfskript
    rechnet wie bisher und meldet „nicht versiegelt“ statt eines Fehlers.'''
    antrag, daten = _entschieden(client, ordnung)
    alt = copy.deepcopy(daten)
    alt.pop('fassungen')
    for eintrag in alt['audit']:
        for feld in ('wortlaut_sha256', 'regeln_sha256', 'fassung'):
            eintrag['ereignis'].pop(feld, None)
    ergebnis = _nachrechnen_laden()(alt)
    assert ergebnis['angenommen'] is True
    assert ergebnis['regeln_versiegelt'] is False and ergebnis['wortlaut_versiegelt'] is False
    ohne_audit = {k: v for k, v in alt.items() if k != 'audit'}
    ergebnis = _nachrechnen_laden()(ohne_audit)
    assert ergebnis['regeln_versiegelt'] is False and ergebnis['wortlaut_versiegelt'] is False


def test_ein_antrag_von_vor_dieser_fassung_wird_exportiert_und_nachgerechnet(client, ordnung):  # noqa: F811
    '''Altbestand in der Datenbank: Die Ereignisse der Einbringung und des Abstimmungsbeginns sind alt
    (ohne Prüfsummen). Export, Archiv und Prüfskript arbeiten; versiegelt ist nur, was diese Fassung
    selbst schreibt.'''
    leute = [mitglied_anlegen(f'a{i}') for i in range(4)]
    jetzt = timezone.now()
    antrag = Antrag.objects.create(
        titel='Altantrag', eingebracht_von=leute[0], policy_snapshot=ordnung.als_policy().als_dict(),
        phase='abstimmung', phase_beginn=jetzt, stimmberechtigte_anzahl=4, stimmberechtigung_stichtag=timezone.localdate(jetzt),
    )
    AntragsFassung.objects.create(antrag=antrag, nummer=1, wortlaut='Alter Wortlaut.')
    AuditEintrag.anhaengen({'typ': 'antrag_eingebracht', 'antrag': antrag.pk, 'titel': 'Altantrag', 'policy': 'test-ordnung v1'})
    AuditEintrag.anhaengen({'typ': 'phasenwechsel', 'antrag': antrag.pk, 'neue_phase': 'abstimmung', 'wirksam_ab': jetzt.isoformat()})
    for m in leute:
        stimme_abgeben(antrag, m, 'ja')
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=jetzt - timedelta(days=8))
    daten = json.loads(client.get(reverse('verfahren:export', args=[antrag.pk])).content)
    ergebnis = _nachrechnen_laden()(daten)
    assert ergebnis['angenommen'] is True
    assert ergebnis['regeln_versiegelt'] is False and ergebnis['wortlaut_versiegelt'] is False
    assert client.get(reverse('verfahren:archiv_export', args=[antrag.pk, 'json'])).status_code == 200
    assert client.get(reverse('verfahren:antrag', args=[antrag.pk])).status_code == 200


def test_das_archiv_gibt_die_pruefsumme_je_fassung_aus(client, ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    archiv = json.loads(client.get(reverse('verfahren:archiv_export', args=[antrag.pk, 'json'])).content)
    (fassung,) = archiv['fassungen']
    assert fassung['wortlaut_sha256'] == _sha(ANTRAG['wortlaut'])
    assert fassung['wortlaut_sha256'] == _ereignis(antrag, 'antrag_eingebracht')['wortlaut_sha256']
