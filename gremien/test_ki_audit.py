"""GP-045: Gremienhandlungen mit Modellaufruf und der Endzustand „gescheitert“ schrieben keinen Audit-Eintrag.

Nach Einschätzung (Entwurfsfenster der Gruppe 1) und Werkstattlauf (Parametertest des Koordinationsrats)
steht je ein Eintrag mit Laufnummer; nach dem letzten Fehlversuch eines Auftrags der Warteschlange einer
mit Auftragsnummer. Kein Eintrag nennt eine Person oder einen Fehlertext des Anbieters."""

from __future__ import annotations

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import EntwurfsBeitrag
from gremien.test_gp129_fassung import KetteGestoert, scheitert  # noqa: F401
from gremien.test_koordination import _ausgewerteter_test, korat
from gremien.test_werkstatt import ordnung, werkstatt_lage  # noqa: F401
from ki.anbieter import AnbieterFehler, AntwortAbgeschnitten, AttrappenAnbieter
from ki.models import Auftragsstatus, KILauf, Zweck
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.warteschlange import HOECHSTVERSUCHE, auftrag_ausfuehren, einreihen
from verfahren.audit_oeffentlich import ereignis_oeffentlich
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db

PERSONENSCHLUESSEL = {'durch', 'mitglied', 'von', 'angefordert_von', 'name', 'email', 'fehler'}


@pytest.fixture
def attrappe(settings, monkeypatch):
    settings.DDOE_KI_ANBIETER = 'attrappe'
    import mitglieder.botschutz

    monkeypatch.setattr(mitglieder.botschutz.time, 'time', lambda: 1_800_000_000.0)


def _eintraege(typ):
    return [e.ereignis for e in AuditEintrag.objects.order_by('pk') if e.ereignis.get('typ') == typ]


def _ohne_person(ereignis, *leute):
    assert not PERSONENSCHLUESSEL & set(ereignis)
    werte = {v for v in ereignis.values() if isinstance(v, str)}
    assert not any('@' in v for v in werte)
    for person in leute:
        assert not {person.anzeigename, person.email, person.username} & werte
    # Im öffentlichen Protokoll steht der Eintrag, wie er ist: Es gibt darin nichts zu schwärzen.
    assert ereignis_oeffentlich(ereignis) == (ereignis, False)


def test_die_einschaetzung_im_entwurfsfenster_steht_mit_laufnummer_im_audit(client, ordnung, attrappe):  # noqa: F811
    antrag, _u, er = werkstatt_lage(ordnung)
    client.force_login(er[0])
    aktion = reverse('gremien:fenster_aktion', args=[antrag.pk])
    client.post(aktion, {'aktion': 'oeffnen'})
    client.post(aktion, {'aktion': 'ki_einschaetzung'})
    lauf = KILauf.objects.get(antrag=antrag)
    assert EntwurfsBeitrag.objects.filter(ki_lauf=lauf).exists()
    eintraege = _eintraege('gremien_ki_lauf')
    assert len(eintraege) == 1
    assert eintraege[0]['lauf'] == lauf.pk and eintraege[0]['zweck'] == Zweck.EINSCHAETZUNG
    assert eintraege[0]['gremium'] == 'expertenrat1' and eintraege[0]['antrag'] == antrag.pk
    _ohne_person(eintraege[0], *er)
    # Dieselbe Anforderung zum selben Stand ruft kein Modell — und schreibt keinen zweiten Eintrag.
    client.post(aktion, {'aktion': 'ki_einschaetzung'})
    assert len(_eintraege('gremien_ki_lauf')) == 1


def test_der_werkstattlauf_zum_parametertest_steht_mit_laufnummer_im_audit(client, attrappe):
    leute = korat()
    test, _beschluss = _ausgewerteter_test(client, leute)
    client.force_login(leute[0])
    client.post(reverse('gremien:koordination_test', args=[test.pk]), {'aktion': 'zukunftswerkstatt'})
    test.refresh_from_db()
    assert test.ki_lauf_id is not None
    eintraege = _eintraege('gremien_ki_lauf')
    assert len(eintraege) == 1
    assert eintraege[0]['lauf'] == test.ki_lauf_id and eintraege[0]['zweck'] == Zweck.PARAMETERVORSCHLAG
    assert eintraege[0]['gremium'] == 'koordinationsrat' and eintraege[0]['test'] == test.pk
    _ohne_person(eintraege[0], *leute)


def test_ein_stummer_steckplatz_schreibt_keinen_lauf_eintrag(client, ordnung, attrappe, monkeypatch):  # noqa: F811
    """Ohne Ergebnis hält das Gremium nichts fest; der gescheiterte Aufruf steht im Lauf-Archiv."""
    def kaputt(self, auftrag, eingabe):
        raise AnbieterFehler('HTTP 503 vom Anbieter')

    monkeypatch.setattr(AttrappenAnbieter, 'frage', kaputt)
    antrag, _u, er = werkstatt_lage(ordnung)
    client.force_login(er[0])
    aktion = reverse('gremien:fenster_aktion', args=[antrag.pk])
    client.post(aktion, {'aktion': 'oeffnen'})
    client.post(aktion, {'aktion': 'ki_einschaetzung'})
    assert not _eintraege('gremien_ki_lauf')


def test_nach_dem_letzten_fehlversuch_steht_die_auftragsnummer_im_audit(a, monkeypatch):  # noqa: F811
    def kaputt(self, auftrag, eingabe):
        raise AnbieterFehler('HTTP 503 vom Anbieter, Konto beispiel@example.org')

    monkeypatch.setattr(AttrappenAnbieter, 'frage', kaputt)
    auftrag = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    jetzt = timezone.now()
    for _versuch in range(HOECHSTVERSUCHE - 1):
        assert auftrag_ausfuehren(auftrag.pk, jetzt) == 'verschoben'
        assert not _eintraege('ki_auftrag_gescheitert')  # ein Rückzug ist kein Endzustand
        jetzt += timedelta(hours=1)
    assert auftrag_ausfuehren(auftrag.pk, jetzt) == 'gescheitert'
    auftrag.refresh_from_db()
    assert auftrag.status == Auftragsstatus.GESCHEITERT
    eintraege = _eintraege('ki_auftrag_gescheitert')
    assert len(eintraege) == 1
    assert eintraege[0]['auftrag'] == auftrag.pk and eintraege[0]['zweck'] == Zweck.RECHTSBEZUG
    assert eintraege[0]['antrag'] == a.pk
    _ohne_person(eintraege[0], a.eingebracht_von)
    text = json.dumps(eintraege[0], ensure_ascii=False)
    assert '503' not in text and 'example.org' not in text  # kein Fehlertext in der Kette
    # Ein gescheiterter Auftrag läuft nicht wieder — es bleibt bei einem Eintrag.
    assert auftrag_ausfuehren(auftrag.pk, jetzt + timedelta(hours=1)) == 'uebersprungen'
    assert len(_eintraege('ki_auftrag_gescheitert')) == 1


def test_auch_eine_abgeschnittene_antwort_endet_mit_eintrag(a, monkeypatch):  # noqa: F811
    from ki import warteschlange

    def abgeschnitten(auftrag):
        raise AntwortAbgeschnitten('Die Antwort des Anbieters wurde an der Längengrenze abgeschnitten.')

    monkeypatch.setitem(warteschlange.ARBEIT, Zweck.RECHTSBEZUG, abgeschnitten)
    auftrag = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert auftrag_ausfuehren(auftrag.pk) == 'gescheitert'
    eintraege = _eintraege('ki_auftrag_gescheitert')
    assert [e['auftrag'] for e in eintraege] == [auftrag.pk]
    assert 'Längengrenze' not in json.dumps(eintraege[0], ensure_ascii=False)


# Gegenlesen: Die neuen Einträge stehen mit ihrer Handlung in einer Transaktion (CLAUDE.md § 4, GP-129).


def test_scheitert_der_eintrag_bleibt_von_der_einschaetzung_kein_beitrag(client, ordnung, attrappe, scheitert):  # noqa: F811
    antrag, _u, er = werkstatt_lage(ordnung)
    client.force_login(er[0])
    aktion = reverse('gremien:fenster_aktion', args=[antrag.pk])
    client.post(aktion, {'aktion': 'oeffnen'})
    scheitert('gremien_ki_lauf')
    with pytest.raises(KetteGestoert):
        client.post(aktion, {'aktion': 'ki_einschaetzung'})
    assert not EntwurfsBeitrag.objects.filter(ki_lauf__isnull=False).exists()
    assert KILauf.objects.filter(antrag=antrag).count() == 1  # der bezahlte Lauf bleibt im Archiv


def test_scheitert_der_eintrag_bleibt_der_laufverweis_am_test_unveraendert(client, attrappe, scheitert):  # noqa: F811
    leute = korat()
    test, _beschluss = _ausgewerteter_test(client, leute)
    client.force_login(leute[0])
    scheitert('gremien_ki_lauf')
    with pytest.raises(KetteGestoert):
        client.post(reverse('gremien:koordination_test', args=[test.pk]), {'aktion': 'zukunftswerkstatt'})
    test.refresh_from_db()
    assert test.ki_lauf_id is None


def test_scheitert_der_eintrag_ist_der_auftrag_nicht_als_gescheitert_verbucht(a, monkeypatch, scheitert):  # noqa: F811
    from ki import warteschlange

    def abgeschnitten(auftrag):
        raise AntwortAbgeschnitten('Die Antwort des Anbieters wurde an der Längengrenze abgeschnitten.')

    monkeypatch.setitem(warteschlange.ARBEIT, Zweck.RECHTSBEZUG, abgeschnitten)
    auftrag = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    scheitert('ki_auftrag_gescheitert')
    with pytest.raises(KetteGestoert):
        auftrag_ausfuehren(auftrag.pk)
    auftrag.refresh_from_db()
    assert auftrag.status == Auftragsstatus.LAEUFT  # Endzustand und Eintrag gemeinsam oder gar nicht
