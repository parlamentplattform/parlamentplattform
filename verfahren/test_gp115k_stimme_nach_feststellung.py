'''Eine Stimme nach der Feststellung landet nicht mehr in der Stimmliste (Abschlusskorrektur 0.115.0).

`stimme_abgeben` und `bewerbung_zustimmen` lasen den Antrag nur bei örtlichem Kreis neu und unter Sperre.
Sonst prüften sie Phase und Frist an dem Objekt, das die Ansicht vor der Feststellung geladen hatte — die
Stimme kam dann in die Liste, nachdem das Ergebnis samt Prüfsumme der Stimmliste in der Audit-Kette stand.
Jetzt wird die Antragszeile immer zuerst gesperrt und neu gelesen (dieselbe Reihenfolge wie
`Antrag.fortschreiben`), erst dann werden Stimmrecht, Phase und Frist geprüft.

Diese Datei prüft, was ohne Zeilensperre prüfbar ist (ein veraltetes Objekt); den Wettlauf zweier
Verbindungen prüft `test_gp115k_stimme_sperre_postgres.py` auf PostgreSQL.'''

import copy
import json
from datetime import timedelta

import pytest
from django.urls import reverse

from plattform_core.phases import abstimmung_frist_ende
from verfahren.models import (
    Antrag,
    AuditEintrag,
    BewerbungsZustimmung,
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

pytestmark = pytest.mark.django_db


def _ergebnis_ereignis(antrag):
    return AuditEintrag.objects.filter(
        ereignis__antrag=antrag.pk, ereignis__typ='phasenwechsel', ereignis__neue_phase__in=['angenommen', 'abgelehnt'],
    ).order_by('-lfd').first().ereignis


def _sachabstimmung(ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f'n{i}') for i in range(6)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:3])
    antrag.refresh_from_db()
    assert antrag.teilnahmegebiet is None  # Bundesebene: der Fall, der bisher nicht neu gelesen wurde
    stimme_abgeben(antrag, leute[0], 'ja')
    stimme_abgeben(antrag, leute[1], 'nein')
    return antrag, leute


def _wahl(ordnung):  # noqa: F811
    autor = mitglied_anlegen('autor')
    leute = [mitglied_anlegen(f'w{i}') for i in range(4)]
    antrag = _kandidatur(ordnung, autor)
    b1 = bewerbung_einreichen(antrag, leute[0], 'A')
    b2 = bewerbung_einreichen(antrag, leute[1], 'B')
    _in_abstimmung(antrag, leute[:2])
    antrag.refresh_from_db()
    assert antrag.teilnahmegebiet is None
    bewerbung_zustimmen(antrag, autor, b1)
    bewerbung_zustimmen(antrag, leute[2], b2)
    return antrag, leute, (b1, b2)


def _export(client, antrag):
    antwort = client.get(reverse('verfahren:export', args=[antrag.pk]))
    assert antwort.status_code == 200
    return json.loads(antwort.content)


def test_eine_stimme_ueber_ein_veraltetes_antragsobjekt_wird_nach_der_feststellung_abgewiesen(client, ordnung):  # noqa: F811
    antrag, leute = _sachabstimmung(ordnung)
    frist = abstimmung_frist_ende(antrag.phase_beginn, antrag.policy())
    veraltet = Antrag.objects.get(pk=antrag.pk)  # so lädt die Ansicht den Antrag vor dem Fristende
    assert veraltet.stimme_zulaessig(frist - timedelta(seconds=1)) is True

    # Inzwischen stellt ein anderer Ablauf (Wächter, Seitenaufruf) das Ergebnis fest.
    assert Antrag.objects.get(pk=antrag.pk).fortschreiben(frist + timedelta(seconds=1)) is True
    siegel = _ergebnis_ereignis(antrag)
    assert siegel['neue_phase'] == 'abgelehnt' and siegel['stimmzettel'] == 2  # 1 : 1, keine Mehrheit
    assert veraltet.phase == 'abstimmung'  # das Objekt der Ansicht weiß davon nichts

    # Eine neue Stimme und eine Stimmänderung, beide mit einem Zeitpunkt vor dem Fristende geprüft:
    with pytest.raises(StimmabgabeFehler):
        stimme_abgeben(veraltet, leute[2], 'ja', jetzt=frist - timedelta(seconds=1))
    with pytest.raises(StimmabgabeFehler):
        stimme_abgeben(veraltet, leute[1], 'ja', jetzt=frist - timedelta(seconds=1))

    frisch = Antrag.objects.get(pk=antrag.pk)
    assert frisch.phase == 'abgelehnt' and frisch.stimmabgaben.count() == 2 and frisch.stimmregister.count() == 2
    assert sorted(frisch.stimmabgaben.values_list('stimme', flat=True)) == ['ja', 'nein']
    assert frisch.stimmliste_pruefsumme() == siegel['stimmliste_sha256']
    assert not AuditEintrag.objects.filter(ereignis__antrag=antrag.pk, ereignis__typ='stimme_geaendert').exists()
    assert AuditEintrag.objects.filter(ereignis__antrag=antrag.pk, ereignis__typ='stimme').count() == 2
    # Export und Siegel stimmen überein: Das Prüfskript rechnet ohne FEHLER dasselbe Ergebnis.
    ergebnis = _nachrechnen_laden()(copy.deepcopy(_export(client, antrag)))
    assert ergebnis['stimmliste_versiegelt'] is True and ergebnis['ergebnis'] == 'abgelehnt'
    assert (ergebnis['ja'], ergebnis['nein']) == (1, 1)


def test_eine_zustimmung_ueber_ein_veraltetes_antragsobjekt_wird_nach_der_feststellung_abgewiesen(client, ordnung):  # noqa: F811
    antrag, leute, (b1, b2) = _wahl(ordnung)
    frist = abstimmung_frist_ende(antrag.phase_beginn, antrag.policy())
    veraltet = Antrag.objects.get(pk=antrag.pk)

    assert Antrag.objects.get(pk=antrag.pk).fortschreiben(frist + timedelta(seconds=1)) is True
    siegel = _ergebnis_ereignis(antrag)
    assert siegel['stimmzettel'] == 2
    vorher = sorted(
        BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag).values_list('pseudonym', 'bewerbung_id', 'zurueckgenommen_am')
    )

    with pytest.raises(StimmabgabeFehler):  # eine neue Zustimmung
        bewerbung_zustimmen(veraltet, leute[3], b2, jetzt=frist - timedelta(seconds=1))
    with pytest.raises(StimmabgabeFehler):  # eine Rücknahme
        bewerbung_zustimmen(veraltet, leute[2], b2, jetzt=frist - timedelta(seconds=1))

    frisch = Antrag.objects.get(pk=antrag.pk)
    assert sorted(
        BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag).values_list('pseudonym', 'bewerbung_id', 'zurueckgenommen_am')
    ) == vorher
    assert frisch.stimmregister.count() == 2
    assert frisch.stimmliste_pruefsumme() == siegel['stimmliste_sha256']
    ergebnis = _nachrechnen_laden()(copy.deepcopy(_export(client, antrag)))
    assert ergebnis['stimmliste_versiegelt'] is True and ergebnis['gewaehlt'] == b1.pk


def test_bis_zum_fristende_bleibt_die_stimme_abgebbar_und_aenderbar(ordnung):  # noqa: F811
    '''Die Sperre nimmt niemandem etwas: Auch über ein älteres Objekt der Ansicht wird bis zum Fristende
    abgestimmt, geändert, zugestimmt und zurückgenommen — und alles zählt.'''
    antrag, leute = _sachabstimmung(ordnung)
    frist = abstimmung_frist_ende(antrag.phase_beginn, antrag.policy())
    veraltet = Antrag.objects.get(pk=antrag.pk)
    kurz_davor = frist - timedelta(seconds=1)
    assert stimme_abgeben(veraltet, leute[2], 'ja', jetzt=kurz_davor).stimme == 'ja'
    assert stimme_abgeben(veraltet, leute[1], 'ja', jetzt=kurz_davor).stimme == 'ja'  # geändert von Nein auf Ja
    with pytest.raises(StimmabgabeFehler):
        stimme_abgeben(veraltet, leute[3], 'ja', jetzt=frist)  # zum Fristende ist Schluss, wie bisher
    assert Antrag.objects.get(pk=antrag.pk).fortschreiben(frist + timedelta(seconds=1)) is True
    siegel = _ergebnis_ereignis(antrag)
    assert siegel['neue_phase'] == 'angenommen' and siegel['grund'].startswith('Angenommen: Ja 3 : Nein 0')
    assert (siegel['stimmzettel'], siegel['stimmereignisse']) == (3, 3)

    wahl, wleute, (b1, b2) = _wahl(ordnung)
    wfrist = abstimmung_frist_ende(wahl.phase_beginn, wahl.policy())
    alt = Antrag.objects.get(pk=wahl.pk)
    assert bewerbung_zustimmen(alt, wleute[3], b2, jetzt=wfrist - timedelta(seconds=1)) is True
    assert bewerbung_zustimmen(alt, wleute[2], b2, jetzt=wfrist - timedelta(seconds=1)) is False  # zurückgenommen
    assert Antrag.objects.get(pk=wahl.pk).fortschreiben(wfrist + timedelta(seconds=1)) is True
    assert _ergebnis_ereignis(wahl)['stimmzettel'] == 2


def test_die_stimmabgabe_liest_den_antrag_unter_sperre_bevor_sie_prueft(ordnung, monkeypatch):  # noqa: F811
    '''Die Reihenfolge, an der die Sperre hängt: zuerst die Antragszeile mit `select_for_update` (wie
    `Antrag.fortschreiben`), dann erst Stimmrecht, Phase und Frist — für jeden Antrag, nicht nur für den
    örtlichen Kreis.'''
    import verfahren.teilnahme as teilnahme
    from verfahren.models import AntragsQuerySet

    antrag, leute = _sachabstimmung(ordnung)
    wahl, wleute, (b1, _b2) = _wahl(ordnung)
    ablauf = []
    echte_sperre = AntragsQuerySet.select_for_update
    echtes_stimmrecht = teilnahme.stimmrecht_im_neuen_kreis
    echte_zulaessigkeit = Antrag.stimme_zulaessig

    def sperre(self, *args, **kwargs):
        ablauf.append('sperre')
        return echte_sperre(self, *args, **kwargs)

    def stimmrecht(*args, **kwargs):
        ablauf.append('stimmrecht')
        return echtes_stimmrecht(*args, **kwargs)

    def zulaessig(self, jetzt=None):
        ablauf.append('frist')
        return echte_zulaessigkeit(self, jetzt)

    monkeypatch.setattr(AntragsQuerySet, 'select_for_update', sperre)
    monkeypatch.setattr(teilnahme, 'stimmrecht_im_neuen_kreis', stimmrecht)
    monkeypatch.setattr(Antrag, 'stimme_zulaessig', zulaessig)

    stimme_abgeben(antrag, leute[3], 'ja')
    assert ablauf[:3] == ['sperre', 'stimmrecht', 'frist']
    del ablauf[:]
    bewerbung_zustimmen(wahl, wleute[3], b1)
    assert ablauf[:3] == ['sperre', 'stimmrecht', 'frist']
