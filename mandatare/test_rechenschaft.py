"""Die öffentlichen Register (S10): Ausstände auf der Mandatar-Seite, das Rechenschaftsregister
je Mandatar und gesamt (HTML und JSON, ohne Personenbezug), der Wahlvorschlag-Export (§ 7 Abs 1)."""

import json
from datetime import date, timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Aufgabe, Bericht, Berichtsart, Rechenschaft
from mandatare.test_mandatare import mandat_anlegen
from verfahren.models import Antragsart, antrag_einbringen, bewerbung_einreichen, bewerbung_zustimmen
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def sitzungstag(mandat, tage=10, titel="Gemeinderatssitzung: Radweg"):
    return Aufgabe.objects.create(
        mandat=mandat, titel=titel, frist=timezone.now() - timedelta(days=tage), sitzungstag=True
    )


def eintragen(mandat, aufgabe=None, **extra):
    felder = {
        "gegenstand": "Radweg an der Bundesstraße",
        "sitzung_am": aufgabe.sitzungstag_datum if aufgabe else date(2026, 9, 1),
        "beschluss_plattform": "angenommen",
        "stimme": "dagegen",
        "begruendung": "Die Finanzierung war nicht gesichert.",
        **extra,
    }
    return Rechenschaft.objects.create(mandat=mandat, aufgabe=aufgabe, **felder)


# ── Öffentliche Mandatar-Seite ────────────────────────────────────────────────────────────


def test_nach_dem_sitzungstag_stehen_die_ausstaende_oeffentlich(client):
    anna = mitglied_anlegen("anna")
    mandat = mandat_anlegen(anna)
    sitzung = sitzungstag(mandat, tage=10)
    faellig = (sitzung.sitzungstag_datum + timedelta(days=7)).strftime("%d.%m.%Y")
    html = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert f"Rechenschaft ausständig seit {faellig}" in html
    assert f"Sammelbericht ausständig seit {faellig}" in html
    assert 'class="ausstand"' in html and "Sitzungstag" in html
    assert sitzung.frist.astimezone(timezone.get_current_timezone()).strftime("%d.%m.%Y %H:%M") in html

    liste = client.get(reverse("mandatare:liste")).content.decode()
    assert "Rechenschaft:" in liste and "eine ausständig" in liste

    # Eintrag und Bericht beenden die Ausstände — beides erscheint öffentlich
    eintragen(mandat, sitzung)
    Bericht.objects.create(mandat=mandat, art=Berichtsart.SAMMELBERICHT, aufgabe=sitzung, text="Der Rat hat mehrheitlich zugestimmt.")
    html = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert "ausständig seit" not in html
    assert "Der Rat hat mehrheitlich zugestimmt." in html
    assert "Radweg an der Bundesstraße" in html and "weicht ab" in html
    assert "Die Finanzierung war nicht gesichert." in html
    liste = client.get(reverse("mandatare:liste")).content.decode()
    assert "ein Eintrag" in liste and "ausständig" not in liste


def test_innerhalb_der_frist_heisst_es_faellig_bis(client):
    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    sitzung = sitzungstag(mandat, tage=2)
    html = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    faellig = (sitzung.sitzungstag_datum + timedelta(days=7)).strftime("%d.%m.%Y")
    assert f"Rechenschaft fällig bis {faellig}" in html and "ausständig" not in html


def test_detailseite_zeigt_die_letzten_fuenf_und_verlinkt_das_register(client):
    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    for i in range(7):
        eintragen(mandat, gegenstand=f"Punkt {i}", sitzung_am=date(2026, 1, 1) + timedelta(days=i))
    html = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert "Punkt 6" in html and "Punkt 2" in html and "Punkt 1" not in html
    assert f'href="/mandatare/{mandat.pk}/rechenschaft/"' in html and "7 Einträge" in html
    register = client.get(reverse("mandatare:rechenschaft_mandat", args=[mandat.pk])).content.decode()
    assert register.count("Punkt ") == 7 and 'class="tabelle"' in register
    assert 'data-label="Beschluss der Plattform"' in register


def test_mandatsfrage_wird_mit_ergebnis_verlinkt(client, ordnung):  # noqa: F811
    from verfahren.models import mandatsfrage_eroeffnen, stimme_abgeben

    anna = mitglied_anlegen("anna")
    mandat = mandat_anlegen(anna)
    aufgabe = Aufgabe.objects.create(mandat=mandat, titel="Radweg", frist=timezone.now() + timedelta(days=14), sitzungstag=True)
    antrag = mandatsfrage_eroeffnen(mandat, aufgabe, "Radweg?", "Ja heißt zustimmen.", ordnung)
    html = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert f'href="/antrag/{antrag.pk}/#abstimmen"' in html and "Jetzt abstimmen" in html
    assert "Mandatsfrage" in html
    stimme_abgeben(antrag, anna, "ja")
    antrag.phase_beginn = timezone.now() - timedelta(days=8)
    antrag.save(update_fields=["phase_beginn"])
    html = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert "Ergebnis:" in html and "#abstimmen" not in html
    antrag.refresh_from_db()
    assert antrag.phase in ("angenommen", "abgelehnt")  # die Seite hat den Antrag fortgeschrieben


# ── Register gesamt ───────────────────────────────────────────────────────────────────────


def test_register_listet_alle_neueste_zuerst_mit_filter_und_ausstaenden(client):
    anna, bert = mitglied_anlegen("anna"), mitglied_anlegen("bert")
    gemeinde = mandat_anlegen(anna)
    land = mandat_anlegen(bert, bezeichnung="Landtag", ebene="land", gebiet="Oberösterreich")
    eintragen(gemeinde, gegenstand="Altes Thema", sitzung_am=date(2026, 8, 1))
    eintragen(land, gegenstand="Neues Thema", sitzung_am=date(2026, 9, 5), stimme="dafuer")
    sitzungstag(gemeinde, tage=12, titel="Budgetsitzung")

    html = client.get(reverse("mandatare:rechenschaft")).content.decode()
    assert html.index("Neues Thema") < html.index("Altes Thema")
    assert anna.anzeigename in html and bert.anzeigename in html
    assert "Budgetsitzung" in html and "ausständig seit" in html
    assert 'data-label="Mandatar"' in html

    nur_land = client.get(reverse("mandatare:rechenschaft") + "?ebene=land").content.decode()
    assert "Neues Thema" in nur_land and "Altes Thema" not in nur_land and "Budgetsitzung" not in nur_land
    assert 'class="chip an" href="?ebene=land"' in nur_land

    leer = client.get(reverse("mandatare:rechenschaft") + "?ebene=bund").content.decode()
    assert "Noch kein Eintrag." in leer and "Keine Ausstände." in leer
    for seite in (html, leer, client.get(reverse("mandatare:rechenschaft_mandat", args=[gemeinde.pk])).content.decode()):
        sichtbar = seite.split("</style>")[-1]
        assert "{%" not in sichtbar and "{{" not in sichtbar


def test_register_json_ohne_e_mail_und_klarnamen(client):
    anna = mitglied_anlegen("anna")
    anna.first_name, anna.last_name, anna.pseudonym_oeffentlich = "Anna", "Musterfrau", "anna_m"
    anna.save()
    mandat = mandat_anlegen(anna)
    sitzung = sitzungstag(mandat, tage=10)
    eintragen(mandat)
    antwort = client.get(reverse("mandatare:rechenschaft_json"))
    assert antwort["Content-Type"].startswith("application/json")
    daten = json.loads(antwort.content)
    (e,) = daten["eintraege"]
    assert e["mandatar"] == "anna_m" and e["stimme"] == "dagegen" and e["weicht_ab"] is True
    assert e["beschluss_plattform"] == "angenommen" and e["lage"] in ("fristgerecht", "verspaetet")
    (a,) = daten["ausstaende"]
    assert a["aufgabe"] == sitzung.pk and a["lage"] == "ausstaendig" and a["seit_tagen"] == 3
    roh = antwort.content.decode()
    assert "example.org" not in roh and "Musterfrau" not in roh
    assert json.loads(client.get(reverse("mandatare:rechenschaft_json") + "?ebene=land").content)["eintraege"] == []


# ── Wahlvorschlag-Export (§ 7 Abs 1) ──────────────────────────────────────────────────────


def kandidatur_beenden(ordnung):  # noqa: F811
    autor = mitglied_anlegen("autor")
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = antrag_einbringen(autor, "Listenreihung Gemeinderat", "Reihung.", "", ordnung, art=Antragsart.MANDAT)
    b1 = bewerbung_einreichen(antrag, leute[0], "Erste")
    b2 = bewerbung_einreichen(antrag, leute[1], "Zweite")
    for u in leute[:2]:
        antrag.unterstuetzungen.create(mitglied=u)
    antrag.fortschreiben()
    antrag.phase_beginn = timezone.now() - timedelta(days=22)
    antrag.save(update_fields=["phase_beginn"])
    antrag.fortschreiben()
    assert antrag.phase == "abstimmung"
    for waehler in (autor, leute[2]):
        bewerbung_zustimmen(antrag, waehler, b2)
    bewerbung_zustimmen(antrag, leute[0], b1)
    antrag.phase_beginn = timezone.now() - timedelta(days=8)
    antrag.save(update_fields=["phase_beginn"])
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "angenommen"
    return antrag, leute


def test_wahlvorschlag_export_reiht_nach_zustimmung(client, ordnung):  # noqa: F811
    antrag, leute = kandidatur_beenden(ordnung)
    antwort = client.get(reverse("mandatare:wahlvorschlag", args=[antrag.pk]))
    assert antwort.status_code == 200 and antwort["Content-Type"].startswith("text/markdown")
    md = antwort.content.decode()
    assert md.startswith("# Wahlvorschlag: Listenreihung Gemeinderat")
    zeilen = [z for z in md.splitlines() if z.startswith("| ") and not z.startswith("| Platz")]
    assert zeilen[0].startswith(f"| 1 | {leute[1].anzeigename} | 2 |")
    assert zeilen[1].startswith(f"| 2 | {leute[0].anzeigename} | 1 |")
    assert "Reihung nach § 7 Abs 1" in md and "Wahlordnung" in md
    assert f"/antrag/{antrag.pk}/export.json" in md
    assert "example.org" not in md


def test_wahlvorschlag_nur_fuer_beendete_kandidaturen(client, ordnung):  # noqa: F811
    autor = mitglied_anlegen("autor")
    laufend = antrag_einbringen(autor, "Listenreihung", "R.", "", ordnung, art=Antragsart.MANDAT)
    assert client.get(reverse("mandatare:wahlvorschlag", args=[laufend.pk])).status_code == 404
    sache = antrag_einbringen(autor, "Sachantrag", "W.", "B.", ordnung)
    sache.phase = "angenommen"
    sache.save(update_fields=["phase"])
    assert client.get(reverse("mandatare:wahlvorschlag", args=[sache.pk])).status_code == 404
    assert client.get(reverse("mandatare:wahlvorschlag", args=[9999])).status_code == 404
