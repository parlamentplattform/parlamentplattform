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
