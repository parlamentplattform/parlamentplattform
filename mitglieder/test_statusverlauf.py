"""Statusverlauf (GP-094, § 4 Abs 4 lit a): Derselbe Stichtag ergibt denselben Nenner — gleich,
an welchem Tag gezählt wird; Zählung und Einzelprüfung lesen denselben Stand am Stichtag."""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Mitglied, Mitgliedsstatus, Statusverlauf, stimmberechtigte_zaehlen
from mitglieder.profil import austreten
from plattform_core import Gegenstand
from plattform_core.eligibility import monate_addieren
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


def zaehlen(stichtag, uebergang=True):
    return stimmberechtigte_zaehlen(Gegenstand.SACHFRAGE, stichtag, uebergang=uebergang)


def darf(mitglied, stichtag, uebergang=True):
    return mitglied.ist_stimmberechtigt(Gegenstand.SACHFRAGE, stichtag, uebergang=uebergang)


def pausieren(mitglied):
    mitglied.save(update_fields=mitglied.status_setzen(Mitgliedsstatus.PAUSIERT, 'Beitrag ausständig'))


def aktivieren(mitglied):
    mitglied.save(update_fields=mitglied.status_setzen(Mitgliedsstatus.AKTIV, ''))


@pytest.fixture
def lage():
    """Drei Stimmberechtigte; der Stichtag liegt drei Tage zurück (der Wächter stand)."""
    heute = timezone.localdate()
    return heute, heute - timedelta(days=3), [mitglied_anlegen(f'm{i}') for i in range(3)]


def test_pause_nach_dem_stichtag_senkt_den_nenner_nicht(lage):
    _heute, stichtag, leute = lage
    assert zaehlen(stichtag) == 3  # pünktlich gezählt
    pausieren(leute[2])
    assert zaehlen(stichtag) == 3  # verspätet gezählt: derselbe Stichtag, derselbe Nenner
    assert zaehlen(leute[2].status_seit) == 2  # ab dem Tag der Pause zählt das Mitglied nicht mehr


def test_ausschluss_und_austritt_nach_dem_stichtag_senken_den_nenner_nicht(client, lage):
    _heute, stichtag, leute = lage
    chefin = mitglied_anlegen('chefin')
    chefin.ist_admin = True
    chefin.save(update_fields=['ist_admin'])
    assert zaehlen(stichtag) == 4
    client.force_login(chefin)
    client.post(
        reverse('mitglieder:verwaltung_mitglied', args=[leute[1].pk]),
        {'aktion': 'ausschliessen', 'grund': 'Beschluss vom Tag'},
    )
    leute[1].refresh_from_db()
    assert leute[1].status == Mitgliedsstatus.AUSGESCHLOSSEN and not leute[1].is_active
    austreten(leute[2])
    assert zaehlen(stichtag) == 4
    assert zaehlen(leute[2].status_seit) == 2
    for konto in leute[1:]:
        assert not darf(konto, stichtag)  # Rechte ruhen oder sind erloschen — wie bisher


def test_einzelpruefung_folgt_der_zaehlung(lage):
    """Wer am Stichtag im Nenner stand, stimmt mit, sobald seine Rechte nicht mehr ruhen —
    bisher schloss ihn das neue Statusdatum aus, obwohl er gezählt war."""
    _heute, stichtag, leute = lage
    paul = leute[2]
    pausieren(paul)
    assert not darf(paul, stichtag)  # während der Pause ruhen die Rechte (F-51)
    aktivieren(paul)
    assert darf(paul, stichtag)
    assert zaehlen(stichtag) == 3


def test_wer_am_stichtag_pausiert_war_bleibt_draussen():
    heute = timezone.localdate()
    stichtag = heute - timedelta(days=3)
    paul = mitglied_anlegen('paul')
    paul.status, paul.status_seit = Mitgliedsstatus.PAUSIERT, stichtag - timedelta(days=5)
    paul.save(update_fields=['status', 'status_seit'])
    assert zaehlen(stichtag) == 0
    aktivieren(paul)
    assert zaehlen(stichtag) == 0 and not darf(paul, stichtag)
    assert zaehlen(paul.status_seit) == 1 and darf(paul, paul.status_seit)
    assert zaehlen(stichtag - timedelta(days=6)) == 1  # vor der Pause: aktiv, im Nenner


def test_pause_nach_dem_stichtag_verschiebt_die_anwartschaft_am_stichtag_nicht():
    """Endet eine Pause, rückt der Beitritt um ihre Dauer vor. Für einen Stichtag VOR der Pause
    gilt der Beitritt von damals — sonst fiele ein gezähltes Mitglied nachträglich heraus."""
    heute = timezone.localdate()
    stichtag = heute - timedelta(days=10)
    knapp = mitglied_anlegen('knapp')
    knapp.beitritt = monate_addieren(stichtag, -3)  # Anwartschaft am Stichtag gerade erfüllt
    knapp.save(update_fields=['beitritt'])
    assert zaehlen(stichtag, uebergang=False) == 1
    knapp.status, knapp.status_seit = Mitgliedsstatus.PAUSIERT, stichtag + timedelta(days=1)
    knapp.save(update_fields=['status', 'status_seit'])
    aktivieren(knapp)
    knapp.refresh_from_db()
    assert knapp.beitritt > monate_addieren(stichtag, -3)  # die Pause ruht die Anwartschaft
    assert zaehlen(stichtag, uebergang=False) == 1
    assert darf(knapp, stichtag, uebergang=False)
    eintrag = Statusverlauf.objects.filter(mitglied=knapp).order_by('pk').last()
    assert eintrag.anwartschaft_verschoben_tage == (knapp.beitritt - monate_addieren(stichtag, -3)).days


def test_altbestand_ohne_verlauf_gilt_mit_dem_heutigen_status_wie_bisher(lage):
    """Für die Zeit vor der Einführung des Verlaufs gibt es keine Zeilen: Ein Statuswechsel
    von damals wirkt wie bisher mit dem heutigen Status — nichts wird nachträglich umgerechnet."""
    _heute, stichtag, leute = lage
    nach = stichtag + timedelta(days=1)
    Mitglied.objects.filter(pk=leute[0].pk).update(status=Mitgliedsstatus.PAUSIERT, status_seit=nach)
    Mitglied.objects.filter(pk=leute[1].pk).update(status=Mitgliedsstatus.AKTIV, status_seit=nach)
    assert not Statusverlauf.objects.exists()
    assert zaehlen(stichtag) == 1
    for konto in leute[:2]:
        konto.refresh_from_db()
        assert not darf(konto, stichtag)
    # Altbestand, dessen Pause vor der Einführung begann und danach endet: Der Verlauf kennt den
    # Beginn aus `status_seit`; davor bleibt der Stand nicht feststellbar wie bisher.
    Mitglied.objects.filter(pk=leute[2].pk).update(
        status=Mitgliedsstatus.PAUSIERT, status_seit=stichtag - timedelta(days=5),
    )
    leute[2].refresh_from_db()
    aktivieren(leute[2])
    assert zaehlen(stichtag) == 0 and not darf(leute[2], stichtag)
    assert not darf(leute[2], stichtag - timedelta(days=8))


def test_verlauf_schreibt_je_statuswechsel_eine_zeile_ohne_begruendung():
    paul = mitglied_anlegen('paul')
    paul.first_name = 'Paul'
    paul.save()
    assert not Statusverlauf.objects.exists()  # kein Wechsel, keine Zeile
    pausieren(paul)
    paul.save(update_fields=paul.status_setzen(Mitgliedsstatus.PAUSIERT, 'anderer Grund'))
    eintrag = Statusverlauf.objects.get()
    assert (eintrag.mitglied_id, eintrag.status_vorher, eintrag.status) == (paul.pk, 'aktiv', 'pausiert')
    assert eintrag.tag == paul.status_seit and eintrag.seit_vorher is None
    assert eintrag.konto_aktiv_vorher is True and eintrag.anwartschaft_verschoben_tage == 0
    assert 'grund' not in ' '.join(f.name for f in Statusverlauf._meta.fields)
    aktivieren(paul)
    zweiter = Statusverlauf.objects.order_by('pk').last()
    assert (zweiter.status_vorher, zweiter.status, zweiter.seit_vorher) == ('pausiert', 'aktiv', eintrag.tag)


def test_statuswechsel_ohne_datum_traegt_den_tag_nach():
    """Wer den Status setzt, ohne `status_seit` mitzuziehen, bekommt den Tag des Wechsels —
    sonst zeigte das Datum auf einen Stand, der nicht mehr gilt."""
    paul = mitglied_anlegen('paul')
    paul.status = Mitgliedsstatus.PAUSIERT
    paul.save(update_fields=['status'])
    paul.refresh_from_db()
    assert paul.status_seit is not None and Statusverlauf.objects.get().tag == paul.status_seit


def test_einzelpruefung_ohne_spaeteren_wechsel_fragt_die_datenbank_nicht(django_assert_num_queries, lage):
    heute, stichtag, leute = lage
    with django_assert_num_queries(0):
        assert darf(leute[0], stichtag) and darf(leute[0], heute)


def test_zaehlung_buendelt_den_verlauf(django_assert_max_num_queries, lage):
    _heute, stichtag, leute = lage
    for konto in leute:
        pausieren(konto)
    with django_assert_max_num_queries(2):
        assert zaehlen(stichtag) == 3


def test_export_fuehrt_den_statusverlauf_und_der_austritt_laesst_ihn_stehen(client):
    paul = mitglied_anlegen('paul')
    pausieren(paul)
    client.force_login(paul)
    daten = json.loads(client.get(reverse('mitglieder:profil_export')).content)
    assert daten['statusverlauf'] == [{
        'tag': paul.status_seit.isoformat(), 'status_vorher': 'aktiv', 'status': 'pausiert',
        'seit_vorher': None, 'konto_aktiv_vorher': True, 'anwartschaft_verschoben_tage': 0,
    }]
    austreten(paul)
    # Status und Tage ohne Freitext: Der Verlauf bleibt wie die Kontozeile selbst (Grundregel 7) —
    # ohne ihn fiele ein am Stichtag gezähltes Mitglied aus einem verspätet festgestellten Nenner.
    assert list(Statusverlauf.objects.filter(mitglied=paul).values_list('status_vorher', 'status')) == [
        ('aktiv', 'pausiert'), ('pausiert', 'ausgetreten'),
    ]
