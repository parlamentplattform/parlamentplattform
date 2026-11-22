"""Gesamtprüfung 18.11.2026, zweite Behebungsrunde — Nachweis, Anzeige und Schutz vor stillem
Überschreiben in den Räten. An Mehrheiten, Fristen, Besetzung und Wirkung der Beschlüsse ändert
sich nichts; die Tests halten fest, was die Kette und die öffentlichen Seiten davon berichten."""

import pytest

from gremien.models import Gremium, Rolle
from gremien.test_pruefung import korat_beschliessen, korat_lage, pruef_lage
from gremien.test_werkstatt import ordnung  # noqa: F401
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db

#: Schlüssel, unter denen ein Ereignis eine Person nennen könnte (vgl. `verfahren.audit_oeffentlich`).
PERSONENSCHLUESSEL = ('mitglied', 'durch', 'konten', 'angelegt_von', 'name', 'grund')


def ereignisse(typ, **felder):
    return [
        e.ereignis
        for e in AuditEintrag.objects.order_by('lfd')
        if e.ereignis.get('typ') == typ and all(e.ereignis.get(k) == v for k, v in felder.items())
    ]


# --- GP-037 · Gremienhandlungen ohne Audit-Eintrag -------------------------------------------


def test_der_pruefbeschluss_steht_als_angelegt_in_der_kette(client, ordnung):  # noqa: F811
    """GP-037: Der Prüfbeschluss der Gruppe 2 entstand ohne Eintrag — als einziger Beschluss der Räte.
    Er trägt dieselbe Art wie alle anderen (`gremienbeschluss_angelegt`) und nennt niemanden."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    eintraege = ereignisse('gremienbeschluss_angelegt', beschluss=beschluss.pk)
    assert len(eintraege) == 1
    eintrag = eintraege[0]
    assert eintrag['gremium'] == Gremium.EXPERTENRAT_2.value and eintrag['anlass'] == 'pruefung'
    assert eintrag['antrag'] == antrag.pk and eintrag['nummer'] == beschluss.nummer
    assert not set(eintrag) & set(PERSONENSCHLUESSEL)
    # Ein zweiter Lauf legt weder einen zweiten Beschluss noch einen zweiten Eintrag an.
    entwurf.fortschreiben(antrag)
    assert len(ereignisse('gremienbeschluss_angelegt', anlass='pruefung')) == 1


def test_der_austausch_beendet_jede_rolle_mit_eintrag(client, ordnung):  # noqa: F811
    """GP-037: Gibt der Koordinationsrat dem Austausch statt, enden die Rollen der Gruppe 1 für diesen
    Antrag. Je Rolle steht das in der Kette — mit der Beschlussnummer, ohne Personenwert."""
    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    beschluss = korat_beschliessen(client, korat, entwurf.pruefungen.get(), 'dafuer', 'Die Zweifel wiegen schwer.')
    beschluss.refresh_from_db()
    beendet = list(Rolle.objects.filter(mitglied__in=er, gremium=Gremium.EXPERTENRAT_1))
    assert beendet and all(not r.aktiv for r in beendet)
    eintraege = ereignisse('rolle_beendet', beschluss=beschluss.pk)
    assert sorted(e['rolle'] for e in eintraege) == sorted(r.pk for r in beendet)
    for eintrag in eintraege:
        assert eintrag['anlass'] == 'austausch' and eintrag['nummer'] == beschluss.nummer
        assert eintrag['antrag'] == antrag.pk and eintrag['gremium'] == Gremium.EXPERTENRAT_1.value
        assert not set(eintrag) & set(PERSONENSCHLUESSEL)


# --- GP-032 · „validiert“ ohne Prüfung ---------------------------------------------------------


def _abschnitt_pruefungen(client, antrag):
    """Der Abschnitt „Prüfungen der Gruppe 2“ der Antragsseite, wie ihn ein Gast liest."""
    from django.urls import reverse

    client.logout()
    inhalt = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert 'Prüfungen der Gruppe 2' in inhalt
    return inhalt.split('Prüfungen der Gruppe 2')[1].split('<h2')[0]


def _ohne_verneinung(text):
    for verneint in ('nicht validiert', 'ohne dass Gruppe 2 ihn validiert hat'):
        text = text.replace(verneint, '')
    return text


def test_schweigen_der_gruppe_2_steht_nicht_als_validiert_da(client, ordnung):  # noqa: F811
    """GP-032, Fahrtenbuch D-I3: „Validiert“ wäre eine Unbedenklichkeitsbescheinigung, die niemand
    ausgestellt hat. Läuft die Prüffrist ohne Stimme ab, geht der Vorschlag weiter wie bisher — aber
    Urteil, Antragsseite und Kette sagen „ohne Ergebnis“, nicht „validiert“."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import BeschlussStatus, EntwurfsStatus, Pruefung

    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=2)
    beschluss.frist = timezone.now() - timedelta(minutes=1)
    beschluss.save(update_fields=['frist'])
    entwurf.fortschreiben(antrag)
    entwurf.refresh_from_db()
    beschluss.refresh_from_db()
    assert beschluss.status == BeschlussStatus.OHNE_ERGEBNIS
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER  # die Wirkung bleibt: Untätigkeit hemmt nie
    urteil = entwurf.pruefungen.get()
    assert urteil.ergebnis == Pruefung.Ergebnis.OHNE_ERGEBNIS
    geprueft = ereignisse('vorschlag_geprueft', beschluss=beschluss.pk)
    assert len(geprueft) == 1 and geprueft[0]['ergebnis'] == 'ergebnislos' and geprueft[0]['ohne_ergebnis'] is True
    abschnitt = _abschnitt_pruefungen(client, antrag)
    assert 'nicht validiert' in abschnitt
    assert 'validiert' not in _ohne_verneinung(abschnitt)


def test_ein_gleichstand_der_gruppe_2_steht_nicht_als_validiert_da(client, ordnung):  # noqa: F811
    """GP-032: Auch der Gleichstand ist kein Urteil — und eine Stimme „validieren“ darin bleibt als
    Stimme lesbar, ohne dass das Ergebnis so hieße."""
    from gremien.models import Pruefung
    from gremien.test_pruefung import stimme

    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung, zweitpruefer=2)
    stimme(client, beschluss, gruppe2[0], 'validiert', 'Unbedenklich.')
    stimme(client, beschluss, gruppe2[1], 'zurueck', 'Die Vergabekriterien fehlen.')
    assert entwurf.pruefungen.get().ergebnis == Pruefung.Ergebnis.OHNE_ERGEBNIS
    assert not ereignisse('vorschlag_geprueft', ergebnis='validiert')
    abschnitt = _abschnitt_pruefungen(client, antrag)
    assert '<strong>ohne Ergebnis — nicht validiert</strong>' in abschnitt


def test_ohne_gruppe_2_steht_der_vorschlag_als_nicht_geprueft_da(client, ordnung):  # noqa: F811
    """GP-032: War in Gruppe 2 binnen der Prüffrist niemand berufen, hat niemand geprüft — und so
    heißt das Urteil auch."""
    from datetime import timedelta

    from gremien.models import Entwurf, EntwurfsStatus, Pruefung
    from gremien.test_werkstatt import einreichen, werkstatt_lage

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    tage = antrag.policy().pruefung_tage
    Entwurf.objects.filter(pk=entwurf.pk).update(eingereicht_am=entwurf.eingereicht_am - timedelta(days=tage, hours=1))
    entwurf.refresh_from_db()
    entwurf.fortschreiben(antrag)
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.UNTERSTUETZER
    assert entwurf.pruefungen.get().ergebnis == Pruefung.Ergebnis.UNGEPRUEFT
    abschnitt = _abschnitt_pruefungen(client, antrag)
    assert '<strong>nicht geprüft — Gruppe 2 unbesetzt</strong>' in abschnitt
    assert 'validiert' not in _ohne_verneinung(abschnitt)


def test_ein_wirkliches_validieren_heisst_weiter_validiert(client, ordnung):  # noqa: F811
    """Gegenprobe zu GP-032: Hat die Gruppe validiert, steht das so da — im Urteil und in der Kette."""
    from gremien.models import Pruefung
    from gremien.test_pruefung import stimme

    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    stimme(client, beschluss, gruppe2[0], 'validiert', 'Kein Beschaffungsrisiko erkennbar.')
    assert entwurf.pruefungen.get().ergebnis == Pruefung.Ergebnis.VALIDIERT
    assert ereignisse('vorschlag_geprueft', beschluss=beschluss.pk)[0]['ergebnis'] == 'validiert'
    assert '<strong>validiert</strong>' in _abschnitt_pruefungen(client, antrag)


def test_altbestand_urteile_ohne_pruefung_werden_berichtigt(client, ordnung):  # noqa: F811
    """GP-032, Altbestand: Vor dieser Fassung stand in beiden Fällen „validiert“ im Urteil. Die
    Datenmigration berichtigt genau diese Zeilen — aus dem Beschluss ohne Ergebnis und aus dem Vermerk
    der unbesetzten Gruppe —, lässt echte Urteile stehen und ändert beim zweiten Lauf nichts mehr."""
    import importlib

    from django.apps import apps
    from django.utils import timezone

    from gremien.models import BeschlussStatus, GremienBeschluss, Pruefung

    migration = importlib.import_module('gremien.migrations.0022_pruefung_ergebnis_ohne_urteil')
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    GremienBeschluss.objects.filter(pk=beschluss.pk).update(
        status=BeschlussStatus.OHNE_ERGEBNIS, ergebnis='', entschieden_am=timezone.now()
    )
    ohne = Pruefung.objects.create(
        entwurf=entwurf, runde=1, ergebnis='validiert', beschluss=beschluss,
        begruendung='Die Prüfung der Gruppe 2 blieb ohne Ergebnis: 0 von 1 nötigen Stimmen bis zum Fristende.',
    )
    unbesetzt = Pruefung.objects.create(
        entwurf=entwurf, runde=1, ergebnis='validiert',
        begruendung='Die Prüfung blieb aus: In Gruppe 2 war binnen der Prüffrist von 7 Tagen keine Rolle besetzt.',
    )
    einzeln = Pruefung.objects.create(  # vor 0.41 entschied eine Person: ein echtes Urteil
        entwurf=entwurf, runde=1, ergebnis='validiert', begruendung='Unbedenklich.', durch=gruppe2[0],
    )
    echter = GremienBeschluss.objects.create(
        gremium=Gremium.EXPERTENRAT_2, gegenstand='Prüfung', optionen=beschluss.optionen,
        status=BeschlussStatus.ENTSCHIEDEN, ergebnis='validiert', antrag=antrag, entwurf=entwurf,
        angelegt_von=gruppe2[0],
    )
    echt = Pruefung.objects.create(
        entwurf=entwurf, runde=1, ergebnis='validiert', begruendung='validieren — Sauber.', beschluss=echter,
    )
    for _lauf in range(2):
        migration.urteile_ohne_pruefung_berichtigen(apps, None)
        assert {p.pk: p.ergebnis for p in Pruefung.objects.all()} == {
            ohne.pk: 'ergebnislos', unbesetzt.pk: 'ungeprueft', einzeln.pk: 'validiert', echt.pk: 'validiert',
        }


# --- GP-035 · Entschiedene Beschlüsse zeigen den heutigen Nenner -------------------------------


def _rat(anzahl, gremium=Gremium.KOORDINATIONSRAT, praefix='nenner'):
    from gremien.test_werkstatt import mitglied_anlegen, rolle_geben

    leute = [mitglied_anlegen(f'{praefix}{i}') for i in range(anzahl)]
    return leute, [rolle_geben(m, gremium) for m in leute]


def _zur_frist_geschlossen(leute, stimmen, **felder):
    """Ein Beschluss des Koordinationsrats, den die Frist schließt: `stimmen` der Leute stimmen „dafür“."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import GremienBeschluss, GremienStimme
    from gremien.test_beschluesse import beschluss_anlegen

    jetzt = timezone.now()
    beschluss = beschluss_anlegen(angelegt_von=leute[0], frist=jetzt - timedelta(hours=1), **felder)
    for m in leute[:stimmen]:
        GremienStimme.objects.create(beschluss=beschluss, mitglied=m, option='dafuer', begruendung='Weil.')
    GremienBeschluss.faellige_abschliessen(jetzt)
    beschluss.refresh_from_db()
    return beschluss


def _protokoll_eintrag(client, beschluss):
    import json

    from django.urls import reverse
    from django.utils import timezone

    jahr = timezone.localtime(beschluss.angelegt_am).year
    daten = json.loads(client.get(reverse('gremien:protokoll', args=[beschluss.gremium, jahr])).content)
    return next(e for e in daten['beschluesse'] if e['nummer'] == beschluss.nummer)


def _rollen_beenden(rollen):
    for rolle in rollen:
        rolle.beendet_grund = 'Rücktritt'
        rolle.save(update_fields=['beendet_grund'])


def test_spaetere_rollenaenderungen_aendern_die_zahlen_eines_beschlusses_nicht(client):
    """GP-035: Einzelseite, Liste, Ratsbereich und Protokoll rechneten bei geschlossenen Beschlüssen
    mit der heutigen Besetzung („3 von 1 nötigen Stimmen“). Die Zahlen des Beschlusszeitpunkts stehen
    jetzt am Beschluss und stimmen mit dem Audit-Eintrag überein — was auch später im Rat geschieht."""
    from django.urls import reverse

    from gremien.models import BeschlussStatus
    from gremien.test_werkstatt import mitglied_anlegen, rolle_geben

    leute, rollen = _rat(5)
    beschluss = _zur_frist_geschlossen(leute, 3)
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN
    audit = ereignisse('gremienbeschluss_ausgewertet', beschluss=beschluss.pk)[0]
    assert (audit['abgegeben'], audit['noetig'], audit['aktive']) == (3, 3, 5)
    assert audit['zaehlung'] == {'dafuer': 3, 'dagegen': 0}

    def gelesen():
        client.logout()
        einzel = client.get(reverse('gremien:beschluss', args=[beschluss.nummer])).content.decode()
        liste = client.get(reverse('gremien:beschluesse')).content.decode()
        client.force_login(leute[0])
        bereich = client.get(reverse('gremien:koordination')).content.decode()
        client.logout()
        eintrag = _protokoll_eintrag(client, beschluss)
        return (
            '3 von 3 nötigen Stimmen bei 5 aktiven Rollen' in einzel,
            '3 von 3 nötigen Stimmen' in liste,
            '3 von 3 nötigen Stimmen' in bereich,
            (eintrag['abgegeben'], eintrag['noetig']),
        )

    erwartet = (True, True, True, (audit['abgegeben'], audit['noetig']))
    assert gelesen() == erwartet
    _rollen_beenden(rollen[1:])  # der Rat schrumpft auf eine Person
    assert gelesen() == erwartet
    for i in range(8):  # und wächst auf neun
        rolle_geben(mitglied_anlegen(f'zuwachs{i}'), Gremium.KOORDINATIONSRAT)
    assert gelesen() == erwartet


def test_ein_beschluss_ohne_ergebnis_behaelt_seinen_nenner(client):
    """GP-035, Gegenrichtung: Ein an der Beschlussfähigkeit gescheiterter Beschluss („1 von 3“) sieht
    nach einem Schrumpfen des Rats nicht aus, als wäre er beschlussfähig gewesen („1 von 1“)."""
    from django.urls import reverse

    from gremien.models import BeschlussStatus

    leute, rollen = _rat(5)
    beschluss = _zur_frist_geschlossen(leute, 1)
    assert beschluss.status == BeschlussStatus.OHNE_ERGEBNIS
    _rollen_beenden(rollen[1:])
    einzel = client.get(reverse('gremien:beschluss', args=[beschluss.nummer])).content.decode()
    assert '1 von 3 nötigen Stimmen bei 5 aktiven Rollen' in einzel
    eintrag = _protokoll_eintrag(client, beschluss)
    assert (eintrag['abgegeben'], eintrag['noetig']) == (1, 3)


def test_altbestand_die_zahlen_kommen_aus_dem_audit_oder_gar_nicht(client):
    """GP-035, Altbestand: Ein vor dieser Fassung geschlossener Beschluss bekommt die Zahlen seines
    Audit-Eintrags nachgetragen. Wo die Kette keine trägt, wird keine erfunden: Die Seite sagt, dass
    keine Auszählung festgehalten ist, und das Protokoll nennt keine Zahl."""
    import importlib

    from django.apps import apps
    from django.urls import reverse
    from django.utils import timezone

    from gremien.models import BeschlussStatus, GremienBeschluss
    from gremien.test_beschluesse import beschluss_anlegen

    migration = importlib.import_module('gremien.migrations.0023_beschluss_auszaehlung_festgehalten')
    leute, rollen = _rat(5)
    jetzt = timezone.now()
    # Wie vor dieser Fassung: geschlossen, nichts am Beschluss, der Eintrag der Kette ohne „aktive“.
    mit_audit = beschluss_anlegen(
        angelegt_von=leute[0], gegenstand='Mit Eintrag in der Kette', status=BeschlussStatus.ENTSCHIEDEN,
        ergebnis='dafuer', regel_version=1, entschieden_am=jetzt,
    )
    AuditEintrag.anhaengen(
        {
            'typ': 'gremienbeschluss_ausgewertet', 'gremium': mit_audit.gremium, 'beschluss': mit_audit.pk,
            'status': 'entschieden', 'ergebnis': 'dafuer', 'zaehlung': {'dafuer': 3, 'dagegen': 0},
            'abgegeben': 3, 'noetig': 3, 'regel_version': 1,
        }
    )
    juenger = _zur_frist_geschlossen(leute, 2, gegenstand='Eintrag mit aktiven Rollen')
    GremienBeschluss.objects.filter(pk=juenger.pk).update(festgehalten=None)
    ohne_audit = beschluss_anlegen(
        angelegt_von=leute[0], gegenstand='Älter als die Kette', status=BeschlussStatus.ENTSCHIEDEN,
        ergebnis='dafuer', entschieden_am=jetzt,
    )
    offener = beschluss_anlegen(angelegt_von=leute[0], gegenstand='Noch offen')
    _rollen_beenden(rollen[1:])
    for _lauf in range(2):  # beliebig oft wiederholbar
        migration.auszaehlung_aus_dem_audit_nachtragen(apps, None)
        mit_audit.refresh_from_db()
        ohne_audit.refresh_from_db()
        offener.refresh_from_db()
        assert mit_audit.festgehalten == {
            'abgegeben': 3, 'noetig': 3, 'zaehlung': {'dafuer': 3, 'dagegen': 0}, 'quelle': 'audit',
        }
        assert ohne_audit.festgehalten is None and offener.festgehalten is None
        juenger.refresh_from_db()
        assert juenger.festgehalten == {
            'abgegeben': 2, 'noetig': 3, 'aktive': 5, 'zaehlung': {'dafuer': 2, 'dagegen': 0}, 'quelle': 'audit',
        }
    einzel = client.get(reverse('gremien:beschluss', args=[mit_audit.nummer])).content.decode()
    assert '3 von 3 nötigen Stimmen' in einzel and 'aktiven Rollen' not in einzel
    einzel = client.get(reverse('gremien:beschluss', args=[ohne_audit.nummer])).content.decode()
    assert 'Keine Auszählung zum Beschlusszeitpunkt festgehalten' in einzel
    assert 'nötigen Stimmen' not in einzel
    liste = client.get(reverse('gremien:beschluesse')).content.decode()
    zeile = liste.split('Älter als die Kette')[1].split('class="zeile"')[0]
    assert 'Keine Auszählung zum Beschlusszeitpunkt festgehalten' in zeile and 'nötigen Stimmen' not in zeile
    eintrag = _protokoll_eintrag(client, ohne_audit)
    assert eintrag['abgegeben'] is None and eintrag['noetig'] is None
    # Der offene Beschluss rechnet weiter mit der Besetzung von heute.
    einzel = client.get(reverse('gremien:beschluss', args=[offener.nummer])).content.decode()
    assert '0 von 1 nötigen Stimmen bei 1 aktiven Rollen' in einzel


# --- GP-034, GP-025 · Vermerke am Beschluss: nichts wird still überschrieben -------------------


def _vermerk_schreiben(client, wer, beschluss, text, **felder):
    from django.urls import reverse

    client.force_login(wer)
    antwort = client.post(
        reverse('gremien:beschluss_umsetzung', args=[beschluss.pk]), {'umsetzungsvermerk': text, **felder}
    )
    client.logout()
    return antwort


def _einzelseite(client, beschluss):
    from django.urls import reverse

    client.logout()
    return client.get(reverse('gremien:beschluss', args=[beschluss.nummer])).content.decode()


def test_ein_vermerk_des_rates_laesst_den_vermerk_der_plattform_stehen(client, ordnung):  # noqa: F811
    """GP-034: Das Formular „Umsetzungsvermerk“ ersetzte den Vermerk der Plattform, warum ein Beschluss
    ohne Wirkung blieb — öffentlich stand dann „entschieden: dafür, erledigt wie beschlossen“. Beide
    Texte bleiben jetzt stehen, und die Kette hält fest, dass der Beschluss ohne Wirkung blieb."""
    from django.urls import reverse

    from gremien.models import Anlass, BeschlussStatus
    from gremien.test_integritaet import antrag_anlegen, beschluss_fassen, rat

    leute = rat(2)  # zwei sind kein Integritätsrat (§ 6 Abs 3 lit a)
    antrag = antrag_anlegen(ordnung)
    beschluss_fassen(client, leute, antrag, Anlass.HERVORHEBUNG)
    beschluss = antrag.gremienbeschluesse.get()
    plattform = beschluss.umsetzungsvermerk
    assert beschluss.status == BeschlussStatus.ENTSCHIEDEN and plattform.startswith('Ohne Wirkung')
    _vermerk_schreiben(client, leute[0], beschluss, 'Erledigt wie beschlossen.')
    beschluss.refresh_from_db()
    assert beschluss.umsetzungsvermerk == plattform
    einzel = _einzelseite(client, beschluss)
    assert 'Ohne Wirkung: Der Integritätsrat war nicht satzungsgemäß besetzt' in einzel
    assert 'Erledigt wie beschlossen.' in einzel
    liste = client.get(reverse('gremien:beschluesse')).content.decode()
    assert 'Ohne Wirkung: Der Integritätsrat war nicht satzungsgemäß besetzt' in liste
    assert 'Erledigt wie beschlossen.' in liste
    vermerkt = ereignisse('gremienbeschluss_vermerkt', beschluss=beschluss.pk)
    assert len(vermerkt) == 1 and vermerkt[0]['ohne_wirkung'] is True
    assert vermerkt[0]['vermerk'] == plattform and vermerkt[0]['nummer'] == beschluss.nummer
    assert not set(vermerkt[0]) & set(PERSONENSCHLUESSEL)


def test_ein_vermerk_der_plattform_mit_wirkung_ist_nicht_ohne_wirkung(client, ordnung):  # noqa: F811
    """Gegenprobe zu GP-034: Auch der gewöhnliche Vermerk der Plattform steht in der Kette — ohne
    das Kennzeichen „ohne Wirkung“."""
    from gremien.models import Anlass, GremienBeschluss
    from gremien.test_werkstatt import einreichen, werkstatt_lage

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    beschluss = GremienBeschluss.objects.get(anlass=Anlass.EINREICHUNG, antrag=antrag)
    assert beschluss.umsetzungsvermerk.startswith('Eingereicht')
    vermerkt = ereignisse('gremienbeschluss_vermerkt', beschluss=beschluss.pk)
    assert len(vermerkt) == 1 and vermerkt[0]['ohne_wirkung'] is False


def _entschiedener_beschluss(leute, **felder):
    from django.utils import timezone

    from gremien.models import BeschlussStatus
    from gremien.test_beschluesse import beschluss_anlegen

    return beschluss_anlegen(
        angelegt_von=leute[0], gegenstand='Monatliche Sitzung', status=BeschlussStatus.ENTSCHIEDEN,
        ergebnis='dafuer', entschieden_am=timezone.now(), **felder,
    )


def test_zwei_vermerke_sind_zwei_oeffentliche_eintraege(client):
    """GP-025: Der zweite Umsetzungsvermerk ersetzte den ersten spurlos, samt Zuweisung und Frist. Jetzt
    wird angefügt: Beide stehen öffentlich mit Zeitpunkt, die Frist und die Zuweisung des ersten
    bleiben lesbar, und die Kette zählt die Vermerke je Beschluss durch — ohne jemanden zu nennen."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import Umsetzungsvermerk

    leute, rollen = _rat(3)
    beschluss = _entschiedener_beschluss(leute)
    heute = timezone.localdate()
    frist = heute + timedelta(days=14)
    _vermerk_schreiben(
        client, leute[0], beschluss, 'Einladung geht per Mail.',
        umsetzung_durch=leute[2].pk, umsetzung_frist=frist.isoformat(),
    )
    _vermerk_schreiben(client, leute[1], beschluss, 'Raum ist gebucht.')
    vermerke = list(Umsetzungsvermerk.objects.filter(beschluss=beschluss).order_by('nummer'))
    assert [(v.nummer, v.text) for v in vermerke] == [(1, 'Einladung geht per Mail.'), (2, 'Raum ist gebucht.')]
    assert vermerke[0].rolle == rollen[2] and vermerke[0].frist == frist
    assert vermerke[1].rolle is None and vermerke[1].frist is None
    beschluss.refresh_from_db()
    assert beschluss.umsetzungsvermerk == ''  # das Feld gehört den Vermerken der Plattform
    assert beschluss.umsetzung_durch is None and beschluss.umsetzung_frist is None  # es gilt der jüngste
    einzel = _einzelseite(client, beschluss)
    assert 'Einladung geht per Mail.' in einzel and 'Raum ist gebucht.' in einzel
    assert einzel.index('Raum ist gebucht.') < einzel.index('Einladung geht per Mail.')  # jüngster zuerst
    assert leute[2].anzeigename in einzel and frist.strftime('%d.%m.%Y') in einzel
    for vermerk in vermerke:
        assert timezone.localtime(vermerk.erstellt_am).strftime('%d.%m.%Y %H:%M') in einzel
    eintraege = ereignisse('umsetzungsvermerk', beschluss=beschluss.pk)
    assert [(e['vermerk_nr'], e['zugewiesen'], e['frist']) for e in eintraege] == [
        (1, True, frist.isoformat()), (2, False, None),
    ]
    assert not any(set(e) & set(PERSONENSCHLUESSEL) for e in eintraege)
    protokoll = _protokoll_eintrag(client, beschluss)
    assert [v['text'] for v in protokoll['umsetzungsvermerke']] == ['Einladung geht per Mail.', 'Raum ist gebucht.']
    assert protokoll['umsetzungsvermerke'][0]['umsetzung_frist'] == frist.isoformat()
    assert protokoll['umsetzungsvermerke'][0]['umsetzung_durch'] == leute[2].anzeigename


def test_eine_verstrichene_umsetzungsfrist_steht_als_ueberfaellig_da(client):
    """GP-025: Eine versäumte Umsetzungsfrist hatte keine Folge — sie stand nirgends. Jetzt nennen
    Beschlussseite und Beschlussliste den ersten Tag nach der Frist, für Gäste wie für den Rat."""
    from datetime import timedelta

    from django.urls import reverse
    from django.utils import timezone

    leute, rollen = _rat(3)
    beschluss = _entschiedener_beschluss(leute)
    heute = timezone.localdate()
    frist = heute - timedelta(days=40)
    marke = f'überfällig seit {(frist + timedelta(days=1)).strftime("%d.%m.%Y")}'
    assert beschluss.umsetzung_ueberfaellig_seit(heute) is None  # ohne Frist ist nichts überfällig
    _vermerk_schreiben(
        client, leute[0], beschluss, 'Einladung geht per Mail.',
        umsetzung_durch=leute[2].pk, umsetzung_frist=frist.isoformat(),
    )
    beschluss.refresh_from_db()
    assert beschluss.umsetzung_ueberfaellig_seit(frist) is None  # am Tag der Frist noch nicht
    assert beschluss.umsetzung_ueberfaellig_seit(frist + timedelta(days=1)) == frist + timedelta(days=1)
    assert marke in _einzelseite(client, beschluss)
    assert marke in client.get(reverse('gremien:beschluesse')).content.decode()
    client.force_login(leute[2])  # die zugewiesene Person in ihrem Ratsbereich
    assert marke in client.get(reverse('gremien:koordination')).content.decode()
    # Ein späterer Vermerk ohne Frist beendet die Überfälligkeit — sichtbar, nicht spurlos.
    _vermerk_schreiben(client, leute[2], beschluss, 'Erledigt am Montag.')
    einzel = _einzelseite(client, beschluss)
    assert marke not in einzel and frist.strftime('%d.%m.%Y') in einzel and 'Erledigt am Montag.' in einzel


def test_altbestand_der_vermerk_des_rates_wandert_in_die_liste(client):
    """GP-025, Altbestand: Vor dieser Fassung stand der Vermerk des Rates im selben Feld wie der der
    Plattform. Wo die Kette einen Umsetzungsvermerk verzeichnet, ist der Text der des Rates und wird
    zum Eintrag der Liste — mit Zuweisung, Frist und dem Zeitpunkt aus der Kette. Ein Vermerk der
    Plattform bleibt, wo er ist. Ein weiterer Vermerk reiht sich danach ein."""
    import importlib
    from datetime import timedelta

    from django.apps import apps
    from django.utils import timezone

    from gremien.models import Umsetzungsvermerk

    migration = importlib.import_module('gremien.migrations.0024_umsetzungsvermerke_anfuegen')
    leute, rollen = _rat(3)
    frist = timezone.localdate() + timedelta(days=14)
    vom_rat = _entschiedener_beschluss(
        leute, umsetzungsvermerk='Einladung geht per Mail.', umsetzung_durch=leute[2], umsetzung_frist=frist,
    )
    for _n in range(2):  # zweimal geschrieben: Der erste Wortlaut ist nicht erhalten
        letzter = AuditEintrag.anhaengen(
            {'typ': 'umsetzungsvermerk', 'beschluss': vom_rat.pk, 'nummer': vom_rat.nummer,
             'zugewiesen': True, 'frist': frist.isoformat()}
        )
    von_der_plattform = _entschiedener_beschluss(leute, umsetzungsvermerk='Ohne Wirkung: Beispiel.')
    for _lauf in range(2):  # beliebig oft wiederholbar
        migration.vermerke_des_rates_uebertragen(apps, None)
        vom_rat.refresh_from_db()
        von_der_plattform.refresh_from_db()
        assert vom_rat.umsetzungsvermerk == '' and von_der_plattform.umsetzungsvermerk == 'Ohne Wirkung: Beispiel.'
        (uebertragen,) = Umsetzungsvermerk.objects.all()
        assert (uebertragen.beschluss, uebertragen.nummer, uebertragen.text) == (vom_rat, 2, 'Einladung geht per Mail.')
        assert uebertragen.rolle == rollen[2] and uebertragen.frist == frist and uebertragen.erstellt_am == letzter.zeit
    assert vom_rat.umsetzung_durch == leute[2] and vom_rat.umsetzung_frist == frist
    _vermerk_schreiben(client, leute[1], vom_rat, 'Raum ist gebucht.')
    assert list(Umsetzungsvermerk.objects.filter(beschluss=vom_rat).order_by('nummer').values_list('nummer', flat=True)) == [2, 3]
    einzel = _einzelseite(client, vom_rat)
    assert 'Einladung geht per Mail.' in einzel and 'Raum ist gebucht.' in einzel and frist.strftime('%d.%m.%Y') in einzel
    assert 'Ohne Wirkung: Beispiel.' in _einzelseite(client, von_der_plattform)


# --- GP-021 (Rest) · Testwerte außerhalb des Wertbereichs --------------------------------------


@pytest.mark.parametrize(
    ('schluessel', 'testwert', 'bereich'),
    [
        ('live-hoechstdauer-stunden', '500', 'von 1 bis 72'),  # eigener Bereich mit Obergrenze
        ('live-hoechstdauer-stunden', '0', 'von 1 bis 72'),
        ('adresswechsel-wartefrist-stunden', '0', 'ab 1'),  # eine Wartefrist 0 ist eine Kontoübernahme
        ('gremien-rollen-dauer-tage', '-1', 'ab 0'),  # ohne eigenen Bereich: keine negativen Werte
        ('gremien-rollen-dauer-tage', '007', 'ab 0'),  # nur die Schreibweise, die das Register auch annimmt
    ],
)
def test_ein_testwert_ausserhalb_des_wertbereichs_wird_abgewiesen(client, schluessel, testwert, bereich):
    """GP-021: Die Verwaltung weist seit 0.113.0 Werte außerhalb des Wertbereichs ab — der Koordinationsrat
    konnte dieselben Werte weiter als Test anordnen. Jetzt gilt dieselbe Prüfung mit derselben Meldung:
    Es entsteht weder ein Test noch ein Beschluss, das Register bleibt, wie es ist."""
    from gremien.models import Anlass, GremienBeschluss
    from gremien.test_gp_runde1 import _korat, _register, _test_anordnen
    from parameter.models import ParameterTest, wert_ausserhalb

    leute = _korat()
    parameter = _register(schluessel)
    vorher = parameter.wert
    assert wert_ausserhalb(parameter, testwert)  # die Regel des Registers, nicht eine zweite
    antwort = _test_anordnen(client, leute[0], parameter, testwert)
    inhalt = antwort.content.decode()
    assert antwort.status_code == 200 and f'nimmt nur ganze Zahlen {bereich}' in inhalt
    assert not ParameterTest.objects.exists()
    assert not GremienBeschluss.objects.filter(anlass=Anlass.PARAMETERTEST).exists()
    assert not ereignisse('gremienbeschluss_angelegt')
    parameter.refresh_from_db()
    assert parameter.wert == vorher and parameter.status != 'im_test'


def test_ein_testwert_im_wertbereich_wird_weiter_angeordnet(client):
    """Gegenprobe zu GP-021: Die Grenzen selbst sind zulässig."""
    from gremien.test_gp_runde1 import _korat, _register, _test_anordnen
    from parameter.models import ParameterTest

    leute = _korat()
    parameter = _register('live-hoechstdauer-stunden')
    assert parameter.wert != '72'
    _test_anordnen(client, leute[0], parameter, '72')
    assert ParameterTest.objects.get().testwert == '72'


def test_altbestand_ein_geplanter_test_ausserhalb_des_bereichs_beginnt_nicht(client):
    """GP-021, Altbestand: Ein vor dieser Fassung angeordneter Test mit einem Wert außerhalb des
    Wertbereichs schriebe ihn mit dem Beschluss des Rates ins Register. Er beginnt nicht — der
    Beschluss steht, mit dem Vermerk, warum er ohne Wirkung blieb."""
    from gremien.test_gp_runde1 import _korat, _rat_stimmt, _register, _test_anordnen
    from parameter.models import Aenderung, ParameterTest, Status, TestStatus

    leute = _korat()
    parameter = _register('live-hoechstdauer-stunden')
    vorher = parameter.wert
    _test_anordnen(client, leute[0], parameter, '48')
    test = ParameterTest.objects.get()
    ParameterTest.objects.filter(pk=test.pk).update(testwert='500')  # wie vor dieser Fassung angeordnet
    beschluss = _rat_stimmt(client, leute, test.beschluss)
    test.refresh_from_db()
    parameter.refresh_from_db()
    assert beschluss.ergebnis == 'dafuer'
    assert test.status == TestStatus.VERWORFEN and 'Wertbereich' in test.auswertung
    assert parameter.wert == vorher and parameter.status == Status.GUELTIG
    assert not Aenderung.objects.filter(parameter=parameter).exists()
    assert 'Nicht angeordnet' in beschluss.umsetzungsvermerk and 'Wertbereich' in beschluss.umsetzungsvermerk
    assert not ereignisse('parametertest_begonnen')


# --- GP-003 (Rest) · Die Wartezeit im Werkstattfenster ------------------------------------------


def _fensterkarte(client, antrag, rat):
    """Die Karte „Stand der Schleife“ im Entwurfsfenster, wie sie ein Mitglied der Gruppe 1 liest."""
    from django.urls import reverse

    client.force_login(rat)
    inhalt = client.get(reverse('gremien:fenster', args=[antrag.pk])).content.decode()
    return inhalt.split('Stand der Schleife', 1)[1].split('</div>', 1)[0]


def test_in_der_wartezeit_nennt_das_werkstattfenster_den_beginn_der_endabstimmung(client, ordnung):  # noqa: F811
    """GP-003, Rest: Zwischen verstrichener Unterstützerfrist und Beratungsende stand im Werkstattfenster
    weiter „Die Unterstützer haben bis <vergangenes Datum> Zeit“, und der Zwischenstand zählte weiter.
    Jetzt steht dort, dass der Vorschlag angenommen ist und wann die Endabstimmung beginnt — mit dem
    Stand, der zum Fristende festgestellt wurde (§ 5 Abs 13)."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.test_werkstatt import (
        _nur_die_unterstuetzerfrist_verstreicht,
        einreichen,
        reagieren,
        systembeitrag,
        werkstatt_lage,
    )
    from verfahren.models import Reaktion

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    reagieren(client, antrag, passt, unterstuetzer[0])
    vorher = _fensterkarte(client, antrag, er[0])
    assert 'Die Unterstützer haben bis' in vorher and 'ist angenommen' not in vorher
    frist = _nur_die_unterstuetzerfrist_verstreicht(entwurf)
    # Eine Ablehnung, die erst nach dem Fristende in der Datenbank steht, zählt nicht mehr mit.
    Reaktion.objects.create(kommentar=passt, mitglied=unterstuetzer[1], art='ablehnung', erstellt_am=frist + timedelta(minutes=30))
    karte = _fensterkarte(client, antrag, er[0])
    antrag.refresh_from_db()
    entwurf.refresh_from_db()
    assert antrag.phase == 'beratung' and entwurf.status == 'unterstuetzer'
    ende = antrag.phase_beginn + timedelta(days=antrag.policy().beratung_tage)
    assert 'Die Unterstützer haben bis' not in karte and 'danach wertet die Frist aus' not in karte
    assert 'ist angenommen' in karte
    assert f'{timezone.localtime(frist):%d.%m.%Y %H:%M}' in karte
    assert f'Ende der Beratung am {timezone.localtime(ende):%d.%m.%Y %H:%M}' in karte
    assert '1 👍 / 0 👎 (100 %)' in karte and '1 👍 / 1 👎' not in karte
    warte = entwurf.endabstimmung_wartet()
    assert (warte['ab'], warte['grund'], warte['frist']) == (ende, 'angenommen', frist)
    assert (warte['stand']['ja'], warte['stand']['nein'], warte['stand']['angenommen']) == (1, 0, True)


def test_in_der_wartezeit_nach_verstrichener_ueberarbeitung_nennt_das_werkstattfenster_das_beratungsende(client, ordnung):  # noqa: F811
    """GP-003, Rest, zweiter Weg: Nach verstrichener Überarbeitungsfrist stand im Werkstattfenster weiter
    „Überarbeitung bis <vergangenes Datum>“."""
    from datetime import timedelta

    from django.utils import timezone

    from gremien.models import Entwurf, EntwurfsStatus
    from gremien.test_werkstatt import einreichen, werkstatt_lage

    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    jetzt = timezone.now()
    Entwurf.objects.filter(pk=entwurf.pk).update(
        status=EntwurfsStatus.IN_ARBEIT, runde=2, review_frist=None, ueberarbeitung_frist=jetzt + timedelta(days=2)
    )
    assert 'Überarbeitung bis' in _fensterkarte(client, antrag, er[0])  # die Frist läuft noch
    frist = jetzt - timedelta(hours=2)
    Entwurf.objects.filter(pk=entwurf.pk).update(ueberarbeitung_frist=frist)
    karte = _fensterkarte(client, antrag, er[0])
    antrag.refresh_from_db()
    assert antrag.phase == 'beratung'
    ende = antrag.phase_beginn + timedelta(days=antrag.policy().beratung_tage)
    assert 'Überarbeitung bis' not in karte
    assert 'Überarbeitungsfrist ist am' in karte and f'{timezone.localtime(frist):%d.%m.%Y %H:%M}' in karte
    assert f'Ende der Beratung am {timezone.localtime(ende):%d.%m.%Y %H:%M}' in karte
    entwurf.refresh_from_db()
    warte = entwurf.endabstimmung_wartet()
    assert (warte['ab'], warte['grund'], warte['frist'], warte['stand']) == (ende, 'ueberarbeitung', frist, None)
