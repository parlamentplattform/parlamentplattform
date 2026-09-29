"""Testkonten, Pause und Beitragsreferenz (Bestandsaufnahme 28.9.2026, Befunde A1, A12 und die
Entscheidung des Gründers, dass eine Pause auch die Anwartschaft ruhen lässt)."""

from datetime import date, timedelta

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from mitglieder.auth_flows import beitragsreferenz
from mitglieder.models import Identitaetsstufe, Mitglied, Mitgliedsstatus, stimmberechtigte_zaehlen
from plattform_core.eligibility import Gegenstand

pytestmark = pytest.mark.django_db


def _mitglied(username: str, **felder) -> Mitglied:
    werte = {
        "email": f"{username}@example.org",
        "beitritt": date(2025, 1, 1),
        "identitaetsstufe": Identitaetsstufe.GEPRUEFT,
        "status": Mitgliedsstatus.AKTIV,
        "geprueft_seit": date(2025, 1, 1),
    }
    werte.update(felder)
    return Mitglied.objects.create(username=username, **werte)


def test_testkonto_steht_in_keinem_nenner_und_keinem_zaehler():
    echt = _mitglied("echt")
    test = _mitglied("probe", testkonto=True)
    heute = timezone.localdate()
    assert stimmberechtigte_zaehlen(Gegenstand.SACHFRAGE, heute, uebergang=True) == 1
    assert echt.ist_stimmberechtigt(Gegenstand.SACHFRAGE, heute, uebergang=True) is True
    assert test.ist_stimmberechtigt(Gegenstand.SACHFRAGE, heute, uebergang=True) is False


def test_uebersicht_und_startseite_zaehlen_keine_testkonten(client):
    _mitglied("echt")
    _mitglied("probe", testkonto=True)
    uebersicht = client.get(reverse("uebersicht:index"))
    assert uebersicht.context["mitglieder_gesamt"] == 1
    start = client.get("/")
    assert start.context["buehne"]["mitglieder"] == 1


@override_settings(DDOE_DEMO=False)
def test_demo_seed_tut_ohne_demo_schalter_nichts():
    call_command("demo_seed", verbosity=0)
    assert not Mitglied.objects.filter(username="demo1").exists()


@override_settings(DDOE_DEMO=False)
def test_demo_seed_laesst_sich_fuer_entwicklung_und_tests_erzwingen():
    call_command("demo_seed", "--erzwingen", verbosity=0)
    assert Mitglied.objects.filter(username__startswith="demo").count() == 5


def test_pause_laesst_die_anwartschaft_ruhen():
    m = _mitglied("pausiert")
    m.status_seit = timezone.localdate() - timedelta(days=40)
    m.status = Mitgliedsstatus.PAUSIERT
    m.save()
    felder = m.status_setzen(Mitgliedsstatus.AKTIV)
    assert "beitritt" in felder and "status" in felder
    assert m.beitritt == date(2025, 1, 1) + timedelta(days=40)  # die 40 Tage Pause zählen nicht


def test_ausschluss_und_rueckkehr_verschieben_den_beitritt_nicht():
    m = _mitglied("ausgeschlossen")
    m.status_seit = timezone.localdate() - timedelta(days=40)
    m.status = Mitgliedsstatus.AUSGESCHLOSSEN
    m.save()
    m.status_setzen(Mitgliedsstatus.AKTIV)
    assert m.beitritt == date(2025, 1, 1)  # ein aufgehobener Ausschluss unterbricht nichts


def test_pause_am_selben_tag_veraendert_den_beitritt_nicht():
    m = _mitglied("kurz")
    m.status_setzen(Mitgliedsstatus.PAUSIERT, "Beitrag offen")
    m.save()
    felder = m.status_setzen(Mitgliedsstatus.AKTIV)
    assert "beitritt" not in felder


def test_beitragsreferenz_bleibt_bei_adresswechsel_gleich():
    m = _mitglied("anna@example.org")
    vorher = beitragsreferenz(m)
    m.refresh_from_db()
    assert m.beitragsreferenz_stamm and vorher.endswith(m.beitragsreferenz_stamm)
    m.username = m.email = "anna.neu@example.org"
    m.save()
    assert beitragsreferenz(Mitglied.objects.get(pk=m.pk)) == vorher


def test_beitragsreferenz_wird_fuer_bestand_aus_dem_alten_verfahren_uebernommen():
    """Ein Konto ohne Stamm bekommt genau die Referenz, die es bis 0.49 hatte."""
    from mitglieder.auth_flows import referenzstamm_ableiten

    m = _mitglied("bestand")
    assert m.beitragsreferenz_stamm == ""
    assert beitragsreferenz(m) == f"DDOE-{m.pk:04d}-{referenzstamm_ableiten(m.pk, 'bestand')}"


def test_rollenformular_zeigt_namen_statt_adressen_und_keine_testkonten():
    from gremien.views import RollenFormular

    echt = _mitglied("anna@example.org", first_name="Anna", last_name="Adler", mitgliedsnummer=12)
    _mitglied("probe", testkonto=True)
    feld = RollenFormular().fields["mitglied"]
    auswahl = {m.pk: feld.label_from_instance(m) for m in feld.queryset}
    assert list(auswahl) == [echt.pk]
    assert auswahl[echt.pk] == "Anna Adler · #000012"
    assert "example.org" not in auswahl[echt.pk]


def test_lostopf_der_fachliste_kennt_keine_testkonten():
    from gremien.models import Fachliste, lostopf_der_fachliste

    echt = _mitglied("fach")
    probe = _mitglied("probe", testkonto=True)
    Fachliste.objects.create(mitglied=echt, schluessel="a" * 8)
    Fachliste.objects.create(mitglied=probe, schluessel="b" * 8)
    assert [k.schluessel for k in lostopf_der_fachliste()] == ["a" * 8]
