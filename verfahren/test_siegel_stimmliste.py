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


def test_eingeschleuste_stimmen_ueber_dem_nenner_halten_an(ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f's{i}') for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.refresh_from_db()
    assert antrag.stimmberechtigte_anzahl == 3
    for m in leute:
        stimme_abgeben(antrag, m, 'ja')
    _zettel_einschleusen(antrag, mitglied_anlegen('spaeter'))

    assert antrag.fortschreiben(_fristende(antrag)) is False
    (halt,) = _halte(antrag)
    # Mit Registerzeile, aber ohne Stimm-Ereignis: Das hält an — die Überzahl steht mit im Befund.
    assert halt['abweichungen'] == [UEBERZAHL, EREIGNISSE_WEICHEN_AB]
    assert (halt['stimmzettel'], halt['stimmberechtigte']) == (4, 3)


def test_mehr_stimmen_als_stimmberechtigte_auf_regulaerem_weg_halten_nicht_an(client, ordnung):  # noqa: F811
    '''Wer am Stichtag erst nach der Zählung freigeschaltet wird, ist nach der geltenden Regel
    stimmberechtigt (§ 4 Abs 4 lit a rechnet in Tagen), steht aber nicht im festgestellten Nenner. Stimmen
    alle, sind es mehr Stimmen als Stimmberechtigte — auf einem regulären Weg, jede mit Registerzeile und
    Stimm-Ereignis. Das Ergebnis wird festgestellt wie vor dieser Fassung, die Abweichung steht im
    Ergebnis-Ereignis, und das Prüfskript rechnet diesen Export voll nach: dasselbe Ergebnis, alle
    Vergleiche mit der Audit-Spur, die Abweichung als Hinweis — kein FEHLER an einem veröffentlichten
    Ergebnis.'''
    from mitglieder.models import Identitaetsstufe, Mitglied
    from plattform_core import Gegenstand

    leute = [mitglied_anlegen(f's{i}') for i in range(3)]
    spaet = mitglied_anlegen('spaet', stufe=Identitaetsstufe.UNGEPRUEFT)
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.refresh_from_db()
    assert antrag.stimmberechtigte_anzahl == 3
    stichtag = antrag.stimmberechtigung_stichtag
    # Freigeschaltet am Stichtag, nach der Zählung — der Tag steht fest, die Uhr spielt keine Rolle.
    Mitglied.objects.filter(pk=spaet.pk).update(identitaetsstufe=Identitaetsstufe.GEPRUEFT, geprueft_seit=stichtag)
    spaet.refresh_from_db()
    assert spaet.ist_stimmberechtigt(Gegenstand.SACHFRAGE, stichtag) is True
    for m in [*leute, spaet]:
        stimme_abgeben(antrag, m, 'ja')

    assert antrag.fortschreiben(_fristende(antrag)) is True
    antrag.refresh_from_db()
    assert antrag.phase == 'angenommen' and _halte(antrag) == []
    ereignis = _ergebnis_ereignis(antrag)
    assert ereignis['grund'].startswith('Angenommen: Ja 4 : Nein 0') and 'Beteiligung 4/3' in ereignis['grund']
    assert ereignis['abweichungen'] == [UEBERZAHL]
    assert (ereignis['stimmzettel'], ereignis['stimmereignisse']) == (4, 4)
    daten = _export(client, antrag)
    ergebnis = _nachrechnen_laden()(copy.deepcopy(daten))
    assert (ergebnis['ja'], ergebnis['nein'], ergebnis['abgegeben'], ergebnis['stimmberechtigte']) == (4, 0, 4, 3)
    assert ergebnis['angenommen'] is True and ergebnis['ergebnis'] == daten['ergebnis'] == 'angenommen'
    # alle Vergleiche mit der Audit-Spur sind gelaufen
    assert ergebnis['nenner_versiegelt'] is True and ergebnis['stimmliste_versiegelt'] is True
    assert ergebnis['regeln_versiegelt'] is True and ergebnis['wortlaut_versiegelt'] is True
    assert ergebnis['abweichung'] == 'mehr_stimmen_als_stimmberechtigte (4 bei 3)'
    assert ergebnis['abweichung_ausgewiesen'] is True
    assert 'weist diese Abweichung selbst aus' in ergebnis['hinweis']

    # Die Siegel gelten weiter: Eine umgeschriebene Stimme bleibt ein FEHLER, auch bei ausgewiesener Überzahl.
    umgeschrieben = copy.deepcopy(daten)
    umgeschrieben['stimmen'][0]['stimme'] = 'nein'
    with pytest.raises(SystemExit, match='FEHLER.*Prüfsumme'):
        _nachrechnen_laden()(umgeschrieben)


def test_nach_der_feststellung_eingeschleuste_stimmen_bleiben_ein_fehler(client, ordnung):  # noqa: F811
    '''Das Gegenstück zum regulären Weg: Das Ergebnis ist festgestellt und versiegelt, die Kette weist keine
    Abweichung aus — und danach stehen mehr Stimmzettel in der Datenbank als Stimmberechtigte. Die Plattform
    liefert den Export, das Prüfskript endet mit FEHLER.'''
    leute = [mitglied_anlegen(f's{i}') for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.refresh_from_db()
    for m in leute:
        stimme_abgeben(antrag, m, 'nein')
    assert antrag.fortschreiben(_fristende(antrag)) is True
    assert 'abweichungen' not in _ergebnis_ereignis(antrag)
    for i in range(4):
        _zettel_einschleusen(antrag, mitglied_anlegen(f'spaeter{i}'))

    daten = _export(client, antrag)
    assert len(daten['stimmen']) == 7 and daten['stimmberechtigte'] == 3
    with pytest.raises(SystemExit, match='FEHLER'):
        _nachrechnen_laden()(daten)


def test_das_pruefskript_meldet_eine_ueberzahl_die_die_kette_nicht_ausweist_als_fehler(client, ordnung):  # noqa: F811
    '''Die eigene Prüfung neben den Siegeln: Begann die Abstimmung vor dem Siegel des Nenners, hält nur der
    Abschluss fest, ob es eine Überzahl gab. Nennt der Export dann einen kleineren Nenner als gezählt wurde,
    passen alle Prüfsummen — aber die Kette weist die Überzahl nicht aus.'''
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
    daten = _export(client, antrag)
    nachrechnen = _nachrechnen_laden()
    unveraendert = nachrechnen(copy.deepcopy(daten))
    assert unveraendert['stimmliste_versiegelt'] is True and unveraendert['nenner_versiegelt'] is False
    assert 'abweichung' not in unveraendert and 'hinweis' not in unveraendert

    kleiner = copy.deepcopy(daten)
    kleiner['stimmberechtigte'] = 2
    with pytest.raises(SystemExit, match=r'FEHLER: mehr Stimmen als Stimmberechtigte \(3 bei 2\).*nicht aus'):
        nachrechnen(kleiner)


def test_eine_im_altbestand_ausgewiesene_ueberzahl_rechnet_das_pruefskript_nach(client, ordnung):  # noqa: F811
    '''Altbestand ohne versiegelten Beginn: Die Zahl der Stimm-Ereignisse wird nicht geprüft, eine Überzahl
    hält nicht an und steht im Ergebnis-Ereignis. Ob sie regulär entstand, sagt die Kette hier nicht —
    das Skript rechnet, nennt die Abweichung und dass die Kette sie ausweist.'''
    leute = [mitglied_anlegen(f'a{i}') for i in range(4)]
    antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    jetzt = timezone.now()
    Antrag._base_manager.filter(pk=antrag.pk).update(
        phase='abstimmung', phase_beginn=jetzt, stimmberechtigte_anzahl=3, stimmberechtigung_stichtag=timezone.localdate(jetzt),
    )
    AuditEintrag.anhaengen({'typ': 'phasenwechsel', 'antrag': antrag.pk, 'neue_phase': 'abstimmung', 'wirksam_ab': jetzt.isoformat()})
    antrag.refresh_from_db()
    for m in leute:
        _zettel_einschleusen(antrag, m)
    assert antrag.fortschreiben(_fristende(antrag)) is True
    assert _ergebnis_ereignis(antrag)['abweichungen'] == [UEBERZAHL]
    ergebnis = _nachrechnen_laden()(_export(client, antrag))
    assert ergebnis['angenommen'] is True and ergebnis['abweichung'] == 'mehr_stimmen_als_stimmberechtigte (4 bei 3)'
    assert ergebnis['abweichung_ausgewiesen'] is True


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
    assert 'abweichungen' not in ereignis
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


def test_das_pruefskript_endet_bei_abweichung_und_falscher_pruefsumme_mit_fehler(client, ordnung):  # noqa: F811
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

    # Mehr Stimmen als Stimmberechtigte in einem versiegelten Export, dessen Kette keine Abweichung
    # ausweist: Die Stimmen kamen nach der Feststellung dazu — das Siegel der Liste passt nicht mehr.
    ueberzahl = copy.deepcopy(daten)
    ueberzahl['stimmen'] += [{'pseudonym': uuid.uuid4().hex, 'stimme': 'ja'} for _ in range(10)]
    with pytest.raises(SystemExit, match='FEHLER.*Prüfsumme'):
        nachrechnen(ueberzahl)

    # Zahl der Stimm-Ereignisse: ein Ereignis „stimme“ aus der Spur genommen
    ohne_ereignis = copy.deepcopy(daten)
    ohne_ereignis['audit'].remove(next(e for e in ohne_ereignis['audit'] if e['typ'] == 'stimme'))
    with pytest.raises(SystemExit, match='FEHLER.*Stimm-Ereignisse'):
        nachrechnen(ohne_ereignis)


def test_ueberzahl_ohne_audit_spur_rechnet_das_skript_wie_am_live_stand():
    '''Ein Export ohne Audit-Spur oder von vor dieser Fassung trägt kein Siegel: Das Skript rechnet wie das
    des Live-Stands 0.114.0 (dort ohne jede Prüfung der Überzahl) und nennt die Abweichung als Hinweis.'''
    nachrechnen = _nachrechnen_laden()
    export = {
        'art': 'sache', 'policy': {'mindestbeteiligung': 0.05}, 'stimmberechtigte': 5,
        'stimmen': [{'pseudonym': f'p{i}', 'stimme': 'ja' if i < 6 else 'nein'} for i in range(9)],
    }
    ergebnis = nachrechnen(export)
    assert (ergebnis['ja'], ergebnis['nein'], ergebnis['abgegeben']) == (6, 3, 9)
    assert ergebnis['beteiligung_erreicht'] is True and ergebnis['angenommen'] is True
    assert ergebnis['abweichung'] == 'mehr_stimmen_als_stimmberechtigte (9 bei 5)'
    assert ergebnis['abweichung_ausgewiesen'] is False and ergebnis['stimmliste_versiegelt'] is False
    assert 'kein Siegel' in ergebnis['hinweis']
    wahl = {
        'art': 'mandat', 'policy': {'mindestbeteiligung': 0.05}, 'stimmberechtigte': 2,
        'bewerbungen': [{'bewerbung': 1, 'name': 'A'}],
        'zustimmungen': [{'pseudonym': f'p{i}', 'bewerbung': 1} for i in range(3)],
    }
    ergebnis = nachrechnen(wahl)
    assert ergebnis['beteiligung'] == 3 and ergebnis['gewaehlt'] == 1 and ergebnis['angenommen'] is True
    assert ergebnis['abweichung'] == 'mehr_stimmen_als_stimmberechtigte (3 bei 2)'
    assert ergebnis['abweichung_ausgewiesen'] is False
    # Auch der alte Export (0.114.0) mit Audit-Spur ohne Siegel: Hinweis, kein FEHLER.
    alt = copy.deepcopy(ALTER_EXPORT)
    alt['stimmberechtigte'] = 4
    ergebnis = nachrechnen(alt)
    assert ergebnis['angenommen'] is True and ergebnis['abweichung'] == 'mehr_stimmen_als_stimmberechtigte (5 bei 4)'
    assert ergebnis['abweichung_ausgewiesen'] is False
    # Ohne Überzahl nennt das Skript keine Abweichung.
    assert 'abweichung' not in nachrechnen(copy.deepcopy(ALTER_EXPORT))


def test_die_ueberzahl_zaehlt_menschen_wie_die_gegenprobe_der_plattform():
    '''Bei der Zustimmungswahl zählt die Plattform für die Überzahl jeden Menschen mit einer geltenden
    Zustimmung — auch zu einer zurückgezogenen Bewerbung, mehrere Zustimmungen einer Person einmal,
    zurückgenommene nicht (`Antrag.stimmliste_gegenprobe`). Das Skript vergleicht mit derselben Zahl.'''
    nachrechnen = _nachrechnen_laden()
    wahl = {
        'art': 'mandat', 'policy': {'mindestbeteiligung': 0.05}, 'stimmberechtigte': 2,
        'bewerbungen': [{'bewerbung': 1, 'name': 'A'}, {'bewerbung': 2, 'name': 'B', 'zurueckgezogen': True}],
        'zustimmungen': [
            {'pseudonym': 'p1', 'bewerbung': 1}, {'pseudonym': 'p1', 'bewerbung': 2},
            {'pseudonym': 'p2', 'bewerbung': 1}, {'pseudonym': 'p3', 'bewerbung': 1, 'zurueckgenommen': True},
        ],
    }
    ergebnis = nachrechnen(copy.deepcopy(wahl))
    assert ergebnis['beteiligung'] == 2 and 'abweichung' not in ergebnis
    wahl['zustimmungen'].append({'pseudonym': 'p4', 'bewerbung': 2})  # nur der zurückgezogenen zugestimmt
    ergebnis = nachrechnen(wahl)
    assert ergebnis['beteiligung'] == 2  # die Auszählung bleibt, wie sie ist
    assert ergebnis['abweichung'] == 'mehr_stimmen_als_stimmberechtigte (3 bei 2)'


def test_weist_die_kette_eine_ueberzahl_aus_die_der_export_nicht_zeigt_steht_das_als_hinweis_da():
    from plattform_core.tally import stimmliste_pruefsumme

    nachrechnen = _nachrechnen_laden()
    export = copy.deepcopy(ALTER_EXPORT)
    export['audit'][-1]['ereignis'].update(
        stimmzettel=5, abweichungen=[UEBERZAHL],
        stimmliste_sha256=stimmliste_pruefsumme([s['pseudonym'], s['stimme']] for s in export['stimmen']),
    )
    ergebnis = nachrechnen(export)
    assert ergebnis['angenommen'] is True and 'abweichung' not in ergebnis
    assert 'zeigt keine Überzahl (5 bei 5)' in ergebnis['hinweis']


def test_das_skript_als_programm_gibt_die_abweichung_als_zeile_aus(tmp_path):
    import os
    import subprocess
    import sys

    from verfahren.test_views_aktionen import NACHRECHNEN_PFAD

    export = {
        'art': 'sache', 'policy': {'mindestbeteiligung': 0.05}, 'stimmberechtigte': 3,
        'stimmen': [{'pseudonym': f'p{i}', 'stimme': 'ja'} for i in range(4)],
    }
    datei = tmp_path / 'export.json'
    datei.write_text(json.dumps(export), encoding='utf-8')
    # Die Kodierung der Ausgabe steht fest: Auf einer Windows-Konsole (cp1252) wären die Umlaute des
    # Hinweises sonst nicht als UTF-8 lesbar, und der Test hinge am Rechner, auf dem er läuft.
    lauf = subprocess.run(
        [sys.executable, str(NACHRECHNEN_PFAD), str(datei)], capture_output=True, text=True, encoding='utf-8',
        check=False, env={**os.environ, 'PYTHONIOENCODING': 'utf-8'},
    )
    assert lauf.returncode == 0, lauf.stderr
    zeilen = lauf.stdout.splitlines()
    assert 'abweichung: mehr_stimmen_als_stimmberechtigte (4 bei 3)' in zeilen
    assert 'angenommen: True' in zeilen and 'FEHLER' not in lauf.stdout + lauf.stderr


def test_beschreibung_und_skript_sagen_dasselbe_ueber_die_ueberzahl():
    from verfahren.test_views_aktionen import NACHRECHNEN_PFAD

    skript = NACHRECHNEN_PFAD.read_text(encoding='utf-8')
    liesmich = (NACHRECHNEN_PFAD.parent / 'README.md').read_text(encoding='utf-8')
    for text in (skript, liesmich):
        assert 'sind in jedem Export ein Fehler' not in text
        assert 'zählt das Skript nicht aus' not in text
        assert 'endet an einem solchen Export mit `FEHLER`' not in text
    assert '`abweichung`' in liesmich and '`abweichung_ausgewiesen`' in liesmich
    assert 'mehr_stimmen_als_stimmberechtigte' in skript.split('import hashlib')[0]  # im Docstring erklärt


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
