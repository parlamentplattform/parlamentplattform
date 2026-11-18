"""Gesamtprüfung 18.11.2026, erste Behebungsrunde: Befunde am Verfahrensmodell, die keine eigene
Testdatei im Gremienpaket haben (das Modell `verfahren/models.py` gehört zu diesem Paket)."""

import pytest

from gremien.test_integritaet import antrag_in_abstimmung
from gremien.test_werkstatt import mitglied_anlegen, ordnung  # noqa: F401
from verfahren.models import AuditEintrag, Stimmabgabe, stimme_abgeben

pytestmark = pytest.mark.django_db


def _stimm_ereignisse(antrag):
    return [
        e.ereignis['typ']
        for e in AuditEintrag.objects.order_by('lfd')
        if e.ereignis['typ'] in ('stimme', 'stimme_geaendert') and e.ereignis.get('antrag') == antrag.pk
    ]


def test_dieselbe_stimme_noch_einmal_ist_keine_aenderung(ordnung):  # noqa: F811
    """GP-164: Ein zweites „ja“ schrieb das öffentliche Ereignis „Stimme geändert“, obwohl sich nichts
    geändert hatte. Jetzt entsteht kein Ereignis, und die Stimmzeile bleibt, wie sie war."""
    antrag = antrag_in_abstimmung(ordnung)
    mitglied = mitglied_anlegen('waehlerin')
    erste = stimme_abgeben(antrag, mitglied, 'ja')
    zeitpunkt = erste.abgegeben_am
    zweite = stimme_abgeben(antrag, mitglied, 'ja')
    assert _stimm_ereignisse(antrag) == ['stimme']
    assert zweite.pk == erste.pk and Stimmabgabe.objects.filter(antrag=antrag).count() == 1
    assert Stimmabgabe.objects.get(pk=erste.pk).abgegeben_am == zeitpunkt


def test_eine_wirklich_geaenderte_stimme_bleibt_eine_aenderung(ordnung):  # noqa: F811
    """Gegenprobe: Das Überschreiben bei einem anderen Wert bleibt — eine Zeile, ein Ereignis mehr."""
    antrag = antrag_in_abstimmung(ordnung)
    mitglied = mitglied_anlegen('waehlerin')
    stimme_abgeben(antrag, mitglied, 'ja')
    stimme_abgeben(antrag, mitglied, 'ja')
    geaendert = stimme_abgeben(antrag, mitglied, 'nein')
    assert _stimm_ereignisse(antrag) == ['stimme', 'stimme_geaendert']
    assert geaendert.stimme == 'nein' and Stimmabgabe.objects.filter(antrag=antrag).count() == 1


# --- Parametertests des Koordinationsrats (GP-013, GP-042, GP-043, GP-044) -------------------


def _korat(anzahl=3):
    from gremien.models import Gremium
    from gremien.test_werkstatt import rolle_geben

    leute = [mitglied_anlegen(f'krat{i}') for i in range(anzahl)]
    for m in leute:
        rolle_geben(m, Gremium.KOORDINATIONSRAT)
    return leute


def _register(schluessel):
    from parameter.models import Parameter, erstbestand_sicherstellen

    erstbestand_sicherstellen()
    return Parameter.objects.get(schluessel=schluessel)


def _test_anordnen(client, wer, parameter, testwert, ende=None, **extra):
    from datetime import timedelta

    from django.urls import reverse
    from django.utils import timezone

    client.force_login(wer)
    return client.post(
        reverse('gremien:koordination_test', args=[0]),
        {
            'aktion': 'anordnen',
            'parameter': parameter.pk,
            'testwert': testwert,
            'hypothese': 'Kürzere Beiträge, mehr Beteiligung.',
            'messgroesse': 'motions.total',
            'ende': (ende or (timezone.localdate() + timedelta(days=30))).isoformat(),
            'rueckweg': 'Der alte Wert kommt am Ende von selbst zurück.',
            **extra,
        },
        follow=True,
    )


def _rat_stimmt(client, leute, beschluss, option='dafuer'):
    from django.urls import reverse

    for m in leute:
        client.force_login(m)
        client.post(reverse('gremien:beschluss_stimme', args=[beschluss.pk]), {'option': option, 'begruendung': 'Weil.'})
    beschluss.refresh_from_db()
    return beschluss


def test_der_vermerk_am_testbeschluss_sagt_was_wirklich_geschieht(client):
    """GP-013: Der Vermerk behauptete, der Testwert gelte „für neu beginnende Verfahren“ — eine
    Stellgröße wie die Zeichen-Höchstzahl im Chat liest aber jedes laufende Verfahren sofort. Der
    Vermerk sagt jetzt dasselbe wie das Register: Der Wert wirkt sofort, wo er gelesen wird."""
    from parameter.models import ParameterTest

    leute = _korat()
    parameter = _register('chat-zeichen-hoechstzahl')
    _test_anordnen(client, leute[0], parameter, '100')
    beschluss = _rat_stimmt(client, leute, ParameterTest.objects.get().beschluss)
    parameter.refresh_from_db()
    assert parameter.wert == '100'  # der Wert steht sofort im Register — für alle, die ihn lesen
    assert 'neu beginnende Verfahren' not in beschluss.umsetzungsvermerk
    assert 'wirkt sofort' in beschluss.umsetzungsvermerk and 'laufenden Verfahren' in beschluss.umsetzungsvermerk


def _laufender_test(client, leute, schluessel='gremien-beschluss-tage', testwert='9'):
    from parameter.models import ParameterTest

    parameter = _register(schluessel)
    _test_anordnen(client, leute[0], parameter, testwert)
    test = ParameterTest.objects.get()
    _rat_stimmt(client, leute, test.beschluss)
    test.refresh_from_db()
    return parameter, test


def test_ein_von_der_verwaltung_ueberschriebener_testwert_bleibt_nicht_im_test(client):
    """GP-042: Der Rückfall am Testende griff nur, wenn der Registerwert noch der Testwert war. Hatte
    die Verwaltung ihn während des Tests geändert, blieb die Stellgröße für immer „im Test“ — mit Band,
    und für jeden weiteren Test gesperrt. Jetzt endet der Teststatus immer; der abweichende Wert bleibt
    stehen und ist in Historie und Audit vermerkt."""
    from datetime import timedelta

    from django.urls import reverse
    from django.utils import timezone

    from gremien.models import parametertests_fortschreiben
    from gremien.views import _testbare_parameter
    from parameter.models import Aenderung, Parameter, ParameterTest, Status

    leute = _korat()
    parameter, test = _laufender_test(client, leute)
    Parameter.objects.filter(pk=parameter.pk).update(wert='12')  # die Verwaltung ändert nur den Wert
    ParameterTest.objects.filter(pk=test.pk).update(ende=timezone.localdate() - timedelta(days=1))
    assert parametertests_fortschreiben() == 1
    parameter.refresh_from_db()
    assert parameter.status == Status.GUELTIG and parameter.test_bis is None and parameter.test_hypothese == ''
    assert parameter.wert == '12'  # der Wert der Verwaltung bleibt stehen — kein Rückfall über ihn hinweg
    assert parameter in _testbare_parameter()
    letzte = Aenderung.objects.filter(parameter=parameter).order_by('-geaendert_am', '-pk').first()
    assert 'Testende' in letzte.durch and letzte.alter_wert == '12' and letzte.neuer_wert == '12'
    assert 'kein Rückfall' in letzte.grund
    ereignis = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis['typ'] == 'parametertest_ausgewertet'][-1]
    assert ereignis['rueckfall'] is False and ereignis['wert'] == '12'
    client.logout()
    seite = client.get(reverse('parameter:liste')).content.decode()
    assert 'Der Testwert wirkt sofort überall' not in seite  # kein Band mehr
