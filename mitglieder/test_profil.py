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
    from mandatare.models import Mandat

    anna, bert, carla = mit_wohnsitz("anna"), mitglied_anlegen("bert"), mitglied_anlegen("carla")
    bert.pseudonym_oeffentlich = "Nachtfalter"
    bert.save(update_fields=["pseudonym_oeffentlich"])
    carla.first_name, carla.last_name = "Carla", "Kern"
    carla.save(update_fields=["first_name", "last_name"])
    Mandat.objects.create(mitglied=carla, bezeichnung="Gemeinderätin", gebiet="Graz")  # öffentliche Funktion
    client.force_login(anna)
    for verboten in ("nachtfalter", "Carla Kern", "carla  kern"):
        antwort = profil_speichern(client, anzeigename=verboten, gemeinde=anna.gemeinde)
        inhalt = antwort.content.decode()
        assert antwort.status_code == 200 and "nicht verfügbar" in inhalt, verboten
        fehler = inhalt.split('<ul class="fehlerliste">')[1].split("</ul>")[0]
        assert "Klarname" not in fehler and "Anzeigenamen" not in fehler  # Meldung neutral
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
    bert = _raete_und_register(anna, admin, antrag, kategorie)
    client.force_login(anna)
    antwort = client.get(EXPORT)
    assert antwort.status_code == 200
    daten = json.loads(antwort.content)
    for ordner in ("reaktionen", "meldungen", "beanstandungen", "anstoesse", "bewerbungen", "abos", "kommentare",
                   "filterprofile", "favoriten", "antraege", "rollen", "mandate", "adresswechsel",
                   "interessenbindungen", "unterstuetzer_voten", "einreichstimmen", "pruefungen",
                   "entwurfsbeitraege", "entwurfsfassungen", "gremienstimmen", "angelegte_beschluesse",
                   "zugewiesene_umsetzungen", "vollzug", "ueberlastungsmeldungen", "parametertests", "ki_laeufe"):
        assert len(daten[ordner]) >= 1, ordner
    md = daten["mandate"][0]
    assert md["aufgaben"][0]["sitzungstag"] is True and md["berichte"][0]["monat"] == "2026-10-01"
    assert md["rechenschaft"][0]["gegenstand"] == "Budget"
    assert daten["stimmen"] is not None
    # Fachliste, Interessenbindungen und Ratsstimmen — der Kern von Befund FP-14
    assert daten["fachliste"]["fachgebiete"] == ["test-bereich"]
    assert daten["fachliste"]["interessenbindungen"] == "Beraterin der Stadtwerke"
    assert daten["fachliste"]["honorare"] == "Vortragshonorar 2025"
    assert daten["interessenbindungen"][0]["text"] == "Ich kenne den Antragsteller"
    assert daten["gremienstimmen"][0] == {
        "beschluss": {"gremium": "koordinationsrat", "nummer": daten["gremienstimmen"][0]["beschluss"]["nummer"],
                      "gegenstand": "Probe", "status": "offen"},
        "option": "dafuer", "begruendung": "Weil.", "abgegeben_am": daten["gremienstimmen"][0]["abgegeben_am"],
        "geaendert_am": None,
    }
    assert daten["unterstuetzer_voten"][0]["wunsch"] == "Kürzer bitte"
    assert daten["pruefungen"][0]["ergebnis"] == "validiert" and daten["vollzug"][0]["status"] == "in_umsetzung"
    assert daten["parametertests"][0]["parameter"] == "gremien-review-tage"
    ki = daten["ki_laeufe"][0]
    assert ki["zweck"] == "einschaetzung" and "eingabe" not in ki and "antwort" not in ki
    # Nichts Fremdes: weder Berts Adresse noch sein Name, weder Hashes noch Token
    roh = antwort.content.decode()
    assert bert.email not in roh and "Bert" not in roh and "Brandstätter" not in roh
    assert "einspruch_hash" not in roh and "token" not in roh.lower() and "wechsel@example.org" not in roh
    assert "Geheime Eingabe" not in roh and "Geheime Antwort" not in roh


def _raete_und_register(anna, bert, antrag, kategorie):
    """Spuren in Räten, Fachliste und Registern — jede Rückbeziehung, die `_gremien_export` abdeckt."""
    from datetime import date

    from gremien.models import (
        EinreichStimme,
        Entwurf,
        EntwurfsBeitrag,
        EntwurfsFassung,
        Fachliste,
        GremienBeschluss,
        GremienStimme,
        Gremium,
        Interessenbindung,
        Pruefung,
        Ueberlastungsmeldung,
        UnterstuetzerVotum,
    )
    from ki.models import KILauf
    from parameter.models import Parameter, ParameterTest
    from verfahren.models import Vollzugseintrag, Vollzugsstatus

    bert.first_name, bert.last_name = "Bert", "Brandstätter"
    bert.save(update_fields=["first_name", "last_name"])
    wechsel, _klar = Adresswechsel.beantragen(anna, "wechsel@example.org", bert)
    wechsel.widerrufen("einspruch")  # widerrufen: sperrt den Stimmregister-Teil nicht
    fachliste = Fachliste.objects.get(mitglied=anna)
    fachliste.interessenbindungen, fachliste.honorare = "Beraterin der Stadtwerke", "Vortragshonorar 2025"
    fachliste.save(update_fields=["interessenbindungen", "honorare"])
    fachliste.fachgebiete.add(kategorie)
    Interessenbindung.objects.create(antrag=antrag, mitglied=anna, text="Ich kenne den Antragsteller")
    entwurf = Entwurf.objects.create(antrag=antrag)
    EntwurfsFassung.objects.create(entwurf=entwurf, nummer=1, wortlaut="Fassung eins", verfasst_von=anna)
    EntwurfsBeitrag.objects.create(entwurf=entwurf, mitglied=anna, text="Ein Beitrag")
    EinreichStimme.objects.create(entwurf=entwurf, mitglied=anna, runde=1, einverstanden=True)
    UnterstuetzerVotum.objects.create(entwurf=entwurf, mitglied=anna, runde=1, annehmen=False, wunsch="Kürzer bitte")
    Pruefung.objects.create(entwurf=entwurf, runde=1, ergebnis=Pruefung.Ergebnis.VALIDIERT, begruendung="Passt.", durch=anna)
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.KOORDINATIONSRAT,
        gegenstand="Probe",
        optionen=[{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}],
        angelegt_von=anna,
        umsetzung_durch=anna,
    )
    GremienStimme.objects.create(beschluss=beschluss, mitglied=anna, option="dafuer", begruendung="Weil.")
    GremienStimme.objects.create(beschluss=beschluss, mitglied=bert, option="dagegen", begruendung="Berts Grund")
    Vollzugseintrag.objects.create(antrag=antrag, status=Vollzugsstatus.IN_UMSETZUNG, vermerk="Läuft", durch=anna)
    Ueberlastungsmeldung.objects.create(stelle="Koordinationsrat", begruendung="Zu viel", gemeldet_von=anna)
    parameter, _neu = Parameter.objects.get_or_create(
        schluessel="gremien-review-tage", defaults={"wert": "7", "beschreibung": "Test", "quelle": "Test"}
    )
    ParameterTest.objects.create(
        parameter=parameter, testwert="3", hypothese="Schneller", messgroesse="x", ende=date(2027, 1, 1),
        rueckweg="zurück", angeordnet_von=anna,
    )
    KILauf.objects.create(
        zweck="einschaetzung", angefordert_von=anna, eingabe="Geheime Eingabe", antwort="Geheime Antwort",
        anbieter="test", modell="t",
    )
    return bert


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
    assert wechsel.neue_email == "" and wechsel.einspruch_hash and wechsel.beantragt_von_id == admin.pk
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


# --- Behebung FP (gegnerische Prüfung S10) ------------------------------------


def test_anzeigename_pruefung_verraet_keine_stille_mitgliedschaft(client):
    """Befund FP-23: Die Kollisionsprüfung darf kein Mitglieder-Orakel sein. Der Klarname eines
    stillen Mitglieds — erst recht eines, das ein Pseudonym führt — ist als Anzeigename erlaubt;
    nur Pseudonyme und die Klarnamen von Mitgliedern mit öffentlicher Funktion sind vergeben."""
    from gremien.models import Fachliste, Gremium, Rolle
    from mandatare.models import Mandat

    anna = mit_wohnsitz("anna")
    still = mitglied_anlegen("still")
    still.first_name, still.last_name = "Erika", "Musterfrau"
    still.save(update_fields=["first_name", "last_name"])
    verborgen = mitglied_anlegen("verborgen")  # tritt öffentlich nur als „Sonnenblume“ auf
    verborgen.first_name, verborgen.last_name, verborgen.pseudonym_oeffentlich = "Max", "Mustermann", "Sonnenblume"
    verborgen.save(update_fields=["first_name", "last_name", "pseudonym_oeffentlich"])
    mandatar = mitglied_anlegen("mandatar")
    mandatar.first_name, mandatar.last_name = "Moritz", "Mandl"
    mandatar.save(update_fields=["first_name", "last_name"])
    Mandat.objects.create(mitglied=mandatar, bezeichnung="Gemeinderat", gebiet="Linz")
    raetin = mitglied_anlegen("raetin")
    raetin.first_name, raetin.last_name = "Rita", "Rat"
    raetin.save(update_fields=["first_name", "last_name"])
    Rolle.objects.create(mitglied=raetin, gremium=Gremium.KOORDINATIONSRAT, endet_am=timezone.localdate() + timedelta(days=30))
    fachfrau = mitglied_anlegen("fachfrau")
    fachfrau.first_name, fachfrau.last_name = "Frida", "Fach"
    fachfrau.save(update_fields=["first_name", "last_name"])
    Fachliste.objects.create(mitglied=fachfrau)
    admin = mitglied_anlegen("admin")
    admin.first_name, admin.last_name, admin.ist_admin = "Adam", "Admin", True
    admin.save(update_fields=["first_name", "last_name", "ist_admin"])
    ex_mandatar = mitglied_anlegen("ex")
    ex_mandatar.first_name, ex_mandatar.last_name = "Egon", "Ehemalig"
    ex_mandatar.save(update_fields=["first_name", "last_name"])
    Mandat.objects.create(mitglied=ex_mandatar, bezeichnung="Gemeinderat", gebiet="Wels", beendet=timezone.localdate())

    client.force_login(anna)
    for vergeben in ("Sonnenblume", "Moritz Mandl", "moritz mandl", "Rita Rat", "Frida Fach", "Adam Admin"):
        antwort = profil_speichern(client, anzeigename=vergeben, gemeinde=anna.gemeinde)
        assert antwort.status_code == 200 and "nicht verfügbar" in antwort.content.decode(), vergeben
    for frei in ("Erika Musterfrau", "Max Mustermann", "Mustermann", "Egon Ehemalig"):
        antwort = profil_speichern(client, anzeigename=frei, gemeinde=anna.gemeinde)
        assert antwort.status_code == 302, frei  # kein Unterschied zu einem Nicht-Mitglied
        anna.refresh_from_db()
        assert anna.pseudonym_oeffentlich == frei


def test_anzeigename_wirkt_sofort_auf_fruehere_antraege(client, ordnung):  # noqa: F811
    """Befund FP-17: Der Hilfetext sagt jetzt, was der Code tut — der Name wird überall live gelesen."""
    anna = mit_wohnsitz("anna")
    anna.first_name, anna.last_name = "Anna", "Adler"
    anna.save(update_fields=["first_name", "last_name"])
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    seite = reverse("verfahren:antrag", args=[antrag.pk])
    assert "Anna Adler" in client.get(seite).content.decode()
    client.force_login(anna)
    profil_speichern(client, anzeigename="Tagpfauenauge", gemeinde=anna.gemeinde)
    inhalt = client.get(seite).content.decode()
    assert "Tagpfauenauge" in inhalt and "Anna Adler" not in inhalt
    daten = json.loads(client.get(EXPORT).content)
    assert daten["stammdaten"]["anzeigename"] == "Tagpfauenauge"
    profil = client.get(PROFIL).content.decode()
    assert "auch bei früheren Beiträgen und in Exporten" in profil
    assert "Bereits veröffentlichte Dokumente behalten" not in profil


def test_profil_hilfetexte_sind_ehrlich_und_der_sprachknopf_gestylt(client):
    """FP-18: Der Satz zum Anzeigenamen verdreht § 5 Abs 3 lit a nicht mehr. FP-11: Der
    Sprachumschalter trägt auf der Karte die Knopfklasse der Nachbarn, nicht das nackte `z`.
    FP-14: Die Exportkarte nennt Fachliste, Interessenbindungen und Räte — und die Ausnahmen."""
    client.force_login(mit_wohnsitz())
    inhalt = client.get(PROFIL).content.decode()
    assert "Ohne Anzeigenamen erscheint heute Ihr Klarname" in inhalt
    assert "nach § 5 Abs 3 lit a soll die Veröffentlichung unter Pseudonym die Regel sein" in inhalt
    karte = inhalt.split('id="sprache"')[1].split("</div>")[0]
    assert 'class="btn-linie klein" lang="en">EN · English</button>' in karte
    assert 'class="z"' not in karte and 'class="sprache"' not in karte
    export = inhalt.split('id="datenexport"')[1].split("</div>")[0]
    assert "Fachlisteneintrag, Interessenbindungen, Stimmen und Beiträge in den Räten" in export
    assert "Nicht enthalten: Anmelde-Token" in export and "Alles, was die Plattform über Sie führt" not in inhalt
    # Die Leiste bleibt bei ihren Klassen (Popover/Panel „z“, Kopfleiste „sprache“).
    leiste = inhalt.split('id="datenexport"')[0]
    assert 'class="z"' in leiste or 'class="sprache"' in leiste


def test_nebenwohnsitz_satz_liest_den_registerwert_bei_0_und_1(client):
    from parameter.models import Parameter

    client.force_login(mitglied_anlegen())
    assert "(heute: 0)" in client.get(PROFIL).content.decode()
    Parameter.objects.update_or_create(
        schluessel="region-nebenwohnsitz-zaehlt", defaults={"wert": "1", "beschreibung": "Test", "quelle": "Test"}
    )
    inhalt = client.get(PROFIL).content.decode()
    assert "(heute: 1)" in inhalt and "(heute: 0)" not in inhalt


def test_export_deckt_jede_rueckbeziehung_des_mitglieds_ab(client, ordnung):  # noqa: F811
    """Wächter zu Befund FP-14: Für jede Rückbeziehung von `Mitglied` (auch die mit
    `related_name="+"`) liefert der Export einen Schlüssel — oder sie steht hier mit Grund als
    Ausnahme. Wer ein Modell mit Mitgliedsbezug ergänzt, muss den Export mitziehen."""
    from mitglieder.auth_flows import EinmalToken  # noqa: F401 — das Modell muss geladen sein

    ORDNER = {
        "Adresswechsel.mitglied": "adresswechsel",
        "Beitragseingang.mitglied": "beitraege",
        "Antrag.eingebracht_von": "antraege",
        "Unterstuetzung.mitglied": "unterstuetzungen",
        "StimmRegister.mitglied": "stimmen",
        "KategorieAbo.mitglied": "abos",
        "Favorit.mitglied": "favoriten",
        "FilterProfil.mitglied": "filterprofile",
        "Bewerbung.mitglied": "bewerbungen",
        "Kommentar.mitglied": "kommentare",
        "Reaktion.mitglied": "reaktionen",
        "Meldung.mitglied": "meldungen",
        "Beanstandung.mitglied": "beanstandungen",
        "Anstoss.nutzer": "anstoesse",
        "Mandat.mitglied": "mandate",
        "Rolle.mitglied": "rollen",
        "EntwurfsFassung.verfasst_von": "entwurfsfassungen",
        "EntwurfsBeitrag.mitglied": "entwurfsbeitraege",
        "EinreichStimme.mitglied": "einreichstimmen",
        "Pruefung.durch": "pruefungen",
        "UnterstuetzerVotum.mitglied": "unterstuetzer_voten",
        "GremienBeschluss.umsetzung_durch": "zugewiesene_umsetzungen",
        "GremienBeschluss.angelegt_von": "angelegte_beschluesse",
        "GremienStimme.mitglied": "gremienstimmen",
        "Fachliste.mitglied": "fachliste",
        "KILauf.angefordert_von": "ki_laeufe",
        "Interessenbindung.mitglied": "interessenbindungen",
        "Ueberlastungsmeldung.gemeldet_von": "ueberlastungsmeldungen",
        "Vollzugseintrag.durch": "vollzug",
        "ParameterTest.angeordnet_von": "parametertests",
    }
    AUSNAHMEN = {
        "EinmalToken.mitglied": "Anmelde-Token: nur Hashes mit Ablauf, Schlüssel und kein Datum über den Menschen",
        "Adresswechsel.beantragt_von": "fremde Vorgänge: Adressen anderer Mitglieder, die dieses Konto als Verwaltung beantragt hat",
        "Adresswechsel.bestaetigt_von": "fremde Vorgänge: Adressen anderer Mitglieder, die dieses Konto als Verwaltung bestätigt hat",
        "WunschVermerk.durch": "Vermerk der Gruppe 2 an einem fremden Kommentar — Verfahrensprotokoll, kein Datum über den Menschen",
        "Hinweis.erledigt_von": "Erledigungsvermerk an einem Hinweis der Zukunftswerkstatt — Verfahrensprotokoll",
        "Lesestand.mitglied": "Lesestände: technischer Zeiger, beim Austritt gelöscht, kein Inhalt",
        "LogEntry.user": "Django-Admin-Protokoll: die Admin-Oberfläche ist nicht eingebunden, die Tabelle bleibt leer",
        "Mitglied_groups.mitglied": "Django-Gruppen: nicht verwendet — Rechte laufen über ist_admin und Rollen",
        "Mitglied_user_permissions.mitglied": "Django-Einzelrechte: nicht verwendet — Rechte laufen über ist_admin und Rollen",
    }
    beziehungen = {
        f"{f.related_model.__name__}.{f.field.name}"
        for f in Mitglied._meta.get_fields(include_hidden=True)
        if f.auto_created and not f.concrete and (f.one_to_many or f.one_to_one or f.many_to_many)
    }
    unbekannt = beziehungen - set(ORDNER) - set(AUSNAHMEN)
    assert not unbekannt, f"Rückbeziehung ohne Export und ohne begründete Ausnahme: {sorted(unbekannt)}"
    veraltet = (set(ORDNER) | set(AUSNAHMEN)) - beziehungen
    assert not veraltet, f"Eintrag ohne Rückbeziehung im Modell: {sorted(veraltet)}"
    anna = mitglied_anlegen()
    client.force_login(anna)
    daten = json.loads(client.get(EXPORT).content)
    fehlend = [schluessel for schluessel in set(ORDNER.values()) if schluessel not in daten]
    assert not fehlend, fehlend


def test_austritt_leert_die_adressen_der_gesamten_wechselhistorie(client, ordnung):  # noqa: F811
    """Befunde FP-1/FP-4: Nach dem Austritt steht keine E-Mail-Adresse mehr in einer Zeile mit
    Bezug zum Mitglied — auch nicht in einem längst wirksam gewordenen Adresswechsel. Wechsel,
    die das Mitglied als Verwaltung für andere geführt hat, bleiben unberührt."""
    from mitglieder.auth_flows import EinmalToken

    anna, admin, zweiter, dritte = (mitglied_anlegen(n) for n in ("anna", "admin", "zweiter", "dritte"))
    for a in (anna, admin, zweiter):
        a.ist_admin = True
        a.save(update_fields=["ist_admin"])
    erste_email = anna.email
    # Ein wirksam gewordener Wechsel: Antrag, Bestätigung durch einen zweiten Admin, Frist um.
    wirksam, _klar = Adresswechsel.beantragen(anna, "neu@example.org", admin)
    assert wirksam.bestaetigen(zweiter)
    wirksam.frist_bis = timezone.now() - timedelta(minutes=1)
    wirksam.save(update_fields=["frist_bis"])
    assert wirksam.wirksam_machen()
    anna.refresh_from_db()
    assert anna.email == "neu@example.org"
    # Ein widerrufener und ein offener Wechsel dazu; ein fremder, den Anna für Dritte beantragt hat.
    widerrufen, _klar = Adresswechsel.beantragen(anna, "widerrufen@example.org", admin)
    widerrufen.widerrufen("einspruch")
    offen, _klar = Adresswechsel.beantragen(anna, "offen@example.org", admin)
    fremd, _klar = Adresswechsel.beantragen(dritte, "dritte-neu@example.org", anna)
    EinmalToken.ausstellen(anna, EinmalToken.Zweck.LOGIN)

    austreten(anna)

    eigene = Adresswechsel.objects.filter(mitglied=anna)
    assert eigene.count() == 3 and list(eigene.values_list("neue_email", flat=True)) == ["", "", ""]
    assert set(eigene.values_list("status", flat=True)) == {"wirksam", "widerrufen"}  # Verfahren bleibt
    wirksam.refresh_from_db()
    assert wirksam.bestaetigt_von_id == zweiter.pk and wirksam.einspruch_hash and wirksam.erledigt_am
    fremd.refresh_from_db()
    assert fremd.neue_email == "dritte-neu@example.org" and fremd.beantragt_von_id == anna.pk
    anna.refresh_from_db()
    assert anna.email == "" and anna.tokens.count() == 0
    # Keine der Adressen steht mehr in irgendeiner Zeile mit Bezug zu Anna — auch nicht im Audit.
    for adresse in (erste_email, "neu@example.org", "widerrufen@example.org", "offen@example.org"):
        assert not Adresswechsel.objects.filter(neue_email=adresse).exists(), adresse
        assert not Mitglied.objects.filter(email=adresse).exists(), adresse
        assert adresse not in json.dumps([e.ereignis for e in AuditEintrag.objects.all()]), adresse


def test_austritt_zieht_bewerbungen_vor_der_abstimmung_zurueck(client, ordnung):  # noqa: F811
    """Befund FP-24: Nach dem Austritt ist eine Bewerbung in einer Kandidatur, die noch nicht
    abgestimmt wird, zurückgezogen (Stempel, kein Löschen, Audit ohne Werte) — sie ist nicht
    mehr wählbar, und die Auszählung ignoriert sie. In der laufenden Abstimmung bleibt sie
    stehen, wie beim freiwilligen Rückzug (Beteiligungsschutz; Nachrücken regelt die
    Verfahrensordnung, § 7 Abs 1 letzter Satz)."""
    from verfahren.models import (
        Antragsart,
        Bewerbung,
        StimmabgabeFehler,
        bewerbung_einreichen,
        bewerbung_zustimmen,
    )

    autor, anna, bert = mitglied_anlegen("autor"), mitglied_anlegen("anna"), mitglied_anlegen("bert")
    waehler = [mitglied_anlegen(f"w{i}") for i in range(2)]
    kandidatur = antrag_einbringen(autor, "Listenreihung Gemeinderat", "Reihung.", "", ordnung, art=Antragsart.MANDAT)
    meine = bewerbung_einreichen(kandidatur, anna, "Ich")
    berts = bewerbung_einreichen(kandidatur, bert, "Er")
    laufend = antrag_einbringen(autor, "Listenreihung Landtag", "Reihung.", "", ordnung, art=Antragsart.MANDAT)
    in_wahl = bewerbung_einreichen(laufend, anna, "Ich auch")
    in_abstimmung_bringen(laufend, waehler)

    austreten(anna)

    meine.refresh_from_db()
    assert meine.zurueckgezogen is True and Bewerbung.objects.filter(pk=meine.pk).exists()
    assert audit("bewerbung_zurueckgezogen", antrag=kandidatur.pk, bewerbung=meine.pk)[0]["anlass"] == "austritt"
    assert "anna" not in json.dumps(audit("bewerbung_zurueckgezogen"))
    in_wahl.refresh_from_db()
    assert in_wahl.zurueckgezogen is False  # laufende Abstimmung: bleibt stehen
    assert audit("bewerbung_zurueckgezogen", antrag=laufend.pk) == []
    # Die Kandidatur kommt in die Abstimmung: Annas Bewerbung ist nicht wählbar und zählt nicht.
    in_abstimmung_bringen(kandidatur, waehler)
    with pytest.raises(StimmabgabeFehler):
        bewerbung_zustimmen(kandidatur, waehler[0], meine)
    assert bewerbung_zustimmen(kandidatur, waehler[0], berts) is True
    client.force_login(waehler[1])
    seite = client.get(reverse("verfahren:antrag", args=[kandidatur.pk])).content.decode()
    assert reverse("verfahren:kandidatur_zustimmen", args=[kandidatur.pk, meine.pk]) not in seite
    assert reverse("verfahren:kandidatur_zustimmen", args=[kandidatur.pk, berts.pk]) in seite
    ergebnis = kandidatur.kandidatur_auszaehlen()
    assert [platz.bewerbung_id for platz in ergebnis.plaetze] == [berts.pk]
