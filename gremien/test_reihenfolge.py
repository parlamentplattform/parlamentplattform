"""Reihenfolge nach einem Stillstand (Gesamtprüfung 18.11.2026, GP-004).

Ein Gremienbeschluss gilt zu seiner Frist, ein Phasenübergang zu seiner. Läuft der Wächter
pünktlich, wendet er beides in der Reihenfolge der Sollzeiten an. Lief er eine Weile nicht, wertete
er bisher erst alle Phasenfristen aus und danach die Beschlüsse — derselbe Sachverhalt führte je
nach Zeitpunkt des Laufs zu verschiedenen Ergebnissen. Jeder Fall steht hier zweimal: pünktlich
und mit einem einzigen Lauf nach beiden Fristen. Der Endzustand muss derselbe sein."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import (
    Anlass,
    Aussetzung,
    BeschlussStatus,
    Entwurf,
    EntwurfsStatus,
    GremienBeschluss,
)
from gremien.test_integritaet import antrag_in_abstimmung, rat
from gremien.test_werkstatt import (  # noqa: F401
    fenster_oeffnen,
    ordnung,
    werkstatt_lage,
)
from verfahren.management.commands.verfahren_fortschreiben import alles_fortschreiben
from verfahren.models import Antrag, AuditEintrag

pytestmark = pytest.mark.django_db
T = timedelta


def stimmen(client, beschluss, leute, option='dafuer', **extra):
    for m in leute:
        client.force_login(m)
        client.post(
            reverse('gremien:beschluss_stimme', args=[beschluss.pk]),
            {'option': option, 'begruendung': 'Begründet.', **extra},
        )
    beschluss.refresh_from_db()
    return beschluss


def einreichung_zwei_von_drei(client, ordnung):  # noqa: F811
    """Beratung seit zehn Tagen (Ende in elf). Gruppe 1 stellt die Einreichungsfrage, zwei von drei
    stimmen dafür, die dritte Person schweigt: Der Beschluss schließt erst mit seiner Frist."""
    antrag, _, er = werkstatt_lage(ordnung, raete=3)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - T(days=10))
    antrag.refresh_from_db()
    fenster_oeffnen(client, antrag, er[0])
    client.post(reverse('gremien:fenster_aktion', args=[antrag.pk]), {'aktion': 'einreichung'})
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.EINREICHUNG, antrag=antrag)
    stimmen(client, beschluss, er[:2], interessenbindung='keine')
    assert beschluss.status == BeschlussStatus.OFFEN
    ende = antrag.phase_beginn + T(days=antrag.policy().beratung_tage)
    assert beschluss.frist < ende  # die Beschlussfrist liegt vor dem Beratungsende
    return antrag, beschluss, ende


def _lage_der_einreichung(antrag, beschluss):
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    entwurf = Entwurf.objects.get(antrag=antrag)
    return antrag.phase, entwurf.status, entwurf.review_frist, beschluss.ergebnis, beschluss.umsetzungsvermerk


def test_einreichung_vor_dem_beratungsende_zaehlt_auch_nach_einem_stillstand(client, ordnung):  # noqa: F811
    """Sonden C1 und C2: Der fristgerecht beschlossene Vorschlag wurde nach einem Stillstand verworfen
    („Der Antrag war nicht mehr in der Beratung“), weil das Beratungsende vor dem Beschluss ausgewertet wurde."""
    antrag, beschluss, ende = einreichung_zwei_von_drei(client, ordnung)
    stand = alles_fortschreiben(ende + T(days=1))  # EIN Lauf nach beiden Fristen
    assert stand['beschluesse'] == 1 and stand['fehler'] == 0  # der Lauf zählt, was er ausgewertet hat
    phase, status, review_frist, ergebnis, vermerk = _lage_der_einreichung(antrag, beschluss)
    assert ergebnis == 'dafuer' and beschluss.entschieden_am == beschluss.frist
    assert 'Eingereicht' in vermerk and 'Nicht eingereicht' not in vermerk
    assert status == EntwurfsStatus.UNTERSTUETZER
    assert review_frist == beschluss.frist + T(days=antrag.policy().review_tage)
    assert phase == 'beratung'  # die Schleife arbeitet und hält die Beratung offen


def test_einreichung_puenktlich_und_nach_stillstand_enden_gleich(client, ordnung):  # noqa: F811
    antrag, beschluss, ende = einreichung_zwei_von_drei(client, ordnung)
    alles_fortschreiben(beschluss.frist + T(minutes=5))
    alles_fortschreiben(ende + T(days=1))
    assert _lage_der_einreichung(antrag, beschluss)[:2] == ('beratung', EntwurfsStatus.UNTERSTUETZER)


def test_einreichung_nach_dem_beratungsende_bleibt_verworfen(client, ordnung):  # noqa: F811
    """Gegenprobe: Liegt die Beschlussfrist NACH dem Beratungsende, geht der Phasenübergang vor —
    auch in einem einzigen späten Lauf. Die Reihenfolge folgt den Sollzeiten, nicht einer festen Rangfolge."""
    antrag, _, er = werkstatt_lage(ordnung, raete=3)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - T(days=18))
    antrag.refresh_from_db()
    fenster_oeffnen(client, antrag, er[0])
    client.post(reverse('gremien:fenster_aktion', args=[antrag.pk]), {'aktion': 'einreichung'})
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.EINREICHUNG, antrag=antrag)
    stimmen(client, beschluss, er[:2], interessenbindung='keine')
    ende = antrag.phase_beginn + T(days=antrag.policy().beratung_tage)
    assert beschluss.frist > ende
    alles_fortschreiben(beschluss.frist + T(hours=1))
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert antrag.phase == 'abstimmung' and antrag.phase_beginn == ende
    assert 'Nicht eingereicht' in beschluss.umsetzungsvermerk


def ir_beschluss_zwei_von_drei(client, ordnung, anlass):  # noqa: F811
    """Die Abstimmung läuft seit zwei Tagen (Ende in fünf). Der Integritätsrat stellt die Frage, zwei von
    drei stimmen dafür; der Beschluss schließt mit seiner Frist in drei Tagen."""
    antrag = antrag_in_abstimmung(ordnung)
    leute = rat(3)
    client.force_login(leute[0])
    client.post(
        reverse('gremien:integritaet_beschluss'),
        {'anlass': anlass, 'antrag': antrag.pk, 'beschreibung': 'Verdacht auf Beeinflussung.'},
    )
    beschluss = GremienBeschluss.objects.get(anlass=anlass, antrag=antrag)
    frist = timezone.now() + T(days=3)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=frist)
    beschluss.refresh_from_db()
    stimmen(client, beschluss, leute[:2])
    assert beschluss.status == BeschlussStatus.OFFEN
    ende = antrag.phase_beginn + T(days=antrag.policy().abstimmung_tage)
    assert beschluss.frist < ende
    return antrag, beschluss, ende


def _aussetzungen(antrag):
    return [(a.gegenstand, a.beginn) for a in Aussetzung.objects.filter(antrag=antrag)]


def test_aussetzung_vor_dem_abstimmungsende_trifft_die_abstimmung_auch_nach_einem_stillstand(client, ordnung):  # noqa: F811
    """Sonden C3 und C4: Aus der beschlossenen Aussetzung der Abstimmung wurde nach einem Stillstand eine
    Aussetzung des Vollzugs — das Ergebnis stand schon, bevor der Beschluss ausgewertet war."""
    antrag, beschluss, ende = ir_beschluss_zwei_von_drei(client, ordnung, Anlass.AUSSETZUNG)
    alles_fortschreiben(ende + T(days=1))  # EIN Lauf nach beiden Fristen
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert beschluss.entschieden_am == beschluss.frist
    assert _aussetzungen(antrag) == [('abstimmung', beschluss.frist)]
    assert antrag.phase == 'abstimmung'


def test_aussetzung_puenktlich_und_nach_stillstand_enden_gleich(client, ordnung):  # noqa: F811
    antrag, beschluss, ende = ir_beschluss_zwei_von_drei(client, ordnung, Anlass.AUSSETZUNG)
    alles_fortschreiben(beschluss.frist + T(minutes=5))
    alles_fortschreiben(ende + T(days=1))
    antrag.refresh_from_db()
    assert _aussetzungen(antrag) == [('abstimmung', beschluss.frist)]
    assert antrag.phase == 'abstimmung'


def test_zurueckweisung_vor_dem_abstimmungsende_merkt_sich_die_abstimmung(client, ordnung):  # noqa: F811
    """Sonde D4: Die Zurückweisung merkte sich nach einem Stillstand „angenommen“ oder „abgelehnt“ als
    Vorzustand — ihre Aufhebung hätte ein Ergebnis hergestellt statt die Restfrist der Abstimmung."""
    antrag, beschluss, ende = ir_beschluss_zwei_von_drei(client, ordnung, Anlass.ZURUECKWEISUNG)
    alles_fortschreiben(ende + T(days=1))
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert antrag.phase == 'zurueckgewiesen' and antrag.phase_beginn == beschluss.frist
    assert beschluss.zustand_vorher['phase'] == 'abstimmung'
    wechsel = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis['typ'] == 'phasenwechsel']
    assert not any(w.get('antrag') == antrag.pk and w['neue_phase'] in ('angenommen', 'abgelehnt') for w in wechsel)


def test_die_antragsseite_wendet_dieselbe_reihenfolge_an(client, ordnung):  # noqa: F811
    """Nicht nur der Wächter: Auch der erste Seitenaufruf nach dem Stillstand reiht nach Sollzeit."""
    antrag, beschluss, ende = ir_beschluss_zwei_von_drei(client, ordnung, Anlass.ZURUECKWEISUNG)
    verschub = ende + T(days=1) - timezone.now()
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=antrag.phase_beginn - verschub)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=beschluss.frist - verschub)
    client.logout()
    assert client.get(reverse('verfahren:antrag', args=[antrag.pk])).status_code == 200
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert antrag.phase == 'zurueckgewiesen'
    assert beschluss.zustand_vorher['phase'] == 'abstimmung'


def test_die_schwelle_wird_nicht_auf_eine_beschlussfrist_zurueckdatiert(client, ordnung):  # noqa: F811
    """Der Vorlauf zur Beschlussfrist wertet nur Fristen aus. Wird die Unterstützungsschwelle JETZT
    erreicht, beginnt die Beratung jetzt — nicht zur Frist eines liegengebliebenen Beschlusses."""
    from gremien.test_integritaet import antrag_anlegen
    from gremien.test_werkstatt import mitglied_anlegen

    antrag = antrag_anlegen(ordnung)
    leute = rat(3)
    client.force_login(leute[0])
    client.post(
        reverse('gremien:integritaet_beschluss'),
        {'anlass': Anlass.HERVORHEBUNG, 'antrag': antrag.pk, 'beschreibung': 'Große Wirkung.'},
    )
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.HERVORHEBUNG, antrag=antrag)
    frist = timezone.now() - T(days=2)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=frist)
    for i in range(antrag.policy().unterstuetzung_schwelle):
        antrag.unterstuetzungen.create(mitglied=mitglied_anlegen(f'spaet{i}'))
    vorher = timezone.now()
    antrag.fortschreiben_bis_zum_stand()
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert beschluss.status != BeschlussStatus.OFFEN and beschluss.entschieden_am == frist
    assert antrag.phase == 'beratung' and antrag.phase_beginn >= vorher


# --- GP-004, Gegenrichtung: Auch Gremienseite und letzte Stimme schreiben den Antrag zuerst fort ---


def _ir_beschluss_nach_dem_abstimmungsende(client, ordnung, anlass=Anlass.ZURUECKWEISUNG):  # noqa: F811
    """Wie `ir_beschluss_zwei_von_drei`, aber die Beschlussfrist liegt NACH dem Abstimmungsende — und beide
    Fristen sind um, ohne dass jemand die Antragsseite geöffnet hat: Der Antrag steht noch auf „abstimmung“."""
    antrag, beschluss, ende = ir_beschluss_zwei_von_drei(client, ordnung, anlass)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=ende + T(days=1))
    verschub = ende + T(days=2) - timezone.now()
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=antrag.phase_beginn - verschub)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=ende + T(days=1) - verschub)
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert antrag.phase == 'abstimmung'  # veralteter Stand: die Abstimmung ist seit zwei Tagen um
    return antrag, beschluss


def test_die_gremienseite_schreibt_den_antrag_vor_der_wirkung_fort(client, ordnung):  # noqa: F811
    """GP-004, Gegenrichtung: Schloss eine Gremienseite den Beschluss, traf die Zurückweisung den veralteten
    Stand „abstimmung“ — und nahm einem Antrag, dessen Abstimmung vor der Beschlussfrist geendet hatte, das
    Ergebnis. Jetzt reiht auch dieser Weg nach Sollzeit: erst das Ergebnis, dann der Beschluss ohne Wirkung."""
    antrag, beschluss = _ir_beschluss_nach_dem_abstimmungsende(client, ordnung)
    client.logout()
    assert client.get(reverse('gremien:beschluesse')).status_code == 200  # ruft faellige_abschliessen
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and beschluss.entschieden_am == beschluss.frist
    assert antrag.phase in ('angenommen', 'abgelehnt')
    assert beschluss.zustand_vorher is None and 'Ohne Wirkung' in beschluss.umsetzungsvermerk


def test_der_sammellauf_zaehlt_den_ueber_den_antrag_geschlossenen_beschluss(client, ordnung):  # noqa: F811
    """Derselbe Fall über den Sammellauf selbst: Er meldet den Beschluss als geschlossen, genau einmal
    ausgewertet — und endet wie die Antragsseite (`test_die_antragsseite_wendet_dieselbe_reihenfolge_an`)."""
    antrag, beschluss = _ir_beschluss_nach_dem_abstimmungsende(client, ordnung)
    assert GremienBeschluss.faellige_abschliessen() == 1
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert antrag.phase in ('angenommen', 'abgelehnt') and beschluss.zustand_vorher is None
    ausgewertet = [
        e.ereignis for e in AuditEintrag.objects.all()
        if e.ereignis['typ'] == 'gremienbeschluss_ausgewertet' and e.ereignis['beschluss'] == beschluss.pk
    ]
    assert len(ausgewertet) == 1
    assert GremienBeschluss.faellige_abschliessen() == 0


def test_die_einzelseite_des_beschlusses_schreibt_den_antrag_vor_der_wirkung_fort(client, ordnung):  # noqa: F811
    antrag, beschluss = _ir_beschluss_nach_dem_abstimmungsende(client, ordnung)
    client.logout()
    assert client.get(reverse('gremien:beschluss', args=[beschluss.nummer])).status_code == 200
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert antrag.phase in ('angenommen', 'abgelehnt') and beschluss.zustand_vorher is None


def test_die_gremienseite_laesst_einen_beschluss_vor_dem_abstimmungsende_wirken(client, ordnung):  # noqa: F811
    """Gegenprobe: Liegt die Beschlussfrist VOR dem Abstimmungsende, wirkt die Zurückweisung zur Frist
    auf die laufende Abstimmung — auch über die Gremienseite, auch nach einem Stillstand."""
    antrag, beschluss, ende = ir_beschluss_zwei_von_drei(client, ordnung, Anlass.ZURUECKWEISUNG)
    verschub = ende + T(days=1) - timezone.now()
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=antrag.phase_beginn - verschub)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(frist=beschluss.frist - verschub)
    client.logout()
    client.get(reverse('gremien:beschluesse'))
    antrag.refresh_from_db()
    beschluss.refresh_from_db()
    assert antrag.phase == 'zurueckgewiesen' and antrag.phase_beginn == beschluss.frist
    assert beschluss.zustand_vorher['phase'] == 'abstimmung'


def test_die_letzte_stimme_schreibt_den_antrag_vor_der_wirkung_fort(client, ordnung):  # noqa: F811
    """GP-004, Gegenrichtung: Schließt die letzte Stimme den Beschluss, galt für die Wirkung der Stand, den
    der Antrag beim letzten Seitenaufruf hatte. Eine Einreichung NACH dem Beratungsende wurde so wirksam,
    weil der Antrag noch auf „beratung“ stand. Jetzt wie beim Wächter
    (`test_einreichung_nach_dem_beratungsende_bleibt_verworfen`): erst der Phasenübergang, dann der Beschluss."""
    antrag, _, er = werkstatt_lage(ordnung, raete=2)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - T(days=20))
    antrag.refresh_from_db()
    fenster_oeffnen(client, antrag, er[0])
    client.post(reverse('gremien:fenster_aktion', args=[antrag.pk]), {'aktion': 'einreichung'})
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.EINREICHUNG, antrag=antrag)
    stimmen(client, beschluss, er[:1], interessenbindung='keine')
    assert beschluss.status == BeschlussStatus.OFFEN
    # Zeitraffer: Die Beratung ist seit einem Tag um; niemand hat seither den Antrag geöffnet.
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=antrag.phase_beginn - T(days=2))
    antrag.refresh_from_db()
    ende = antrag.phase_beginn + T(days=antrag.policy().beratung_tage)
    assert antrag.phase == 'beratung' and ende < timezone.now() < beschluss.frist
    stimmen(client, beschluss, er[1:], interessenbindung='keine')  # die letzte Stimme schließt
    antrag.refresh_from_db()
    entwurf = Entwurf.objects.get(antrag=antrag)
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and beschluss.ergebnis == 'dafuer'
    assert antrag.phase == 'abstimmung' and antrag.phase_beginn == ende
    assert 'Nicht eingereicht' in beschluss.umsetzungsvermerk
    assert entwurf.status == EntwurfsStatus.IN_ARBEIT and entwurf.eingereicht_am is None


def test_die_letzte_stimme_vor_dem_beratungsende_reicht_weiter_ein(client, ordnung):  # noqa: F811
    """Gegenprobe: Läuft die Beratung noch, reicht die letzte Stimme ein wie bisher."""
    antrag, _, er = werkstatt_lage(ordnung, raete=2)
    fenster_oeffnen(client, antrag, er[0])
    client.post(reverse('gremien:fenster_aktion', args=[antrag.pk]), {'aktion': 'einreichung'})
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.EINREICHUNG, antrag=antrag)
    stimmen(client, beschluss, er, interessenbindung='keine')
    antrag.refresh_from_db()
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and 'Eingereicht' in beschluss.umsetzungsvermerk
    assert antrag.phase == 'beratung'
    assert Entwurf.objects.get(antrag=antrag).status == EntwurfsStatus.UNTERSTUETZER
