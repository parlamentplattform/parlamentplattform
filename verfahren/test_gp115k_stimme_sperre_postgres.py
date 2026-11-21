'''Stimmabgabe und Feststellung unter Nebenläufigkeit (Abschlusskorrektur 0.115.0).

Zwei Verbindungen, ein Antrag: Die Stimmabgabe und die Feststellung des Ergebnisses sperren beide zuerst
die Antragszeile. Wer zuerst kommt, wird fertig; der andere wartet und sieht dann den neuen Stand. So
landet keine Stimme nach der Feststellung in der Liste, und die Prüfsumme der Stimmliste im
Ergebnis-Ereignis passt zum Export.

Die Zeilensperre wirkt nur auf PostgreSQL (SQLite serialisiert ohnehin); darum laufen diese Tests nur
dort — die CI fährt sie im Job `pruefen_postgres`. Was ohne Sperre prüfbar ist, steht in
`test_gp115k_stimme_nach_feststellung.py`.

Die Tests hängen nicht an der Rechnergeschwindigkeit: Ist der wartende Ablauf langsamer als die Pause des
anderen, laufen beide nacheinander — mit demselben geprüften Ausgang.'''

import copy
import json
import threading
import time
from datetime import timedelta

import pytest
from django.db import connection, connections
from django.urls import reverse

# Das Einmal-Token-Modell liegt in `mitglieder.auth_flows`, nicht in `models.py`; ohne diesen
# Import kennt der Flush der transaktionalen Tests die Tabelle nicht und scheitert am Fremdschlüssel.
import mitglieder.auth_flows  # noqa: F401
from plattform_core.phases import abstimmung_frist_ende
from verfahren.models import (
    Antrag,
    AuditEintrag,
    StimmabgabeFehler,
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

pytestmark = [
    pytest.mark.django_db(transaction=True),
    pytest.mark.skipif(connection.vendor != 'postgresql', reason='Zeilensperren wirken nur auf PostgreSQL'),
]

PAUSE = 1.0  # so lange hält der erste Ablauf die Antragszeile, bevor er weiterarbeitet


def _ergebnis_ereignis(antrag):
    return AuditEintrag.objects.filter(
        ereignis__antrag=antrag.pk, ereignis__typ='phasenwechsel', ereignis__neue_phase__in=['angenommen', 'abgelehnt'],
    ).order_by('-lfd').first().ereignis


def _sachabstimmung(ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f'p{i}') for i in range(6)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.refresh_from_db()
    stimme_abgeben(antrag, leute[0], 'ja')
    stimme_abgeben(antrag, leute[1], 'nein')
    return antrag, leute


def _im_faden(name, ablauf):
    '''Startet `ablauf` in einem eigenen Faden mit eigener Datenbankverbindung. Rückgabe: der Faden und die
    Liste, in der eine Ausnahme des Fadens landet.'''
    fehler = []

    def lauf():
        try:
            ablauf()
        except Exception as exc:  # noqa: BLE001 — der Test zeigt jede Ausnahme des Fadens
            fehler.append(exc)
        finally:
            connections.close_all()

    faden = threading.Thread(target=lauf, name=name)
    faden.start()
    return faden, fehler


def _export_gegen_siegel(client, antrag):
    antwort = client.get(reverse('verfahren:export', args=[antrag.pk]))
    assert antwort.status_code == 200
    daten = json.loads(antwort.content)
    ergebnis = _nachrechnen_laden()(copy.deepcopy(daten))  # endet mit SystemExit, wenn ein Siegel nicht passt
    assert ergebnis['stimmliste_versiegelt'] is True
    assert Antrag.objects.get(pk=antrag.pk).stimmliste_pruefsumme() == daten['stimmliste_sha256']
    return daten, ergebnis


def test_die_stimmabgabe_haelt_die_sperre_und_die_feststellung_zaehlt_die_stimme_mit(client, ordnung, monkeypatch):  # noqa: F811
    antrag, leute = _sachabstimmung(ordnung)
    frist = abstimmung_frist_ende(antrag.phase_beginn, antrag.policy())
    gesperrt = threading.Event()
    echte = Antrag.stimme_zulaessig

    def langsam(self, jetzt=None):
        # Hier hält die Stimmabgabe die Antragszeile bereits (sie sperrt zuerst und prüft dann).
        if threading.current_thread().name == 'stimme':
            gesperrt.set()
            time.sleep(PAUSE)
        return echte(self, jetzt)

    monkeypatch.setattr(Antrag, 'stimme_zulaessig', langsam)
    veraltet = Antrag.objects.get(pk=antrag.pk)
    faden, fehler = _im_faden(
        'stimme', lambda: stimme_abgeben(veraltet, leute[2], 'ja', jetzt=frist - timedelta(seconds=1))
    )
    assert gesperrt.wait(10)

    # Die Feststellung wartet auf die Stimmabgabe und zählt deren Stimme mit.
    assert Antrag.objects.get(pk=antrag.pk).fortschreiben(frist + timedelta(seconds=1)) is True
    faden.join(20)
    assert not faden.is_alive() and fehler == []

    siegel = _ergebnis_ereignis(antrag)
    assert siegel['neue_phase'] == 'angenommen' and siegel['grund'].startswith('Angenommen: Ja 2 : Nein 1')
    assert (siegel['stimmzettel'], siegel['stimmereignisse']) == (3, 3)
    daten, ergebnis = _export_gegen_siegel(client, antrag)
    assert len(daten['stimmen']) == 3 and (ergebnis['ja'], ergebnis['nein']) == (2, 1)
    assert ergebnis['ergebnis'] == 'angenommen'


def test_die_feststellung_haelt_die_sperre_und_die_stimmabgabe_wird_danach_abgewiesen(client, ordnung, monkeypatch):  # noqa: F811
    antrag, leute = _sachabstimmung(ordnung)
    frist = abstimmung_frist_ende(antrag.phase_beginn, antrag.policy())
    gesperrt = threading.Event()
    echte = Antrag.stimmliste_gegenprobe

    def langsam(self):
        # Die Gegenprobe läuft in `fortschreiben`, unter der Sperre der Antragszeile.
        if threading.current_thread().name == 'feststellung':
            gesperrt.set()
            time.sleep(PAUSE)
        return echte(self)

    monkeypatch.setattr(Antrag, 'stimmliste_gegenprobe', langsam)
    veraltet = Antrag.objects.get(pk=antrag.pk)  # vor der Feststellung geladen, wie in der Ansicht
    faden, fehler = _im_faden(
        'feststellung', lambda: Antrag.objects.get(pk=antrag.pk).fortschreiben(frist + timedelta(seconds=1))
    )
    assert gesperrt.wait(10)

    # Eine neue Stimme und eine Stimmänderung warten auf die Feststellung und werden dann abgewiesen.
    with pytest.raises(StimmabgabeFehler):
        stimme_abgeben(veraltet, leute[2], 'ja', jetzt=frist - timedelta(seconds=1))
    with pytest.raises(StimmabgabeFehler):
        stimme_abgeben(veraltet, leute[1], 'ja', jetzt=frist - timedelta(seconds=1))
    faden.join(20)
    assert not faden.is_alive() and fehler == []

    siegel = _ergebnis_ereignis(antrag)
    assert siegel['neue_phase'] == 'abgelehnt' and siegel['stimmzettel'] == 2  # 1 : 1, keine Mehrheit
    daten, ergebnis = _export_gegen_siegel(client, antrag)
    assert len(daten['stimmen']) == 2 and ergebnis['ergebnis'] == 'abgelehnt'
    assert Antrag.objects.get(pk=antrag.pk).stimmregister.count() == 2


def test_die_zustimmung_haelt_die_sperre_und_die_feststellung_zaehlt_sie_mit(client, ordnung, monkeypatch):  # noqa: F811
    autor = mitglied_anlegen('autor')
    leute = [mitglied_anlegen(f'w{i}') for i in range(4)]
    antrag = _kandidatur(ordnung, autor)
    b1 = bewerbung_einreichen(antrag, leute[0], 'A')
    b2 = bewerbung_einreichen(antrag, leute[1], 'B')
    _in_abstimmung(antrag, leute[:2])
    antrag.refresh_from_db()
    bewerbung_zustimmen(antrag, autor, b1)
    bewerbung_zustimmen(antrag, leute[2], b2)
    frist = abstimmung_frist_ende(antrag.phase_beginn, antrag.policy())
    gesperrt = threading.Event()
    echte = Antrag.stimme_zulaessig

    def langsam(self, jetzt=None):
        if threading.current_thread().name == 'zustimmung':
            gesperrt.set()
            time.sleep(PAUSE)
        return echte(self, jetzt)

    monkeypatch.setattr(Antrag, 'stimme_zulaessig', langsam)
    veraltet = Antrag.objects.get(pk=antrag.pk)
    faden, fehler = _im_faden(
        'zustimmung', lambda: bewerbung_zustimmen(veraltet, leute[3], b2, jetzt=frist - timedelta(seconds=1))
    )
    assert gesperrt.wait(10)

    assert Antrag.objects.get(pk=antrag.pk).fortschreiben(frist + timedelta(seconds=1)) is True
    faden.join(20)
    assert not faden.is_alive() and fehler == []

    siegel = _ergebnis_ereignis(antrag)
    assert (siegel['stimmzettel'], siegel['stimmereignisse']) == (3, 3)  # die Zustimmung zählt mit
    assert 'auszaehlung_angehalten' not in set(
        AuditEintrag.objects.filter(ereignis__antrag=antrag.pk).values_list('ereignis__typ', flat=True)
    )
    daten, ergebnis = _export_gegen_siegel(client, antrag)
    assert ergebnis['gewaehlt'] == b2.pk and ergebnis['beteiligung'] == 3
