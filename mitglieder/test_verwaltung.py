"""Mitgliederverwaltung (F-51): Zugang, Aktionen, Schutzregeln, Audit."""

import json

import pytest
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Mitglied, Mitgliedsstatus
from verfahren.models import Antrag, AuditEintrag
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _gemeindeverzeichnis(db):
    from django.core.management import call_command

    call_command("gemeinden_laden")


def admin_anlegen(name="admina"):
    m = mitglied_anlegen(name)
    m.ist_admin = True
    m.save(update_fields=["ist_admin"])
    return m


def detail(pk):
    return reverse("mitglieder:verwaltung_mitglied", args=[pk])


# --- Zugang -----------------------------------------------------------------


def test_zugang_nur_fuer_admins(client):
    anna = mitglied_anlegen()
    url = reverse("mitglieder:verwaltung")
    assert client.get(url).status_code == 302  # anonym -> Login
    client.force_login(anna)
    assert client.get(url).status_code == 403  # Mitglied ohne Adminrechte
    client.force_login(admin_anlegen())
    antwort = client.get(url)
    assert antwort.status_code == 200
    assert "Mitgliederverwaltung" in antwort.content.decode()


def test_fixer_admin_hat_zugang_ohne_ernennung(client):
    michael = mitglied_anlegen("michael")
    michael.email = "didide@ddoe.at"  # DDOE_FIX_ADMIN (Standardwert)
    michael.save(update_fields=["email"])
    assert michael.ist_admin is False
    assert michael.hat_adminrechte is True
    client.force_login(michael)
    assert client.get(reverse("mitglieder:verwaltung")).status_code == 200


# --- Pause und Beitrag -------------------------------------------------------


def test_pausieren_setzt_status_und_sperrt_mitwirkung(client, ordnung):  # noqa: F811
    anna, chefin = mitglied_anlegen(), admin_anlegen()
    client.force_login(chefin)
    client.post(detail(anna.pk), {"aktion": "pausieren", "grund": "Beitrag seit 14 Monaten ausständig."})
    anna.refresh_from_db()
    assert anna.status == Mitgliedsstatus.PAUSIERT
    assert "14 Monaten" in anna.status_grund

    client.force_login(anna)  # pausiert: anmelden geht, mitwirken nicht
    antwort = client.post(reverse("verfahren:einbringen"), ANTRAG)
    assert antwort.status_code == 403
    assert "ruhen" in antwort.content.decode()
    assert Antrag.objects.count() == 0
    assert anna.ist_stimmberechtigt("sachfrage", timezone.now().date(), uebergang=True) is False


def test_pausieren_verlangt_begruendung(client):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), {"aktion": "pausieren", "grund": ""})
    anna.refresh_from_db()
    assert anna.status == Mitgliedsstatus.AKTIV  # ohne Begründung passiert nichts


def test_beitragseingang_hebt_die_pause_auf(client):
    anna = mitglied_anlegen()
    anna.status = Mitgliedsstatus.PAUSIERT
    anna.save(update_fields=["status"])
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), {"aktion": "beitrag"})
    anna.refresh_from_db()
    assert anna.status == Mitgliedsstatus.AKTIV
    assert anna.beitrag_zuletzt_am == timezone.localdate()


# --- Ausschluss und Reaktivierung ---------------------------------------------


def test_ausschliessen_deaktiviert_und_reaktivieren_macht_es_rueckgaengig(client):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    client.post(
        detail(anna.pk), {"aktion": "ausschliessen", "grund": "Beschluss des Schiedsorgans S-2026-01."}
    )
    anna.refresh_from_db()
    assert anna.status == Mitgliedsstatus.AUSGESCHLOSSEN
    assert anna.is_active is False

    client.post(detail(anna.pk), {"aktion": "reaktivieren"})
    anna.refresh_from_db()
    assert anna.status == Mitgliedsstatus.AKTIV
    assert anna.is_active is True
    assert anna.status_grund == ""


def test_fixer_admin_ist_unantastbar_und_niemand_wirkt_auf_sich_selbst(client):
    michael = mitglied_anlegen("michael")
    michael.email = "didide@ddoe.at"
    michael.save(update_fields=["email"])
    chefin = admin_anlegen()
    client.force_login(chefin)
    client.post(detail(michael.pk), {"aktion": "ausschliessen", "grund": "x"})
    client.post(detail(michael.pk), {"aktion": "admin_nehmen"})
    michael.refresh_from_db()
    assert michael.is_active is True and michael.hat_adminrechte is True

    client.post(detail(chefin.pk), {"aktion": "pausieren", "grund": "x"})  # sich selbst: nein
    chefin.refresh_from_db()
    assert chefin.status == Mitgliedsstatus.AKTIV


# --- Adminrechte ---------------------------------------------------------------


def test_admins_ernennen_und_entziehen_einander(client):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), {"aktion": "admin_geben"})
    anna.refresh_from_db()
    assert anna.hat_adminrechte is True
    client.post(detail(anna.pk), {"aktion": "admin_nehmen"})
    anna.refresh_from_db()
    assert anna.hat_adminrechte is False


# --- Stammdaten -----------------------------------------------------------------


def stammdaten(person, **aenderungen):
    daten = {
        "aktion": "stammdaten",
        "vorname": person.first_name,
        "nachname": person.last_name,
        "email": person.email,
        "anzeigename": person.pseudonym_oeffentlich,
        "gemeinde": person.gemeinde,
        "identitaetsstufe": person.identitaetsstufe,
        "beitrag_zuletzt_am": "",
    }
    daten.update(aenderungen)
    return daten


def test_falsche_angaben_korrigieren(client):
    anna = mitglied_anlegen()
    anna.username = anna.email = "anna@example.org"
    anna.first_name = "Ana"
    anna.save()
    client.force_login(admin_anlegen())
    client.post(
        detail(anna.pk),
        stammdaten(anna, vorname="Anna", email="anna.neu@example.org", gemeinde="Krumbach (Bregenz)"),
    )
    anna.refresh_from_db()
    assert anna.first_name == "Anna"
    assert anna.email == "anna.neu@example.org"
    assert anna.username == "anna.neu@example.org"  # Anmeldename folgt der Adresse
    assert anna.bundesland == "vorarlberg"  # Bundesland folgt dem Verzeichnis, nie der Hand


def test_email_kollision_wird_abgelehnt(client):
    anna, bernd = mitglied_anlegen(), mitglied_anlegen("bernd")
    client.force_login(admin_anlegen())
    antwort = client.post(detail(anna.pk), stammdaten(anna, email=bernd.email))
    assert "anderen Konto" in antwort.content.decode()
    anna.refresh_from_db()
    assert anna.email == "anna@example.org"


# --- Audit ----------------------------------------------------------------------


def test_jede_handlung_landet_im_audit_log_ohne_personenwerte(client):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), stammdaten(anna, email="ganz.neu@example.org"))
    client.post(detail(anna.pk), {"aktion": "pausieren", "grund": "Beitrag ausständig."})
    eintraege = [e.ereignis for e in AuditEintrag.objects.filter(ereignis__typ="verwaltung")]
    assert [e["aktion"] for e in eintraege] == ["stammdaten_geaendert", "pausieren"]
    # E-Mail geändert; „wohnsitz“ heilt nebenbei den fehlenden Verzeichnis-Verweis der Testperson.
    assert eintraege[0]["felder"] == ["email", "wohnsitz"]
    assert "ganz.neu" not in json.dumps(eintraege)  # Feldnamen ja, Werte nie (Log ist öffentlich)
    assert Mitglied.objects.filter(email="ganz.neu@example.org").exists()
