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


AUSGENOMMEN_WEIL_LIVE_GELESEN = ('chat-zeichen-hoechstzahl', 'kritik-mindestzeichen', 'chat-bearbeitungsfenster-minuten')


@pytest.mark.parametrize('schluessel', AUSGENOMMEN_WEIL_LIVE_GELESEN)
def test_was_ein_laufendes_verfahren_liest_laesst_sich_nicht_testen(client, schluessel):
    """GP-013, D-J3g: „Ein Test wirkt nur auf Registerwerte, die kein laufendes Verfahren liest.“ Die
    Zeichengrenzen und das Bearbeitungsfenster liest der Chat jedes laufenden Antrags bei jedem Beitrag —
    ein Test auf ihnen änderte die Bedingungen mitten im Verfahren. Er wird abgewiesen, mit Meldung."""
    from django.urls import reverse

    from gremien.models import Anlass, GremienBeschluss
    from gremien.views import IM_LAUFENDEN_VERFAHREN_GELESEN, _testbare_parameter
    from parameter.models import ParameterTest

    leute = _korat()
    parameter = _register(schluessel)
    vorher = parameter.wert
    assert schluessel in IM_LAUFENDEN_VERFAHREN_GELESEN
    assert parameter not in _testbare_parameter()
    client.force_login(leute[0])
    seite = client.get(reverse('gremien:koordination')).content.decode()
    auswahl = seite.split('id="pt-parameter"')[1].split('</select>')[0]
    assert f'value="{parameter.pk}"' not in auswahl
    antwort = _test_anordnen(client, leute[0], parameter, '7')
    assert antwort.status_code == 200  # eine Meldung, kein 404
    assert 'Laufende Verfahren lesen ihren Wert' in antwort.content.decode()
    assert not ParameterTest.objects.exists()
    assert not GremienBeschluss.objects.filter(anlass=Anlass.PARAMETERTEST).exists()
    parameter.refresh_from_db()
    assert parameter.wert == vorher and parameter.status != 'im_test'


def test_der_vermerk_am_testbeschluss_sagt_was_wirklich_geschieht(client):
    """GP-013: Der Vermerk behauptete erst, der Testwert gelte „für neu beginnende Verfahren“, dann, er
    wirke „auch in laufenden Verfahren“. Seit die live gelesenen Stellgrößen ausgenommen sind (D-J3g),
    sagt er das: Der Wert wirkt sofort, wo er gelesen wird — und was laufende Verfahren lesen, ist ausgenommen."""
    from parameter.models import ParameterTest

    leute = _korat()
    parameter = _register('gremien-rollen-dauer-tage')
    _test_anordnen(client, leute[0], parameter, '365')
    beschluss = _rat_stimmt(client, leute, ParameterTest.objects.get().beschluss)
    parameter.refresh_from_db()
    assert parameter.wert == '365'  # der Wert steht sofort im Register — für alle, die ihn lesen
    vermerk = beschluss.umsetzungsvermerk
    assert 'neu beginnende Verfahren' not in vermerk and 'auch in laufenden Verfahren' not in vermerk
    assert 'wirkt sofort' in vermerk and 'vom Test ausgenommen' in vermerk


def test_der_vermerk_nimmt_nicht_alles_aus_was_der_chat_liest(client):
    """GP-013, Gegenlesen: Der Vermerk sagte, „die Stellgrößen, die der Chat laufender Verfahren liest“, seien
    vom Test ausgenommen. Ausgenommen sind aber nur die Zeichengrenzen und das Bearbeitungsfenster; wie viele
    Beiträge der Faden zeigt (`chat-faden-wurzeln`), liest der Chat jedes laufenden Antrags ebenfalls, und
    das bleibt testbar. Der Vermerk nennt deshalb, was ausgenommen ist, statt mehr zu behaupten."""
    from parameter.models import ParameterTest
    from verfahren import chat

    leute = _korat()
    parameter = _register('chat-faden-wurzeln')
    _test_anordnen(client, leute[0], parameter, '5')
    beschluss = _rat_stimmt(client, leute, ParameterTest.objects.get().beschluss)
    assert chat.faden_wurzeln() == 5  # der Chat liest den Testwert sofort — auch in laufenden Verfahren
    vermerk = beschluss.umsetzungsvermerk
    assert 'die der Chat laufender Verfahren liest' not in vermerk
    assert 'Zeichengrenzen' in vermerk and 'Bearbeitungsfenster' in vermerk and 'vom Test ausgenommen' in vermerk


#: Die testbaren Stellgrößen, deren Lesestellen nach D-J3g geprüft sind (Stand der zweiten Behebungsrunde,
#: 18.11.2026): Keine davon liest der Chat eines laufenden Verfahrens bei jedem Zugriff. Sie begrenzen Anzeige,
#: Post, Schutzgrenzen und KI-Budget, oder sie werden gelesen, wenn etwas Neues entsteht (ein Antrag, eine
#: Vertrauens- oder Mandatsfrage, eine Rolle), und dort festgeschrieben. Zweifelsfälle, bewusst nicht ausgenommen:
#: gremien-beschluss-tage, live-hoechstdauer-stunden, mandatar-monatsbericht-frist-tage (siehe Docstring von
#: `gremien.views._testbare_parameter`).
GEPRUEFT_TESTBAR = frozenset({
    'adresswechsel-wartefrist-stunden', 'aehnlichkeit-bedeutung-je-stunde', 'aehnlichkeit-bedeutung-schwelle-prozent',
    'aehnlichkeit-einbettungen-je-aufruf', 'aehnlichkeit-schwelle-prozent', 'aehnlichkeit-treffer',
    'aehnlichkeit-vorschau-hoechstzeichen', 'aehnlichkeit-vorschau-mindestzeichen', 'aehnlichkeit-vorschau-wartezeit-ms',
    'aehnlichkeit-zeitgrenze-sekunden', 'anstoss-mindestabstand-sekunden', 'anstoss-tagesgrenze', 'archiv-audit-anzeige',
    'audit-seite-eintraege', 'audit-vollpruefung-tage', 'beitrag-erinnerung-fruehestens-tage', 'chat-faden-wurzeln',
    'faecher-kinder-hoechstzahl', 'faktenbasis-bestandsnachweis-hoechstzahl', 'faktenbasis-manuelle-abrufe-je-stunde',
    'faktenbasis-seitengroesse', 'gegenueberstellung-hoechstpaare', 'gegenueberstellung-je-stunde',
    'gegenueberstellung-textzeichen', 'gegenueberstellung-zeitgrenze-sekunden', 'gespraeche-liste-hoechstzahl',
    'gremien-beschluesse-seite', 'gremien-beschluss-tage', 'gremien-rollen-dauer-tage', 'kacheln-abgeschlossen',
    'kacheln-hervorgehoben', 'kategorien-je-antrag', 'ki-antwort-hoechsttokens', 'ki-einschaetzungen-je-seite',
    'ki-monatstokens', 'ki-tageslaeufe', 'live-hoechstdauer-stunden', 'live-takt-sekunden',
    'mandatar-monatsbericht-frist-tage', 'mandatsfrage-abstimmung-tage', 'post-hoechstversuche', 'post-neuer-antrag-bund',
    'quellenkontext-bestandsgrenze', 'quellenkontext-hoechstzahl', 'quellenkontext-mindestwortlaenge',
    'quellenkontext-textzeichen', 'rechtsfolgen-eingabezeichen', 'region-nebenwohnsitz-zaehlt', 'suche-treffer-hoechstzahl',
    'uebersicht-abstimmungen', 'vertrauensfrage-abstimmung-tage', 'vertrauensfrage-unterstuetzung-tage',
    'weicherfilter-profile-hoechstzahl',
})


def test_waechter_jede_testbare_stellgroesse_ist_nach_d_j3g_geprueft():
    """GP-013, Wächter: Eine neue Stellgröße ist nicht von selbst testbar. Wer eine anlegt, prüft ihre
    Lesestellen: Liest ein laufendes Verfahren den Wert bei jedem Zugriff, gehört sie in die Ausnahmeliste
    `gremien.views.IM_LAUFENDEN_VERFAHREN_GELESEN`, sonst in `GEPRUEFT_TESTBAR` hier."""
    from gremien.views import IM_LAUFENDEN_VERFAHREN_GELESEN, _testbare_parameter
    from parameter.models import ERSTBESTAND, erstbestand_sicherstellen

    erstbestand_sicherstellen()
    testbar = set(_testbare_parameter().values_list('schluessel', flat=True))
    assert testbar == GEPRUEFT_TESTBAR, (
        f'Ungeprüft testbar: {sorted(testbar - GEPRUEFT_TESTBAR)}; nicht mehr testbar: {sorted(GEPRUEFT_TESTBAR - testbar)}'
    )
    im_register = {e['schluessel'] for e in ERSTBESTAND}
    assert set(IM_LAUFENDEN_VERFAHREN_GELESEN) <= im_register  # keine toten Einträge
    assert set(IM_LAUFENDEN_VERFAHREN_GELESEN) == set(AUSGENOMMEN_WEIL_LIVE_GELESEN)
    assert not set(IM_LAUFENDEN_VERFAHREN_GELESEN) & testbar
    assert all(grund.strip() for grund in IM_LAUFENDEN_VERFAHREN_GELESEN.values())  # jede Ausnahme ist begründet


def test_waechter_der_chat_liest_keine_testbare_stellgroesse_ungeprueft():
    """GP-013, Wächter am Quelltext: Der Chat (Antrags- und Abstimmungs-Chat) ist der Ort, an dem ein laufendes
    Verfahren das Register bei jedem Beitrag liest. Jeder Schlüssel, den `verfahren/chat.py` oder das
    Beitragsmodell liest, ist ausgenommen — außer er steuert nur die Anzeige."""
    import inspect
    import re

    from gremien.views import IM_LAUFENDEN_VERFAHREN_GELESEN
    from verfahren import chat
    from verfahren.models import Kommentar

    # Wie viele Wurzelbeiträge eine Seite zeigt und wie lang die Liste „Meine Gespräche“ ist — Anzeige, keine Bedingung.
    nur_anzeige = {'chat-faden-wurzeln', 'gespraeche-liste-hoechstzahl'}
    quelltext = inspect.getsource(chat) + inspect.getsource(Kommentar)
    gelesen = set(re.findall(r'zahl\(\s*"([a-z0-9-]+)"', quelltext))
    assert {'chat-zeichen-hoechstzahl', 'kritik-mindestzeichen', 'chat-bearbeitungsfenster-minuten'} <= gelesen
    offen = gelesen - nur_anzeige - set(IM_LAUFENDEN_VERFAHREN_GELESEN)
    assert not offen, sorted(offen)


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


def test_ein_test_beginnt_nicht_nach_seinem_eigenen_ende(client):
    """GP-043: Lag das Testende vor dem Beschluss des Rates, begann der Test trotzdem — der Wert stand
    im Register und fiel beim nächsten Seitenaufruf zurück, mit einer „Auswertung“ über null Tage."""
    from datetime import timedelta

    from django.utils import timezone

    from parameter.models import Aenderung, ParameterTest, Status, TestStatus

    leute = _korat()
    parameter = _register('gremien-beschluss-tage')
    _test_anordnen(client, leute[0], parameter, '9')
    test = ParameterTest.objects.get()
    ParameterTest.objects.filter(pk=test.pk).update(ende=timezone.localdate() - timedelta(days=1))  # Zeitraffer
    beschluss = _rat_stimmt(client, leute, test.beschluss)
    test.refresh_from_db()
    parameter.refresh_from_db()
    assert test.status == TestStatus.VERWORFEN and 'Ende' in test.auswertung
    assert parameter.wert == '7' and parameter.status == Status.GUELTIG
    assert not Aenderung.objects.filter(parameter=parameter).exists()
    assert 'Nicht angeordnet' in beschluss.umsetzungsvermerk and 'Ende' in beschluss.umsetzungsvermerk


def test_das_testende_muss_nach_der_beschlussfrist_liegen(client):
    """GP-043, beim Anordnen: Ein Test, der enden kann, bevor der Rat entschieden haben muss, entsteht nicht."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import GremienBeschluss
    from parameter.models import ParameterTest

    leute = _korat()
    parameter = _register('gremien-beschluss-tage')  # Beschlussfrist: sieben Tage
    antwort = _test_anordnen(client, leute[0], parameter, '9', ende=timezone.localdate() + timedelta(days=3))
    assert not ParameterTest.objects.exists() and not GremienBeschluss.objects.exists()
    assert 'nach der Beschlussfrist' in antwort.content.decode()
    _test_anordnen(client, leute[0], parameter, '9', ende=timezone.localdate() + timedelta(days=9))
    assert ParameterTest.objects.count() == 1


# --- GP-040: Sätze, die sagen, was geschieht -------------------------------------------------


def test_die_pruefliste_nennt_die_frist_und_ihre_folge_statt_zu_warten(client, ordnung):  # noqa: F811
    """GP-040 (a): Ohne besetzte Gruppe 2 „wartet“ der Vorschlag nicht — nach der Prüffrist geht er weiter."""
    from datetime import timedelta

    from django.urls import reverse
    from django.utils import timezone

    from gremien.test_werkstatt import einreichen, werkstatt_lage

    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    entwurf.refresh_from_db()
    admin = mitglied_anlegen('aufsicht')
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    seite = client.get(reverse('gremien:pruefung')).content.decode()
    frist = timezone.localtime(entwurf.eingereicht_am + timedelta(days=antrag.policy().pruefung_tage))
    assert 'wartet, bis eine besetzt ist' not in seite
    assert 'ohne Prüfung an die Unterstützer' in seite and f'{frist:%d.%m.%Y %H:%M}' in seite


def test_unbesetzte_gremien_versprechen_keine_laufende_ausschreibung(client):
    """GP-040 (b): Eine Ausschreibung gibt es auf der Plattform nicht — die Verwaltung besetzt von Hand."""
    from django.urls import reverse

    assert 'Ausschreibung läuft' not in client.get(reverse('gremien:uebersicht')).content.decode()
    assert 'Noch unbesetzt.' in client.get(reverse('gremien:uebersicht')).content.decode()
    admin = mitglied_anlegen('aufsicht')
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    seite = client.get(reverse('gremien:rat', args=['berichtswesenrat'])).content.decode()
    assert 'Ausschreibung läuft' not in seite and 'Noch unbesetzt.' in seite


def test_ein_austauschbeschluss_ohne_ergebnis_ist_keine_ablehnung(client, ordnung):  # noqa: F811
    """GP-040: Ein Gleichstand im Koordinationsrat stand als „abgelehnt“ am Antrag."""
    from django.urls import reverse

    from gremien.models import Anlass, BeschlussStatus, GremienBeschluss, Gremium, Pruefung
    from gremien.test_pruefung import korat_lage, stimme
    from gremien.test_werkstatt import rolle_geben

    antrag, entwurf, _er, korat = korat_lage(client, ordnung)
    zweite = mitglied_anlegen('koordinator2')
    rolle_geben(zweite, Gremium.KOORDINATIONSRAT)
    pruefung = entwurf.pruefungen.get()
    client.force_login(korat)
    client.post(reverse('gremien:koordination_beschluss'), {'anlass': 'austausch', 'pruefung': pruefung.pk, 'beschreibung': 'Prüfen wir.'})
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.AUSTAUSCH, antrag=antrag)
    stimme(client, beschluss, korat, 'dafuer')
    stimme(client, beschluss, zweite, 'dagegen')
    beschluss.refresh_from_db()
    pruefung.refresh_from_db()
    assert beschluss.status == BeschlussStatus.OHNE_ERGEBNIS
    assert pruefung.korat_entscheid == Pruefung.KoratEntscheid.OHNE_ERGEBNIS != 'abgelehnt'
    assert 'Ohne Ergebnis' in beschluss.umsetzungsvermerk and 'Abgelehnt' not in beschluss.umsetzungsvermerk
    ereignis = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis['typ'] == 'austausch_entschieden'][-1]
    assert ereignis['entscheid'] == 'ergebnislos'
    client.logout()
    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert 'ohne Ergebnis' in seite


def test_die_aussetzungskarte_nennt_nach_dem_vermerk_das_schiedsgericht_statt_der_frist(client, ordnung):  # noqa: F811
    """GP-040: Nach dem Vermerk endet die Aussetzung nicht mehr mit der Frist — die Karte nannte sie weiter."""
    from django.urls import reverse

    from gremien.models import Anlass, Aussetzung
    from gremien.test_integritaet import beschluss_fassen, rat

    leute = rat()
    antrag = antrag_in_abstimmung(ordnung)
    beschluss_fassen(client, leute, antrag, Anlass.AUSSETZUNG, 'Verdacht auf Manipulation.')
    aussetzung = Aussetzung.objects.get(antrag=antrag)
    client.force_login(leute[0])
    assert 'Antrag ans Schiedsgericht bis' in client.get(reverse('gremien:integritaet')).content.decode()
    client.post(reverse('gremien:integritaet_schiedsgericht', args=[aussetzung.pk]), {'kennung': 'PSG-2026-004'})
    seite = client.get(reverse('gremien:integritaet')).content.decode()
    assert 'Antrag ans Schiedsgericht bis' not in seite and 'beim Parteischiedsgericht seit' in seite


def test_die_alten_saetze_stehen_in_keinem_template_mehr():
    from pathlib import Path

    alle = '\n'.join(p.read_text(encoding='utf-8') for p in Path(__file__).parent.glob('templates/gremien/*.html'))
    for alt in ('wartet, bis eine besetzt ist', 'die Ausschreibung läuft über den Koordinationsrat', 'mit Grund dokumentiert'):
        assert alt not in alle


# --- GP-044: Keine Tests auf Versionsschildern, keine unlesbaren Testwerte --------------------


def test_versionsschilder_stehen_nicht_zur_wahl_und_lassen_sich_nicht_testen(client):
    """GP-044: Der Rat konnte eine Regelfassung „testen“, die es im Code nicht gibt — das Register wies
    dann eine Fassung „im Test“ aus, nach der niemand rechnete."""
    from gremien.views import _testbare_parameter
    from parameter.models import ParameterTest

    leute = _korat()
    schild = _register('weicherfilter-regel')
    assert schild.einheit == 'Regelfassung'
    assert not _testbare_parameter().filter(einheit='Regelfassung').exists()
    antwort = _test_anordnen(client, leute[0], schild, '3')
    # Eine Meldung wie bei den übrigen Abweisungen, kein 404 (GP-044, Gegenlesen).
    assert antwort.status_code == 200 and not ParameterTest.objects.exists()
    assert 'Ein Versionsschild lässt sich nicht testen' in antwort.content.decode()


def test_auch_ordnungsschluessel_und_laufende_tests_werden_mit_meldung_abgewiesen(client):
    """GP-044, Gegenlesen: Jede Abweisung beim Anordnen sagt, warum — auch bei einer handgebauten Anfrage auf
    einen Wert der Verfahrensordnung (D-J3g) oder auf eine Stellgröße, die schon im Test steht. Nur eine
    Kennung, die es nicht gibt, bleibt ein 404."""
    from gremien.views import _nicht_testbar, _testbare_parameter
    from parameter.models import Parameter, ParameterTest, Status

    leute = _korat()
    ordnungswert = _register('verfahren-abstimmung-tage')
    antwort = _test_anordnen(client, leute[0], ordnungswert, '10')
    assert antwort.status_code == 200 and not ParameterTest.objects.exists()
    assert 'Werte der Verfahrensordnung lassen sich nicht testen' in antwort.content.decode()
    im_test = _register('gremien-rollen-dauer-tage')
    Parameter.objects.filter(pk=im_test.pk).update(status=Status.IM_TEST)
    antwort = _test_anordnen(client, leute[0], im_test, '365')
    assert antwort.status_code == 200 and not ParameterTest.objects.exists()
    assert 'läuft schon ein Test' in antwort.content.decode()
    im_test.pk = 999999
    assert _test_anordnen(client, leute[0], im_test, '365').status_code == 404
    # Auswahlliste und Abweisung lesen dieselben Ausnahmen: Was nicht zur Wahl steht, hat einen Grund.
    Parameter.objects.filter(status=Status.IM_TEST).update(status=Status.GUELTIG)
    testbar = set(_testbare_parameter().values_list('pk', flat=True))
    for parameter in Parameter.objects.all():
        assert (_nicht_testbar(parameter) is None) == (parameter.pk in testbar), parameter.schluessel


def test_ein_unlesbarer_testwert_wird_abgewiesen(client):
    """GP-044: „keine“ als Testwert einer Zahl las die Plattform als den eingebauten Zielwert — der Test
    maß nichts, stand aber im Register, im Bericht und im Posteingang."""
    from parameter.models import ParameterTest

    leute = _korat()
    parameter = _register('gremien-rollen-dauer-tage')
    antwort = _test_anordnen(client, leute[0], parameter, 'keine')
    assert not ParameterTest.objects.exists()
    assert 'ganze Zahl' in antwort.content.decode()
    _test_anordnen(client, leute[0], parameter, '100')
    assert ParameterTest.objects.count() == 1


# --- GP-047: Das Werkstattfenster verlinkt den Folgenbericht, statt rohes JSON zu zeigen ------


def test_das_fenster_zeigt_den_folgenbericht_nicht_als_rohes_json(client, ordnung, monkeypatch):  # noqa: F811
    """GP-047: Ohne Werkstatt-Einschätzung fiel die Arbeitsunterlage auf den Rechtsfolgenlauf zurück — und
    zeigte dessen JSON, bei 1200 Zeichen abgeschnitten. Der Verweis „in Zone 2“ zielte auf eine id, die es
    auf der Antragsseite nicht gibt."""
    import re
    from types import SimpleNamespace

    from django.urls import reverse
    from django.utils import timezone

    import verfahren.views
    from gremien.test_werkstatt import fenster_oeffnen, werkstatt_lage

    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    fenster_oeffnen(client, antrag, er[0])
    echt = verfahren.views._einschaetzung

    def mit_folgenlauf(antrag, *args, **kwargs):
        lage = echt(antrag, *args, **kwargs)
        lage['lauf'] = SimpleNamespace(zweck='rechtsfolgen', antwort='{"normen": [], "judikatur": {"text": "x"}}', erstellt_am=timezone.now(), modell='attrappe')
        lage['beanstandungen'] = [SimpleNamespace(pk=1)]
        return lage

    monkeypatch.setattr(verfahren.views, '_einschaetzung', mit_folgenlauf)
    seite = client.get(reverse('gremien:fenster', args=[antrag.pk])).content.decode()
    assert '&quot;normen&quot;' not in seite and '"normen"' not in seite and '&quot;judikatur&quot;' not in seite
    assert 'Zum Rechtsfolgenbericht am Antrag' in seite
    assert '#zone-2' not in seite
    ziele = set(re.findall(rf'href="/antrag/{antrag.pk}/#([a-z0-9-]+)"', seite))
    assert ziele == {'zone-einschaetzung'}
    client.logout()
    antragsseite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert 'id="zone-einschaetzung"' in antragsseite


def test_eine_werkstatt_einschaetzung_steht_weiter_im_fenster(client, ordnung, monkeypatch):  # noqa: F811
    from types import SimpleNamespace

    from django.urls import reverse
    from django.utils import timezone

    import verfahren.views
    from gremien.test_werkstatt import fenster_oeffnen, werkstatt_lage

    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    fenster_oeffnen(client, antrag, er[0])
    echt = verfahren.views._einschaetzung

    def mit_einschaetzung(antrag, *args, **kwargs):
        lage = echt(antrag, *args, **kwargs)
        lage['lauf'] = SimpleNamespace(zweck='einschaetzung', antwort='Die Fassung ist schlüssig.', erstellt_am=timezone.now(), modell='attrappe')
        return lage

    monkeypatch.setattr(verfahren.views, '_einschaetzung', mit_einschaetzung)
    assert 'Die Fassung ist schlüssig.' in client.get(reverse('gremien:fenster', args=[antrag.pk])).content.decode()


# --- GP-167: „Mein Gremium“ nennt alle Anträge einer Rolle ------------------------------------


def test_mein_gremium_nennt_alle_gelosten_antraege(client, ordnung):  # noqa: F811
    """GP-167: Wer in Gruppe 1 für zwei Anträge gelost war, las auf der Auswahlseite nur den ersten."""
    from django.urls import reverse

    from gremien.models import Gremium
    from gremien.test_werkstatt import rolle_geben
    from verfahren.models import antrag_einbringen

    rat = mitglied_anlegen('doppelrat')
    stellerin = mitglied_anlegen('stellerin')
    erster = antrag_einbringen(stellerin, titel='Radwege an der Hauptstraße', wortlaut='A.', begruendung='B.', ordnung=ordnung)
    zweiter = antrag_einbringen(stellerin, titel='Trinkbrunnen am Marktplatz', wortlaut='A.', begruendung='B.', ordnung=ordnung)
    rolle_geben(rat, Gremium.EXPERTENRAT_1, antrag=erster)
    rolle_geben(rat, Gremium.EXPERTENRAT_1, antrag=zweiter)
    rolle_geben(rat, Gremium.KOORDINATIONSRAT)
    client.force_login(rat)
    seite = client.get(reverse('gremien:mein')).content.decode()
    assert 'Radwege an der Hauptstraße' in seite and 'Trinkbrunnen am Marktplatz' in seite
    assert seite.count('class="bereich"') == 2  # je Gremium eine Kachel, nicht je Rolle


# --- GP-166: Keine Formulare, die nur abgewiesen werden ---------------------------------------


def test_wer_fuer_einen_anderen_antrag_gelost_ist_sieht_kein_stimmformular(client, ordnung):  # noqa: F811
    """GP-166: `darf_stimmen` galt bereichsweit — die für Antrag A Geloste sah am Einreichungsbeschluss zu
    Antrag B ein Stimmformular, das beim Absenden nur eine Fehlermeldung auslöste."""
    from django.urls import reverse

    from gremien.models import Anlass, GremienBeschluss, Gremium, Rolle
    from gremien.test_werkstatt import fenster_oeffnen, rolle_geben, werkstatt_lage
    from verfahren.models import antrag_einbringen

    antrag_b, _unterstuetzer, er = werkstatt_lage(ordnung)
    for rat in er:
        Rolle.objects.filter(mitglied=rat).update(antrag=antrag_b)
    fenster_oeffnen(client, antrag_b, er[0])
    client.post(reverse('gremien:fenster_aktion', args=[antrag_b.pk]), {'aktion': 'einreichung'})
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.EINREICHUNG, antrag=antrag_b)
    antrag_a = antrag_einbringen(mitglied_anlegen('andere'), titel='Antrag A', wortlaut='A.', begruendung='B.', ordnung=ordnung)
    fremde = mitglied_anlegen('fremde')
    rolle_geben(fremde, Gremium.EXPERTENRAT_1, antrag=antrag_a)
    stimmformular = reverse('gremien:beschluss_stimme', args=[beschluss.pk])
    client.force_login(fremde)
    seite = client.get(reverse('gremien:expertenrat')).content.decode()
    assert beschluss.nummer in seite and stimmformular not in seite
    client.force_login(er[1])
    assert stimmformular in client.get(reverse('gremien:expertenrat')).content.decode()  # die Zuständige stimmt weiter ab


def test_die_verwaltung_sieht_im_integritaetsbereich_den_hinweis_statt_des_formulars(client, ordnung):  # noqa: F811
    from django.urls import reverse

    from gremien.test_integritaet import rat

    leute = rat()
    admin = mitglied_anlegen('aufsicht')
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    seite = client.get(reverse('gremien:integritaet')).content.decode()
    assert reverse('gremien:integritaet_beschluss') not in seite
    assert 'Sie sehen diesen Bereich als Aufsicht' in seite
    client.force_login(leute[0])
    seite = client.get(reverse('gremien:integritaet')).content.decode()
    assert reverse('gremien:integritaet_beschluss') in seite and 'Sie sehen diesen Bereich als Aufsicht' not in seite
