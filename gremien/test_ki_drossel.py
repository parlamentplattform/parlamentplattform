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


def _grenze(wert: int) -> None:
    """Setzt die Stundengrenze an der Lesestelle selbst — der Test hängt nicht am Erstbestand."""
    from parameter.models import Parameter

    Parameter.objects.update_or_create(
        schluessel='gremien-ki-je-stunde',
        defaults={'wert': str(wert), 'beschreibung': 'KI-Anfragen je Konto und Stunde in den Räten.', 'quelle': 'GP-046'},
    )


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


def test_ueber_der_stundengrenze_entsteht_kein_lauf(client, ordnung, attrappe):  # noqa: F811
    _grenze(2)
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


def test_auch_der_koordinationsrat_fragt_die_zukunftswerkstatt_nur_einmal_je_stand(client, attrappe):
    _grenze(1)
    leute = korat()
    test, _beschluss = _ausgewerteter_test(client, leute)
    client.force_login(leute[0])
    ziel = reverse('gremien:koordination_test', args=[test.pk])
    vorher = KILauf.objects.count()
    client.post(ziel, {'aktion': 'zukunftswerkstatt'})
    client.post(ziel, {'aktion': 'zukunftswerkstatt'})
    assert KILauf.objects.count() == vorher + 1
    type(test).objects.filter(pk=test.pk).update(hypothese='Eine neue Hypothese.')  # ein neuer Stand
    antwort = client.post(ziel, {'aktion': 'zukunftswerkstatt'}, follow=True)
    assert KILauf.objects.count() == vorher + 1  # neuer Stand, aber die Stundengrenze ist erreicht
    assert 'Stundengrenze' in antwort.content.decode()


def test_die_stundengrenze_kommt_aus_dem_register_und_0_heisst_keine_grenze():
    """GP-046, Folgewelle: Die Grenze ist eine Stellgröße (`gremien-ki-je-stunde`) mit Startwert 0 = keine
    Grenze (die Zahl ist eine offene Frage an den Gründer, E-13.4). Ohne Registereintrag gilt der Startwert;
    0 und Werte darunter sperren nie, jeder Wert ab 1 drosselt."""
    from parameter.models import Parameter

    assert not hasattr(views, 'GREMIEN_KI_JE_STUNDE')  # keine harte Zahl neben dem Register
    Parameter.objects.filter(schluessel='gremien-ki-je-stunde').delete()
    assert views._ki_je_stunde() == 0
    _grenze(3)
    assert views._ki_je_stunde() == 3
    _grenze(-5)
    assert views._ki_je_stunde() == 0  # ein Wert unter 0 sperrt nicht — er schaltet die Drossel aus


def test_mit_angelegtem_erstbestand_fragen_die_raete_mehrmals_je_stunde(client, ordnung, attrappe):  # noqa: F811
    '''Schlusspflege (E-13.4 offen): Mit dem ausgelieferten Startwert ist ein Konto nicht auf eine
    Anfrage je Stunde begrenzt — weder im Entwurfsfenster noch beim Parametertest.'''
    from gremien.models import EntwurfsFassung
    from parameter.models import Parameter, erstbestand_sicherstellen

    erstbestand_sicherstellen()
    assert Parameter.objects.get(schluessel='gremien-ki-je-stunde').wert == '0'
    antrag, er, aktion = _fenster(client, ordnung)
    for nummer in (2, 3, 4):
        EntwurfsFassung.objects.create(entwurf=antrag.entwurf, nummer=nummer, wortlaut=f'Fassung {nummer}.', verfasst_von=er[0])
        antwort = client.post(aktion, {'aktion': 'ki_einschaetzung'}, follow=True)
        assert 'Stundengrenze' not in antwort.content.decode()
    assert KILauf.objects.filter(antrag=antrag).count() == 3


def test_mit_angelegtem_erstbestand_fragt_der_koordinationsrat_mehrmals_je_stunde(client, attrappe):
    from parameter.models import Parameter, erstbestand_sicherstellen

    erstbestand_sicherstellen()
    assert Parameter.objects.get(schluessel='gremien-ki-je-stunde').wert == '0'
    leute = korat()
    test, _beschluss = _ausgewerteter_test(client, leute)
    client.force_login(leute[0])
    ziel = reverse('gremien:koordination_test', args=[test.pk])
    vorher = KILauf.objects.count()
    client.post(ziel, {'aktion': 'zukunftswerkstatt'})
    type(test).objects.filter(pk=test.pk).update(hypothese='Eine neue Hypothese.')
    antwort = client.post(ziel, {'aktion': 'zukunftswerkstatt'}, follow=True)
    assert KILauf.objects.count() == vorher + 2
    assert 'Stundengrenze' not in antwort.content.decode()


def test_bei_grenze_0_greift_die_drossel_nie(client, ordnung, attrappe):  # noqa: F811
    from gremien.models import EntwurfsFassung
    from mitglieder.models import Drosselzaehler

    _grenze(0)
    antrag, er, aktion = _fenster(client, ordnung)
    entwurf = antrag.entwurf
    for nummer in (2, 3, 4, 5):
        EntwurfsFassung.objects.create(entwurf=entwurf, nummer=nummer, wortlaut=f'Fassung {nummer}.', verfasst_von=er[0])
        antwort = client.post(aktion, {'aktion': 'ki_einschaetzung'}, follow=True)
        assert 'Stundengrenze' not in antwort.content.decode()
    assert KILauf.objects.filter(antrag=antrag).count() == 4
    assert not Drosselzaehler.objects.filter(zweck='gremien_ki').exists()
