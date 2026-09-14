"""Post an Mitglieder (FB-K7): Willkommensbrief nach der Bestätigung, Freischaltungsbrief beim
ersten Wechsel von „ungeprüft“ — je Konto genau einmal, Versand als Höflichkeit, Audit ohne Werte."""

import re

import pytest
from django.core import mail
from django.urls import reverse

from mitglieder.auth_flows import beitragsreferenz
from mitglieder.models import Identitaetsstufe, Mitglied, Mitgliedsstatus, beitrag_verbuchen
from mitglieder.post import freischaltung_senden, willkommen_senden
from mitglieder.test_beitraege import eingang
from mitglieder.test_verwaltung import admin_anlegen, detail, stammdaten
from mitglieder.test_views import ANMELDUNG, botschutz, link_aus_mail
from plattform_core.eligibility import monate_addieren
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen  # noqa: F401

pytestmark = pytest.mark.django_db

WILLKOMMEN = "Willkommen — ParlamentPlattform"
FREISCHALTUNG = "Ihre Prüfung ist abgeschlossen — ParlamentPlattform"
BEITRAG = "Ihr Mitgliedsbeitrag ist eingegangen"
BASIS = "https://parlament.ddoe.at"


@pytest.fixture(autouse=True)
def _gemeindeverzeichnis(db):
    from django.core.management import call_command

    call_command("gemeinden_laden")


def post_audit(art=None):
    return [
        e.ereignis
        for e in AuditEintrag.objects.all()
        if e.ereignis.get("typ") == "post" and (art is None or e.ereignis.get("art") == art)
    ]


def registrieren_und_bestaetigen(client, **extra):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **extra, **botschutz(client)})
    link = link_aus_mail(mail.outbox[0])
    client.get(link, follow=True)
    return Mitglied.objects.get(email=ANMELDUNG["email"]), link


# ── Willkommen ────────────────────────────────────────────────────────────────────────────


def test_bestaetigung_schickt_den_willkommensbrief_genau_einmal(client, settings):
    settings.DDOE_UEBERGANGSREGEL = True
    m, link = registrieren_und_bestaetigen(client)
    assert [n.subject for n in mail.outbox] == ["Bitte bestätigen Sie Ihre E-Mail-Adresse — ParlamentPlattform", WILLKOMMEN]
    brief = mail.outbox[1]
    assert brief.to == [m.email] and brief.from_email == settings.DEFAULT_FROM_EMAIL
    text = brief.body
    assert text.startswith("Guten Tag Eva Muster,")
    # Ehrlich gegen `_mitwirkung_gesperrt`: Ungeprüfte lesen alles, einbringen/unterstützen/mitreden erst
    # nach der Freischaltung — der Brief verspricht nichts, was die Plattform am selben Tag verweigert.
    assert "Ab sofort können Sie alles lesen: Anträge, Beratungen und Ergebnisse sind öffentlich (§ 2 Abs 5)." in text
    assert "Einbringen, Unterstützen und Mitreden sowie Stimm- und Wahlrecht setzen eine geprüfte Identität voraus." in text
    assert "Ab sofort können Sie Anträge einbringen" not in text
    assert "Nach der Freischaltung gilt für Abstimmungen und Wahlen: Stimmberechtigt sind Sie ohne Wartefrist" in text
    assert "Übergangsregel des § 4 Abs 4 lit d" in text and "ab sofort" not in text  # Satzungsbezug statt Daten
    assert "geprüfte Identität" in text and "Selbsteinschätzung (§ 4 Abs 3)" in text
    assert beitragsreferenz(m) in text and f"{BASIS}/beitrag/" in text
    assert f"Öffentlich erscheinen Sie als „Mitglied {m.pk}“" in text  # ohne Haken: kein Klarname (§ 5 Abs 3 lit a)
    for pfad in ("/einfuehrung/1/", "/parlament/", "/profil/"):
        assert f"{BASIS}{pfad}" in text
    assert text.rstrip().endswith("Direkte Demokratie Österreich — Wir sind das Werkzeug.")
    assert "<" not in text  # reiner Text, keine Bilder, kein HTML
    m.refresh_from_db()
    assert m.willkommen_post_am is not None
    eintraege = post_audit("willkommen")
    assert len(eintraege) == 1 and eintraege[0]["mitglied"] == m.pk
    assert "example.org" not in str(eintraege) and "Eva" not in str(eintraege)  # ohne Adresse, ohne Inhalt

    # Zweiter Klick auf den Link: Token verbraucht — und selbst ein erneuter Aufruf schreibt keinen Brief.
    client.post(reverse("mitglieder:abmelden"))
    assert client.get(link).status_code == 400
    assert willkommen_senden(m) is False
    assert len(mail.outbox) == 2 and len(post_audit("willkommen")) == 1


def test_willkommensbrief_rechnet_die_anwartschaft_ehrlich_ohne_uebergangsregel(client, settings):
    settings.DDOE_UEBERGANGSREGEL = False
    m, _link = registrieren_und_bestaetigen(client, klarname_oeffentlich="on")
    text = mail.outbox[1].body
    sach = monate_addieren(m.beitritt, 3)
    pers = monate_addieren(m.beitritt, 12)
    assert f"bei Sachfragen ab {sach:%d.%m.%Y}, bei Personenwahlen, Satzungsänderungen und der Auflösung ab {pers:%d.%m.%Y}." in text
    assert "Übergangsregel" not in text
    assert "Stichtag ist jeweils der Beginn einer Abstimmung (§ 4 Abs 4 lit a)" in text
    assert "Öffentlich erscheinen Sie als „Eva Muster“" in text  # mit Haken: der Klarname


def test_willkommensbrief_geht_nicht_an_inaktive_konten():
    m = mitglied_anlegen("zu")
    m.is_active = False
    m.status = Mitgliedsstatus.AUSGESCHLOSSEN
    m.save(update_fields=["is_active", "status"])
    assert willkommen_senden(m) is False and mail.outbox == [] and post_audit() == []
    m.refresh_from_db()
    assert m.willkommen_post_am is None


# ── Freischaltung ─────────────────────────────────────────────────────────────────────────


def test_bankabgleich_schickt_beitragsbestaetigung_und_freischaltung(settings):
    settings.DDOE_UEBERGANGSREGEL = False
    m = mitglied_anlegen("neu", tage=200, stufe=Identitaetsstufe.UNGEPRUEFT)
    m.first_name, m.last_name = "Nina", "Neu"
    m.save(update_fields=["first_name", "last_name"])
    assert beitrag_verbuchen(m, eingang("u1"), namens_ok=True) is True
    assert [n.subject for n in mail.outbox] == [BEITRAG, FREISCHALTUNG]
    text = mail.outbox[1].body
    assert text.startswith("Guten Tag Nina Neu,")
    assert "Ihre Prüfung ist abgeschlossen (Stufe: geprüft (Beitragseingang verbucht))." in text
    pers = monate_addieren(m.beitritt, 12)
    # 200 Tage dabei: Sachfragen schon erreicht, Personenwahlen noch nicht.
    assert f"bei Sachfragen ab sofort, bei Personenwahlen, Satzungsänderungen und der Auflösung ab {pers:%d.%m.%Y}." in text
    assert f"{BASIS}/parlament/" in text and text.rstrip().endswith("Wir sind das Werkzeug.")
    m.refresh_from_db()
    assert m.freischaltung_post_am is not None
    assert [e["mitglied"] for e in post_audit("freischaltung")] == [m.pk]

    # Erneute Verbuchung: Beitragsbestätigung ja, Freischaltung nie wieder.
    assert beitrag_verbuchen(m, eingang("u2"), namens_ok=True) is True
    assert [n.subject for n in mail.outbox] == [BEITRAG, FREISCHALTUNG, BEITRAG]


def test_verwaltung_setzt_praesenz_und_loest_die_freischaltung_aus(client, settings):
    settings.DDOE_UEBERGANGSREGEL = True
    anna = mitglied_anlegen("anna", stufe=Identitaetsstufe.UNGEPRUEFT)
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), stammdaten(anna, identitaetsstufe=Identitaetsstufe.PRAESENZ))
    anna.refresh_from_db()
    assert anna.identitaetsstufe == Identitaetsstufe.PRAESENZ
    assert [n.subject for n in mail.outbox] == [FREISCHALTUNG]
    text = mail.outbox[0].body
    assert "(Stufe: Präsenz-Identitätsfeststellung (§ 13 Abs 2))" in text
    assert "Ab sofort können Sie Anträge einbringen, unterstützen und mitreden (§ 4 Abs 4 lit b)." in text
    assert "ruhen" not in text  # aktives Konto
    assert "ohne Wartefrist" in text and "§ 4 Abs 4 lit d" in text
    assert len(post_audit("freischaltung")) == 1

    # Danach verbucht die Bank: Beitragsbestätigung, aber keine zweite Freischaltung.
    beitrag_verbuchen(anna, eingang("u9"), namens_ok=True)
    assert [n.subject for n in mail.outbox] == [FREISCHALTUNG, BEITRAG]
    # Und ein Stufenwechsel geprüft → eID ist kein Anlass mehr.
    client.post(detail(anna.pk), stammdaten(anna, identitaetsstufe=Identitaetsstufe.EID))
    assert len(mail.outbox) == 2


def test_freischaltung_eines_pausierten_kontos_verspricht_keine_mitwirkung(client, settings):
    """Die Verwaltung stellt die Identität eines pausierten Mitglieds fest (Beitrag ausständig):
    Der Brief sagt, dass die Mitwirkungsrechte ruhen — nicht „ab sofort einbringen“ (F-51)."""
    settings.DDOE_UEBERGANGSREGEL = True
    paul = mitglied_anlegen("paul", stufe=Identitaetsstufe.UNGEPRUEFT)
    paul.status_setzen(Mitgliedsstatus.PAUSIERT, "Beitrag ausständig")
    paul.save()
    client.force_login(admin_anlegen())
    client.post(detail(paul.pk), stammdaten(paul, identitaetsstufe=Identitaetsstufe.PRAESENZ))
    assert [n.subject for n in mail.outbox] == [FREISCHALTUNG]
    text = mail.outbox[0].body
    assert "Ihre Mitwirkungsrechte ruhen allerdings, solange der Mitgliedsbeitrag aussteht (§ 4 Abs 3)" in text
    assert "Ab sofort können Sie Anträge einbringen" not in text
    paul.refresh_from_db()
    assert paul.status == Mitgliedsstatus.PAUSIERT and paul.freischaltung_post_am is not None


def test_vor_der_bestaetigung_festgestellte_identitaet_bekommt_den_brief_mit_der_bestaetigung(client, settings):
    """Die Verwaltung setzt die Stufe, solange das Konto noch inaktiv ist (E-Mail unbestätigt):
    kein Brief an eine unbestätigte Adresse — er kommt mit der Bestätigung, nach dem Willkommen."""
    settings.DDOE_UEBERGANGSREGEL = True
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    eva = Mitglied.objects.get(email=ANMELDUNG["email"])
    assert eva.is_active is False
    admin = admin_anlegen()
    client.force_login(admin)
    client.post(detail(eva.pk), stammdaten(eva, identitaetsstufe=Identitaetsstufe.PRAESENZ))
    eva.refresh_from_db()
    assert eva.identitaetsstufe == Identitaetsstufe.PRAESENZ and eva.freischaltung_post_am is None
    assert [n.subject for n in mail.outbox] == ["Bitte bestätigen Sie Ihre E-Mail-Adresse — ParlamentPlattform"]
    client.post(reverse("mitglieder:abmelden"))
    client.get(link_aus_mail(mail.outbox[0]), follow=True)
    assert [n.subject for n in mail.outbox][1:] == [WILLKOMMEN, FREISCHALTUNG]
    assert sorted(e["art"] for e in post_audit()) == ["freischaltung", "willkommen"]


def test_stufenwechsel_zwischen_gepruerften_stufen_ist_kein_anlass(client):
    anna = mitglied_anlegen("anna", stufe=Identitaetsstufe.GEPRUEFT)
    client.force_login(admin_anlegen())
    client.post(detail(anna.pk), stammdaten(anna, identitaetsstufe=Identitaetsstufe.PRAESENZ))
    anna.refresh_from_db()
    assert anna.identitaetsstufe == Identitaetsstufe.PRAESENZ
    assert mail.outbox == [] and post_audit() == []


def test_versandstoerung_blockiert_die_verbuchung_nicht(monkeypatch):
    def kaputt(*args, **kwargs):
        raise OSError("SMTP nicht erreichbar")

    monkeypatch.setattr("mitglieder.post.send_mail", kaputt)
    m = mitglied_anlegen("still", stufe=Identitaetsstufe.UNGEPRUEFT)
    assert beitrag_verbuchen(m, eingang("u1"), namens_ok=True) is True
    m.refresh_from_db()
    assert m.identitaetsstufe == Identitaetsstufe.GEPRUEFT
    assert m.freischaltung_post_am is not None  # der Versuch zählt — kein zweiter Brief
    assert post_audit() == []  # nichts vorgetäuscht: kein Audit für einen Brief, der nicht ging
    assert freischaltung_senden(m) is False


def test_freischaltung_geht_nicht_an_inaktive_konten():
    m = mitglied_anlegen("weg", stufe=Identitaetsstufe.GEPRUEFT)
    m.is_active = False
    m.status = Mitgliedsstatus.AUSGETRETEN
    m.save(update_fields=["is_active", "status"])
    assert freischaltung_senden(m) is False and mail.outbox == []


# ── Vorlagen ──────────────────────────────────────────────────────────────────────────────


def test_vorlagen_ohne_interne_kennungen_und_immer_deutsch(client, settings):
    from pathlib import Path

    from django.utils import translation

    ordner = Path(__file__).with_name("templates") / "mitglieder" / "post"
    for datei in ("willkommen.txt", "freischaltung.txt"):
        quelle = (ordner / datei).read_text(encoding="utf-8")
        assert not re.search(r"\b(F|FB|A0|ADR)-\d", quelle), datei
        assert "{% load i18n %}" in quelle
    # Wer die Oberfläche auf Englisch nutzt, bekommt den Brief trotzdem auf Deutsch —
    # ein Sprachfeld am Konto gibt es nicht.
    m = mitglied_anlegen("en", stufe=Identitaetsstufe.UNGEPRUEFT)
    with translation.override("en"):
        beitrag_verbuchen(m, eingang("u1"), namens_ok=True)
    assert mail.outbox[1].subject == FREISCHALTUNG and "Guten Tag" in mail.outbox[1].body
    assert "Dear" not in mail.outbox[1].body and "as of now" not in mail.outbox[1].body
