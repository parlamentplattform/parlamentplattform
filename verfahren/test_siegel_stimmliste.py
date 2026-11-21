'''Stimmzettel unter Schutz und Gegenprobe (Gesamtprüfung GP-138).

Die Kette bewies bisher, dass Stimm-Ereignisse stattfanden — nicht, welche Stimmen gezählt wurden. Jetzt
gilt: Stimmzettel lassen sich nur auf dem Weg der Stimmabgabe schreiben; vor der Feststellung eines
Ergebnisses vergleicht die Plattform Stimmzettel, Stimmregister, Nenner und Stimm-Ereignisse und hält bei
einer Abweichung an, statt ein Ergebnis festzustellen; das Ergebnis-Ereignis trägt die Prüfsumme der
Stimmliste, und das Prüfskript rechnet sie nach.'''

import copy
import json
import uuid
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from plattform_core.tally import EREIGNISSE_WEICHEN_AB, OHNE_REGISTERZEILE, UEBERZAHL
from verfahren.models import (
    Antrag,
    AuditEintrag,
    BewerbungsZustimmung,
    Stimmabgabe,
    StimmRegister,
    antrag_einbringen,
    bewerbung_einreichen,
    bewerbung_zustimmen,
    stimme_abgeben,
)
from verfahren.test_kandidatur import _in_abstimmung, _kandidatur
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    _nachrechnen_laden,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _abstimmung(ordnung, anzahl=6, stimmen=('ja', 'ja', 'nein')):  # noqa: F811
    leute = [mitglied_anlegen(f's{i}') for i in range(anzahl)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.refresh_from_db()
    for m, wahl in zip(leute, stimmen, strict=False):
        stimme_abgeben(antrag, m, wahl)
    return antrag, leute


def _fristende(antrag):
    return antrag.phase_beginn + timedelta(days=8)


def _halte(antrag):
    return [
        e.ereignis
        for e in AuditEintrag.objects.filter(ereignis__antrag=antrag.pk, ereignis__typ='auszaehlung_angehalten').order_by('lfd')
    ]


def _ergebnis_ereignis(antrag):
    return AuditEintrag.objects.filter(
        ereignis__antrag=antrag.pk, ereignis__typ='phasenwechsel', ereignis__neue_phase__in=['angenommen', 'abgelehnt'],
    ).order_by('-lfd').first().ereignis


def _zettel_einschleusen(antrag, mitglied=None, stimme='ja'):
    '''Ein Stimmzettel an den Fachwegen vorbei, wie ihn nur ein Datenbankzugriff anlegen kann —
    mit `mitglied` samt Registerzeile, sonst unter einem erfundenen Pseudonym.'''
    pseudonym = uuid.uuid4()
    if mitglied is not None:
        StimmRegister.objects.create(antrag=antrag, mitglied=mitglied, pseudonym=pseudonym)
    Stimmabgabe._base_manager.bulk_create([Stimmabgabe(antrag=antrag, pseudonym=pseudonym, stimme=stimme)])
    return pseudonym


# --- Gegenprobe vor der Feststellung: ausgewiesener Fehlerzustand statt Ergebnis ----------------------


def test_ein_stimmzettel_ohne_registerzeile_haelt_die_auszaehlung_an(client, ordnung):  # noqa: F811
    antrag, _leute = _abstimmung(ordnung)
    erfunden = _zettel_einschleusen(antrag)
    ende = _fristende(antrag)

    assert antrag.fortschreiben(ende) is False
    antrag.refresh_from_db()
    assert antrag.phase == 'abstimmung'  # kein Ergebnis
    (halt,) = _halte(antrag)
    # Der erfundene Zettel hat weder Registerzeile noch Stimm-Ereignis — beides steht im Befund.
    assert halt['abweichungen'] == [OHNE_REGISTERZEILE, EREIGNISSE_WEICHEN_AB]
    assert (halt['stimmzettel'], halt['ohne_registerzeile'], halt['stimmberechtigte']) == (4, 1, 6)
    assert halt['stimmereignisse'] == 3
    assert 'ohne Registerzeile' in halt['grund'] and 'kein Ergebnis' in halt['grund']
    # ohne personenbezogene Werte: keine Pseudonyme, keine Kennungen
    assert erfunden.hex not in json.dumps(halt) and 'mitglied' not in halt
    assert antrag.auszaehlung_angehalten() == halt

    # Wiederholtes Fortschreiben (jeder Seitenaufruf, jeder Takt des Wächters) schreibt nicht noch einmal.
    assert antrag.fortschreiben(ende) is False
    assert antrag.fortschreiben_bis_zum_stand(ende) == 0
    assert len(_halte(antrag)) == 1


def test_der_angehaltene_antrag_bleibt_lesbar_und_weist_den_befund_aus(client, ordnung):  # noqa: F811
    antrag, _leute = _abstimmung(ordnung)
    _zettel_einschleusen(antrag)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))

    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk]))
    assert seite.status_code == 200
    inhalt = seite.content.decode()
    assert 'auszaehlung_angehalten' in inhalt and 'ohne Registerzeile' in inhalt  # Audit-Spur im Archiv
    assert client.get(reverse('verfahren:export', args=[antrag.pk])).status_code == 409  # kein Ergebnis, kein Export
    antrag.refresh_from_db()
    assert antrag.phase == 'abstimmung'


def test_nach_der_klaerung_wird_das_ergebnis_festgestellt(ordnung):  # noqa: F811
    antrag, _leute = _abstimmung(ordnung)
    erfunden = _zettel_einschleusen(antrag)
    ende = _fristende(antrag)
    assert antrag.fortschreiben(ende) is False
    Stimmabgabe._base_manager.filter(antrag=antrag, pseudonym=erfunden).delete()  # nur mit Datenbankzugriff

    assert antrag.fortschreiben(ende) is True
    antrag.refresh_from_db()
    assert antrag.phase == 'angenommen' and antrag.auszaehlung_angehalten() is None
    assert len(_halte(antrag)) == 1  # der Halt bleibt in der Kette stehen


def test_mehr_stimmen_als_stimmberechtigte_halten_an(ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f's{i}') for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.refresh_from_db()
    assert antrag.stimmberechtigte_anzahl == 3
    for m in leute:
        stimme_abgeben(antrag, m, 'ja')
    _zettel_einschleusen(antrag, mitglied_anlegen('spaeter'))

    assert antrag.fortschreiben(_fristende(antrag)) is False
    (halt,) = _halte(antrag)
    assert UEBERZAHL in halt['abweichungen'] and (halt['stimmzettel'], halt['stimmberechtigte']) == (4, 3)


def test_ein_stimmzettel_ohne_stimmereignis_haelt_an(ordnung):  # noqa: F811
    antrag, leute = _abstimmung(ordnung)
    _zettel_einschleusen(antrag, leute[5])  # mit Registerzeile, innerhalb des Nenners — aber ohne Ereignis

    assert antrag.fortschreiben(_fristende(antrag)) is False
    (halt,) = _halte(antrag)
    assert halt['abweichungen'] == [EREIGNISSE_WEICHEN_AB]
    assert (halt['stimmzettel'], halt['stimmereignisse']) == (4, 3)


def test_eine_abstimmung_von_vor_dieser_fassung_laeuft_zu_ende(client, ordnung):  # noqa: F811
    '''Altbestand: Die Abstimmung begann, bevor ihr Beginn versiegelt wurde, und ihre Stimmzettel haben
    Registerzeilen, aber nicht zu jedem ein Stimm-Ereignis. Die Zahl der Ereignisse wird dann nicht
    geprüft; das Ergebnis ist dasselbe wie vor dieser Fassung.'''
    leute = [mitglied_anlegen(f'a{i}') for i in range(5)]
    antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    jetzt = timezone.now()
    Antrag._base_manager.filter(pk=antrag.pk).update(
        phase='abstimmung', phase_beginn=jetzt, stimmberechtigte_anzahl=5, stimmberechtigung_stichtag=timezone.localdate(jetzt),
    )
    AuditEintrag.anhaengen({'typ': 'phasenwechsel', 'antrag': antrag.pk, 'neue_phase': 'abstimmung', 'wirksam_ab': jetzt.isoformat()})
    antrag.refresh_from_db()
    for m in leute[:3]:
        _zettel_einschleusen(antrag, m)

    assert antrag.fortschreiben(_fristende(antrag)) is True
    antrag.refresh_from_db()
    assert antrag.phase == 'angenommen' and _halte(antrag) == []
    ereignis = _ergebnis_ereignis(antrag)
    assert ereignis['grund'] == 'Angenommen: Ja 3 : Nein 0, Enthaltungen 0; Beteiligung 3/5 (§ 5 Abs 4).'
    assert ereignis['stimmzettel'] == 3 and 'stimmereignisse' not in ereignis
    daten = json.loads(client.get(reverse('verfahren:export', args=[antrag.pk])).content)
    ergebnis = _nachrechnen_laden()(daten)
    assert ergebnis['angenommen'] is True and ergebnis['stimmliste_versiegelt'] is True


def test_ein_unverfaelschter_bestand_ergibt_dasselbe_wie_bisher(ordnung):  # noqa: F811
    antrag, _leute = _abstimmung(ordnung, stimmen=('ja', 'ja', 'nein', 'enthaltung'))
    vorher = antrag.auszaehlen()
    assert antrag.fortschreiben(_fristende(antrag)) is True
    antrag.refresh_from_db()
    assert antrag.phase == 'angenommen' and _halte(antrag) == []
    ereignis = _ergebnis_ereignis(antrag)
    assert ereignis['grund'] == vorher.begruendung == 'Angenommen: Ja 2 : Nein 1, Enthaltungen 1; Beteiligung 4/6 (§ 5 Abs 4).'
    assert antrag.auszaehlen() == vorher


# --- Abschluss-Eintrag mit Prüfsumme, Export, Prüfskript ------------------------------------------------


def _export(client, antrag):
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))
    return json.loads(client.get(reverse('verfahren:export', args=[antrag.pk])).content)


def test_das_ergebnis_ereignis_versiegelt_die_stimmliste_und_das_pruefskript_rechnet_nach(client, ordnung):  # noqa: F811
    from plattform_core.tally import stimmliste_pruefsumme

    antrag, _leute = _abstimmung(ordnung)
    daten = _export(client, antrag)
    ereignis = _ergebnis_ereignis(antrag)
    summe = stimmliste_pruefsumme([s['pseudonym'], s['stimme']] for s in daten['stimmen'])
    assert ereignis['stimmliste_sha256'] == daten['stimmliste_sha256'] == summe
    assert (ereignis['stimmzettel'], ereignis['stimmereignisse']) == (3, 3)
    ergebnis = _nachrechnen_laden()(copy.deepcopy(daten))
    assert ergebnis['angenommen'] is True and ergebnis['stimmliste_versiegelt'] is True


def test_das_pruefskript_endet_bei_ueberzahl_abweichung_und_falscher_pruefsumme_mit_fehler(client, ordnung):  # noqa: F811
    antrag, _leute = _abstimmung(ordnung)
    daten = _export(client, antrag)
    nachrechnen = _nachrechnen_laden()

    umgeschrieben = copy.deepcopy(daten)
    umgeschrieben['stimmen'][0]['stimme'] = 'nein' if umgeschrieben['stimmen'][0]['stimme'] == 'ja' else 'ja'
    with pytest.raises(SystemExit, match='FEHLER.*Prüfsumme'):
        nachrechnen(umgeschrieben)

    erfunden = copy.deepcopy(daten)
    erfunden['stimmen'].append({'pseudonym': uuid.uuid4().hex, 'stimme': 'ja'})
    with pytest.raises(SystemExit, match='FEHLER'):
        nachrechnen(erfunden)

    ueberzahl = copy.deepcopy(daten)
    ueberzahl['stimmen'] += [{'pseudonym': uuid.uuid4().hex, 'stimme': 'ja'} for _ in range(10)]
    with pytest.raises(SystemExit, match='FEHLER.*mehr Stimmen als Stimmberechtigte'):
        nachrechnen(ueberzahl)

    # Zahl der Stimm-Ereignisse: ein Ereignis „stimme“ aus der Spur genommen
    ohne_ereignis = copy.deepcopy(daten)
    ohne_ereignis['audit'].remove(next(e for e in ohne_ereignis['audit'] if e['typ'] == 'stimme'))
    with pytest.raises(SystemExit, match='FEHLER.*Stimm-Ereignisse'):
        nachrechnen(ohne_ereignis)


def test_ueberzahl_ist_auch_ohne_audit_spur_ein_fehler():
    nachrechnen = _nachrechnen_laden()
    export = {
        'art': 'sache', 'policy': {'mindestbeteiligung': 0.05}, 'stimmberechtigte': 5,
        'stimmen': [{'pseudonym': f'p{i}', 'stimme': 'ja'} for i in range(9)],
    }
    with pytest.raises(SystemExit, match='FEHLER.*mehr Stimmen als Stimmberechtigte'):
        nachrechnen(export)
    wahl = {
        'art': 'mandat', 'policy': {'mindestbeteiligung': 0.05}, 'stimmberechtigte': 2,
        'bewerbungen': [{'bewerbung': 1, 'name': 'A'}],
        'zustimmungen': [{'pseudonym': f'p{i}', 'bewerbung': 1} for i in range(3)],
    }
    with pytest.raises(SystemExit, match='FEHLER.*mehr Stimmen als Stimmberechtigte'):
        nachrechnen(wahl)


#: Ein Export, wie ihn der Live-Stand 0.114.0 liefert (gekürzt): ohne Stichtag, ohne Prüfsumme, die
#: Ereignisse ohne die neuen Felder — und die ältesten sogar ohne `zeit` und `grund`.
ALTER_EXPORT = {
    'antrag': 3, 'titel': 'Abgeschlossenes Beispiel', 'art': 'sache', 'eigenstaendigkeit': [],
    'policy': {'id': 'sachantrag-standard', 'version': 1, 'mindestbeteiligung': 0.05, 'mehrheitsbasis': 'ja_nein'},
    'stimmberechtigte': 5,
    'stimmen': [
        {'pseudonym': '0a', 'stimme': 'ja'}, {'pseudonym': '1b', 'stimme': 'ja'}, {'pseudonym': '2c', 'stimme': 'ja'},
        {'pseudonym': '3d', 'stimme': 'nein'}, {'pseudonym': '4e', 'stimme': 'enthaltung'},
    ],
    'audit': [
        {'lfd': 4, 'typ': 'antrag_eingebracht', 'vorgaenger': None, 'hash': None, 'geschwaerzt': False,
         'ereignis': {'typ': 'antrag_eingebracht', 'titel': 'Abgeschlossenes Beispiel', 'antrag': 3, 'policy': 'sachantrag-standard v1'}},
        {'lfd': 6, 'typ': 'phasenwechsel', 'vorgaenger': None, 'hash': None, 'geschwaerzt': False,
         'ereignis': {'typ': 'phasenwechsel', 'antrag': 3, 'neue_phase': 'abstimmung', 'wirksam_ab': '2026-08-18T23:36:39+00:00'}},
        *[
            {'lfd': 7 + i, 'typ': 'stimme', 'vorgaenger': None, 'hash': None, 'geschwaerzt': True,
             'ereignis': {'typ': 'stimme', 'antrag': 3, 'pseudonym': '•'}}
            for i in range(5)
        ],
        {'lfd': 12, 'typ': 'phasenwechsel', 'vorgaenger': None, 'hash': None, 'geschwaerzt': False,
         'ereignis': {'typ': 'phasenwechsel', 'antrag': 3, 'neue_phase': 'angenommen', 'wirksam_ab': '2026-08-18T23:36:39+00:00'}},
    ],
}


def test_ein_export_von_vor_dieser_fassung_laeuft_ohne_fehler_durch():
    nachrechnen = _nachrechnen_laden()
    ergebnis = nachrechnen(copy.deepcopy(ALTER_EXPORT))
    assert (ergebnis['ja'], ergebnis['nein'], ergebnis['enthaltung'], ergebnis['angenommen']) == (3, 1, 1, True)
    assert ergebnis['stimmliste_versiegelt'] is False
    # Auch wenn in einem alten Export Stimmzettel und Stimm-Ereignisse nicht gleich viele sind: Ohne
    # Abschluss-Eintrag ist das kein Fehler des Exports, sondern fehlender Nachweis.
    weniger = copy.deepcopy(ALTER_EXPORT)
    weniger['audit'] = [e for e in weniger['audit'] if e['typ'] != 'stimme']
    assert nachrechnen(weniger)['stimmliste_versiegelt'] is False
    ohne_audit = {k: v for k, v in ALTER_EXPORT.items() if k != 'audit'}
    assert nachrechnen(ohne_audit)['stimmliste_versiegelt'] is False


# --- Zustimmungswahl -------------------------------------------------------------------------------------


def _wahl(ordnung):  # noqa: F811
    autor = mitglied_anlegen('autor')
    leute = [mitglied_anlegen(f'w{i}') for i in range(3)]
    antrag = _kandidatur(ordnung, autor)
    b1 = bewerbung_einreichen(antrag, leute[0], 'A')
    b2 = bewerbung_einreichen(antrag, leute[1], 'B')
    _in_abstimmung(antrag, leute[:2])
    antrag.refresh_from_db()
    bewerbung_zustimmen(antrag, autor, b1)
    bewerbung_zustimmen(antrag, leute[2], b1)
    bewerbung_zustimmen(antrag, leute[2], b2)
    bewerbung_zustimmen(antrag, leute[2], b2)  # zurückgenommen
    return antrag, leute, (b1, b2)


def test_die_zustimmungswahl_wird_versiegelt_und_nachgerechnet(client, ordnung):  # noqa: F811
    antrag, _leute, (b1, _b2) = _wahl(ordnung)
    vorher = antrag.kandidatur_auszaehlen()
    daten = _export(client, antrag)
    antrag.refresh_from_db()
    assert antrag.phase == 'angenommen' and _halte(antrag) == []
    assert antrag.kandidatur_auszaehlen() == vorher and vorher.gewonnen_id == b1.pk
    ereignis = _ergebnis_ereignis(antrag)
    assert ereignis['stimmliste_sha256'] == daten['stimmliste_sha256']
    assert (ereignis['stimmzettel'], ereignis['stimmereignisse']) == (2, 2)  # zwei geltende Zustimmungen
    nachrechnen = _nachrechnen_laden()
    assert nachrechnen(copy.deepcopy(daten))['stimmliste_versiegelt'] is True

    umgehaengt = copy.deepcopy(daten)
    umgehaengt['zustimmungen'][0]['zurueckgenommen'] = not umgehaengt['zustimmungen'][0]['zurueckgenommen']
    with pytest.raises(SystemExit, match='FEHLER'):
        nachrechnen(umgehaengt)
    zurueckgezogen = copy.deepcopy(daten)
    zurueckgezogen['bewerbungen'][0]['zurueckgezogen'] = True
    with pytest.raises(SystemExit, match='FEHLER.*Prüfsumme'):
        nachrechnen(zurueckgezogen)


def test_eine_zustimmung_ohne_registerzeile_haelt_die_wahl_an(ordnung):  # noqa: F811
    antrag, _leute, (b1, _b2) = _wahl(ordnung)
    BewerbungsZustimmung._base_manager.bulk_create([BewerbungsZustimmung(bewerbung=b1, pseudonym=uuid.uuid4())])

    assert antrag.fortschreiben(_fristende(antrag)) is False
    antrag.refresh_from_db()
    assert antrag.phase == 'abstimmung'
    (halt,) = _halte(antrag)
    assert OHNE_REGISTERZEILE in halt['abweichungen'] and halt['ohne_registerzeile'] == 1


# --- Schreibriegel am Stimmzettel -------------------------------------------------------------------------


@pytest.mark.parametrize('weg', ['save', 'save_felder', 'update', 'bulk_update', 'delete', 'query_delete', 'neu', 'bulk_neu', 'umschreiben'])
def test_ein_stimmzettel_laesst_sich_ausserhalb_der_stimmabgabe_nicht_schreiben(ordnung, weg):  # noqa: F811
    antrag, _leute = _abstimmung(ordnung)
    zettel = antrag.stimmabgaben.filter(stimme='nein').get()
    vorher = sorted(antrag.stimmabgaben.values_list('pseudonym', 'stimme', 'abgegeben_am'))
    with pytest.raises(ValidationError):
        if weg == 'save':
            zettel.stimme = 'ja'
            zettel.save()
        elif weg == 'save_felder':
            zettel.stimme = 'ja'
            zettel.save(update_fields=['stimme'])
        elif weg == 'update':
            antrag.stimmabgaben.filter(stimme='nein').update(stimme='ja')
        elif weg == 'bulk_update':
            zettel.stimme = 'ja'
            Stimmabgabe.objects.bulk_update([zettel], ['stimme'])
        elif weg == 'delete':
            zettel.delete()
        elif weg == 'query_delete':
            antrag.stimmabgaben.all().delete()
        elif weg == 'neu':
            Stimmabgabe.objects.create(antrag=antrag, pseudonym=uuid.uuid4(), stimme='ja')
        elif weg == 'bulk_neu':
            Stimmabgabe.objects.bulk_create([Stimmabgabe(antrag=antrag, pseudonym=uuid.uuid4(), stimme='ja')])
        else:
            Stimmabgabe.objects.update_or_create(antrag=antrag, pseudonym=zettel.pseudonym, defaults={'stimme': 'ja'})
    assert sorted(antrag.stimmabgaben.values_list('pseudonym', 'stimme', 'abgegeben_am')) == vorher


@pytest.mark.parametrize('weg', ['save', 'update', 'bulk_update', 'delete', 'query_delete', 'neu', 'bulk_neu'])
def test_eine_zustimmung_laesst_sich_ausserhalb_der_wahl_nicht_schreiben(ordnung, weg):  # noqa: F811
    antrag, _leute, (b1, b2) = _wahl(ordnung)
    zeile = BewerbungsZustimmung.objects.filter(bewerbung=b2).get()
    vorher = sorted(BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag).values_list('pseudonym', 'bewerbung_id', 'zurueckgenommen_am'))
    with pytest.raises(ValidationError):
        if weg == 'save':
            zeile.zurueckgenommen_am = None
            zeile.save(update_fields=['zurueckgenommen_am'])
        elif weg == 'update':
            BewerbungsZustimmung.objects.filter(pk=zeile.pk).update(zurueckgenommen_am=None)
        elif weg == 'bulk_update':
            zeile.zurueckgenommen_am = None
            BewerbungsZustimmung.objects.bulk_update([zeile], ['zurueckgenommen_am'])
        elif weg == 'delete':
            zeile.delete()
        elif weg == 'query_delete':
            b1.zustimmungen.all().delete()
        elif weg == 'neu':
            BewerbungsZustimmung.objects.create(bewerbung=b1, pseudonym=uuid.uuid4())
        else:
            BewerbungsZustimmung.objects.bulk_create([BewerbungsZustimmung(bewerbung=b1, pseudonym=uuid.uuid4())])
    assert sorted(
        BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag).values_list('pseudonym', 'bewerbung_id', 'zurueckgenommen_am')
    ) == vorher


def test_die_regulaeren_wege_der_stimmabgabe_schreiben_weiter(ordnung):  # noqa: F811
    '''Abgeben, bis zum Fristende ändern, dieselbe Stimme noch einmal (GP-164), Zustimmung geben,
    zurücknehmen und wieder geben.'''
    antrag, leute = _abstimmung(ordnung)
    zeitpunkt = antrag.phase_beginn + timedelta(days=2)
    geaendert = stimme_abgeben(antrag, leute[0], 'nein', jetzt=zeitpunkt)
    assert geaendert.stimme == 'nein' and geaendert.abgegeben_am == zeitpunkt
    assert Stimmabgabe.objects.get(pk=geaendert.pk).stimme == 'nein'
    nochmal = stimme_abgeben(antrag, leute[0], 'nein', jetzt=zeitpunkt + timedelta(hours=1))
    assert nochmal.pk == geaendert.pk and Stimmabgabe.objects.get(pk=geaendert.pk).abgegeben_am == zeitpunkt
    assert antrag.stimmabgaben.count() == 3
    typen = list(
        AuditEintrag.objects.filter(ereignis__antrag=antrag.pk, ereignis__typ__startswith='stimme')
        .order_by('lfd').values_list('ereignis__typ', flat=True)
    )
    assert typen == ['stimme', 'stimme', 'stimme', 'stimme_geaendert']
    # Die geänderte Stimme zählt, und die Abstimmung kommt zu ihrem Ergebnis.
    assert antrag.fortschreiben(_fristende(antrag)) is True
    assert _ergebnis_ereignis(antrag)['grund'].startswith('Abgelehnt: keine Mehrheit — Ja 1 : Nein 2')

    wahl, wleute, (b1, _b2) = _wahl(ordnung)
    assert bewerbung_zustimmen(wahl, wleute[1], b1) is True
    assert bewerbung_zustimmen(wahl, wleute[1], b1) is False
    assert bewerbung_zustimmen(wahl, wleute[1], b1) is True
    assert BewerbungsZustimmung.gueltige().filter(bewerbung=b1).count() == 3


def test_austritt_und_anonymisierung_lassen_stimmzettel_und_register_stehen(ordnung):  # noqa: F811
    from mitglieder.profil import austreten

    antrag, leute = _abstimmung(ordnung)
    vorher = sorted(antrag.stimmabgaben.values_list('pseudonym', 'stimme'))
    austreten(leute[1])
    assert sorted(antrag.stimmabgaben.values_list('pseudonym', 'stimme')) == vorher
    assert antrag.stimmregister.count() == 3
    assert antrag.fortschreiben(_fristende(antrag)) is True  # die Gegenprobe besteht weiter


def test_ein_stimmzettel_des_altbestands_bleibt_lesbar_und_zaehlbar(ordnung):  # noqa: F811
    '''Stimmzettel von vor dieser Fassung (hier: an den Fachwegen vorbei angelegt, wie die historischen
    Modelle einer Migration es tun) werden gezählt und angezeigt wie bisher.'''
    antrag, leute = _abstimmung(ordnung, stimmen=())
    for m in leute[:2]:
        _zettel_einschleusen(antrag, m)
    assert antrag.auszaehlen().ja == 2
    assert str(antrag.stimmabgaben.first()).startswith('Stimme ')
