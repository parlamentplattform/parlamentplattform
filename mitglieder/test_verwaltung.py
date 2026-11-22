"""Mitgliederverwaltung (F-51): Zugang, Aktionen, Schutzregeln, Audit."""

import json
import re
from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import (
    Adresswechsel,
    Identitaetsstufe,
    Mitglied,
    Mitgliedsstatus,
    stimmberechtigte_zaehlen,
)
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
    if person.klarname_oeffentlich:
        daten["klarname_oeffentlich"] = "on"  # so sendet der Browser das angehakte Kästchen
    daten.update(aenderungen)
    return daten


def test_falsche_angaben_korrigieren(client):
    anna = mitglied_anlegen()
    anna.username = anna.email = "anna@example.org"
    anna.first_name = "Ana"
    anna.save()
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), stammdaten(anna, vorname="Anna", gemeinde="Krumbach (Bregenz)"))
    anna.refresh_from_db()
    assert anna.first_name == "Anna"
    assert anna.bundesland == "vorarlberg"  # Bundesland folgt dem Verzeichnis, nie der Hand


# --- Adresswechsel (Befunde #1, #2): nie sofort, Einspruch, Frist, zweiter Admin ------


def adresse_beantragen(client, person, neu="anna.neu@example.org"):
    client.post(detail(person.pk), stammdaten(person, email=neu))
    return Adresswechsel.offener(person)


def einspruchslink(nachricht) -> str:
    treffer = re.search(r"http://testserver(/adresse/einspruch/\S+)", nachricht.body)
    assert treffer, "kein Einspruchslink in der Nachricht an die bisherige Adresse"
    return treffer.group(1)


def test_adressaenderung_wird_nicht_sofort_wirksam_und_warnt_die_bisherige_adresse(client):
    """Befund #1: Der Login läuft passwortlos über die Adresse — eine sofortige Änderung
    wäre eine Kontoübernahme samt Blick auf das Stimmregister-Pseudonym (§ 5 Abs 3)."""
    anna = mitglied_anlegen()
    anna.username = anna.email = "anna@example.org"
    anna.save()
    client.force_login(admin_anlegen())
    wechsel = adresse_beantragen(client, anna)
    anna.refresh_from_db()
    assert anna.email == "anna@example.org" and anna.username == "anna@example.org"  # unverändert
    assert wechsel is not None and wechsel.neue_email == "anna.neu@example.org"
    assert wechsel.bestaetigt_von is None
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["anna@example.org"]  # die BISHERIGE Adresse, nie die neue
    assert "widersprechen" in mail.outbox[0].body
    eintraege = [e.ereignis for e in AuditEintrag.objects.filter(ereignis__typ="verwaltung")]
    assert eintraege[-1]["aktion"] == "email_geaendert_beantragt"
    assert "anna.neu" not in json.dumps(eintraege)  # Audit ohne Adresswerte (öffentlich, F-22)
    assert anna.adresswechsel_offen is True


def test_waehrend_der_frist_gehen_keine_anmeldelinks_an_die_neue_adresse(client):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    adresse_beantragen(client, anna)
    mail.outbox.clear()
    from mitglieder.test_views import botschutz

    client.logout()
    client.post(reverse("mitglieder:login"), {"email": "anna.neu@example.org", **botschutz(client)})
    assert mail.outbox == []  # die neue Adresse ist (noch) niemandes Anmeldeadresse


def test_einspruch_der_bisherigen_adresse_verwirft_die_aenderung(client):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    wechsel = adresse_beantragen(client, anna)
    link = einspruchslink(mail.outbox[0])
    client.logout()  # der Inhaber ist womöglich nicht angemeldet
    antwort = client.get(link)
    assert antwort.status_code == 200 and "verwerfen" in antwort.content.decode()
    wechsel.refresh_from_db()
    assert wechsel.status == Adresswechsel.Status.OFFEN  # GET wirkt nicht (Mail-Vorschau-Schutz)
    client.post(link)
    wechsel.refresh_from_db()
    assert wechsel.status == Adresswechsel.Status.WIDERRUFEN
    anna.refresh_from_db()
    assert anna.email == "anna@example.org"
    letzter = AuditEintrag.objects.filter(ereignis__typ="verwaltung").last().ereignis
    assert letzter["aktion"] == "email_geaendert_widerrufen" and letzter["anlass"] == "einspruch"
    assert client.get("/adresse/einspruch/gibt-es-nicht/").status_code == 400


def test_wirksam_erst_nach_frist_und_zweitem_admin(client):
    anna = mitglied_anlegen()
    anna.username = anna.email = "anna@example.org"
    anna.save()
    erste, zweite = admin_anlegen("admina"), admin_anlegen("adminb")
    client.force_login(erste)
    wechsel = adresse_beantragen(client, anna)

    # Vier-Augen: Der Antragsteller kann nicht selbst bestätigen.
    client.post(detail(anna.pk), {"aktion": "adresswechsel_bestaetigen"})
    wechsel.refresh_from_db()
    assert wechsel.bestaetigt_von is None

    client.force_login(zweite)
    client.post(detail(anna.pk), {"aktion": "adresswechsel_bestaetigen"})
    wechsel.refresh_from_db()
    assert wechsel.bestaetigt_von == zweite

    # Bestätigt, aber die Frist läuft noch: nichts passiert, auch nicht beim nächsten Seitenaufruf.
    client.get(detail(anna.pk))
    anna.refresh_from_db()
    assert anna.email == "anna@example.org"

    # Frist um: Der nächste Aufruf einer Verwaltungsseite macht den Wechsel wirksam.
    Adresswechsel.objects.filter(pk=wechsel.pk).update(frist_bis=timezone.now() - timedelta(minutes=1))
    client.get(detail(anna.pk))
    anna.refresh_from_db()
    wechsel.refresh_from_db()
    assert anna.email == "anna.neu@example.org"
    assert anna.username == "anna.neu@example.org"  # Anmeldename folgt der Adresse
    assert wechsel.status == Adresswechsel.Status.WIRKSAM
    aktionen = [e.ereignis["aktion"] for e in AuditEintrag.objects.filter(ereignis__typ="verwaltung")]
    assert aktionen[-3:] == ["email_geaendert_beantragt", "email_geaendert_bestaetigt", "email_geaendert_wirksam"]


def test_frist_allein_genuegt_nicht_ohne_zweiten_admin(client):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    wechsel = adresse_beantragen(client, anna)
    Adresswechsel.objects.filter(pk=wechsel.pk).update(frist_bis=timezone.now() - timedelta(days=1))
    client.get(reverse("mitglieder:verwaltung"))
    anna.refresh_from_db()
    assert anna.email == "anna@example.org"
    assert Adresswechsel.offener(anna) is not None


def test_admin_kann_laufende_aenderung_abbrechen_und_keine_zweite_starten(client):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    adresse_beantragen(client, anna)
    antwort = client.post(detail(anna.pk), stammdaten(anna, email="noch.eine@example.org"))
    assert "läuft bereits eine Adressänderung" in antwort.content.decode()
    assert Adresswechsel.objects.filter(mitglied=anna).count() == 1
    client.post(detail(anna.pk), {"aktion": "adresswechsel_abbrechen"})
    assert Adresswechsel.offener(anna) is None
    assert anna.adresswechsel_offen is False


def test_ohne_nachricht_an_die_bisherige_adresse_gibt_es_keinen_antrag(client, monkeypatch):
    """Ohne Einspruchsmöglichkeit des Inhabers wäre die Frist wertlos."""

    def kaputt(*args, **kwargs):
        raise OSError("SMTP nicht erreichbar")

    monkeypatch.setattr("mitglieder.verwaltung.send_mail", kaputt)
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    antwort = client.post(detail(anna.pk), stammdaten(anna, email="anna.neu@example.org"), follow=True)
    assert "nicht vorgemerkt" in antwort.content.decode()
    assert Adresswechsel.objects.filter(mitglied=anna).count() == 0


def test_fixer_admin_verliert_seine_adresse_nicht_und_niemand_bekommt_sie(client):
    """Befund #2: ist_fixer_admin hängt an der Adresse (DDOE_FIX_ADMIN). Wer sie ihm
    nähme, entmachtete ihn; wer sie sich gäbe, würde selbst unantastbar."""
    michael = mitglied_anlegen("michael")
    michael.email = "didide@ddoe.at"
    michael.save(update_fields=["email"])
    chefin = admin_anlegen()
    client.force_login(chefin)
    antwort = client.post(detail(michael.pk), stammdaten(michael, email="abgeschoben@example.org"))
    assert "Erstzugangs wird hier nicht geändert" in antwort.content.decode()
    michael.refresh_from_db()
    assert michael.hat_adminrechte is True and Adresswechsel.objects.count() == 0

    antwort = client.post(detail(chefin.pk), stammdaten(chefin, email="DIDIDE@ddoe.at"))
    assert "vorbehalten" in antwort.content.decode()
    chefin.refresh_from_db()
    assert chefin.ist_fixer_admin is False and Adresswechsel.objects.count() == 0

    # Tiefenverteidigung: Selbst ein fertig bestätigter, fälliger Wechsel auf die Adresse
    # des Erstzugangs wird beim Wirksammachen verworfen — nicht nur im Formular.
    wechsel, _klar = Adresswechsel.beantragen(chefin, "didide@ddoe.at", durch=chefin)
    wechsel.bestaetigt_von = admin_anlegen("adminb")
    wechsel.frist_bis = timezone.now() - timedelta(hours=1)
    wechsel.save()
    assert wechsel.wirksam_machen() is False
    wechsel.refresh_from_db()
    chefin.refresh_from_db()
    assert wechsel.status == Adresswechsel.Status.WIDERRUFEN and chefin.ist_fixer_admin is False


def test_email_kollision_wird_abgelehnt(client):
    anna, bernd = mitglied_anlegen(), mitglied_anlegen("bernd")
    client.force_login(admin_anlegen())
    antwort = client.post(detail(anna.pk), stammdaten(anna, email=bernd.email))
    assert "anderen Konto" in antwort.content.decode()
    anna.refresh_from_db()
    assert anna.email == "anna@example.org"


def _faelliger_wechsel(anna, neue="anna.neu@example.org"):
    wechsel, _klar = Adresswechsel.beantragen(anna, neue, durch=admin_anlegen())
    wechsel.bestaetigt_von = admin_anlegen("adminb")
    wechsel.frist_bis = timezone.now() - timedelta(hours=1)
    wechsel.save()
    return wechsel


def test_zweimal_angewendeter_wechsel_ergibt_genau_einen_audit_eintrag():
    """Auflage zu GP-211: Hintergrundlauf und Seitenaufruf können denselben fälligen Wechsel
    gleichzeitig anwenden — jeder mit seinem eigenen, schon geladenen Stand."""
    anna = mitglied_anlegen()
    wechsel = _faelliger_wechsel(anna)
    zweiter_lauf = Adresswechsel.objects.get(pk=wechsel.pk)
    assert wechsel.wirksam_machen() is True
    assert zweiter_lauf.wirksam_machen() is False
    assert Adresswechsel.faellige_anwenden() == 0
    aktionen = [e.ereignis["aktion"] for e in AuditEintrag.objects.filter(ereignis__typ="verwaltung")]
    assert aktionen.count("email_geaendert_wirksam") == 1 and "email_geaendert_widerrufen" not in aktionen
    zweiter_lauf.refresh_from_db()
    assert zweiter_lauf.status == Adresswechsel.Status.WIRKSAM


def test_zweimal_bestaetigter_wechsel_ergibt_genau_einen_audit_eintrag():
    """Restauflage zu GP-211 (Nachbar): Zwei Bestätigungen mit veraltetem Stand — die zweite findet
    den Wechsel bestätigt vor und schreibt nichts."""
    anna = mitglied_anlegen()
    wechsel, _klar = Adresswechsel.beantragen(anna, "anna.neu@example.org", durch=admin_anlegen())
    zweite = Adresswechsel.objects.get(pk=wechsel.pk)
    adminb, adminc = admin_anlegen("adminb"), admin_anlegen("adminc")
    assert wechsel.bestaetigen(adminb) is True
    assert zweite.bestaetigen(adminc) is False
    aktionen = [e.ereignis["aktion"] for e in AuditEintrag.objects.filter(ereignis__typ="verwaltung")]
    assert aktionen.count("email_geaendert_bestaetigt") == 1
    wechsel.refresh_from_db()
    assert wechsel.bestaetigt_von_id == adminb.pk


def test_bestaetigung_eines_inzwischen_widerrufenen_wechsels_schreibt_nichts():
    anna = mitglied_anlegen()
    wechsel, _klar = Adresswechsel.beantragen(anna, "anna.neu@example.org", durch=admin_anlegen())
    veraltet = Adresswechsel.objects.get(pk=wechsel.pk)
    assert wechsel.widerrufen("einspruch") is True
    assert veraltet.bestaetigen(admin_anlegen("adminb")) is False
    aktionen = [e.ereignis["aktion"] for e in AuditEintrag.objects.filter(ereignis__typ="verwaltung")]
    assert "email_geaendert_bestaetigt" not in aktionen
    wechsel.refresh_from_db()
    assert wechsel.bestaetigt_von_id is None


def test_bestaetigen_mit_scheiterndem_audit_aendert_nichts(monkeypatch):
    anna = mitglied_anlegen()
    wechsel, _klar = Adresswechsel.beantragen(anna, "anna.neu@example.org", durch=admin_anlegen())

    def kaputt(ereignis):
        raise RuntimeError("Audit nicht erreichbar")

    monkeypatch.setattr("verfahren.models.AuditEintrag.anhaengen", kaputt)
    with pytest.raises(RuntimeError):
        wechsel.bestaetigen(admin_anlegen("adminb"))
    wechsel.refresh_from_db()
    assert wechsel.bestaetigt_von_id is None and wechsel.bestaetigt_am is None


def test_wirksam_machen_mit_scheiterndem_audit_aendert_nichts(monkeypatch):
    anna = mitglied_anlegen()
    wechsel = _faelliger_wechsel(anna)

    def kaputt(ereignis):
        raise RuntimeError("Audit nicht erreichbar")

    monkeypatch.setattr("verfahren.models.AuditEintrag.anhaengen", kaputt)
    with pytest.raises(RuntimeError):
        wechsel.wirksam_machen()
    anna.refresh_from_db()
    wechsel.refresh_from_db()
    assert anna.email == "anna@example.org" and wechsel.status == Adresswechsel.Status.OFFEN


# --- Audit ----------------------------------------------------------------------


def test_jede_handlung_landet_im_audit_log_ohne_personenwerte(client):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), stammdaten(anna, vorname="Annika", email="ganz.neu@example.org"))
    client.post(detail(anna.pk), {"aktion": "pausieren", "grund": "Beitrag ausständig."})
    eintraege = [e.ereignis for e in AuditEintrag.objects.filter(ereignis__typ="verwaltung")]
    assert [e["aktion"] for e in eintraege] == ["stammdaten_geaendert", "email_geaendert_beantragt", "pausieren"]
    # Vorname geändert; „wohnsitz“ heilt nebenbei den fehlenden Verzeichnis-Verweis der Testperson.
    # Die Adresse steht NICHT unter den Stammdaten-Feldern: Sie ist ein eigener Vorgang (Befund #1).
    assert eintraege[0]["felder"] == ["first_name", "wohnsitz"]
    assert "ganz.neu" not in json.dumps(eintraege)  # Feldnamen ja, Werte nie (Log ist öffentlich)
    assert "Annika" not in json.dumps(eintraege)


# --- Stichtag (Befund #25, § 4 Abs 4 lit a): Zähler und Nenner folgen demselben Tag ------


def test_wer_nach_dem_stichtag_freigeschaltet_wird_stimmt_bei_dieser_abstimmung_nicht_mit(client):
    """Am Stichtag ungeprüft heißt: nicht im Nenner. Dann darf die Freischaltung während
    der Abstimmung nicht in den Zähler führen — sonst sind Beteiligungen über 100 % möglich."""
    stichtag = timezone.localdate() - timedelta(days=3)
    anna, chefin = mitglied_anlegen(stufe=Identitaetsstufe.UNGEPRUEFT), admin_anlegen()
    assert stimmberechtigte_zaehlen("sachfrage", stichtag, uebergang=True) == 1  # nur die Chefin
    client.force_login(chefin)
    client.post(detail(anna.pk), stammdaten(anna, identitaetsstufe=Identitaetsstufe.PRAESENZ))
    anna.refresh_from_db()
    assert anna.identitaetsstufe == Identitaetsstufe.PRAESENZ
    assert anna.geprueft_seit == timezone.localdate()
    assert anna.ist_stimmberechtigt("sachfrage", stichtag, uebergang=True) is False  # damals noch nicht
    assert anna.ist_stimmberechtigt("sachfrage", timezone.localdate(), uebergang=True) is True  # ab heute
    assert stimmberechtigte_zaehlen("sachfrage", stichtag, uebergang=True) == 1  # Nenner bleibt
    assert stimmberechtigte_zaehlen("sachfrage", timezone.localdate(), uebergang=True) == 2


def test_beitragseingang_schaltet_ab_heute_frei_nicht_rueckwirkend():
    from decimal import Decimal
    from types import SimpleNamespace

    from mitglieder.models import beitrag_verbuchen

    stichtag = timezone.localdate() - timedelta(days=3)
    anna = mitglied_anlegen(stufe=Identitaetsstufe.UNGEPRUEFT)
    eingang = SimpleNamespace(umsatz_id="u-1", betrag=Decimal("30"), gebucht_am=stichtag - timedelta(days=2))
    assert beitrag_verbuchen(anna, eingang, namens_ok=True) is True
    anna.refresh_from_db()
    assert anna.identitaetsstufe == Identitaetsstufe.GEPRUEFT
    assert anna.geprueft_seit == timezone.localdate()  # nicht der Buchungstag: der Nenner stand schon fest
    assert anna.ist_stimmberechtigt("sachfrage", stichtag, uebergang=True) is False


def test_wer_nach_dem_stichtag_wieder_aktiv_wird_stimmt_bei_dieser_abstimmung_nicht_mit(client):
    stichtag = timezone.localdate() - timedelta(days=3)
    anna = mitglied_anlegen()
    anna.status = Mitgliedsstatus.PAUSIERT
    anna.status_seit = stichtag - timedelta(days=10)
    anna.save(update_fields=["status", "status_seit"])
    assert stimmberechtigte_zaehlen("sachfrage", stichtag, uebergang=True) == 0
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), {"aktion": "reaktivieren"})
    anna.refresh_from_db()
    assert anna.status == Mitgliedsstatus.AKTIV and anna.status_seit == timezone.localdate()
    assert anna.ist_stimmberechtigt("sachfrage", stichtag, uebergang=True) is False
    assert anna.ist_stimmberechtigt("sachfrage", timezone.localdate(), uebergang=True) is True


def test_altbestand_ohne_freischaltdatum_gilt_seit_beitritt():
    """Vor Befund #25 gab es kein `geprueft_seit`; Konten von damals verlieren nichts."""
    anna = mitglied_anlegen(tage=30)
    assert anna.geprueft_seit is None
    assert anna.ist_stimmberechtigt("sachfrage", timezone.localdate() - timedelta(days=10), uebergang=True)
    assert not anna.ist_stimmberechtigt("sachfrage", timezone.localdate() - timedelta(days=40), uebergang=True)


# --- Reaktivieren eines nie bestätigten Kontos (Befund #21) ------------------------------


def test_reaktivieren_eines_unbestaetigten_kontos_setzt_den_beitritt(client):
    """Ohne Beitritt bliebe das Konto für immer ohne Anwartschaft (§ 4 Abs 4) —
    der Rettungsweg der Verwaltung wäre wirkungslos."""
    eva = Mitglied.objects.create(username="eva@example.org", email="eva@example.org", is_active=False)
    client.force_login(admin_anlegen())
    client.post(detail(eva.pk), {"aktion": "reaktivieren"})
    eva.refresh_from_db()
    assert eva.is_active is True and eva.beitritt == timezone.localdate()


# --- Zugängliche Namen der Verwaltungsfelder (Befund #85) ---------------------------------


def test_verwaltungsfelder_haben_zugaengliche_namen(client):
    """Suchfeld, Statusfilter, Bankwahl und Datei-Eingabe hatten weder Label noch aria-label —
    ein Screenreader sagte nur „Eingabefeld“ an."""
    client.force_login(admin_anlegen())
    liste = client.get(reverse("mitglieder:verwaltung")).content.decode()
    assert 'name="q" value="" aria-label="Suchbegriff"' in liste
    assert 'name="status" aria-label="Status filtern"' in liste
    beitraege = client.get(reverse("mitglieder:verwaltung_beitraege")).content.decode()
    assert "<label>Kontoauszug (camt.053-XML oder CSV) <input type=\"file\"" in beitraege


# --- Übersetzbarkeit der Verwaltung (Befund #91) ------------------------------------------


def test_verwaltungsmeldungen_und_formularbeschriftungen_sind_uebersetzbar():
    """CLAUDE.md § 4: Jeder Nutzertext übersetzbar, Verwaltung eingeschlossen. Ein Wächter
    über den Quelltext — nackte Strings in messages.*() oder label= fallen hier auf."""
    from pathlib import Path

    quelle = Path(__file__).with_name("verwaltung.py").read_text(encoding="utf-8")
    nackt = re.findall(r'messages\.\w+\(\s*request,\s*f?"', quelle)
    assert nackt == [], f"Meldungen ohne gettext: {nackt}"
    assert re.findall(r'label="', quelle) == []
    assert re.findall(r'ValidationError\(\s*f?"', quelle) == []


# --- Fundament S10: Nebenwohnsitz und Austritt ----------------------------------------------


def test_nebenwohnsitz_ist_ein_zweiter_verweis_ins_gemeindeverzeichnis_ohne_stimmwirkung(ordnung):  # noqa: F811
    """FB-J6: Der Nebenwohnsitz ordnet nur zu — die Stimmberechtigung kennt keine Region (§ 5 Abs 6)."""
    from mitglieder.models import Gemeinde
    from plattform_core import Gegenstand

    anna = mitglied_anlegen("anna")
    assert anna.nebenwohnsitz is None
    gemeinde = Gemeinde.objects.exclude(name=anna.gemeinde).first()
    anna.nebenwohnsitz = gemeinde
    anna.save(update_fields=["nebenwohnsitz"])
    anna.refresh_from_db()
    assert anna.nebenwohnsitz == gemeinde
    assert anna in gemeinde.nebenwohnsitz_mitglieder.all()
    assert anna.gemeinde != gemeinde.name  # Hauptwohnsitz bleibt unberührt
    vorher = anna.ist_stimmberechtigt(Gegenstand.SACHFRAGE, timezone.localdate())
    anna.nebenwohnsitz = None
    assert anna.ist_stimmberechtigt(Gegenstand.SACHFRAGE, timezone.localdate()) == vorher
    # SET_NULL: verschwindet die Gemeinde, bleibt das Mitglied
    gemeinde.delete()
    anna.refresh_from_db()
    assert anna.nebenwohnsitz is None


def test_status_ausgetreten_zaehlt_nicht_zu_den_stimmberechtigten_und_bleibt_von_nie_bestaetigt_getrennt():
    from mitglieder.views import nie_bestaetigt
    from plattform_core import Gegenstand

    anna = mitglied_anlegen("anna")
    stichtag = timezone.localdate()
    davor = stimmberechtigte_zaehlen(Gegenstand.SACHFRAGE, stichtag)
    felder = anna.status_setzen(Mitgliedsstatus.AUSGETRETEN, "")
    assert set(felder) == {"status", "status_seit"}
    anna.is_active = False
    anna.save(update_fields=[*felder, "is_active"])
    assert anna.status == "ausgetreten" and anna.get_status_display() == "ausgetreten"
    assert stimmberechtigte_zaehlen(Gegenstand.SACHFRAGE, stichtag) == davor - 1
    assert anna.ist_stimmberechtigt(Gegenstand.SACHFRAGE, stichtag) is False
    assert anna.darf_mitwirken is False
    assert nie_bestaetigt(anna) is False  # ausgetreten ist kein nie bestätigtes Konto


def test_verwaltung_kann_die_einwilligung_zum_klarnamen_nur_zuruecknehmen(client):
    """§ 5 Abs 3 lit a, § 8 Abs 4: Einwilligen kann nur der Mensch selbst. Die Verwaltung darf
    das Häkchen entfernen, aber nicht setzen — sonst wäre eine Einwilligung von Amts wegen möglich."""
    admin = admin_anlegen()
    client.force_login(admin)
    person = mitglied_anlegen("ohne_einwilligung")
    person.klarname_oeffentlich = False
    person.save(update_fields=["klarname_oeffentlich"])
    daten = stammdaten(person)
    daten["klarname_oeffentlich"] = "on"
    client.post(reverse("mitglieder:verwaltung_mitglied", args=[person.pk]), daten)
    person.refresh_from_db()
    assert person.klarname_oeffentlich is False
    person.klarname_oeffentlich = True
    person.save(update_fields=["klarname_oeffentlich"])
    daten = stammdaten(person)
    daten.pop("klarname_oeffentlich", None)
    client.post(reverse("mitglieder:verwaltung_mitglied", args=[person.pk]), daten)
    person.refresh_from_db()
    assert person.klarname_oeffentlich is False


# --- Niemand wirkt auf das eigene Konto (GP-016, KM-03; CONCEPT F-51) -------------------


@pytest.mark.parametrize('aktion', ['reaktivieren', 'beitrag', 'admin_geben'])
def test_admin_handelt_nicht_am_eigenen_konto(client, aktion):
    chefin = admin_anlegen('chefin')
    chefin.status = Mitgliedsstatus.PAUSIERT
    chefin.save(update_fields=['status'])
    client.force_login(chefin)
    vorher = Mitglied.objects.filter(pk=chefin.pk).values().get()
    antwort = client.post(detail(chefin.pk), {'aktion': aktion}, follow=True)
    assert 'Diese Aktion können nur andere Admins auf Ihr Konto anwenden.' in antwort.content.decode()
    assert Mitglied.objects.filter(pk=chefin.pk).values().get() == vorher
    assert not AuditEintrag.objects.filter(ereignis__typ='verwaltung', ereignis__mitglied=chefin.pk).exists()


def test_admin_setzt_eigene_stufe_und_eigenes_beitragsdatum_nicht(client):
    chefin = admin_anlegen('chefin')
    chefin.identitaetsstufe = Identitaetsstufe.UNGEPRUEFT
    chefin.save(update_fields=['identitaetsstufe'])
    client.force_login(chefin)
    antwort = client.post(detail(chefin.pk), stammdaten(chefin, identitaetsstufe=Identitaetsstufe.PRAESENZ), follow=True)
    assert 'Diese Aktion können nur andere Admins auf Ihr Konto anwenden.' in antwort.content.decode()
    client.post(detail(chefin.pk), stammdaten(chefin, beitrag_zuletzt_am=timezone.localdate().isoformat()))
    chefin.refresh_from_db()
    assert chefin.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT and chefin.geprueft_seit is None
    assert chefin.beitrag_zuletzt_am is None
    assert not AuditEintrag.objects.filter(ereignis__typ='verwaltung', ereignis__mitglied=chefin.pk).exists()


def test_eigener_kontoauszug_verbucht_die_eigene_zeile_nicht(client):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from mitglieder.auth_flows import beitragsreferenz

    chefin = admin_anlegen('chefin')
    chefin.identitaetsstufe = Identitaetsstufe.UNGEPRUEFT
    chefin.save(update_fields=['identitaetsstufe'])
    anna = mitglied_anlegen('anna')
    inhalt = (
        'Buchungsdatum;Teilnehmer;Verwendungszweck;Betrag;Währung\n'
        f'28.08.2026;Chefin;{beitragsreferenz(chefin)} Beitrag;30,00;EUR\n'
        f'28.08.2026;Anna;{beitragsreferenz(anna)} Beitrag;30,00;EUR\n'
    ).encode()
    client.force_login(chefin)
    antwort = client.post(
        reverse('mitglieder:auszug_hochladen'), {'auszug': SimpleUploadedFile('auszug.csv', inhalt)}, follow=True
    )
    chefin.refresh_from_db()
    anna.refresh_from_db()
    assert chefin.beitrag_zuletzt_am is None and chefin.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT
    assert anna.beitrag_zuletzt_am is not None
    assert '1 Zeile mit Ihrer eigenen Beitragsreferenz nicht verbucht' in antwort.content.decode()
    import hashlib

    eintrag = AuditEintrag.objects.filter(ereignis__aktion='auszug_abgleich').get().ereignis
    assert eintrag['pruefsumme'] == hashlib.sha256(inhalt).hexdigest()
    assert eintrag['eigene_uebersprungen'] == 1


# --- Handlung und Audit-Eintrag stehen in einer Klammer (GP-102, KM-17) -----------------


def _audit_kaputt(monkeypatch):
    def kaputt(*args, **kwargs):
        raise RuntimeError('Audit nicht schreibbar')

    monkeypatch.setattr(AuditEintrag, 'anhaengen', kaputt)


def test_ohne_audit_bleibt_der_status_unveraendert(client, monkeypatch):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    _audit_kaputt(monkeypatch)
    with pytest.raises(RuntimeError):
        client.post(detail(anna.pk), {'aktion': 'ausschliessen', 'grund': 'Beschluss S-1.'})
    anna.refresh_from_db()
    assert anna.status == Mitgliedsstatus.AKTIV and anna.is_active is True


def test_ohne_audit_bleiben_die_stammdaten_unveraendert(client, monkeypatch):
    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    _audit_kaputt(monkeypatch)
    with pytest.raises(RuntimeError):
        client.post(detail(anna.pk), stammdaten(anna, vorname='Anneliese'))
    anna.refresh_from_db()
    assert anna.first_name != 'Anneliese'


def test_abschluss_einer_bankkopplung_wird_auditiert(client, monkeypatch):
    from mitglieder import bank
    from mitglieder.models import Bankkopplung

    kopplung = Bankkopplung.objects.create(requisition_id='r1', consent_bis=timezone.localdate() + timedelta(days=180))
    monkeypatch.setattr(bank, 'kopplung_abschliessen', lambda: kopplung)
    client.force_login(admin_anlegen())
    client.get(reverse('mitglieder:bank_rueckkehr'))
    eintrag = AuditEintrag.objects.filter(ereignis__aktion='bank_gekoppelt').get().ereignis
    assert eintrag['typ'] == 'verwaltung' and 'requisition' not in json.dumps(eintrag)


def test_ohne_audit_bleibt_die_bankkopplung_unscharf(client, monkeypatch):
    from mitglieder import bank
    from mitglieder.models import Bankkopplung

    Bankkopplung.objects.create(requisition_id='r1', consent_bis=timezone.localdate())
    monkeypatch.setattr(bank, '_get', lambda pfad, **params: {'status': 'LN', 'accounts': ['k1']})
    client.force_login(admin_anlegen())
    _audit_kaputt(monkeypatch)
    antwort = client.get(reverse('mitglieder:bank_rueckkehr'), follow=True)
    assert 'nicht abgeschlossen' in antwort.content.decode()
    assert Bankkopplung.aktuelle() is None  # Kopplung und Audit gemeinsam oder gar nicht


def test_ohne_audit_des_auszugs_bleibt_nichts_verbucht(client, monkeypatch):
    """Auflage zu GP-102: Verbuchen und Audit-Eintrag „auszug_abgleich“ stehen in einer Klammer."""
    from django.core.files.uploadedfile import SimpleUploadedFile

    from mitglieder.auth_flows import beitragsreferenz
    from mitglieder.models import Beitragseingang

    zahler = mitglied_anlegen('zahler')
    client.force_login(admin_anlegen())
    inhalt = (
        'Buchungsdatum;Teilnehmer;Verwendungszweck;Betrag;Währung\n'
        f'28.08.2026;Zahler;{beitragsreferenz(zahler)} Beitrag;30,00;EUR\n'
    ).encode()
    echt = AuditEintrag.anhaengen

    def nur_der_abgleich_scheitert(ereignis):
        if ereignis.get('aktion') == 'auszug_abgleich':
            raise RuntimeError('Audit nicht erreichbar')
        return echt(ereignis)

    monkeypatch.setattr(AuditEintrag, 'anhaengen', nur_der_abgleich_scheitert)
    with pytest.raises(RuntimeError):
        client.post(reverse('mitglieder:auszug_hochladen'), {'auszug': SimpleUploadedFile('auszug.csv', inhalt)})
    zahler.refresh_from_db()
    assert Beitragseingang.objects.count() == 0 and zahler.beitrag_zuletzt_am is None
    assert not AuditEintrag.objects.filter(ereignis__typ='beitrag').exists()


def _auszug_mit_beitrag(zahler):
    from django.core.files.uploadedfile import SimpleUploadedFile

    from mitglieder.auth_flows import beitragsreferenz

    inhalt = (
        'Buchungsdatum;Teilnehmer;Verwendungszweck;Betrag;Währung\n'
        f'28.08.2026;Zahler;{beitragsreferenz(zahler)} Beitrag;30,00;EUR\n'
    ).encode()
    return {'auszug': SimpleUploadedFile('auszug.csv', inhalt)}


def test_ohne_audit_des_auszugs_geht_keine_beitragsbestaetigung_hinaus(
    client, monkeypatch, django_capture_on_commit_callbacks
):
    """Restauflage zu GP-102: Die Mail „Ihr Mitgliedsbeitrag ist eingegangen“ geht erst nach dem
    Festschreiben hinaus. Scheitert der Audit-Eintrag des Abgleichs, gibt es keine Buchung und keine Mail."""
    from mitglieder.models import Beitragseingang

    zahler = mitglied_anlegen('zahler')
    client.force_login(admin_anlegen())
    echt = AuditEintrag.anhaengen

    def nur_der_abgleich_scheitert(ereignis):
        if ereignis.get('aktion') == 'auszug_abgleich':
            raise RuntimeError('Audit nicht erreichbar')
        return echt(ereignis)

    monkeypatch.setattr(AuditEintrag, 'anhaengen', nur_der_abgleich_scheitert)
    with django_capture_on_commit_callbacks(execute=True), pytest.raises(RuntimeError):
        client.post(reverse('mitglieder:auszug_hochladen'), _auszug_mit_beitrag(zahler))
    assert Beitragseingang.objects.count() == 0
    assert [n.subject for n in mail.outbox] == []


def test_gelingt_der_abgleich_geht_die_beitragsbestaetigung_nach_dem_festschreiben(
    client, django_capture_on_commit_callbacks
):
    zahler = mitglied_anlegen('zahler')
    client.force_login(admin_anlegen())
    with django_capture_on_commit_callbacks(execute=False) as rueckrufe:
        client.post(reverse('mitglieder:auszug_hochladen'), _auszug_mit_beitrag(zahler))
    assert mail.outbox == []  # noch nichts verschickt, solange nicht festgeschrieben ist
    for rueckruf in rueckrufe:
        rueckruf()
    assert [n.subject for n in mail.outbox] == ['Ihr Mitgliedsbeitrag ist eingegangen']
    assert mail.outbox[0].to == [zahler.email]


def test_scheitert_das_audit_meldet_die_verwaltung_keinen_erfolg(monkeypatch):
    """Auflage zu GP-102: Die Erfolgsmeldung stand in der Klammer vor dem Audit-Eintrag — nach
    der Rücknahme meldete die nächste Seite trotzdem „ausgeschlossen“."""
    from django.contrib.messages import get_messages
    from django.test import Client

    anna = mitglied_anlegen()
    client = Client(raise_request_exception=False)
    client.force_login(admin_anlegen())
    _audit_kaputt(monkeypatch)
    antwort = client.post(detail(anna.pk), {'aktion': 'ausschliessen', 'grund': 'Beschluss S-1.'})
    assert antwort.status_code == 500
    assert [str(m) for m in get_messages(antwort.wsgi_request)] == []
    anna.refresh_from_db()
    assert anna.status == Mitgliedsstatus.AKTIV


def test_ausschluss_vermerkt_die_entzogenen_adminrechte_im_audit(client):
    anna = mitglied_anlegen()
    anna.ist_admin = True
    anna.save(update_fields=['ist_admin'])
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), {'aktion': 'ausschliessen', 'grund': 'Beschluss S-1.'})
    anna.refresh_from_db()
    assert anna.ist_admin is False
    eintrag = AuditEintrag.objects.filter(ereignis__aktion='ausschliessen').get().ereignis
    assert eintrag['adminrechte_entzogen'] is True and eintrag['mitglied'] == anna.pk


# --- Einstiege in Parameter- und Quellenverwaltung (GP-105, GP-086) -----------


def test_verwaltung_verweist_auf_parameter_und_quellenverwaltung(client):
    admin = admin_anlegen()
    client.force_login(admin)
    html = client.get(reverse("mitglieder:verwaltung")).content.decode()
    assert f'href="{reverse("parameter:verwaltung")}"' in html
    assert f'href="{reverse("faktenbasis:verwaltung")}"' in html
    admin.identitaetsstufe = "ungeprueft"
    admin.save(update_fields=["identitaetsstufe"])
    html = client.get(reverse("mitglieder:verwaltung")).content.decode()
    assert f'href="{reverse("faktenbasis:verwaltung")}"' not in html  # nur für Berechtigte


# --- Satzungsverweise auf § 4 (GP-176, OCR-16) --------------------------------


def test_verweise_auf_paragraf_4_nennen_nur_vorhandene_absaetze():
    """§ 4 des Satzungsentwurfs 2.5 hat fünf Absätze; der Ausschluss steht in Abs 5."""
    from pathlib import Path

    vorlagen = Path(__file__).parent / "templates"
    zitate = [
        (datei.name, int(absatz))
        for datei in vorlagen.rglob("*.*")
        for absatz in re.findall(r"§ 4 Abs (\d+)", datei.read_text(encoding="utf-8"))
    ]
    assert zitate and all(1 <= absatz <= 5 for _datei, absatz in zitate), zitate


# --- Feldfehler mit dem Feld verknüpft (GP-088, ZB-03) ------------------------


def test_feldfehler_der_stammdaten_sind_verknuepft(client):
    from mitglieder.test_views import verweise_ins_leere

    anna = mitglied_anlegen()
    client.force_login(admin_anlegen())
    antwort = client.post(detail(anna.pk), {
        "aktion": "stammdaten", "email": "keine-adresse", "wohnsitz_art": "oesterreich",
        "gemeinde": "Nirgendwo im Nichts", "identitaetsstufe": "falsch", "beitrag_zuletzt_am": "kein-datum",
    })
    assert antwort.status_code == 200
    assert verweise_ins_leere(antwort.content.decode()) == []


# --- Liste mit Seitenwechsel, Bestand ohne Testkonten (GP-103, KM-18) -------


def _konten_anlegen(anzahl):
    jetzt = timezone.now()
    Mitglied.objects.bulk_create([
        Mitglied(username=f'liste{i}@example.org', email=f'liste{i}@example.org',
                 date_joined=jetzt - timedelta(minutes=i))
        for i in range(anzahl)
    ])


def test_liste_nennt_n_von_m_und_fuehrt_zur_zweiten_seite(client):
    client.force_login(admin_anlegen())
    _konten_anlegen(204)  # mit der Admina 205 Konten
    url = reverse('mitglieder:verwaltung')
    html = client.get(url).content.decode()
    assert '200 von 205' in html
    assert 'href="?seite=2"' in html
    assert html.count('öffnen →') == 200
    zweite = client.get(url, {'seite': 2}).content.decode()
    assert zweite.count('öffnen →') == 5
    assert '201–205 von 205' in zweite
    # die älteste Anlage steht am Ende der zweiten Seite
    assert zweite.rindex('liste203@example.org') > zweite.index('liste199@example.org')


def test_seitenwechsel_behaelt_suche_und_filter(client):
    client.force_login(admin_anlegen())
    _konten_anlegen(205)
    html = client.get(reverse('mitglieder:verwaltung'), {'q': 'liste', 'status': 'aktiv'}).content.decode()
    assert 'href="?q=liste&amp;status=aktiv&amp;seite=2"' in html


def test_bestand_zaehlt_keine_testkonten_und_die_liste_kennzeichnet_sie(client):
    client.force_login(admin_anlegen())
    test = mitglied_anlegen('probe')
    Mitglied.objects.filter(pk=test.pk).update(testkonto=True)
    antwort = client.get(reverse('mitglieder:verwaltung'))
    assert antwort.context['zahlen']['gesamt'] == 1
    assert antwort.context['zahlen']['aktiv'] == 1
    zeile = antwort.content.decode().split(reverse('mitglieder:verwaltung_mitglied', args=[test.pk]), 1)[1]
    assert 'Testkonto' in zeile.split('</tr>', 1)[0]


def test_blaetterzeile_sagt_dass_sie_testkonten_mitzaehlt(client):
    """Gesamtprüfung 0.115.0 (oberflaeche): Oben zählt der Bestand ohne Testkonten, die Blätterzeile
    zählt jede Zeile der Liste — sie sagt deshalb, dass Testkonten darin stehen."""
    client.force_login(admin_anlegen())
    test = mitglied_anlegen('probe')
    Mitglied.objects.filter(pk=test.pk).update(testkonto=True)
    antwort = client.get(reverse('mitglieder:verwaltung'))
    assert antwort.context['zahlen']['gesamt'] == 1
    assert 'Konten 1–2 von 2, Testkonten eingeschlossen, neueste Kontoanlage zuerst' in antwort.content.decode()


# --- GP-188 Punkte 3 und 4 (KM-26) -------------------------------------------


def test_auswahltexte_von_status_und_identitaet_sind_uebersetzbar():
    # Die englische Fassung folgt mit dem Katalog; hier zählt, dass jeder Text durch gettext läuft.
    from django.utils.functional import Promise

    for wahl in (Mitgliedsstatus, Identitaetsstufe):
        for wert in wahl:
            assert isinstance(wert.label, Promise), wert
    assert str(Mitgliedsstatus.PAUSIERT.label) == 'pausiert (Beitrag ausständig)'


def test_unbestaetigtes_konto_hat_den_freischaltknopf_und_wird_nicht_admin(client):
    client.force_login(admin_anlegen())
    offen = Mitglied.objects.create(username='offen@example.org', email='offen@example.org', is_active=False)
    html = client.get(detail(offen.pk)).content.decode()
    assert 'value="reaktivieren"' in html and 'Ohne E-Mail-Bestätigung freischalten' in html
    assert 'value="admin_geben"' not in html
    client.post(detail(offen.pk), {'aktion': 'admin_geben'})
    offen.refresh_from_db()
    assert not offen.ist_admin
    assert not AuditEintrag.objects.filter(ereignis__aktion='admin_geben').exists()
    client.post(detail(offen.pk), {'aktion': 'reaktivieren'})
    offen.refresh_from_db()
    assert offen.is_active and offen.beitritt is not None


# --- Satzungsverweis beim Ausschluss (GP-176, OCR-16) -------------------------


def test_ausschluss_verweist_auf_paragraf_4_absatz_5():
    from pathlib import Path

    from django.conf import settings

    hilfe = Mitglied._meta.get_field('status_grund').help_text
    assert '§ 4 Abs 5' in hilfe and '§ 4 Abs 6' not in hilfe
    konzept = Path(settings.BASE_DIR, 'docs', 'CONCEPT.md').read_text(encoding='utf-8')
    zeile = next(z for z in konzept.splitlines() if z.startswith('| F-51 |'))
    assert '§ 4 Abs 6' not in zeile and '§ 4 Abs 5' in zeile


# --- Wartefrist des Adresswechsels klammert nach unten (GP-021, RVA-01) -------


@pytest.mark.parametrize('wert', ['0', '-1', '-72'])
def test_wartefrist_des_adresswechsels_faellt_nie_unter_eine_stunde(wert):
    from parameter.models import WERTBEREICHE, Parameter

    Parameter.objects.update_or_create(
        schluessel='adresswechsel-wartefrist-stunden',
        defaults={'wert': wert, 'einheit': 'Stunden', 'beschreibung': 'Wartefrist', 'quelle': '§ 4'},
    )
    # Die Untergrenze führt das Register; hebt es sie an, folgt die Lesestelle — und dieser Test.
    untergrenze = max(1, WERTBEREICHE['adresswechsel-wartefrist-stunden'][0])
    assert Adresswechsel.wartefrist_stunden() == untergrenze >= 1


def test_wartefrist_des_adresswechsels_folgt_einem_gueltigen_registerwert():
    from parameter.models import Parameter

    Parameter.objects.update_or_create(
        schluessel='adresswechsel-wartefrist-stunden',
        defaults={'wert': '48', 'einheit': 'Stunden', 'beschreibung': 'Wartefrist', 'quelle': '§ 4'},
    )
    assert Adresswechsel.wartefrist_stunden() == 48


def test_seitengroesse_der_liste_kommt_aus_dem_register(client):
    from parameter.models import Parameter

    Parameter.objects.update_or_create(
        schluessel='verwaltung-liste-seitengroesse', defaults={'wert': '10', 'beschreibung': 'Test', 'quelle': 'Test'}
    )
    client.force_login(admin_anlegen())
    _konten_anlegen(14)  # mit der Admina 15 Konten
    html = client.get(reverse('mitglieder:verwaltung')).content.decode()
    assert '10 von 15' in html and html.count('öffnen →') == 10
    assert client.get(reverse('mitglieder:verwaltung'), {'seite': 2}).content.decode().count('öffnen →') == 5


# ── GP-100, Schlusspflege 0.115.0: jede Verwaltungsseite schickt Gäste mit Ziel zur Anmeldung ───────


@pytest.mark.parametrize('name', [
    'mitglieder:verwaltung', 'mitglieder:verwaltung_beitraege', 'anstoss:verwaltung', 'faktenbasis:verwaltung',
    'gremien:rollen', 'gremien:fachliste_verwaltung', 'mandatare:verwaltung', 'parameter:verwaltung',
])
def test_gast_kommt_von_jeder_verwaltungsseite_mit_ziel_zur_anmeldung(client, name):
    from urllib.parse import urlencode

    pfad = reverse(name)
    antwort = client.get(pfad)
    assert antwort.status_code == 302
    assert antwort['Location'] == reverse('mitglieder:login') + '?' + urlencode({'next': pfad})


def test_schreibende_verwaltungswege_schicken_ohne_ziel_zur_anmeldung(client):
    for name in ('parameter:verwaltung_aktion', 'mandatare:verwaltung_aktion', 'gremien:rollen_aktion'):
        antwort = client.post(reverse(name), {})
        assert antwort.status_code == 302 and antwort['Location'] == reverse('mitglieder:login'), name


def test_keine_umleitung_zur_anmeldung_ohne_ziel_im_code():
    '''Gäste kommen über `mitglieder.anmeldeziel.zur_anmeldung` (oder `login_required`) zur Anmeldung;
    ein blankes `redirect('mitglieder:login')` verlöre bei einem Lesezugriff die aufgerufene Seite.'''
    import pathlib
    import re

    wurzel = pathlib.Path(__file__).resolve().parent.parent
    muster = re.compile(r'''redirect\(\s*(?:reverse\(\s*)?["']mitglieder:login["']''')
    funde = [
        str(datei.relative_to(wurzel))
        for datei in wurzel.rglob('*.py')
        if not set(datei.parts) & {'venv', '.venv', 'migrations'} and not datei.name.startswith('test_')
        and muster.search(datei.read_text(encoding='utf-8'))
    ]
    assert funde == []
