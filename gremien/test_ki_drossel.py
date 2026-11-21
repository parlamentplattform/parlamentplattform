"""GP-046: Die KI-Aufrufe der Räte liefen ohne Drossel.

Jeder Klick auf „Einschätzung anfordern“ erzeugte einen Lauf, belegte einen Arbeiter, zehrte am Budget
aller und legte einen weiteren Beitrag ab. Jetzt liefert dieselbe Anforderung zur selben Fassung den
vorhandenen Lauf, und je Konto und Stunde gilt eine Grenze."""

from __future__ import annotations

import pytest
from django.urls import reverse

from gremien import views
from gremien.models import EntwurfsBeitrag
from gremien.test_koordination import _ausgewerteter_test, korat
from gremien.test_werkstatt import ordnung, werkstatt_lage  # noqa: F401
from ki.models import KILauf

pytestmark = pytest.mark.django_db


@pytest.fixture
def attrappe(settings, monkeypatch):
    settings.DDOE_KI_ANBIETER = 'attrappe'
    # Die Drossel zählt je Kalenderstunde: eine feste Stunde, damit kein Lauf über die volle Stunde kippt.
    import mitglieder.botschutz

    monkeypatch.setattr(mitglieder.botschutz.time, 'time', lambda: 1_800_000_000.0)


def _fenster(client, ordnung):  # noqa: F811
    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    client.force_login(er[0])
    aktion = reverse('gremien:fenster_aktion', args=[antrag.pk])
    client.post(aktion, {'aktion': 'oeffnen'})
    return antrag, er, aktion


def test_dieselbe_anforderung_zur_selben_fassung_erzeugt_einen_lauf(client, ordnung, attrappe):  # noqa: F811
    antrag, er, aktion = _fenster(client, ordnung)
    client.post(aktion, {'aktion': 'ki_einschaetzung'})
    antwort = client.post(aktion, {'aktion': 'ki_einschaetzung'}, follow=True)
    assert KILauf.objects.filter(antrag=antrag).count() == 1
    assert EntwurfsBeitrag.objects.filter(ki_lauf__isnull=False).count() == 1
    assert 'bereits vor' in antwort.content.decode()
    # Ein anderes Ratsmitglied bekommt denselben Lauf — die Fassung hat sich nicht geändert.
    client.force_login(er[1])
    client.post(aktion, {'aktion': 'ki_einschaetzung'})
    assert KILauf.objects.filter(antrag=antrag).count() == 1


def test_ueber_der_stundengrenze_entsteht_kein_lauf(client, ordnung, attrappe, monkeypatch):  # noqa: F811
    monkeypatch.setattr(views, '_ki_je_stunde', lambda: 2)
    antrag, er, aktion = _fenster(client, ordnung)
    from gremien.models import EntwurfsFassung

    entwurf = antrag.entwurf
    for nummer in (2, 3, 4):
        # Jede neue Fassung ist eine neue Anforderung; die Grenze zählt Aufrufe je Konto.
        EntwurfsFassung.objects.create(entwurf=entwurf, nummer=nummer, wortlaut=f'Fassung {nummer}.', verfasst_von=er[0])
        antwort = client.post(aktion, {'aktion': 'ki_einschaetzung'}, follow=True)
    assert KILauf.objects.filter(antrag=antrag).count() == 2
    assert 'Stundengrenze' in antwort.content.decode()
    # Die Grenze gilt je Konto: Ein anderes Ratsmitglied fragt weiter.
    client.force_login(er[1])
    client.post(aktion, {'aktion': 'ki_einschaetzung'})
    assert KILauf.objects.filter(antrag=antrag).count() == 3


def test_auch_der_koordinationsrat_fragt_die_zukunftswerkstatt_nur_einmal_je_stand(client, attrappe, monkeypatch):
    leute = korat()
    test, _beschluss = _ausgewerteter_test(client, leute)
    client.force_login(leute[0])
    ziel = reverse('gremien:koordination_test', args=[test.pk])
    vorher = KILauf.objects.count()
    client.post(ziel, {'aktion': 'zukunftswerkstatt'})
    client.post(ziel, {'aktion': 'zukunftswerkstatt'})
    assert KILauf.objects.count() == vorher + 1
    monkeypatch.setattr(views, '_ki_je_stunde', lambda: 1)
    type(test).objects.filter(pk=test.pk).update(hypothese='Eine neue Hypothese.')  # ein neuer Stand
    antwort = client.post(ziel, {'aktion': 'zukunftswerkstatt'}, follow=True)
    assert KILauf.objects.count() == vorher + 1  # neuer Stand, aber die Stundengrenze ist erreicht
    assert 'Stundengrenze' in antwort.content.decode()


def test_die_stundengrenze_kommt_aus_dem_register_und_sperrt_nie_ganz():
    """Gegenlesen: Die Grenze ist eine Stellgröße (`gremien-ki-je-stunde`); ohne Registereintrag gilt der
    eingebaute Zielwert. Ein Wert unter 1 sperrte die Räte ganz aus — die Lesestelle klammert auf 1."""
    from parameter.models import Parameter

    Parameter.objects.filter(schluessel='gremien-ki-je-stunde').delete()
    assert views._ki_je_stunde() == views.GREMIEN_KI_JE_STUNDE
    eintrag = Parameter.objects.create(
        schluessel='gremien-ki-je-stunde', wert='3', beschreibung='KI-Anfragen je Konto und Stunde in den Räten.',
        quelle='GP-046',
    )
    assert views._ki_je_stunde() == 3
    for wert in ('0', '-5'):
        Parameter.objects.filter(pk=eintrag.pk).update(wert=wert)
        assert views._ki_je_stunde() == 1
