"""Beitragsabgleich (F-59): Verbuchung, Freischaltung, Meldeknopf, Erinnerungen."""

from datetime import date, timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from mitglieder import bank
from mitglieder.auth_flows import beitragsreferenz
from mitglieder.models import (
    Bankkopplung,
    Beitragseingang,
    Identitaetsstufe,
    Mitglied,
    Mitgliedsstatus,
    beitrag_verbuchen,
)
from plattform_core.beitraege import Eingang
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen  # noqa: F401

pytestmark = pytest.mark.django_db


def eingang(umsatz_id="u1", betrag="30.00", tag=None):
    from decimal import Decimal

    return Eingang(
        umsatz_id=umsatz_id,
        betrag=Decimal(betrag),
        waehrung="EUR",
        gebucht_am=tag or timezone.localdate(),
        verwendungszweck="",
        absender="",
    )


def test_verbuchen_schaltet_frei_und_ist_idempotent():
    m = mitglied_anlegen("zahlerin")
    m.identitaetsstufe = Identitaetsstufe.UNGEPRUEFT
    m.status = Mitgliedsstatus.PAUSIERT
    m.save(update_fields=["identitaetsstufe", "status"])

    assert beitrag_verbuchen(m, eingang(), namens_ok=True) is True
    m.refresh_from_db()
    assert m.status == Mitgliedsstatus.AKTIV  # § 4 Abs 3: Beitrag beendet die Pause
    assert m.identitaetsstufe == Identitaetsstufe.GEPRUEFT  # Freischaltung wie versprochen
    assert m.beitrag_zuletzt_am == timezone.localdate()
    assert AuditEintrag.objects.filter(ereignis__typ="beitrag").count() == 1

    assert beitrag_verbuchen(m, eingang(), namens_ok=True) is False  # gleicher Umsatz zählt einmal
    assert Beitragseingang.objects.count() == 1
    assert len(mail.outbox) == 1  # eine Bestätigung, keine zweite


def test_aelterer_eingang_setzt_beitragsdatum_nicht_zurueck():
    m = mitglied_anlegen("stamm")
    beitrag_verbuchen(m, eingang("neu", tag=date(2026, 8, 1)), namens_ok=True)
    beitrag_verbuchen(m, eingang("alt", tag=date(2026, 1, 1)), namens_ok=False)
    m.refresh_from_db()
    assert m.beitrag_zuletzt_am == date(2026, 8, 1)
    assert Beitragseingang.objects.get(umsatz_id="alt").namens_hinweis is True


def test_beitragsseite_zeigt_referenz_und_meldeknopf(client):
    m = mitglied_anlegen("mitglied1")
    client.force_login(m)
    antwort = client.get(reverse("mitglieder:beitrag"))
    assert antwort.status_code == 200
    assert beitragsreferenz(m) in antwort.content.decode()

    antwort = client.post(reverse("mitglieder:beitrag_gemeldet"), follow=True)
    assert "noch nicht eingerichtet" in antwort.content.decode()  # ohne Kopplung ehrlich


def test_gemeldet_ruft_ab_und_verbucht_sofort(client, settings, monkeypatch):
    settings.DDOE_BANK_SECRET_ID = "x"
    settings.DDOE_BANK_SECRET_KEY = "y"
    Bankkopplung.objects.create(requisition_id="r1", institution_id="TEST", account_id="k1")
    m = mitglied_anlegen("sofort")
    m.status = Mitgliedsstatus.PAUSIERT
    m.first_name, m.last_name = "Sofie", "Sofort"
    m.save(update_fields=["status", "first_name", "last_name"])

    def unechte_umsaetze(pfad, **params):
        assert pfad.startswith("/accounts/k1/transactions/")
        return {
            "transactions": {
                "booked": [
                    {
                        "internalTransactionId": "bank-1",
                        "transactionAmount": {"amount": "25.00", "currency": "EUR"},
                        "bookingDate": timezone.localdate().isoformat(),
                        "remittanceInformationUnstructured": f"{beitragsreferenz(m)} Mitgliedsbeitrag",
                        "debtorName": "Ganz Anders",
                    }
                ]
            }
        }

    monkeypatch.setattr(bank, "_get", unechte_umsaetze)
    client.force_login(m)
    antwort = client.post(reverse("mitglieder:beitrag_gemeldet"), follow=True)
    assert "verbucht" in antwort.content.decode()
    m.refresh_from_db()
    assert m.status == Mitgliedsstatus.AKTIV
    assert Beitragseingang.objects.get().namens_hinweis is True  # „Ganz Anders" ≠ Mitgliedsname
    kopplung = Bankkopplung.objects.get()
    assert (kopplung.abrufe_heute, kopplung.abruf_tag) == (1, timezone.localdate())


def test_kontingent_erschoepft_wird_ehrlich_gemeldet(client, settings):
    settings.DDOE_BANK_SECRET_ID = "x"
    settings.DDOE_BANK_SECRET_KEY = "y"
    Bankkopplung.objects.create(
        requisition_id="r1",
        institution_id="TEST",
        account_id="k1",
        abruf_tag=timezone.localdate(),
        abrufe_heute=4,
        zuletzt_abgerufen=timezone.now() - timedelta(hours=1),
    )
    m = mitglied_anlegen("geduld")
    client.force_login(m)
    antwort = client.post(reverse("mitglieder:beitrag_gemeldet"), follow=True)
    assert "Kontingent" in antwort.content.decode()


def test_verwaltung_beitraege_nur_fuer_admins_und_listet_faellige(client):
    m = mitglied_anlegen("faellig")
    Mitglied.objects.filter(pk=m.pk).update(beitrag_zuletzt_am=timezone.localdate() - timedelta(days=400))
    frisch = mitglied_anlegen("frisch")
    Mitglied.objects.filter(pk=frisch.pk).update(beitrag_zuletzt_am=timezone.localdate())

    client.force_login(m)
    assert client.get(reverse("mitglieder:verwaltung_beitraege")).status_code == 403

    admin = mitglied_anlegen("chefin")
    admin.ist_admin = True
    admin.save(update_fields=["ist_admin"])
    client.force_login(admin)
    antwort = client.get(reverse("mitglieder:verwaltung_beitraege"))
    faellige = list(antwort.context["faellige"])
    assert m in faellige and admin in faellige  # admin hat nie gezahlt -> fällig
    assert frisch not in faellige


def test_erinnerung_geht_an_alle_faelligen_mit_referenz_und_wird_auditiert(client):
    saeumig = mitglied_anlegen("saeumig")
    admin = mitglied_anlegen("chefin2")
    admin.ist_admin = True
    admin.beitrag_zuletzt_am = timezone.localdate()
    admin.save(update_fields=["ist_admin", "beitrag_zuletzt_am"])

    client.force_login(admin)
    antwort = client.post(reverse("mitglieder:beitrag_erinnern"), {"alle": "1"}, follow=True)
    assert "versendet" in antwort.content.decode()
    assert len(mail.outbox) == 1
    assert beitragsreferenz(saeumig) in mail.outbox[0].body
    assert "/beitrag/" in mail.outbox[0].body
    assert AuditEintrag.objects.filter(ereignis__aktion="beitrag_erinnerung").exists()

    mail.outbox.clear()
    antwort = client.post(reverse("mitglieder:beitrag_erinnern"), {"mitglied": []}, follow=True)
    assert len(mail.outbox) == 0  # ohne Auswahl wird niemand angeschrieben
