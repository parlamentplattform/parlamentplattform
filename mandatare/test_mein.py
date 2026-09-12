"""Der Bereich des Mandatars (S10, § 7 Abs 3 lit b, Abs 5, Abs 9): Zugang, Instant-Report,
Mandatsfrage aus dem Report, Aufgaben, Berichte, Rechenschaft — und die Audit-Spur dazu."""

from datetime import date, datetime, time, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Aufgabe, Bericht, Berichtsart, Mandat, Rechenschaft
from mandatare.test_mandatare import PNG_MINI, mandat_anlegen
from mitglieder.models import Identitaetsstufe, Mitgliedsstatus
from verfahren.models import Antrag, Antragsart, AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

MEIN = reverse("mandatare:mein")
AKTION = reverse("mandatare:mein_aktion")


def wiener(tag: date, stunde: int = 18, minute: int = 0):
    return timezone.make_aware(datetime.combine(tag, time(stunde, minute)))


def mandatar(client, name="anna", **extra):
    m = mitglied_anlegen(name)
    mandat = mandat_anlegen(m, **extra)
    client.force_login(m)
    return m, mandat


def report(client, mandat, tage=14, **extra):
    daten = {
        "aktion": "report",
        "mandat": mandat.pk,
        "titel": "Soll die Gemeinde dem Radweg zustimmen?",
        "beschreibung": "Der Gemeinderat entscheidet am Sitzungstag.",
        "frist_datum": (timezone.localdate() + timedelta(days=tage)).isoformat(),
        "frist_zeit": "18:30",
        **extra,
    }
    return client.post(AKTION, daten, follow=True)


def typen(typ: str) -> list[dict]:
    return [e.ereignis for e in AuditEintrag.objects.filter(ereignis__typ=typ)]


# ── Rechte-Matrix ─────────────────────────────────────────────────────────────────────────


def test_gast_wird_zur_anmeldung_geschickt(client):
    antwort = client.get(MEIN)
    assert antwort.status_code == 302 and antwort["Location"].startswith("/anmelden/")
    assert client.post(AKTION, {"aktion": "report", "mandat": 1}).status_code == 302


def test_mitglied_ohne_mandat_bekommt_403_mit_weg_zur_liste(client):
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.get(MEIN)
    assert antwort.status_code == 403
    assert 'href="/mandatare/"' in antwort.content.decode()


def test_mandatar_sieht_die_vier_karten(client):
    _, mandat = mandatar(client)
    html = client.get(MEIN).content.decode()
    assert "Mein Mandat" in html
    for kennung in ('id="karte"', 'id="report"', 'id="aufgaben"', 'id="berichte"'):
        assert kennung in html
    assert 'name="aktion" value="report"' in html and 'name="frist_zeit"' in html
    assert f'href="/mandatare/{mandat.pk}/"' in html  # Link zur öffentlichen Seite
    kennungen = [k for k in html.split(' id="')[1:]]
    ids = [k.split('"')[0] for k in kennungen]
    assert len(ids) == len(set(ids)), "doppelte id im Dokument"
    sichtbar = html.split("</style>")[-1]
    assert "{%" not in sichtbar and "{{" not in sichtbar  # kein Vorlagen-Rohmaterial


def test_pausierter_mandatar_liest_aber_schreibt_nicht(client):
    m, mandat = mandatar(client)
    m.status = Mitgliedsstatus.PAUSIERT
    m.save(update_fields=["status"])
    html = client.get(MEIN).content.decode()
    assert "Mein Mandat" in html and 'name="aktion" value="report"' not in html
    antwort = client.post(AKTION, {"aktion": "vorstellung", "mandat": mandat.pk, "vorstellung": "x"})
    assert antwort.status_code == 403  # Meldung wie beim Einbringen (mitwirkung_ruht)
    mandat.refresh_from_db()
    assert mandat.vorstellung == ""


def test_ungeprueftes_konto_liest_mit_eigenem_hinweis(client):
    """Identität ungeprüft: lesen ja, schreiben nein — und Band UND Leerzustand der Report-Karte
    nennen den wahren Grund, nicht den Beitragsstatus (Ehrlichkeit der Texte)."""
    m, mandat = mandatar(client)
    m.identitaetsstufe = Identitaetsstufe.UNGEPRUEFT
    m.save(update_fields=["identitaetsstufe"])
    html = client.get(MEIN).content.decode()
    assert "Identität ist noch nicht geprüft" in html and "Mitwirkung ruht" not in html
    assert 'name="aktion" value="report"' not in html
    assert "Schreiben geht nach der Bestätigung." in html and "aktiven Status" not in html
    # pausiert mit geprüfter Identität: der andere Grund, an beiden Stellen
    m.identitaetsstufe = Identitaetsstufe.GEPRUEFT
    m.status = Mitgliedsstatus.PAUSIERT
    m.save(update_fields=["identitaetsstufe", "status"])
    html = client.get(MEIN).content.decode()
    assert "Mitwirkung ruht" in html and "Schreiben ruht bis zum aktiven Status." in html
    assert "nach der Bestätigung" not in html
    assert client.post(AKTION, {"aktion": "vorstellung", "mandat": mandat.pk, "vorstellung": "x"}).status_code == 403


def test_fremdes_mandat_ist_tabu(client):
    _, fremd = mandatar(client, name="carla")
    anna, _ = mandatar(client, name="anna")
    assert client.get(reverse("mandatare:mein_mandat", args=[fremd.pk])).status_code == 403
    antwort = client.post(AKTION, {"aktion": "vorstellung", "mandat": fremd.pk, "vorstellung": "übernommen"})
    assert antwort.status_code == 403
    fremd.refresh_from_db()
    assert fremd.vorstellung == ""


def test_beendetes_mandat_oeffnet_den_bereich_nach_der_nachfrist_nicht(client):
    m, mandat = mandatar(client, beendet=timezone.localdate() - timedelta(days=8))
    assert client.get(MEIN).status_code == 403
    assert client.get(reverse("mandatare:mein_mandat", args=[mandat.pk])).status_code == 403
    for aktion in ("vorstellung", "rechenschaft", "sammelbericht", "monatsbericht", "report"):
        assert client.post(AKTION, {"aktion": aktion, "mandat": mandat.pk}).status_code == 403


def test_nachfrist_erlaubt_nur_rechenschaft_und_berichte(client):
    """Mandat vor drei Tagen beendet, Sitzungstag zwei Tage davor: Der Bereich bleibt für die
    Nachfrist offen (Band nennt Ende und Frist), Rechenschaft und Sammelbericht gehen noch,
    Report, Foto und Vorstellung nicht mehr; Sitzungstage nach dem Ende zählen nicht."""
    ende = timezone.localdate() - timedelta(days=3)
    m, mandat = mandatar(client, beendet=ende)
    vorher = Aufgabe.objects.create(
        mandat=mandat, titel="Letzte Sitzung", frist=wiener(ende - timedelta(days=2)), sitzungstag=True
    )
    Aufgabe.objects.create(mandat=mandat, titel="Sitzung danach", frist=wiener(ende + timedelta(days=1)), sitzungstag=True)
    antwort = client.get(MEIN)
    assert antwort.status_code == 200
    html = antwort.content.decode()
    assert f"Ihr Mandat endete am {ende:%d.%m.%Y}" in html
    assert f"noch bis {(ende + timedelta(days=7)):%d.%m.%Y} möglich" in html
    assert 'name="aktion" value="rechenschaft"' in html and 'name="aktion" value="sammelbericht"' in html
    assert 'name="aktion" value="report"' not in html and 'name="aktion" value="foto"' not in html
    assert "Mandat beendet — kein neuer Report." in html
    assert "Letzte Sitzung" in html
    # Sitzungstag nach dem Ende: keine Pflicht, kein Ausstand
    assert [p["aufgabe"].pk for p in mandat.offene_pflichten()["rechenschaften"]] == [vorher.pk]

    assert client.post(AKTION, {"aktion": "vorstellung", "mandat": mandat.pk, "vorstellung": "x"}).status_code == 403
    assert report(client, mandat).status_code == 403 and mandat.aufgaben.count() == 2
    client.post(AKTION, {"aktion": "sammelbericht", "mandat": mandat.pk, "aufgabe": vorher.pk, "text": "Bericht."})
    client.post(
        AKTION,
        {"aktion": "rechenschaft", "mandat": mandat.pk, "aufgabe": vorher.pk, "gegenstand": "",
         "beschluss_plattform": "keiner", "stimme": "dafuer", "begruendung": "Nachgetragen."},
    )
    assert mandat.berichte.count() == 1 and mandat.rechenschaft.count() == 1
    pflichten = mandat.offene_pflichten()
    assert pflichten["rechenschaften"] == [] and pflichten["sammelberichte"] == []


def test_mehrere_mandate_fuehren_zur_auswahl(client):
    m, gemeinde = mandatar(client)
    land = mandat_anlegen(m, bezeichnung="Landtag", ebene="land", gebiet="Oberösterreich")
    html = client.get(MEIN).content.decode()
    assert f'href="/mandatare/mein/{gemeinde.pk}/"' in html and f'href="/mandatare/mein/{land.pk}/"' in html
    assert client.get(reverse("mandatare:mein_mandat", args=[land.pk])).status_code == 200


# ── Instant-Report und Mandatsfrage ───────────────────────────────────────────────────────


def test_report_ohne_abstimmung_traegt_zeitpunkt_und_sitzungstag(client, ordnung):  # noqa: F811
    _, mandat = mandatar(client)
    antwort = report(client, mandat, tage=3, sitzungstag="on")
    assert antwort.status_code == 200
    aufgabe = mandat.aufgaben.get()
    assert aufgabe.titel == "Soll die Gemeinde dem Radweg zustimmen?" and aufgabe.sitzungstag is True
    lokal = timezone.localtime(aufgabe.frist)
    assert (lokal.hour, lokal.minute) == (18, 30) and lokal.date() == timezone.localdate() + timedelta(days=3)
    assert aufgabe.antrag is None
    assert Antrag.objects.count() == 0
    (eintrag,) = typen("instant_report")
    assert eintrag["mandat"] == mandat.pk and eintrag["aufgabe"] == aufgabe.pk
    assert "titel" not in eintrag and "beschreibung" not in eintrag
    html = antwort.content.decode()
    assert "Report veröffentlicht" in html and "Sitzungstag" in html


def test_report_ohne_uhrzeit_endet_um_23_59(client):
    _, mandat = mandatar(client)
    report(client, mandat, frist_zeit="")
    lokal = timezone.localtime(mandat.aufgaben.get().frist)
    assert (lokal.hour, lokal.minute) == (23, 59)


def test_report_mit_abstimmung_eroeffnet_die_mandatsfrage(client, ordnung):  # noqa: F811
    for i in range(3):
        mitglied_anlegen(f"w{i}")
    _, mandat = mandatar(client)
    antwort = report(client, mandat, tage=14, sitzungstag="on", abstimmung="on")
    aufgabe = mandat.aufgaben.get()
    antrag = aufgabe.antrag
    assert antrag is not None and antrag.art == Antragsart.MANDATSFRAGE and antrag.phase == "abstimmung"
    assert antrag.ebene == "gemeinde" and antrag.gebiet == mandat.gebiet
    html = antwort.content.decode()
    assert "Mandatsfrage eröffnet" in html and f'href="/antrag/{antrag.pk}/"' in html
    assert typen("mandatsfrage_eroeffnet")[0]["aufgabe"] == aufgabe.pk
    # der Bereich verlinkt die laufende Abstimmung aus der Aufgabe
    assert f"/antrag/{antrag.pk}/#abstimmen" in html


def test_zu_knappe_frist_laesst_den_report_ohne_abstimmung(client, ordnung):  # noqa: F811
    _, mandat = mandatar(client)
    antwort = report(client, mandat, tage=3, abstimmung="on")
    aufgabe = mandat.aufgaben.get()
    assert aufgabe.antrag is None and Antrag.objects.count() == 0
    html = antwort.content.decode()
    assert "ohne Abstimmung" in html and "mindestens 7 Tage" in html
    assert typen("instant_report") and not typen("mandatsfrage_eroeffnet")


def test_ueberlanger_titel_wird_gekuerzt_auch_in_der_mandatsfrage(client, ordnung):  # noqa: F811
    """Ein POST am maxlength vorbei: Report und Mandatsfrage tragen den gekürzten Titel
    (Antrag.titel fasst 200 Zeichen — PostgreSQL würde sonst abbrechen)."""
    _, mandat = mandatar(client)
    report(client, mandat, tage=14, abstimmung="on", titel="Frage? " * 60)
    aufgabe = mandat.aufgaben.get()
    assert len(aufgabe.titel) == 120 and aufgabe.antrag is not None
    assert aufgabe.antrag.titel == aufgabe.titel


def test_ohne_verfahrensordnung_bleibt_es_beim_report(client):
    _, mandat = mandatar(client)
    html = report(client, mandat, tage=14, abstimmung="on").content.decode()
    assert mandat.aufgaben.count() == 1 and Antrag.objects.count() == 0
    assert "keine Verfahrensordnung" in html


def test_report_braucht_titel_und_gueltiges_datum(client):
    _, mandat = mandatar(client)
    html = report(client, mandat, titel="").content.decode()
    assert "braucht einen Titel" in html
    html = report(client, mandat, frist_datum="morgen").content.decode()
    assert "gültiges Datum" in html
    assert mandat.aufgaben.count() == 0


def test_report_mit_datum_am_rand_des_wertebereichs_endet_in_einer_meldung(client):
    """Jahr 1 und Jahr 9999 laufen bei der UTC-Umrechnung über — statt 500 kommt die
    Datumsmeldung; das Formular kommt mit den Eingaben zurück."""
    _, mandat = mandatar(client)
    for datum, zeit in (("0001-01-01", "00:00"), ("9999-12-31", "23:59"), ("1999-12-31", ""), ("2201-01-01", "")):
        antwort = report(client, mandat, frist_datum=datum, frist_zeit=zeit, beschreibung="Bleibt stehen.")
        assert antwort.status_code == 200
        html = antwort.content.decode()
        assert "gültiges Datum" in html and "Bleibt stehen." in html
        assert 'value="Soll die Gemeinde dem Radweg zustimmen?"' in html
    assert mandat.aufgaben.count() == 0


def test_doppelter_report_post_legt_nichts_zweites_an(client, ordnung):  # noqa: F811
    """Doppelklick oder Zurück + neu senden: derselbe Report (Titel, Frist) binnen kurzer Zeit
    erzeugt keine zweite Aufgabe und keine zweite Mandatsfrage — nur eine Meldung mit Link."""
    for i in range(2):
        mitglied_anlegen(f"w{i}")
    _, mandat = mandatar(client)
    report(client, mandat, tage=14, abstimmung="on")
    html = report(client, mandat, tage=14, abstimmung="on").content.decode()
    assert mandat.aufgaben.count() == 1
    assert Antrag.objects.filter(art=Antragsart.MANDATSFRAGE).count() == 1
    assert "bereits angelegt" in html and f'href="/antrag/{mandat.aufgaben.get().antrag_id}/"' in html
    assert len(typen("instant_report")) == 1
    # ein anderer Titel ist ein neuer Report
    report(client, mandat, tage=14, titel="Zweite Frage?")
    assert mandat.aufgaben.count() == 2


def test_status_foto_vorstellung_werden_auditiert_ohne_werte(client):
    _, mandat = mandatar(client)
    aufgabe = Aufgabe.objects.create(mandat=mandat, titel="Protokolle", frist=timezone.now() + timedelta(days=2))
    client.post(AKTION, {"aktion": "aufgabe_status", "mandat": mandat.pk, "aufgabe": aufgabe.pk, "status": "erledigt"})
    aufgabe.refresh_from_db()
    assert aufgabe.status == "erledigt"
    (e,) = typen("mandats_aufgabe_status")
    assert e["mandat"] == mandat.pk and e["aufgabe"] == aufgabe.pk and "status" not in e

    client.post(AKTION, {"aktion": "vorstellung", "mandat": mandat.pk, "vorstellung": "Offene Sitzungen. " * 200})
    mandat.refresh_from_db()
    assert 0 < len(mandat.vorstellung) <= 2000
    (e,) = typen("mandat_vorstellung")
    assert e == {"typ": "mandat_vorstellung", "mandat": mandat.pk, "zeit": e["zeit"]}

    from django.core.files.uploadedfile import SimpleUploadedFile

    client.post(
        AKTION,
        {"aktion": "foto", "mandat": mandat.pk, "foto": SimpleUploadedFile("ich.png", PNG_MINI, "image/png")},
    )
    mandat.refresh_from_db()
    assert mandat.foto_typ == "image/png"
    assert typen("mandat_foto")[0]["mandat"] == mandat.pk

    html = client.post(
        AKTION,
        {"aktion": "foto", "mandat": mandat.pk, "foto": SimpleUploadedFile("x.gif", b"GIF89a", "image/gif")},
        follow=True,
    ).content.decode()
    assert "nicht erkannt" in html


def test_fremde_aufgabe_kann_nicht_umgestellt_werden(client):
    _, fremd = mandatar(client, name="carla")
    aufgabe = Aufgabe.objects.create(mandat=fremd, titel="Fremd")
    _, meins = mandatar(client, name="anna")
    antwort = client.post(AKTION, {"aktion": "aufgabe_status", "mandat": meins.pk, "aufgabe": aufgabe.pk, "status": "erledigt"})
    assert antwort.status_code == 404
    aufgabe.refresh_from_db()
    assert aufgabe.status == "offen"
    # verformte Kennung: sauberer 404 statt ValueError
    antwort = client.post(AKTION, {"aktion": "aufgabe_status", "mandat": meins.pk, "aufgabe": "abc", "status": "erledigt"})
    assert antwort.status_code == 404


# ── Sitzungstag: Pflichten, Sammelbericht, Rechenschaft ───────────────────────────────────


def sitzungstag_vorbei(mandat, tage=10):
    return Aufgabe.objects.create(
        mandat=mandat,
        titel="Gemeinderatssitzung: Radweg",
        frist=timezone.now() - timedelta(days=tage),
        sitzungstag=True,
    )


def test_nach_dem_sitzungstag_zeigt_der_bereich_die_pflichten(client):
    _, mandat = mandatar(client)
    sitzung = sitzungstag_vorbei(mandat, tage=10)
    html = client.get(MEIN).content.decode()
    assert "Sammelbericht schreiben" in html and "Rechenschaft eintragen" in html
    assert "ausständig seit 3 Tagen" in html  # Sitzungstag vor 10 Tagen, Frist 7 Tage
    assert f"?aufgabe={sitzung.pk}#rechenschaft" in html
    # innerhalb der sieben Tage: Zähler statt Ausstand
    sitzung.frist = timezone.now() - timedelta(days=2)
    sitzung.save(update_fields=["frist"])
    html = client.get(MEIN).content.decode()
    assert "noch 5 Tage" in html and "ausständig" not in html


def test_sammelbericht_und_rechenschaft_schliessen_die_pflichten(client):
    m, mandat = mandatar(client)
    sitzung = sitzungstag_vorbei(mandat)
    client.post(AKTION, {"aktion": "sammelbericht", "mandat": mandat.pk, "aufgabe": sitzung.pk, "text": "Beschlossen: Radweg kommt."})
    bericht = mandat.berichte.get()
    assert bericht.art == Berichtsart.SAMMELBERICHT and bericht.aufgabe == sitzung
    assert bericht.lage().status == "verspaetet"
    (e,) = typen("mandatsbericht")
    assert e["bericht"] == bericht.pk and e["art"] == "sammelbericht" and "text" not in e

    client.post(
        AKTION,
        {
            "aktion": "rechenschaft",
            "mandat": mandat.pk,
            "aufgabe": sitzung.pk,
            "gegenstand": "",
            "sitzung_am": "2020-01-01",  # wird vom Sitzungstag überschrieben
            "beschluss_plattform": "angenommen",
            "stimme": "dagegen",
            "begruendung": "Die Finanzierung war nicht gesichert.",
        },
    )
    eintrag = mandat.rechenschaft.get()
    assert eintrag.aufgabe == sitzung and eintrag.sitzung_am == sitzung.sitzungstag_datum
    assert eintrag.gegenstand == sitzung.titel  # leerer Gegenstand → Titel des Reports
    assert eintrag.beschluss_plattform == "angenommen" and eintrag.stimme == "dagegen" and eintrag.weicht_ab
    (e,) = typen("rechenschaft")
    assert e["aufgabe"] == sitzung.pk and e["rechenschaft"] == eintrag.pk and "begruendung" not in e

    pflichten = mandat.offene_pflichten()
    assert pflichten["sammelberichte"] == [] and pflichten["rechenschaften"] == []
    html = client.get(MEIN).content.decode()
    assert "Sammelbericht liegt vor" in html and "Rechenschaft liegt vor" in html
    assert "weicht ab" in html


def test_rechenschaft_frei_braucht_gegenstand_sitzungstag_und_begruendung(client):
    _, mandat = mandatar(client)
    daten = {"aktion": "rechenschaft", "mandat": mandat.pk, "aufgabe": "", "gegenstand": "Budget 2027",
             "sitzung_am": "2026-09-10", "beschluss_plattform": "keiner", "stimme": "enthalten", "begruendung": ""}
    html = client.post(AKTION, daten, follow=True).content.decode()
    assert "Begründung" in html and Rechenschaft.objects.count() == 0
    html = client.post(AKTION, {**daten, "begruendung": "Unklare Zahlen.", "sitzung_am": ""}, follow=True).content.decode()
    assert "Sitzungstag" in html and Rechenschaft.objects.count() == 0
    client.post(AKTION, {**daten, "begruendung": "Unklare Zahlen."})
    eintrag = Rechenschaft.objects.get()
    assert eintrag.sitzung_am == date(2026, 9, 10) and eintrag.aufgabe is None and eintrag.antrag is None


def test_rechenschaft_formular_behaelt_die_eingabe_beim_fehler(client):
    """Ohne Skript, ohne Verlust: Fehlt der Sitzungstag, kommt das Formular mit Gegenstand,
    Stimme, Beschluss und der ganzen Begründung zurück — samt Meldung, ohne Umleitung."""
    _, mandat = mandatar(client)
    begruendung = "Eine lange öffentliche Begründung. " * 40
    antwort = client.post(
        AKTION,
        {"aktion": "rechenschaft", "mandat": mandat.pk, "aufgabe": "", "gegenstand": "Budget 2027",
         "sitzung_am": "", "beschluss_plattform": "abgelehnt", "stimme": "enthalten", "begruendung": begruendung},
    )
    assert antwort.status_code == 200 and Rechenschaft.objects.count() == 0
    html = antwort.content.decode()
    assert "Bitte den Sitzungstag angeben." in html
    assert begruendung.strip() in html and 'value="Budget 2027"' in html
    assert '<option value="enthalten" selected>' in html and '<option value="abgelehnt" selected>' in html
    assert '<details class="klappe" id="rechenschaft" open>' in html


def test_freier_sitzungstag_darf_nicht_in_der_zukunft_liegen(client):
    """Ein Sitzungstag im Jahr 9999 legte das JSON-Register lahm (Fristrechnung läuft über);
    Rechenschaft gibt es ohnehin nur über Abstimmungen, die stattgefunden haben."""
    _, mandat = mandatar(client)
    daten = {"aktion": "rechenschaft", "mandat": mandat.pk, "aufgabe": "", "gegenstand": "G",
             "beschluss_plattform": "keiner", "stimme": "dafuer", "begruendung": "B"}
    for tag in ("9999-12-31", (timezone.localdate() + timedelta(days=1)).isoformat()):
        html = client.post(AKTION, {**daten, "sitzung_am": tag}, follow=True).content.decode()
        assert "darf nicht in der Zukunft liegen" in html
    assert Rechenschaft.objects.count() == 0
    client.post(AKTION, {**daten, "sitzung_am": timezone.localdate().isoformat()})  # heute geht
    assert Rechenschaft.objects.count() == 1
    assert client.get(reverse("mandatare:rechenschaft_json")).status_code == 200


def test_rechenschaft_zur_mandatsfrage_uebernimmt_den_beschluss(client, ordnung):  # noqa: F811
    from verfahren.models import mandatsfrage_eroeffnen, stimme_abgeben

    waehler = [mitglied_anlegen(f"w{i}") for i in range(2)]
    m, mandat = mandatar(client)
    sitzung = Aufgabe.objects.create(
        mandat=mandat, titel="Radweg", frist=timezone.now() + timedelta(days=14), sitzungstag=True
    )
    antrag = mandatsfrage_eroeffnen(mandat, sitzung, "Radweg?", "Ja heißt zustimmen.", ordnung)
    for w in waehler:
        stimme_abgeben(antrag, w, "ja")
    stimme_abgeben(antrag, m, "ja")
    # Zeitraffer: Abstimmung vorbei, Sitzungstag vorbei
    antrag.phase_beginn = timezone.now() - timedelta(days=8)
    antrag.save(update_fields=["phase_beginn"])
    sitzung.frist = timezone.now() - timedelta(hours=1)
    sitzung.save(update_fields=["frist"])
    client.post(
        AKTION,
        {"aktion": "rechenschaft", "mandat": mandat.pk, "aufgabe": sitzung.pk, "gegenstand": "Radweg",
         "beschluss_plattform": "abgelehnt", "stimme": "dafuer", "begruendung": "Wie beschlossen."},
    )
    eintrag = mandat.rechenschaft.get()
    assert eintrag.antrag == antrag and eintrag.beschluss_plattform == "angenommen"  # aus dem Antrag, nicht aus dem Feld
    assert not eintrag.weicht_ab
    assert typen("rechenschaft")[0]["antrag"] == antrag.pk


def test_monatsbericht_nur_fuer_faellige_monate(client, monkeypatch):
    _, mandat = mandatar(client, angetreten=date(2026, 9, 1))
    html = client.get(MEIN).content.decode()
    assert "Kein Monatsbericht fällig." in html  # Berichtspflicht beginnt mit Oktober 2026
    antwort = client.post(
        AKTION, {"aktion": "monatsbericht", "mandat": mandat.pk, "monat": "2026-09-01", "text": "Zu früh."}, follow=True
    )
    assert "fälligen Monat" in antwort.content.decode() and mandat.berichte.count() == 0

    fest = timezone.make_aware(datetime(2026, 11, 3, 12, 0))
    monkeypatch.setattr(timezone, "now", lambda: fest)
    client.force_login(mandat.mitglied)  # die Sitzung aus dem September wäre im November abgelaufen
    html = client.get(MEIN).content.decode()
    assert 'value="2026-10-01"' in html and "Oktober 2026" in html
    client.post(AKTION, {"aktion": "monatsbericht", "mandat": mandat.pk, "monat": "2026-10-01", "text": "Drei Sitzungen, zwei Anträge."})
    bericht = mandat.berichte.get()
    assert bericht.art == Berichtsart.MONATSBERICHT and bericht.monat == date(2026, 10, 1)
    assert bericht.lage(heute=date(2026, 11, 3)).status == "fristgerecht"
    assert typen("mandatsbericht")[0]["art"] == "monatsbericht"
    # der Monat ist nicht mehr fällig, steht aber als Nachtrag zur Wahl — ein zweiter Bericht,
    # gekennzeichnet; die Pflicht bleibt erfüllt
    html = client.get(MEIN).content.decode()
    assert 'value="2026-10-01">Oktober 2026 · Nachtrag' in html
    html = client.post(AKTION, {"aktion": "monatsbericht", "mandat": mandat.pk, "monat": "2026-10-01", "text": "Nachtrag: Zahl berichtigt."}, follow=True).content.decode()
    assert mandat.berichte.count() == 2 and "Nachtrag zum Monatsbericht eingereicht." in html
    assert html.count("Oktober 2026") >= 2 and ">Nachtrag</span>" in html
    assert mandat.offene_pflichten()["monatsberichte"] == []
    # ein nie geschuldeter Monat bleibt abgewiesen
    html = client.post(AKTION, {"aktion": "monatsbericht", "mandat": mandat.pk, "monat": "2026-08-01", "text": "x"}, follow=True).content.decode()
    assert mandat.berichte.count() == 2 and "fälligen Monat" in html


def test_unbekannte_handlung_bleibt_folgenlos(client):
    _, mandat = mandatar(client)
    html = client.post(AKTION, {"aktion": "loeschen", "mandat": mandat.pk}, follow=True).content.decode()
    assert "Unbekannte Handlung" in html
    assert Mandat.objects.filter(pk=mandat.pk).exists() and Bericht.objects.count() == 0


def test_laufende_mandatsfrage_laesst_keinen_erfundenen_beschluss_zu(client, ordnung):  # noqa: F811
    from verfahren.models import mandatsfrage_eroeffnen

    _, mandat = mandatar(client)
    sitzung = Aufgabe.objects.create(mandat=mandat, titel="Radweg", frist=timezone.now() + timedelta(days=14), sitzungstag=True)
    antrag = mandatsfrage_eroeffnen(mandat, sitzung, "Radweg?", "Ja heißt zustimmen.", ordnung)
    sitzung.frist = timezone.now() - timedelta(hours=1)  # Sitzungstag vorbei, Abstimmung läuft noch
    sitzung.save(update_fields=["frist"])
    html = client.post(
        AKTION,
        {"aktion": "rechenschaft", "mandat": mandat.pk, "aufgabe": sitzung.pk, "gegenstand": "Radweg",
         "beschluss_plattform": "angenommen", "stimme": "dafuer", "begruendung": "Vorab."},
        follow=True,
    ).content.decode()
    eintrag = mandat.rechenschaft.get()
    assert eintrag.antrag_id == antrag.pk and eintrag.beschluss_plattform == "keiner"
    assert "läuft noch" in html and eintrag.beschluss_anzeige == "keiner" and not eintrag.weicht_ab
    assert typen("rechenschaft")[0]["antrag"] == antrag.pk
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung"


def test_rechenschaft_zu_laufender_mandatsfrage_zeigt_spaeter_den_beschluss(client, ordnung):  # noqa: F811
    """Eintrag während der laufenden Abstimmung; nach dem Fristende zeigen Register, JSON und
    der Bereich „angenommen“, „weicht ab“ und den Antragslink — und der gespeicherte Wert
    wird nachgezogen (§ 7 Abs 5: Beschluss und Stimme dauerhaft nebeneinander)."""
    from verfahren.models import mandatsfrage_eroeffnen, stimme_abgeben

    waehler = [mitglied_anlegen(f"w{i}") for i in range(2)]
    m, mandat = mandatar(client)
    sitzung = Aufgabe.objects.create(mandat=mandat, titel="Radweg", frist=timezone.now() + timedelta(days=14), sitzungstag=True)
    antrag = mandatsfrage_eroeffnen(mandat, sitzung, "Radweg?", "Ja heißt zustimmen.", ordnung)
    for w in [*waehler, m]:
        stimme_abgeben(antrag, w, "ja")
    sitzung.frist = timezone.now() - timedelta(hours=1)
    sitzung.save(update_fields=["frist"])
    client.post(
        AKTION,
        {"aktion": "rechenschaft", "mandat": mandat.pk, "aufgabe": sitzung.pk, "gegenstand": "Radweg",
         "beschluss_plattform": "keiner", "stimme": "dagegen", "begruendung": "Vorab."},
    )
    eintrag = mandat.rechenschaft.get()
    assert eintrag.antrag_id == antrag.pk and eintrag.beschluss_plattform == "keiner"
    register = client.get(reverse("mandatare:rechenschaft_mandat", args=[mandat.pk])).content.decode()
    assert "kein Beschluss der Plattform" in register and "weicht ab" not in register
    # Zeitraffer: die Abstimmung endet
    antrag.phase_beginn = timezone.now() - timedelta(days=8)
    antrag.save(update_fields=["phase_beginn"])
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "angenommen"
    register = client.get(reverse("mandatare:rechenschaft_mandat", args=[mandat.pk])).content.decode()
    assert f'href="/antrag/{antrag.pk}/">angenommen</a>' in register and "weicht ab" in register
    import json

    (e,) = json.loads(client.get(reverse("mandatare:rechenschaft_json")).content)["eintraege"]
    assert e["beschluss_plattform"] == "angenommen" and e["weicht_ab"] is True and e["antrag"] == antrag.pk
    eintrag.refresh_from_db()
    assert eintrag.beschluss_plattform == "angenommen"  # nachgezogen — auch der Export trägt den Stand
    html = client.get(MEIN).content.decode()
    assert "weicht ab" in html and ">Mandatsfrage</span>" in html


def test_betreute_sachabstimmung_heisst_im_bereich_nicht_mandatsfrage(client, ordnung):  # noqa: F811
    _, mandat = mandatar(client)
    from verfahren.models import antrag_einbringen
    from verfahren.test_views_aktionen import ANTRAG

    sache = antrag_einbringen(mandat.mitglied, **ANTRAG, ordnung=ordnung)
    Aufgabe.objects.create(mandat=mandat, titel="Budget-Sitzung", antrag=sache)
    html = client.get(MEIN).content.decode()
    assert ">Betreute Abstimmung</span>" in html and ">Mandatsfrage</span>" not in html
