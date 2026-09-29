"""E-Mail-Einwilligung (Anweisung des Gründers 28.9.2026): Haken bei Registrierung und im Profil,
Bestand per Migration auf „ja“, Postaufträge je Anlass, Beitragserinnerung über den Postausgang."""

import importlib
import json
from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from mitglieder.beitraege_views import erinnerung_beauftragen
from mitglieder.models import Mitglied, Mitgliedsstatus, Postauftrag
from mitglieder.postausgang import beauftragen, offene_zustellen, zustellen
from mitglieder.test_profil import PROFIL, audit, mit_wohnsitz, profil_speichern
from mitglieder.test_views import ANMELDUNG, botschutz
from verfahren.models import AuditEintrag, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _gemeindeverzeichnis(db):
    from django.core.management import call_command

    call_command("gemeinden_laden")


def eingewilligt(name="anna", **extra):
    m = mitglied_anlegen(name)
    m.post_einwilligung = True
    for feld, wert in extra.items():
        setattr(m, feld, wert)
    m.save()
    return m


# ── Registrierung ────────────────────────────────────────────────────────────────────────


def test_registrierung_ohne_haken_speichert_keine_einwilligung(client):
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, **botschutz(client)})
    assert Mitglied.objects.get(email=ANMELDUNG["email"]).post_einwilligung is False


def test_registrierung_mit_haken_speichert_die_einwilligung(client):
    seite = client.get(reverse("mitglieder:registrieren")).content.decode()
    assert 'name="post_einwilligung"' in seite and "Die Plattform darf mir E-Mails schicken" in seite
    assert "kommen unabhängig davon" in seite
    client.post(reverse("mitglieder:registrieren"), {**ANMELDUNG, "post_einwilligung": "on", **botschutz(client)})
    assert Mitglied.objects.get(email=ANMELDUNG["email"]).post_einwilligung is True


def test_registrierung_nennt_alles_was_der_haken_erlaubt_und_was_ohne_ihn_kommt(client):
    # Derselbe Haken erlaubt auch Bundesanträge und die Beitragserinnerung — das muss dort stehen, wo
    # eingewilligt wird. Der Hilfetext nennt jede Konto-Nachricht, die ohne Haken kommt.
    from mitglieder.views import RegistrierungsFormular

    feld = RegistrierungsFormular.base_fields["post_einwilligung"]
    label, hilfe = str(feld.label), str(feld.help_text)
    assert "ganz Österreich" in label and "Beitrag" in label and "Zukunftswerkstatt" in label
    for nachricht in ("Anmelde", "Bestätigungs", "Willkommens", "Freischaltungs", "Ausweis",
                      "Beitragseingang", "Einspruchslink", "Vertrauensfrage"):
        assert nachricht in hilfe, nachricht
    seite = client.get(reverse("mitglieder:registrieren")).content.decode()
    assert "ganz Österreich" in seite and "Beitragseingang" in seite


# ── Profil ───────────────────────────────────────────────────────────────────────────────


def test_profil_setzt_und_entfernt_den_haken_und_auditiert_nur_den_feldnamen(client):
    anna = mit_wohnsitz("anna")
    client.force_login(anna)
    seite = client.get(PROFIL).content.decode()
    assert 'id="nachrichten"' in seite and 'type="checkbox" name="post_einwilligung"' in seite
    assert "Ohne Haken:" in seite and "Mit Haken:" in seite

    profil_speichern(client, gemeinde=anna.gemeinde, post_einwilligung="on")
    anna.refresh_from_db()
    assert anna.post_einwilligung is True
    eintrag = audit("profil", aktion="geaendert", mitglied=anna.pk)[-1]
    assert eintrag["felder"] == ["post_einwilligung"]
    assert "true" not in json.dumps(eintrag).lower() and "example.org" not in json.dumps(eintrag)

    profil_speichern(client, gemeinde=anna.gemeinde)  # ohne Haken: Einwilligung zurückgenommen
    anna.refresh_from_db()
    assert anna.post_einwilligung is False
    assert audit("profil", aktion="geaendert", mitglied=anna.pk)[-1]["felder"] == ["post_einwilligung"]

    profil_speichern(client, gemeinde=anna.gemeinde)  # unverändert: kein weiterer Eintrag
    assert len(audit("profil", aktion="geaendert", mitglied=anna.pk)) == 2


def test_profilkarte_nennt_jede_konto_nachricht_und_bundesantraege_nur_wenn_sie_kommen(client):
    # „Ohne Haken: nur …“ muss vollständig sein; „Mit Haken“ nennt ganz Österreich nur, solange das
    # Register Bundesanträge an alle schickt — und verspricht nicht „jeden“ Antrag.
    import re

    from parameter.models import Parameter

    anna = mit_wohnsitz("anna")
    client.force_login(anna)
    seite = client.get(PROFIL).content.decode()
    ohne = re.search(r"Ohne Haken: nur ([^<]*)</p>", seite).group(1)
    for nachricht in ("Anmelde", "Bestätigungs", "Willkommens", "Freischaltungs", "Ausweis",
                      "Beitragseingang", "Einspruchslink", "Vertrauensfrage"):
        assert nachricht in ohne, nachricht
    mit = re.search(r"Mit Haken: ([^<]*)</p>", seite).group(1)
    assert "ganz Österreich" in mit and "Beitragserinnerung" in mit and "jedem" not in mit

    Parameter.objects.update_or_create(
        schluessel="post-neuer-antrag-bund", defaults={"wert": "0", "beschreibung": "Test", "quelle": "Test"}
    )
    mit = re.search(r"Mit Haken: ([^<]*)</p>", client.get(PROFIL).content.decode()).group(1)
    assert "ganz Österreich" not in mit and "Bundesland" in mit and "Beitragserinnerung" in mit


def test_datenexport_traegt_die_einwilligung_und_den_bezug_der_postauftraege(client, ordnung):  # noqa: F811
    anna = eingewilligt("anna")
    antrag = antrag_einbringen(mitglied_anlegen("bert"), **ANTRAG, ordnung=ordnung)
    beauftragen(anna, "neuer_antrag", antrag=antrag)
    client.force_login(anna)
    daten = json.loads(client.get(reverse("mitglieder:profil_export")).content)
    assert daten["stammdaten"]["post_einwilligung"] is True
    assert daten["postauftraege"][0]["art"] == "neuer_antrag"
    assert daten["postauftraege"][0]["bezug"] == f"antrag:{antrag.pk}"
    assert daten["postauftraege"][0]["antrag"] == antrag.pk


# ── Migration: Bestand hat zugestimmt ────────────────────────────────────────────────────


def test_migration_setzt_den_bestand_auf_ja_und_ist_idempotent():
    from django.apps import apps
    from django.db import connection

    migration = importlib.import_module("mitglieder.migrations.0022_post_einwilligung_und_postbezug")
    alt = mitglied_anlegen("alt")
    schon = eingewilligt("schon")
    zweiter = mitglied_anlegen("zweiter")

    class Editor:
        pass

    editor = Editor()
    editor.connection = connection
    assert migration.bestand_einwilligen(apps, editor) == 2
    for m in (alt, schon, zweiter):
        m.refresh_from_db()
        assert m.post_einwilligung is True
    assert migration.bestand_einwilligen(apps, editor) == 0
    eintraege = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis.get("typ") == "post_einwilligung_bestand"]
    assert len(eintraege) == 1 and eintraege[0]["konten"] == 2
    assert "example.org" not in json.dumps(eintraege)


def test_migrationen_0021_und_0022_haben_keinen_rueckweg_und_0022_willigt_nur_einmal_ein():
    # Der Rückweg löschte Spalten mit Daten, die kein erneutes Vorwärts wiederherstellt (eingefrorener
    # Beitragsreferenz-Stamm, Einwilligungsentscheidungen); das erneute Vorwärts machte aus jedem Nein
    # ein Ja. Deshalb: kein Rückweg, und die Bestandseinwilligung läuft genau einmal.
    from django.apps import apps
    from django.db import connection, migrations

    for name in ("0021_referenzstamm_und_testkonten", "0022_post_einwilligung_und_postbezug"):
        modul = importlib.import_module(f"mitglieder.migrations.{name}")
        laeufe = [op for op in modul.Migration.operations if isinstance(op, migrations.RunPython)]
        assert laeufe and all(not op.reversible for op in laeufe), name

    migration = importlib.import_module("mitglieder.migrations.0022_post_einwilligung_und_postbezug")
    alt = mitglied_anlegen("alt")

    class Editor:
        pass

    editor = Editor()
    editor.connection = connection
    assert migration.bestand_einwilligen(apps, editor) == 1
    nein = mitglied_anlegen("nein")  # nach 0.50 registriert, ohne Haken
    Mitglied.objects.filter(pk=alt.pk).update(post_einwilligung=False)  # später im Profil abbestellt
    assert migration.bestand_einwilligen(apps, editor) == 0
    for m in (alt, nein):
        m.refresh_from_db()
        assert m.post_einwilligung is False
    assert sum(e.ereignis.get("typ") == "post_einwilligung_bestand" for e in AuditEintrag.objects.all()) == 1


def test_bestandseinwilligung_gilt_nur_fuer_die_instanz_der_ddoe(settings):
    # Die Aussage des Gründers betrifft die Mitglieder der DDÖ — nicht den Bestand einer Partner-Instanz.
    from django.apps import apps
    from django.db import connection

    migration = importlib.import_module("mitglieder.migrations.0022_post_einwilligung_und_postbezug")
    partner = mitglied_anlegen("partner")

    class Editor:
        pass

    editor = Editor()
    editor.connection = connection
    settings.DDOE_SYSTEM_ID = "xx-test"
    assert migration.bestand_einwilligen(apps, editor) == 0
    partner.refresh_from_db()
    assert partner.post_einwilligung is False
    assert not any(e.ereignis.get("typ") == "post_einwilligung_bestand" for e in AuditEintrag.objects.all())


# ── Postaufträge je Anlass ───────────────────────────────────────────────────────────────


def test_verfahrenspost_braucht_einwilligung_und_bezug(ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen("bert"), **ANTRAG, ordnung=ordnung)
    ohne = mitglied_anlegen("ohne")
    assert not beauftragen(ohne, "neuer_antrag", antrag=antrag)
    assert not beauftragen(ohne, "beitragserinnerung", bezug="jahr:2026")
    assert not Postauftrag.objects.exists()
    mit = eingewilligt("mit")
    with pytest.raises(ValueError):
        beauftragen(mit, "neuer_antrag")
    with pytest.raises(ValueError):
        beauftragen(mit, "beitragserinnerung")
    with pytest.raises(ValueError):
        beauftragen(mit, "rundbrief")
    assert beauftragen(mit, "neuer_antrag", antrag=antrag)
    assert beauftragen(mit, "beitragserinnerung", bezug="jahr:2026")
    assert not beauftragen(mit, "neuer_antrag", antrag=antrag)  # zweite Beauftragung: No-op
    assert not beauftragen(mit, "beitragserinnerung", bezug="jahr:2026")
    assert beauftragen(mit, "beitragserinnerung", bezug="jahr:2027")  # ein anderes Jahr ist ein anderer Anlass
    arten = sorted(Postauftrag.objects.filter(mitglied=mit).values_list("art", "bezug"))
    assert arten == [("beitragserinnerung", "jahr:2026"), ("beitragserinnerung", "jahr:2027"),
                     ("neuer_antrag", f"antrag:{antrag.pk}")]
    assert Postauftrag.objects.get(art="neuer_antrag").antrag_id == antrag.pk
    assert mail.outbox == []  # nur angelegt — zugestellt wird im Hintergrundlauf


@pytest.mark.parametrize("felder", [
    {"testkonto": True}, {"is_active": False}, {"email": ""},
    {"status": Mitgliedsstatus.AUSGETRETEN}, {"status": Mitgliedsstatus.AUSGESCHLOSSEN},
])
def test_unzulaessige_konten_bekommen_auch_mit_einwilligung_nichts(ordnung, felder):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen("bert"), **ANTRAG, ordnung=ordnung)
    m = eingewilligt("gesperrt", **felder)
    assert not beauftragen(m, "neuer_antrag", antrag=antrag)
    assert not beauftragen(m, "beitragserinnerung", bezug="jahr:2026")
    assert not Postauftrag.objects.filter(mitglied=m).exists()


def test_kontobriefe_brauchen_keine_einwilligung(django_capture_on_commit_callbacks):
    m = mitglied_anlegen("konto")
    m.first_name = "Anna"
    m.save()
    assert m.post_einwilligung is False
    with django_capture_on_commit_callbacks(execute=True):
        assert beauftragen(m, "willkommen")
    assert len(mail.outbox) == 1


def test_zurueckgenommene_einwilligung_stoppt_den_versand_und_stempelt_den_auftrag(ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen("bert"), **ANTRAG, ordnung=ordnung)
    m = eingewilligt("widerruf")
    assert beauftragen(m, "neuer_antrag", antrag=antrag)
    m.post_einwilligung = False
    m.save(update_fields=["post_einwilligung"])
    a = Postauftrag.objects.get(mitglied=m)
    assert not zustellen(a.pk)
    a.refresh_from_db()
    assert a.erledigt and a.versandt_am is None and mail.outbox == []
    assert Postauftrag.objects.filter(pk=a.pk).exists()  # gestempelt, nicht gelöscht


def test_dauerhaft_abgewiesene_adresse_endet_nach_der_hoechstzahl_an_versuchen(ordnung, monkeypatch):  # noqa: F811
    # Eine vom Server dauerhaft abgewiesene Adresse darf die Verfahrenspost nicht stündlich und ohne Ende
    # wiederholen: nach der Höchstzahl gescheiterter Versuche ist der Auftrag erledigt (gestempelt, nicht
    # gelöscht) — ohne Versand. Kontobriefe bleiben offen.
    import smtplib

    from mitglieder.postausgang import HOECHSTVERSUCHE_VERFAHRENSPOST

    antrag = antrag_einbringen(mitglied_anlegen("bert"), **ANTRAG, ordnung=ordnung)
    m = eingewilligt("abgewiesen")
    assert beauftragen(m, "neuer_antrag", antrag=antrag)
    konto = Postauftrag.objects.create(mitglied=m, art="willkommen")

    def abweisen(self, fail_silently=False):
        raise smtplib.SMTPRecipientsRefused({m.email: (550, b"5.1.1 User unknown")})

    monkeypatch.setattr("mitglieder.post.EmailMessage.send", abweisen)
    a = Postauftrag.objects.get(mitglied=m, art="neuer_antrag")
    jetzt = timezone.now()
    for _ in range(HOECHSTVERSUCHE_VERFAHRENSPOST + 5):
        assert not zustellen(a.pk, jetzt)
        zustellen(konto.pk, jetzt)
        jetzt += timedelta(minutes=61)
    a.refresh_from_db()
    konto.refresh_from_db()
    assert a.erledigt and a.versandt_am is None and a.versuche == HOECHSTVERSUCHE_VERFAHRENSPOST
    assert Postauftrag.objects.filter(pk=a.pk).exists() and mail.outbox == []
    assert not konto.erledigt and konto.versuche == HOECHSTVERSUCHE_VERFAHRENSPOST + 5
    assert a.pk not in {p.pk for p in Postauftrag.objects.filter(erledigt=False)}


# ── Beitragserinnerung ───────────────────────────────────────────────────────────────────


def test_erinnerung_nur_mit_einwilligung_nach_wartezeit_einmal_je_jahr_und_nie_an_testkonten():
    from parameter.models import Parameter

    heute = timezone.localdate()
    saeumig = eingewilligt("saeumig")
    frisch = eingewilligt("frisch", beitritt=heute - timedelta(days=10))
    ohne = mitglied_anlegen("ohne")
    test = eingewilligt("test", testkonto=True)
    konten = Mitglied.objects.filter(pk__in=[saeumig.pk, frisch.pk, ohne.pk, test.pk])

    assert erinnerung_beauftragen(konten, heute) == (1, 1, 2)
    assert list(Postauftrag.objects.values_list("mitglied_id", "art", "bezug")) == [
        (saeumig.pk, "beitragserinnerung", f"jahr:{heute.year}")
    ]
    assert erinnerung_beauftragen(konten, heute) == (0, 1, 3)  # heuer schon erinnert
    # nächstes Jahr wieder — dann ist auch „frisch“ alt genug
    assert erinnerung_beauftragen(konten, heute + timedelta(days=366)) == (2, 1, 1)
    assert Postauftrag.objects.filter(mitglied=saeumig).count() == 2

    Parameter.objects.update_or_create(
        schluessel="beitrag-erinnerung-fruehestens-tage", defaults={"wert": "5", "beschreibung": "Test", "quelle": "Test"}
    )
    assert erinnerung_beauftragen(konten, heute) == (1, 1, 2)  # frisch ist mit 10 Tagen nun alt genug
    assert Postauftrag.objects.filter(mitglied=frisch).exists()
    assert not Postauftrag.objects.filter(mitglied__in=[ohne, test]).exists()

    assert offene_zustellen() == 4
    assert {n.to[0] for n in mail.outbox} == {saeumig.email, frisch.email}
    brief = mail.outbox[0]
    assert brief.subject == "Erinnerung: Ihr Mitgliedsbeitrag bei der DDÖ"
    assert "/beitrag/" in brief.body and "/profil/#nachrichten" in brief.body and "502117" in brief.body


def test_erinnerung_nur_fuer_admins(client):
    url = reverse("mitglieder:beitrag_erinnern")
    assert client.post(url, {"alle": "1"}).status_code == 302  # Gast: zum Login
    m = eingewilligt("mitglied")
    client.force_login(m)
    assert client.post(url, {"alle": "1"}).status_code == 403
    assert client.get(url).status_code == 403
    assert not Postauftrag.objects.exists()


def test_verwaltungsmeldung_nennt_auftraege_und_uebergangene(client):
    eingewilligt("saeumig")
    mitglied_anlegen("ohne")
    admin = eingewilligt("chefin", ist_admin=True, beitrag_zuletzt_am=timezone.localdate())
    client.force_login(admin)
    inhalt = client.post(reverse("mitglieder:beitrag_erinnern"), {"alle": "1"}, follow=True).content.decode()
    assert "1 Erinnerung(en) beauftragt" in inhalt and "1 Konto/Konten ohne E-Mail-Einwilligung übergangen" in inhalt
    assert Postauftrag.objects.filter(art="beitragserinnerung").count() == 1


# ── Verwaltungsansicht ───────────────────────────────────────────────────────────────────


def test_verwaltungsansicht_zeigt_neue_arten_mit_bezug(client, ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen("bert"), **ANTRAG, ordnung=ordnung)
    person = eingewilligt("person")
    beauftragen(person, "neuer_antrag", antrag=antrag)
    beauftragen(person, "beitragserinnerung", bezug="jahr:2026")
    admin = eingewilligt("chefin", ist_admin=True)
    client.force_login(admin)
    inhalt = client.get(reverse("mitglieder:verwaltung_mitglied", args=[person.pk])).content.decode()
    assert "Neuer Antrag in der Region" in inhalt and f"antrag:{antrag.pk}" in inhalt
    assert f'href="/antrag/{antrag.pk}/"' in inhalt
    assert "Beitragserinnerung" in inhalt and "jahr:2026" in inhalt
    assert inhalt.count("Noch nicht versendet") == 2 and "PDF noch nicht versendet" not in inhalt
