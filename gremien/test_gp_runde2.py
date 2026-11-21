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
