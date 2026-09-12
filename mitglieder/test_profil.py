"""Profilseite (FB-K5) und Austritt (§ 4 Abs 5): Zugang, Wohnsitze, Anzeigename, Export,
Sitzungen, Austritt mit allen Wirkungen — und was dabei stehen bleibt."""

import json
from datetime import timedelta
from decimal import Decimal

import pytest
from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Adresswechsel, Beitragseingang, Gemeinde, Mitglied, Mitgliedsstatus
from mitglieder.profil import AustrittFehler, austreten
from mitglieder.test_views import botschutz
from verfahren.models import Antrag, AuditEintrag, Stimmabgabe, StimmRegister, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

PROFIL = reverse("mitglieder:profil")
EXPORT = reverse("mitglieder:profil_export")
AUSTRITT = reverse("mitglieder:profil_austritt")
SITZUNGEN = reverse("mitglieder:profil_sitzungen_beenden")


@pytest.fixture(autouse=True)
def _gemeindeverzeichnis(db):
    from django.core.management import call_command

    call_command("gemeinden_laden")


def audit(typ, **filter_):
    return [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis.get("typ") == typ and all(
        e.ereignis.get(k) == v for k, v in filter_.items()
    )]


def profil_speichern(client, **felder):
    daten = {"anzeigename": "", "gemeinde": "", "nebenwohnsitz": ""}
    daten.update(felder)
    return client.post(PROFIL, daten)


def mit_wohnsitz(name="anna"):
    """Ein Mitglied, dessen Wohnsitz vollständig (Name, Bundesland UND Verweis) gesetzt ist —
    `mitglied_anlegen` setzt nur den Namen."""
    m = mitglied_anlegen(name)
    m.wohnsitz = Gemeinde.objects.get(name=m.gemeinde)
    m.save(update_fields=["wohnsitz"])
    return m


# --- Zugang -------------------------------------------------------------------


def test_gast_wird_zum_login_geschickt(client):
    for url in (PROFIL, EXPORT, AUSTRITT):
        antwort = client.get(url)
        assert antwort.status_code == 302 and antwort["Location"].startswith(reverse("mitglieder:login"))
    assert client.post(SITZUNGEN).status_code == 302


def test_pausiertes_mitglied_erreicht_profil_export_und_austritt(client):
    """Export und Austritt sind Rechte des Menschen, keine Mitwirkungsrechte — auch ohne Beitrag."""
    anna = mitglied_anlegen()
    anna.save(update_fields=anna.status_setzen(Mitgliedsstatus.PAUSIERT, "Beitrag ausständig"))
    client.force_login(anna)
    assert client.get(PROFIL).status_code == 200
    assert client.get(EXPORT).status_code == 200
    assert client.get(AUSTRITT).status_code == 200


def test_profilseite_nennt_den_registerwert_des_nebenwohnsitzes(client):
    client.force_login(mitglied_anlegen())
    inhalt = client.get(PROFIL).content.decode()
    assert "region-nebenwohnsitz-zaehlt" in inhalt and "(heute: 0)" in inhalt
    assert "§ 5 Abs 6" in inhalt
    assert 'id="gemeinden"' in inhalt and inhalt.count('list="gemeinden"') == 2
    assert "Benachrichtigungen per E-Mail gibt es noch nicht" in inhalt


# --- Wohnsitz und Nebenwohnsitz -----------------------------------------------


def test_wohnsitzaenderung_setzt_dreiklang_und_auditiert_ohne_ortsnamen(client):
    anna = mitglied_anlegen()
    client.force_login(anna)
    graz = Gemeinde.objects.get(name="Graz")
    antwort = profil_speichern(client, gemeinde="Graz")
    assert antwort.status_code == 302
    anna.refresh_from_db()
    assert (anna.gemeinde, anna.bundesland, anna.wohnsitz) == ("Graz", "steiermark", graz)
    eintraege = audit("profil", aktion="geaendert", mitglied=anna.pk)
    assert len(eintraege) == 1 and eintraege[0]["felder"] == ["wohnsitz"]
    assert "Graz" not in json.dumps(eintraege[0]) and "steiermark" not in json.dumps(eintraege[0])


def test_wohnsitz_leeren_ist_erlaubt(client):
    anna = mitglied_anlegen()
    client.force_login(anna)
    profil_speichern(client, gemeinde="Graz")
    profil_speichern(client, gemeinde="")
    anna.refresh_from_db()
    assert (anna.gemeinde, anna.bundesland, anna.wohnsitz) == ("", "", None)


def test_unbekannte_und_mehrdeutige_gemeinde_werden_abgewiesen(client):
    anna = mitglied_anlegen()
    client.force_login(anna)
    antwort = profil_speichern(client, gemeinde="Atlantis")
    assert antwort.status_code == 200 and "Gemeindeverzeichnis" in antwort.content.decode()
    anna.refresh_from_db()
    assert anna.wohnsitz is None


def test_nebenwohnsitz_speichern_und_leeren(client):
    anna = mit_wohnsitz()
    client.force_login(anna)
    graz = Gemeinde.objects.get(name="Graz")
    profil_speichern(client, gemeinde=anna.gemeinde, nebenwohnsitz=graz.anzeige)
    anna.refresh_from_db()
    assert anna.nebenwohnsitz == graz
    assert anna.gemeinde == "St. Marienkirchen an der Polsenz"  # Hauptwohnsitz unberührt
    eintraege = audit("profil", aktion="geaendert", mitglied=anna.pk)
    assert eintraege[-1]["felder"] == ["nebenwohnsitz"]
    assert "Graz" not in json.dumps(eintraege)
    # Leeren
    profil_speichern(client, gemeinde=anna.gemeinde, nebenwohnsitz="")
    anna.refresh_from_db()
    assert anna.nebenwohnsitz is None
    assert audit("profil", aktion="geaendert", mitglied=anna.pk)[-1]["felder"] == ["nebenwohnsitz"]


def test_nebenwohnsitz_gleich_wohnsitz_wird_abgewiesen(client):
    anna = mitglied_anlegen()
    client.force_login(anna)
    antwort = profil_speichern(client, gemeinde="Graz", nebenwohnsitz="Graz")
    assert antwort.status_code == 200
    anna.refresh_from_db()
    assert anna.nebenwohnsitz is None and anna.wohnsitz is None


def test_ohne_aenderung_kein_audit(client):
    anna = mit_wohnsitz()
    client.force_login(anna)
    profil_speichern(client, gemeinde=anna.gemeinde)
    assert audit("profil", mitglied=anna.pk) == []


# --- Anzeigename ---------------------------------------------------------------


def test_anzeigename_wird_normalisiert_und_auditiert_ohne_wert(client):
    anna = mit_wohnsitz()
    client.force_login(anna)
    profil_speichern(client, anzeigename="  Frau   Holle ", gemeinde=anna.gemeinde)
    anna.refresh_from_db()
    assert anna.pseudonym_oeffentlich == "Frau Holle"
    eintrag = audit("profil", aktion="geaendert", mitglied=anna.pk)[0]
    assert eintrag["felder"] == ["anzeigename"] and "Holle" not in json.dumps(eintrag)


def test_anzeigename_kollidiert_nicht_mit_fremdem_pseudonym_oder_klarnamen(client):
    anna, bert, carla = mit_wohnsitz("anna"), mitglied_anlegen("bert"), mitglied_anlegen("carla")
    bert.pseudonym_oeffentlich = "Nachtfalter"
    bert.save(update_fields=["pseudonym_oeffentlich"])
    carla.first_name, carla.last_name = "Carla", "Kern"
    carla.save(update_fields=["first_name", "last_name"])
    client.force_login(anna)
    for verboten in ("nachtfalter", "Carla Kern", "carla  kern"):
        antwort = profil_speichern(client, anzeigename=verboten, gemeinde=anna.gemeinde)
        assert antwort.status_code == 200 and "schon vergeben" in antwort.content.decode()
        anna.refresh_from_db()
        assert anna.pseudonym_oeffentlich == ""
    profil_speichern(client, anzeigename="Tagpfauenauge", gemeinde=anna.gemeinde)
    anna.refresh_from_db()
    assert anna.pseudonym_oeffentlich == "Tagpfauenauge"
    # Der eigene Klarname bleibt erlaubt, Leeren auch.
    anna.first_name, anna.last_name = "Anna", "Adler"
    anna.save(update_fields=["first_name", "last_name"])
    profil_speichern(client, anzeigename="Anna Adler", gemeinde=anna.gemeinde)
    anna.refresh_from_db()
    assert anna.pseudonym_oeffentlich == "Anna Adler"
    profil_speichern(client, anzeigename="", gemeinde=anna.gemeinde)
    anna.refresh_from_db()
    assert anna.pseudonym_oeffentlich == ""


def test_vorbehaltene_anzeigenamen_werden_abgewiesen(client):
    """„Die Plattform“ ist der Verfasser der Systembeiträge, „Ehemaliges Mitglied n“ der Platzhalter
    Ausgetretener — beides darf sich niemand geben (Verwechslung mit der Plattform selbst)."""
    anna = mit_wohnsitz()
    client.force_login(anna)
    for verboten in ("Die Plattform", "die  plattform", "The Platform", "Ehemaliges Mitglied 7", "ehemaliges mitglied"):
        antwort = profil_speichern(client, anzeigename=verboten, gemeinde=anna.gemeinde)
        assert antwort.status_code == 200 and "vorbehalten" in antwort.content.decode(), verboten
        anna.refresh_from_db()
        assert anna.pseudonym_oeffentlich == ""
    assert audit("profil", mitglied=anna.pk) == []


# --- Datenexport (Art 15/20 DSGVO) --------------------------------------------


def _abstimmung_mit_stimmen(ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    return leute, antrag


def test_export_enthaelt_eigene_daten_und_eigene_stimme_aber_nichts_fremdes(client, ordnung):  # noqa: F811
    leute, antrag = _abstimmung_mit_stimmen(ordnung)
    anna, bert = leute[1], leute[2]
    anna.first_name, anna.last_name = "Anna", "Adler"
    anna.save(update_fields=["first_name", "last_name"])
    Beitragseingang.objects.create(mitglied=anna, betrag=Decimal("12.50"), gebucht_am=timezone.localdate(), umsatz_id="U-1")
    client.force_login(anna)
    client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    c2 = Client()
    c2.force_login(bert)
    c2.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "nein"})

    antwort = client.get(EXPORT)
    assert antwort.status_code == 200
    assert antwort["Content-Type"].startswith("application/json")
    assert antwort["Content-Disposition"] == 'attachment; filename="meine-daten.json"'
    daten = json.loads(antwort.content)
    assert daten["mitglied"] == anna.pk and daten["system_id"] and daten["exportiert_am"]
    assert daten["stammdaten"]["email"] == anna.email and daten["stammdaten"]["nachname"] == "Adler"
    assert daten["wohnsitz"]["name"] == anna.gemeinde
    assert daten["beitraege"] == [{"betrag": "12.50", "gebucht_am": str(timezone.localdate()), "namens_hinweis": False}]
    assert [u["antrag"] for u in daten["unterstuetzungen"]] == [antrag.pk]
    eigene = StimmRegister.objects.get(antrag=antrag, mitglied=anna)
    assert daten["stimmen"] == [
        {
            "antrag": antrag.pk,
            "titel": antrag.titel,
            "pseudonym": eigene.pseudonym.hex,
            "pruefcode": eigene.pruefcode,
            "stimme": "ja",
            "abgegeben_am": daten["stimmen"][0]["abgegeben_am"],
            "zustimmungen": [],
        }
    ]
    roh = antwort.content.decode()
    fremde = StimmRegister.objects.get(antrag=antrag, mitglied=bert)
    assert fremde.pseudonym.hex not in roh and fremde.pruefcode not in roh
    assert bert.email not in roh and "U-1" not in roh
    assert audit("profil", aktion="datenexport", mitglied=anna.pk)
    assert "Adler" not in json.dumps(audit("profil", aktion="datenexport", mitglied=anna.pk))


def test_export_ohne_stimmen_bei_offenem_adresswechsel(client, ordnung):  # noqa: F811
    leute, antrag = _abstimmung_mit_stimmen(ordnung)
    anna, admin = leute[1], leute[2]
    client.force_login(anna)
    client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    Adresswechsel.beantragen(anna, "neu@example.org", admin)
    daten = json.loads(client.get(EXPORT).content)
    assert daten["stimmen"] is None and "Anmeldeadresse" in daten["stimmen_hinweis"]
    eigene = StimmRegister.objects.get(antrag=antrag, mitglied=anna)
    assert eigene.pseudonym.hex not in json.dumps(daten)


def test_export_eines_voll_ausgestatteten_mitglieds_laeuft_durch(client, ordnung):  # noqa: F811
    """Jeder Ordner des Exports wird mit mindestens einer Zeile durchlaufen — sonst prüft nur die
    leere Liste, ob die Feldnamen stimmen."""
    from datetime import date

    from mandatare.models import Aufgabe, Bericht, Berichtsart, Beschluss, Rechenschaft, Stimmverhalten
    from verfahren.models import Beanstandung, Bewerbung, Kategorie, KategorieAbo, Meldung, Reaktion

    anna, admin, antrag, eigener, kommentar, mandat, rolle, fachliste = _voll_ausgestattet(ordnung)
    Reaktion.objects.create(kommentar=kommentar, mitglied=anna, art=Reaktion._meta.get_field("art").choices[0][0])
    Meldung.objects.create(kommentar=kommentar, mitglied=anna, grund=Meldung.Grund.values[0], erlaeuterung="E")
    Beanstandung.objects.create(antrag=antrag, mitglied=anna, text="Stimmt nicht")
    anna.anstoesse.create(text="Ein Anstoß", seite="/")
    Bewerbung.objects.create(antrag=antrag, mitglied=anna, vorstellung="Ich")
    kategorie = Kategorie.objects.create(slug="test-bereich", name="Testbereich")
    KategorieAbo.objects.create(kategorie=kategorie, mitglied=anna)
    Aufgabe.objects.create(mandat=mandat, titel="Sitzung", frist=timezone.now() + timedelta(days=10), sitzungstag=True)
    Bericht.objects.create(mandat=mandat, art=Berichtsart.values[0], monat=date(2026, 10, 1), text="T")
    Rechenschaft.objects.create(
        mandat=mandat,
        gegenstand="Budget",
        sitzung_am=timezone.localdate(),
        beschluss_plattform=Beschluss.values[0],
        stimme=Stimmverhalten.values[0],
        begruendung="B",
    )
    client.force_login(anna)
    antwort = client.get(EXPORT)
    assert antwort.status_code == 200
    daten = json.loads(antwort.content)
    for ordner in ("reaktionen", "meldungen", "beanstandungen", "anstoesse", "bewerbungen", "abos", "kommentare",
                   "filterprofile", "favoriten", "antraege", "rollen", "mandate"):
        assert len(daten[ordner]) >= 1, ordner
    md = daten["mandate"][0]
    assert md["aufgaben"][0]["sitzungstag"] is True and md["berichte"][0]["monat"] == "2026-10-01"
    assert md["rechenschaft"][0]["gegenstand"] == "Budget"
    assert daten["stimmen"] is not None


# --- Sitzungen ----------------------------------------------------------------


def test_alle_anderen_geraete_abmelden_laesst_das_eigene_angemeldet(client):
    anna = mitglied_anlegen()
    client.force_login(anna)
    anderes = Client()
    anderes.force_login(anna)
    assert anderes.get(PROFIL).status_code == 200
    antwort = client.post(SITZUNGEN)
    assert antwort.status_code == 302 and antwort["Location"] == PROFIL
    assert client.get(PROFIL).status_code == 200  # das eigene Gerät bleibt
    assert anderes.get(PROFIL).status_code == 302  # das andere ist abgemeldet
    assert audit("profil", aktion="sitzungen_beendet", mitglied=anna.pk)
    assert client.get(SITZUNGEN).status_code == 405  # nur POST


# --- Austritt (§ 4 Abs 5) -----------------------------------------------------


def _voll_ausgestattet(ordnung):  # noqa: F811
    """Ein Mitglied mit Spuren überall: Antrag, Stimme, Beitrag, Kommentar, Favorit, Profil,
    Mandat, Rolle, Fachliste, Adminrechte."""
    from gremien.models import Fachliste, Gremium, Rolle
    from mandatare.models import Mandat
    from verfahren.models import FilterProfil, Kommentar

    leute, antrag = _abstimmung_mit_stimmen(ordnung)
    anna, admin = leute[1], leute[2]
    anna.first_name, anna.last_name, anna.ist_admin = "Anna", "Adler", True
    anna.save(update_fields=["first_name", "last_name", "ist_admin"])
    eigener = antrag_einbringen(anna, titel="Annas Antrag", wortlaut="W", begruendung="B", ordnung=ordnung)
    Beitragseingang.objects.create(mitglied=anna, betrag=Decimal("20"), gebucht_am=timezone.localdate(), umsatz_id="U-7")
    kommentar = Kommentar.objects.create(antrag=antrag, mitglied=anna, text="Mein Beitrag", phase="abstimmung")
    anna.favoriten.create(antrag=antrag)
    FilterProfil.objects.create(mitglied=anna, name="Meins", aktiv=True)
    anna.lesestaende.create(antrag=antrag)
    from mitglieder.auth_flows import EinmalToken

    EinmalToken.ausstellen(anna, EinmalToken.Zweck.LOGIN)
    mandat = Mandat.objects.create(
        mitglied=anna, bezeichnung="Gemeinderätin", gebiet="Graz", foto=b"PNG-Bytes", foto_typ="image/png"
    )
    rolle = Rolle.objects.create(
        mitglied=anna, gremium=Gremium.KOORDINATIONSRAT, endet_am=timezone.localdate() + timedelta(days=300)
    )
    fachliste = Fachliste.objects.create(mitglied=anna)
    return anna, admin, antrag, eigener, kommentar, mandat, rolle, fachliste


def test_austritt_anonymisiert_deaktiviert_und_laesst_das_verfahren_vollstaendig(client, ordnung):  # noqa: F811
    anna, admin, antrag, eigener, kommentar, mandat, rolle, fachliste = _voll_ausgestattet(ordnung)
    client.force_login(anna)
    client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    assert StimmRegister.objects.filter(antrag=antrag, mitglied=anna).exists()
    wechsel, _klar = Adresswechsel.beantragen(anna, "neu@example.org", admin)  # nach der Stimme: sie sperrt
    stimmen_vorher = list(Stimmabgabe.objects.filter(antrag=antrag).values_list("pseudonym", "stimme"))
    register_vorher = StimmRegister.objects.filter(antrag=antrag).count()
    audit_vorher = AuditEintrag.objects.count()
    pk, alte_email = anna.pk, anna.email

    antwort = client.post(AUSTRITT, {"bestaetigung": "AUSTRITT"})
    assert antwort.status_code == 302 and antwort["Location"] == reverse("verfahren:index")
    assert client.get(PROFIL).status_code == 302  # abgemeldet

    anna = Mitglied.objects.get(pk=pk)
    assert anna.status == Mitgliedsstatus.AUSGETRETEN and anna.status_seit == timezone.localdate()
    assert anna.is_active is False and anna.ist_admin is False and anna.hat_adminrechte is False
    assert (anna.first_name, anna.last_name, anna.email) == ("", "", "")
    assert anna.username == f"ausgetreten-{pk}"
    assert (anna.gemeinde, anna.bundesland, anna.wohnsitz, anna.nebenwohnsitz) == ("", "", None, None)
    assert anna.pseudonym_oeffentlich == f"Ehemaliges Mitglied {pk}"
    assert anna.anzeigename == f"Ehemaliges Mitglied {pk}"
    assert not anna.has_usable_password()
    assert anna.beitritt is not None  # bleibt: kein „nie bestätigtes“ Konto
    # Persönliches weg
    assert anna.filterprofile.count() == 0 and anna.favoriten.count() == 0
    assert anna.lesestaende.count() == 0 and anna.tokens.count() == 0 and anna.kategorie_abos.count() == 0
    # Verfahren vollständig
    assert list(Stimmabgabe.objects.filter(antrag=antrag).values_list("pseudonym", "stimme")) == stimmen_vorher
    assert StimmRegister.objects.filter(antrag=antrag).count() == register_vorher
    assert StimmRegister.objects.filter(antrag=antrag, mitglied=anna).exists()
    assert anna.unterstuetzung_set.filter(antrag=antrag).exists()
    assert Antrag.objects.get(pk=eigener.pk).eingebracht_von_id == pk
    kommentar.refresh_from_db()
    assert kommentar.mitglied_id == pk and kommentar.text == "Mein Beitrag"
    assert anna.beitraege.count() == 1
    assert AuditEintrag.objects.count() > audit_vorher  # nichts gelöscht, nur angehängt
    # Beendet, nicht gelöscht
    mandat.refresh_from_db()
    assert mandat.beendet == timezone.localdate() and anna.ist_mandatar is False
    assert mandat.foto is None and mandat.foto_typ == ""  # Lichtbild geht mit dem Menschen
    assert audit("mandat_foto", mandat=mandat.pk, aktion="entfernt")
    rolle.refresh_from_db()
    assert rolle.beendet_grund == "Austritt" and rolle.aktiv is False
    fachliste.refresh_from_db()
    assert fachliste.gestrichen_am == timezone.localdate() and fachliste.gestrichen_grund == "Austritt"
    assert fachliste.einwilligung_widerrufen_am == timezone.localdate()
    assert fachliste.anzeigename == fachliste.schluessel
    wechsel.refresh_from_db()
    assert wechsel.status == Adresswechsel.Status.WIDERRUFEN and anna.adresswechsel_offen is False
    # Audit: eigener Eintrag und die Beendigungen, ohne Werte
    assert audit("austritt", mitglied=pk) == [{"typ": "austritt", "mitglied": pk, "zeit": audit("austritt", mitglied=pk)[0]["zeit"]}]
    assert audit("mandat_beendet", mandat=mandat.pk) and audit("rolle_beendet", rolle=rolle.pk)
    assert audit("verwaltung", aktion="email_geaendert_widerrufen", mitglied=pk)[0]["anlass"] == "austritt"
    alles = json.dumps([e.ereignis for e in AuditEintrag.objects.all()])
    assert alte_email not in alles and "Adler" not in alles


def test_falsches_bestaetigungswort_tut_nichts(client):
    anna = mitglied_anlegen()
    client.force_login(anna)
    for falsch in ("", "austritt", "Austritt bitte"):
        antwort = client.post(AUSTRITT, {"bestaetigung": falsch})
        assert antwort.status_code == 302 and antwort["Location"] == AUSTRITT
    anna.refresh_from_db()
    assert anna.is_active and anna.status == Mitgliedsstatus.AKTIV and anna.email
    assert audit("austritt") == []
    assert client.get(PROFIL).status_code == 200  # noch angemeldet


def test_fixer_admin_kann_nicht_austreten(client):
    michael = mitglied_anlegen("michael")
    michael.email = "didide@ddoe.at"  # DDOE_FIX_ADMIN (Standardwert)
    michael.save(update_fields=["email"])
    with pytest.raises(AustrittFehler):
        austreten(michael)
    client.force_login(michael)
    assert "kann nicht austreten" in client.get(AUSTRITT).content.decode()
    antwort = client.post(AUSTRITT, {"bestaetigung": "AUSTRITT"})
    assert antwort.status_code == 302
    michael.refresh_from_db()
    assert michael.is_active and michael.email == "didide@ddoe.at" and michael.ist_fixer_admin
    assert audit("austritt") == []


def test_nach_dem_austritt_gibt_es_keinen_anmeldelink_mehr(client):
    anna = mitglied_anlegen()
    alte_email = anna.email
    austreten(anna)
    mail.outbox.clear()
    antwort = client.post(reverse("mitglieder:login"), {"email": alte_email, **botschutz(client)})
    assert antwort.status_code == 200
    assert mail.outbox == []  # weder Anmelde- noch Bestätigungslink
    from mitglieder.views import nie_bestaetigt

    anna.refresh_from_db()
    anna.beitritt = None  # selbst ohne Beitritt gilt das Konto nicht als „nie bestätigt“
    assert nie_bestaetigt(anna) is False


def test_verwaltung_zeigt_ausgetretene_und_reaktiviert_sie_nicht(client):
    anna, chefin = mitglied_anlegen(), mitglied_anlegen("chefin")
    chefin.ist_admin = True
    chefin.save(update_fields=["ist_admin"])
    austreten(anna)
    client.force_login(chefin)
    liste = client.get(reverse("mitglieder:verwaltung")).content.decode()
    assert "ausgetreten" in liste and "<strong>1</strong> ausgetreten" in liste
    detail = reverse("mitglieder:verwaltung_mitglied", args=[anna.pk])
    seite = client.get(detail).content.decode()
    assert 'class="badge badge-still">ausgetreten' in seite
    assert 'value="reaktivieren"' not in seite and 'value="stammdaten"' not in seite
    assert "unbestätigt" not in seite
    client.post(detail, {"aktion": "reaktivieren"})
    anna.refresh_from_db()
    assert anna.is_active is False and anna.status == Mitgliedsstatus.AUSGETRETEN
    client.post(detail, {"aktion": "admin_geben"})
    anna.refresh_from_db()
    assert anna.ist_admin is False
    # Der Zähler „unbestätigt“ zählt Ausgetretene nicht mit
    gefiltert = client.get(reverse("mitglieder:verwaltung") + "?status=ausgetreten").content.decode()
    assert f"ausgetreten-{anna.pk}" not in gefiltert  # Anmeldename bleibt intern
    assert f"Ehemaliges Mitglied {anna.pk}" in gefiltert


def test_profilseiten_ohne_doppelte_ids_und_mit_echten_formularen(client):
    """Grundregel 3: jede Handlung ein echtes POST-Formular; keine doppelten id= im Dokument."""
    import re

    anna = mit_wohnsitz()
    client.force_login(anna)
    for url in (PROFIL, AUSTRITT):
        html = client.get(url).content.decode()
        ids = re.findall(r'\sid="([^"]+)"', html)
        doppelt = {i for i in ids if ids.count(i) > 1}
        assert not doppelt, f"{url}: doppelte id {doppelt}"
    html = client.get(PROFIL).content.decode()
    assert html.count('method="post"') >= 3  # Profil, Sprache, Sitzungen
    assert f'action="{SITZUNGEN}"' in html and f'href="{EXPORT}"' in html and f'href="{AUSTRITT}"' in html
