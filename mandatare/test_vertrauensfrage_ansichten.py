"""Die Ansichten der Vertrauensfrage (§ 7 Abs 10, S10c, Cluster M): Einbringen von der Mandatar-Seite,
Stellungnahme des Mandatsträgers, Bestätigungsantrag im Bereich, Verwaltungsvermerke mit Audit,
`/vertrauensfragen/` samt JSON, der Abschnitt „Vertrauen“ mit Fristzähler, die Registerzeile —
und dass die Abfragezahl nicht an der Zahl der Vertrauensfragen hängt."""

import itertools
from datetime import date

import pytest
from django.contrib.messages import get_messages
from django.core import mail
from django.db import connection
from django.template.loader import render_to_string
from django.test import RequestFactory
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from gremien.models import Gremium
from gremien.test_werkstatt import rolle_geben
from mandatare import models as mm
from mandatare.models import Aufgabe, Mandat, Rechenschaft, Stellungnahme, Vertrauensfrage
from mandatare.test_mandatare import admin_anlegen, mandat_anlegen
from mandatare.views import _rueckgabezusagen_fuer
from mitglieder.models import Mitgliedsstatus
from plattform_core import Phase
from verfahren.models import Antrag, Antragsart, Bewerbung, Rueckgabezusage, vertrauensfrage_einbringen
from verfahren.test_vertrauensfrage import (  # noqa: F401
    _verloren,
    abweichung,
    altmandat,
    audit,
    einbringen,
    tage,
)
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

MEIN = reverse("mandatare:mein")
MEIN_AKTION = reverse("mandatare:mein_aktion")
VERWALTUNG_AKTION = reverse("mandatare:verwaltung_aktion")
LISTE = reverse("mandatare:vertrauensfragen")
_ZAEHLER = itertools.count(1)


def stellen_url(mandat):
    return reverse("mandatare:vertrauensfrage_stellen", args=[mandat.pk])


def stellungnahme_url(antrag):
    return reverse("mandatare:stellungnahme", args=[antrag.pk])


def meldungen(antwort) -> str:
    return " ".join(str(m) for m in get_messages(antwort.wsgi_request))


def stellen(client, mandat, anlass, begruendung="Die Abweichung wurde nicht erklärt.", **extra):
    daten = {"anlass": [anlass.pk] if anlass is not None else [], "begruendung": begruendung, **extra}
    return client.post(stellen_url(mandat), daten)


# ── Einbringen (lit b) ─────────────────────────────────────────────────────────────────────


def test_gast_wird_zur_anmeldung_geschickt(client, altmandat):  # noqa: F811
    for antwort in (client.get(stellen_url(altmandat)), client.post(stellen_url(altmandat), {})):
        assert antwort.status_code == 302 and antwort["Location"].startswith("/anmelden/")
    assert client.post(stellungnahme_url(Antrag(pk=1)), {"text": "x"}).status_code == 302


def test_mandatar_seite_traegt_den_knopf_und_den_abschnitt_vertrauen(client, altmandat):  # noqa: F811
    html = client.get(reverse("mandatare:detail", args=[altmandat.pk])).content.decode()
    assert 'id="vertrauen"' in html and f'href="{stellen_url(altmandat)}"' in html
    assert "Keine Vertrauensfrage bisher." in html and "Rückgabezusage (§ 7 Abs 3):" in html
    assert "keine Angabe" in html  # ehrlich: die Erklärung fehlt


def test_mitglied_stellt_die_vertrauensfrage_und_sieht_die_zahlen_im_band(client, ordnung, altmandat):  # noqa: F811
    anlass = abweichung(altmandat)
    anna = mitglied_anlegen("anna")
    client.force_login(anna)
    html = client.get(stellen_url(altmandat)).content.decode()
    assert f'name="anlass" value="{anlass.pk}"' in html and "weicht ab" in html
    assert "sobald die Plattform Gliederungen führt" in html  # der regionale Weg — ehrlich benannt
    assert 'id="sperrhinweis"' not in html
    antwort = stellen(client, altmandat, anlass)
    antrag = Antrag.objects.get(art=Antragsart.VERTRAUENSFRAGE)
    assert antwort.status_code == 302 and antwort["Location"] == f"/antrag/{antrag.pk}/"
    text = meldungen(antwort)
    vf = antrag.vertrauensfrage
    assert f"Stimmberechtigte am Einbringungstag: {vf.stimmberechtigte_partei_am_einbringungstag}" in text
    assert f"Schwelle: {vf.schwelle_partei} Unterstützungen" in text and "Sperrhinweis" not in text
    assert list(vf.anlaesse.all()) == [anlass] and antrag.eingebracht_von == anna
    assert audit("vertrauensfrage_eingebracht")[0]["anlaesse"] == [anlass.pk]
    assert len(mail.outbox) == 1  # der Mandatar ist verständigt (Fundament)
    # Doppelabsendung: derselbe Antrag, kein zweiter
    antwort = stellen(client, altmandat, anlass)
    assert antwort["Location"] == f"/antrag/{antrag.pk}/" and Antrag.objects.filter(art=Antragsart.VERTRAUENSFRAGE).count() == 1


def test_ohne_anlass_kein_antrag_und_die_eingabe_bleibt(client, ordnung, altmandat):  # noqa: F811
    abweichung(altmandat)
    client.force_login(mitglied_anlegen("anna"))
    antwort = stellen(client, altmandat, None, begruendung="Meine Begründung bleibt stehen.")
    assert antwort.status_code == 200 and not Antrag.objects.filter(art=Antragsart.VERTRAUENSFRAGE).exists()
    html = antwort.content.decode()
    assert "mindestens einen Anlass" in html and "Meine Begründung bleibt stehen." in html
    assert 'name="anlass"' in html  # das Formular steht wieder da
    # Begründung fehlt → ebenfalls kein Antrag
    anlass = Rechenschaft.objects.get()
    antwort = stellen(client, altmandat, anlass, begruendung="   ")
    assert antwort.status_code == 200 and "Begründung" in meldungen(antwort)
    assert not Antrag.objects.filter(art=Antragsart.VERTRAUENSFRAGE).exists()


def test_ohne_jeden_moeglichen_anlass_gibt_es_kein_formular(client, ordnung, altmandat):  # noqa: F811
    client.force_login(mitglied_anlegen("anna"))
    html = client.get(stellen_url(altmandat)).content.decode()
    assert "Kein Anlass vorhanden." in html and 'name="begruendung"' not in html


def test_ausstand_als_anlass_wird_als_kontrollkaestchen_angeboten(client, ordnung, altmandat):  # noqa: F811
    sitzung = Aufgabe.objects.create(
        mandat=altmandat, titel="Budget", frist=timezone.now() - tage(60), sitzungstag=True
    )
    client.force_login(mitglied_anlegen("anna"))
    html = client.get(stellen_url(altmandat)).content.decode()
    assert f'name="ausstand" value="rechenschaft:{sitzung.pk}"' in html
    antwort = client.post(
        stellen_url(altmandat), {"ausstand": [f"rechenschaft:{sitzung.pk}"], "begruendung": "Seit Wochen nichts."}
    )
    assert antwort.status_code == 302
    vf = Vertrauensfrage.objects.get()
    assert vf.anlass_ausstaende[0]["kennung"] == f"rechenschaft:{sitzung.pk}"


def test_sperrhinweis_erscheint_und_hindert_nicht(client, ordnung):  # noqa: F811
    """lit g erster Fall: ein Mandat in der Schonfrist — die Seite zeigt den Hinweis, der Antrag entsteht
    trotzdem; feststellen tut es der Integritätsrat (§ 2 Abs 6)."""
    mandat = mandat_anlegen(mitglied_anlegen("neu"), angetreten=timezone.localdate() - tage(10))
    anlass = abweichung(mandat)
    client.force_login(mitglied_anlegen("anna"))
    html = client.get(stellen_url(mandat)).content.decode()
    assert 'id="sperrhinweis"' in html and "Schonfrist" in html and "Integritätsrat" in html
    antwort = stellen(client, mandat, anlass)
    assert antwort.status_code == 302
    vf = Vertrauensfrage.objects.get()
    assert vf.sperrhinweis and "Sperrhinweis nach § 7 Abs 10 lit g" in meldungen(antwort)


def test_pausiertes_mitglied_darf_nicht_stellen(client, ordnung, altmandat):  # noqa: F811
    abweichung(altmandat)
    paul = mitglied_anlegen("paul")
    paul.status = Mitgliedsstatus.PAUSIERT
    paul.save(update_fields=["status"])
    client.force_login(paul)
    assert client.get(stellen_url(altmandat)).status_code == 403
    assert client.post(stellen_url(altmandat), {"begruendung": "x"}).status_code == 403


def test_ohne_verfahrensordnung_kein_antrag(client, altmandat):  # noqa: F811
    anlass = abweichung(altmandat)
    client.force_login(mitglied_anlegen("anna"))
    html = client.get(stellen_url(altmandat)).content.decode()
    assert "keine Verfahrensordnung" in html and 'name="begruendung"' not in html
    assert stellen(client, altmandat, anlass).status_code == 200
    assert not Antrag.objects.exists()


# ── Stellungnahme (lit d) ──────────────────────────────────────────────────────────────────


def test_nur_der_betroffene_nimmt_stellung_und_nur_solange_es_laeuft(client, ordnung, altmandat):  # noqa: F811
    antrag = einbringen(mitglied_anlegen("anna"), altmandat, ordnung)
    client.force_login(mitglied_anlegen("fremd"))
    assert client.post(stellungnahme_url(antrag), {"text": "Ich rede mit."}).status_code == 403
    assert not Stellungnahme.objects.exists()
    client.force_login(altmandat.mitglied)
    assert client.get(stellungnahme_url(antrag)).status_code == 405  # nur POST
    antwort = client.post(stellungnahme_url(antrag), {"text": "Ich habe so gestimmt, weil …"})
    assert antwort.status_code == 302 and antwort["Location"] == f"/antrag/{antrag.pk}/#stellungnahme"
    assert Stellungnahme.objects.count() == 1 and audit("vertrauensfrage_stellungnahme")
    # leer → Meldung, kein Eintrag
    antwort = client.post(stellungnahme_url(antrag), {"text": "   "})
    assert antwort.status_code == 302 and Stellungnahme.objects.count() == 1
    # nach dem Ende: keine Ergänzung mehr
    antrag.phase = Phase.ABGELEHNT.value
    antrag.save(update_fields=["phase"])
    antwort = client.post(stellungnahme_url(antrag), {"text": "Nachtrag"})
    assert antwort.status_code == 302 and Stellungnahme.objects.count() == 1
    assert "beendet" in meldungen(antwort)
    assert client.post(stellungnahme_url(Antrag(pk=999999)), {"text": "x"}).status_code == 404


def test_teiltemplate_der_stellungnahmen_zeigt_formular_nur_dem_betroffenen(ordnung, altmandat):  # noqa: F811
    """Vertrag für Cluster R: `{% include "mandatare/_stellungnahmen.html" with vf=vf %}` liest `request.user`."""
    antrag = einbringen(mitglied_anlegen("anna"), altmandat, ordnung)
    vf = antrag.vertrauensfrage
    Stellungnahme.objects.create(vertrauensfrage=vf, text="Erste Stellungnahme.")

    def rendern(user):
        request = RequestFactory().get("/")
        request.user = user
        return render_to_string("mandatare/_stellungnahmen.html", {"vf": vf}, request=request)

    html = rendern(altmandat.mitglied)
    assert 'id="stellungnahme"' in html and "Erste Stellungnahme." in html
    assert f'action="{stellungnahme_url(antrag)}"' in html and 'name="text"' in html
    fremd = rendern(mitglied_anlegen("fremd"))
    assert "Erste Stellungnahme." in fremd and 'name="text"' not in fremd
    antrag.phase = Phase.ABGELEHNT.value
    antrag.save(update_fields=["phase"])
    vf.refresh_from_db()
    html = rendern(altmandat.mitglied)
    assert 'name="text"' not in html and "nicht mehr möglich" in html


# ── Bereich des Mandatars: Band, Bestätigung, Ende der Vertretung ──────────────────────────


def test_band_im_bereich_waehrend_die_vertrauensfrage_laeuft(client, ordnung, altmandat):  # noqa: F811
    antrag = einbringen(mitglied_anlegen("anna"), altmandat, ordnung)
    client.force_login(altmandat.mitglied)
    html = client.get(MEIN).content.decode()
    assert "Vertrauensfrage eingebracht am" in html and f'href="/antrag/{antrag.pk}/#stellungnahme"' in html
    assert "Stellung nehmen ›" in html
    ids = [k.split('"')[0] for k in html.split(' id="')[1:]]
    assert len(ids) == len(set(ids)), "doppelte id im Dokument"


def test_nach_verlorener_vertrauensfrage_bietet_der_report_keine_mandatsfrage_an(client, ordnung, altmandat):  # noqa: F811
    """§ 7 Abs 10 lit f Z 6: Die Befugnis, Abstimmungen zu betreuen, ruht ab der Veröffentlichung des
    Ergebnisses — der Report bleibt möglich, das Häkchen „Daraus eine Abstimmung erzeugen“ fehlt, und der
    Bereich sagt, warum. Eine Aufhebung durch das Parteischiedsgericht (lit h) bringt das Häkchen zurück."""
    client.force_login(altmandat.mitglied)
    html = client.get(MEIN).content.decode()
    assert 'name="abstimmung"' in html and "ruht die Befugnis" not in html
    antrag, ende = _verloren(ordnung, altmandat)
    html = client.get(MEIN).content.decode()
    assert 'name="aktion" value="report"' in html  # der Report selbst bleibt (Mandat noch aktiv)
    assert 'name="abstimmung"' not in html
    assert "ruht die Befugnis, Abstimmungen zu betreuen, und endet mit Ablauf der Anfechtungsfrist (§ 7 Abs 10 lit f Z 6)" in html
    vf = antrag.vertrauensfrage
    mm.vertrauensfrage_anfechtung_vermerken(vf, "PSG 2026/9", jetzt=ende + tage(1))
    mm.vertrauensfrage_entscheidung_vermerken(vf, "aufgehoben", jetzt=ende + tage(10))
    html = client.get(MEIN).content.decode()
    assert 'name="abstimmung"' in html and "ruht die Befugnis" not in html


def test_bestaetigung_erst_nach_sechs_monaten_und_nur_fuer_die_person(client, ordnung, altmandat):  # noqa: F811
    rolle = rolle_geben(altmandat.mitglied, Gremium.BERICHTSWESENRAT)
    antrag, ende = _verloren(ordnung, altmandat)
    client.force_login(altmandat.mitglied)
    html = client.get(MEIN).content.decode()
    assert 'name="aktion" value="bestaetigung"' not in html and "Bestätigung beantragbar ab" in html
    assert "Ersuchen um Rückgabe des Mandats" in html and "noch " in html  # Fristzähler
    rolle.refresh_from_db()
    assert rolle.ruht and "ruht seit" in html  # Band für die ruhende Rolle
    # zu früh → Fachoperation weist ab, der Bereich bleibt
    antwort = client.post(MEIN_AKTION, {"aktion": "bestaetigung", "mandat": altmandat.pk}, follow=True)
    assert "frühestens" in antwort.content.decode()
    assert not Vertrauensfrage.objects.filter(art="bestaetigung").exists()
    # sechs Monate später (Stempel zurückdatiert): Knopf da, Antrag entsteht
    frueher = timezone.now() - tage(200)
    Mandat.objects.filter(pk=altmandat.pk).update(vertrauen_entzogen_am=frueher, rueckgabe_ersucht_bis=timezone.localdate(frueher) + tage(30))
    Vertrauensfrage.objects.filter(antrag=antrag).update(wirkungen_ab=frueher)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=frueher)
    html = client.get(MEIN).content.decode()
    assert 'name="aktion" value="bestaetigung"' in html
    antwort = client.post(MEIN_AKTION, {"aktion": "bestaetigung", "mandat": altmandat.pk, "begruendung": "Seither jeder Beschluss."})
    b = Vertrauensfrage.objects.get(art="bestaetigung")
    assert antwort.status_code == 302 and antwort["Location"] == f"/antrag/{b.antrag_id}/"
    assert "Bestätigungsantrag eingebracht" in meldungen(antwort)
    html = client.get(MEIN).content.decode()
    assert "Ihr Bestätigungsantrag läuft seit" in html and 'name="aktion" value="bestaetigung"' not in html
    # eine fremde Person kann den Knopf nicht drücken
    client.force_login(mitglied_anlegen("fremd"))
    assert client.post(MEIN_AKTION, {"aktion": "bestaetigung", "mandat": altmandat.pk}).status_code == 403


def test_bereich_bleibt_nach_dem_ende_der_vertretung_lesbar_und_die_bestaetigung_erreichbar(client, ordnung, altmandat):  # noqa: F811
    antrag, ende = _verloren(ordnung, altmandat)
    frueher = timezone.now() - tage(200)
    Mandat.objects.filter(pk=altmandat.pk).update(
        vertrauen_entzogen_am=frueher,
        rueckgabe_ersucht_bis=timezone.localdate(frueher) + tage(30),
        vertretung_beendet_am=timezone.localdate(frueher) + tage(30),
    )
    Vertrauensfrage.objects.filter(antrag=antrag).update(wirkungen_ab=frueher)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=frueher)
    altmandat.refresh_from_db()
    assert not altmandat.mitglied.ist_mandatar and not altmandat.in_nachfrist()
    client.force_login(altmandat.mitglied)
    antwort = client.get(MEIN)
    assert antwort.status_code == 200
    html = antwort.content.decode()
    assert "Die Vertretung endete am" in html and 'name="aktion" value="report"' not in html
    assert 'name="aktion" value="bestaetigung"' in html
    assert client.get(reverse("mandatare:mein_mandat", args=[altmandat.pk])).status_code == 200
    # Schreibrechte wie beendetes Mandat: kein Report
    assert client.post(MEIN_AKTION, {"aktion": "report", "mandat": altmandat.pk, "titel": "x"}).status_code == 403


# ── Verwaltung (V10) ───────────────────────────────────────────────────────────────────────


def test_verwaltungshandlungen_mit_audit(client, ordnung, altmandat):  # noqa: F811
    rolle = rolle_geben(altmandat.mitglied, Gremium.BERICHTSWESENRAT)
    antrag, ende = _verloren(ordnung, altmandat)
    vf = antrag.vertrauensfrage
    client.force_login(mitglied_anlegen("kein_admin"))
    assert client.post(VERWALTUNG_AKTION, {"aktion": "rueckgabezusage", "mandat": altmandat.pk, "wert": "abgegeben"}).status_code == 403
    client.force_login(admin_anlegen())
    html = client.get(reverse("mandatare:verwaltung")).content.decode()
    assert f'id="vertrauen-{altmandat.pk}"' in html and "Vertrauensfrage verloren" in html
    assert 'name="aktion" value="anfechtung"' in html

    client.post(VERWALTUNG_AKTION, {"aktion": "rueckgabezusage", "mandat": altmandat.pk, "wert": "abgegeben"})
    altmandat.refresh_from_db()
    assert altmandat.rueckgabezusage == Rueckgabezusage.ABGEGEBEN and altmandat.rueckgabezusage_am == timezone.localdate()
    assert audit("rueckgabezusage")
    client.post(VERWALTUNG_AKTION, {"aktion": "rueckgabezusage", "mandat": altmandat.pk, "wert": "widerrufen"})
    altmandat.refresh_from_db()
    assert altmandat.rueckgabezusage == Rueckgabezusage.UNBEKANNT and len(audit("rueckgabezusage")) == 2
    antwort = client.post(VERWALTUNG_AKTION, {"aktion": "rueckgabezusage", "mandat": altmandat.pk, "wert": "quatsch"})
    assert "wählen" in meldungen(antwort) and len(audit("rueckgabezusage")) == 2

    client.post(VERWALTUNG_AKTION, {"aktion": "lit_h", "mandat": altmandat.pk, "datum": "2026-10-01"})
    altmandat.refresh_from_db()
    assert altmandat.mandatsvereinbarung_lit_h_am == date(2026, 10, 1)
    spur = audit("mandatsvereinbarung_lit_h")[0]
    assert spur["mandat"] == altmandat.pk and spur["feld"] == "mandatsvereinbarung_lit_h_am" and "2026" not in str(spur.get("datum", ""))
    antwort = client.post(VERWALTUNG_AKTION, {"aktion": "lit_h", "mandat": altmandat.pk, "datum": "kein"})
    assert "Datum" in meldungen(antwort)

    # Entscheidung ohne Anfechtung: nichts
    antwort = client.post(VERWALTUNG_AKTION, {"aktion": "entscheidung", "vertrauensfrage": vf.pk, "entscheidung": "aufgehoben"})
    assert "Anfechtung voraus" in meldungen(antwort)
    client.post(VERWALTUNG_AKTION, {"aktion": "anfechtung", "vertrauensfrage": vf.pk, "datum": timezone.localdate().isoformat(), "aktenkennung": "PSG 2026/7"})
    vf.refresh_from_db()
    assert vf.angefochten_am is not None and vf.aktenkennung == "PSG 2026/7" and audit("vertrauensfrage_angefochten")
    html = client.get(reverse("mandatare:verwaltung")).content.decode()
    assert 'name="entscheidung" value="aufgehoben"' in html and "PSG 2026/7" in html
    antwort = client.post(VERWALTUNG_AKTION, {"aktion": "entscheidung", "vertrauensfrage": vf.pk, "entscheidung": "egal"})
    assert "wählen" in meldungen(antwort)
    client.post(VERWALTUNG_AKTION, {"aktion": "entscheidung", "vertrauensfrage": vf.pk, "entscheidung": "aufgehoben"})
    vf.refresh_from_db()
    altmandat.refresh_from_db()
    rolle.refresh_from_db()
    assert vf.entscheidung == "aufgehoben" and altmandat.vertrauen_entzogen_am is None and rolle.aktiv
    assert audit("vertrauensfrage_aufgehoben")[0]["rollen_wiederhergestellt"] == [rolle.pk]
    assert client.post(VERWALTUNG_AKTION, {"aktion": "anfechtung", "vertrauensfrage": "abc"}).status_code == 404


def test_verwaltung_legt_kein_mandat_fuer_eine_person_mit_kandidatursperre_an(client, ordnung, altmandat):  # noqa: F811
    """lit f Z 3: Erst die Annahme der Bestätigung „ermöglicht eine neue Mandatsvereinbarung nach Abs 3“ —
    der Kandidatur-Weg ist gesperrt (bewerbung_einreichen), der Verwaltungsweg darf keine Hintertür sein."""
    _verloren(ordnung, altmandat)
    person = altmandat.mitglied
    client.force_login(admin_anlegen())
    daten = {"aktion": "anlegen", "mitglied": person.pk, "bezeichnung": "Landtag", "ebene": "land", "angetreten": timezone.localdate().isoformat()}
    antwort = client.post(VERWALTUNG_AKTION, daten)
    assert antwort.status_code == 302 and Mandat.objects.filter(mitglied=person).count() == 1
    assert "keine neue Mandatsvereinbarung möglich (§ 7 Abs 10 lit f Z 3)" in meldungen(antwort)
    assert not audit("mandat_angelegt")
    altmandat.bestaetigen("wahl")
    antwort = client.post(VERWALTUNG_AKTION, daten)
    assert Mandat.objects.filter(mitglied=person).count() == 2 and "angelegt" in meldungen(antwort)


def test_verformte_mandatskennung_antwortet_404_statt_500(client, ordnung, altmandat):  # noqa: F811
    """Dieselbe Regel wie für die Vertrauensfrage-Kennung (`_vertrauensfrage_der_verwaltung`): eine
    unbrauchbare Kennung ist eine unbekannte, kein Serverfehler — für die drei Vermerke aus 0.48 wie für
    Beenden, Foto und Aufgabe im Bestand; ebenso der Aufgabenstatus."""
    client.force_login(admin_anlegen())
    handlungen = (
        {"aktion": "rueckgabezusage", "wert": "abgegeben"},
        {"aktion": "lit_h", "datum": "2026-10-01"},
        {"aktion": "bestaetigung_durch_wahl"},
        {"aktion": "beenden"},
        {"aktion": "foto"},
        {"aktion": "aufgabe", "titel": "x"},
    )
    for daten in handlungen:
        for kennung in ("abc", "", "1 OR 1"):
            antwort = client.post(VERWALTUNG_AKTION, {**daten, "mandat": kennung})
            assert antwort.status_code == 404, (daten, kennung, antwort.status_code)
    assert client.post(VERWALTUNG_AKTION, {"aktion": "aufgabe_status", "aufgabe": "abc", "status": "erledigt"}).status_code == 404
    assert client.post(VERWALTUNG_AKTION, {"aktion": "beenden", "mandat": 999999}).status_code == 404
    altmandat.refresh_from_db()
    assert altmandat.beendet is None and altmandat.rueckgabezusage_am is None


def test_entscheidung_bestaetigt_vollzieht_stufe_zwei_sofort(client, ordnung, altmandat):  # noqa: F811
    rolle = rolle_geben(altmandat.mitglied, Gremium.BERICHTSWESENRAT)
    antrag, ende = _verloren(ordnung, altmandat)
    vf = antrag.vertrauensfrage
    frueher = timezone.now() - tage(40)  # das Ergebnis liegt länger zurück als die Rückgabefrist
    Vertrauensfrage.objects.filter(pk=vf.pk).update(wirkungen_ab=frueher, angefochten_am=frueher + tage(2))
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=frueher)
    Mandat.objects.filter(pk=altmandat.pk).update(vertrauen_entzogen_am=frueher, rueckgabe_ersucht_bis=timezone.localdate(frueher) + tage(30))
    client.force_login(admin_anlegen())
    client.post(VERWALTUNG_AKTION, {"aktion": "entscheidung", "vertrauensfrage": vf.pk, "entscheidung": "bestaetigt"})
    vf.refresh_from_db()
    altmandat.refresh_from_db()
    rolle.refresh_from_db()
    assert vf.entscheidung == "bestaetigt" and vf.wirkungen_endgueltig_am is not None
    assert rolle.beendet_grund == mm.BEENDIGUNGSGRUND and altmandat.vertretung_beendet_am is not None
    assert altmandat.beendet is None  # nichts setzt Mandat.beendet
    assert audit("vertrauensfrage_bestaetigt") and audit("vertretung_beendet")


def test_anfechtung_vor_dem_ergebnis_nennt_die_grenze_der_plattform_ehrlich(client, ordnung, altmandat):  # noqa: F811
    """lit h kennt vier Anfechtungsfälle; die Plattform vermerkt nur den vierten. Die Meldung sagt das —
    und behauptet nicht, die Satzung ließe nur ein veröffentlichtes Ergebnis anfechten."""
    antrag = einbringen(mitglied_anlegen("anna"), altmandat, ordnung)
    client.force_login(admin_anlegen())
    antwort = client.post(VERWALTUNG_AKTION, {"aktion": "anfechtung", "vertrauensfrage": antrag.vertrauensfrage.pk})
    text = meldungen(antwort)
    assert "außerhalb der Plattform" in text and "lit b, c und g" in text
    assert "Angefochten werden kann nur" not in text
    antrag.vertrauensfrage.refresh_from_db()
    assert antrag.vertrauensfrage.angefochten_am is None


def test_bestaetigung_durch_wahl_hebt_die_kandidatursperre_auf(client, ordnung, altmandat):  # noqa: F811
    _verloren(ordnung, altmandat)
    client.force_login(admin_anlegen())
    html = client.get(reverse("mandatare:verwaltung")).content.decode()
    assert 'value="bestaetigung_durch_wahl"' in html
    client.post(VERWALTUNG_AKTION, {"aktion": "bestaetigung_durch_wahl", "mandat": altmandat.pk})
    altmandat.refresh_from_db()
    assert not altmandat.kandidatursperre and audit("vertrauen_bestaetigt")[0]["grund"] == "wahl"
    antwort = client.post(VERWALTUNG_AKTION, {"aktion": "bestaetigung_durch_wahl", "mandat": altmandat.pk})
    assert "nichts zu bestätigen" in meldungen(antwort)


# ── Öffentlich: /vertrauensfragen/, JSON, Register, Fristzähler ────────────────────────────


def test_vertrauensfragen_seite_zeigt_laufende_und_entschiedene(client, ordnung, altmandat):  # noqa: F811
    verloren, ende = _verloren(ordnung, altmandat)
    land = Mandat.objects.create(mitglied=mitglied_anlegen("landrat", tage=600), bezeichnung="Landtag", ebene="land", angetreten=date(2025, 1, 1))
    laufend = einbringen(mitglied_anlegen("anna"), land, ordnung)
    html = client.get(LISTE).content.decode()
    assert 'id="laufende"' in html and f'href="/antrag/{laufend.pk}/"' in html
    assert f"0 von {laufend.vertrauensfrage.schwelle_partei} Unterstützungen" in html
    assert f'href="/antrag/{verloren.pk}/"' in html and "Vertrauensfrage verloren" in html
    assert "Ergebnis veröffentlicht am" in html and "Stimmen von" in html
    assert "sobald die Plattform Gliederungen führt" in html
    nur_land = client.get(LISTE + "?ebene=land").content.decode()
    assert f'href="/antrag/{laufend.pk}/"' in nur_land and f'href="/antrag/{verloren.pk}/"' not in nur_land
    assert "Derzeit läuft keine Vertrauensfrage." in client.get(LISTE + "?ebene=bund").content.decode()


def test_rechenschaft_json_und_register_fuehren_die_vertrauensfragen(client, ordnung, altmandat):  # noqa: F811
    verloren, ende = _verloren(ordnung, altmandat)
    abweichung(altmandat, tag=timezone.localdate() - tage(3))
    daten = client.get(reverse("mandatare:rechenschaft_json")).json()
    eintrag = daten["vertrauensfragen"][0]
    assert eintrag["antrag"] == verloren.pk and eintrag["ergebnis"] == "verloren" and eintrag["art"] == "vertrauensfrage"
    assert eintrag["schwelle"] == verloren.vertrauensfrage.schwelle_partei and eintrag["rechtsschutz"] == ""
    assert eintrag["rueckgabe_ersucht_bis"] and eintrag["mandatar"] == altmandat.mitglied.anzeigename
    assert "vertrauensfragen" in client.get(reverse("mandatare:rechenschaft_json") + "?ebene=land").json()
    html = client.get(reverse("mandatare:rechenschaft")).content.decode()
    assert '<tr class="vertrauensfrage">' in html and "Vertrauensfrage verloren" in html
    assert "Ergebnis der Mitgliederversammlung (§ 7 Abs 10 lit e)" in html
    # neuester Tag zuerst: das Ergebnis liegt (Zeitraffer) nach dem Registereintrag
    assert html.index('<tr class="vertrauensfrage">') < html.index("Radweg")
    einzeln = client.get(reverse("mandatare:rechenschaft_mandat", args=[altmandat.pk])).content.decode()
    assert '<tr class="vertrauensfrage">' in einzeln and 'id="vertrauen"' in einzeln


def test_fristzaehler_und_vermerk_auf_der_mandatar_seite(client, ordnung, altmandat):  # noqa: F811
    verloren, ende = _verloren(ordnung, altmandat)
    url = reverse("mandatare:detail", args=[altmandat.pk])
    html = client.get(url).content.decode()
    assert "Vertrauensfrage verloren" in html and "Ersuchen um Rückgabe des Mandats" in html
    altmandat.refresh_from_db()
    rest = (altmandat.rueckgabe_ersucht_bis - timezone.localdate()).days
    assert f"noch {rest} Tage" in html
    assert "Vermerk des Registers" not in html  # die Frist läuft noch — kein Vermerk
    assert "Keine Kandidatur nach § 7 Abs 1" in html
    assert f'href="{stellen_url(altmandat)}"' in html  # eine neue ist möglich — mit Sperrhinweis, den der IR feststellt
    Mandat.objects.filter(pk=altmandat.pk).update(rueckgabe_ersucht_bis=timezone.localdate() - tage(2))
    html = client.get(url).content.decode()
    assert "abgelaufen seit 2 Tagen" in html and "keine Rückgabezusage abgegeben" in html


def _abstimmung_abgelaufen_ohne_aufruf(ordnung, mandat, vor_tagen: int):  # noqa: F811
    """Eine Vertrauensfrage, deren Abstimmung vor `vor_tagen` Tagen endete, ohne dass jemand eine Seite
    aufrief: der Antrag steht noch in der Abstimmung, alle Stimmen lauten auf Ja."""
    from verfahren.models import stimme_abgeben

    leute = [mitglied_anlegen(f"s{next(_ZAEHLER)}") for _ in range(5)]
    t0 = timezone.now() - tage(vor_tagen + 14)
    antrag = einbringen(leute[0], mandat, ordnung, jetzt=t0)
    for m in leute[1:]:  # vier Unterstützungen — die Schwelle (fünf Prozent) wächst mit jedem angelegten Mitglied
        antrag.unterstuetzungen.create(mitglied=m, erklaert_am=t0 + tage(1))
    antrag.fortschreiben(t0 + tage(1))
    antrag.fortschreiben(t0 + tage(7))
    for m in leute:
        stimme_abgeben(antrag, m, "ja", jetzt=t0 + tage(8))
    antrag.refresh_from_db()
    assert antrag.phase == Phase.ABSTIMMUNG.value
    return antrag


def _weiteres_altmandat(name: str):
    return mandat_anlegen(mitglied_anlegen(name, tage=600), angetreten=timezone.localdate() - tage(400))


def test_erster_aufruf_nach_dem_fristende_zeigt_die_eben_eingetretenen_wirkungen(client, ordnung, altmandat):  # noqa: F811
    """Die Abstimmung endet, niemand ruft eine Seite auf; der erste Aufruf ist die Mandatar-Seite. Sie
    schreibt den Antrag fort (Stufe 1 stempelt auf einer anderen Mandat-Instanz), zieht Stufe 2 nach und
    rendert den Stand, den sie selbst erzeugt hat — Ersuchen um Rückgabe, Kandidatursperre, Fristzähler;
    die ruhende Rolle ist im selben Aufruf beendet (acht Tage nach dem Ergebnis). Der Knopf „Vertrauensfrage
    stellen“ bleibt bewusst (Sperre nur als Hinweis, der Integritätsrat stellt sie fest)."""
    rolle = rolle_geben(altmandat.mitglied, Gremium.BERICHTSWESENRAT)
    antrag = _abstimmung_abgelaufen_ohne_aufruf(ordnung, altmandat, vor_tagen=8)
    antwort = client.get(reverse("mandatare:detail", args=[altmandat.pk]))
    assert antwort.status_code == 200
    antrag.refresh_from_db()
    assert antrag.phase == Phase.ANGENOMMEN.value
    ctx = antwort.context
    assert ctx["mandat"].vertrauen_entzogen_am is not None and ctx["mandat"].kandidatursperre
    assert ctx["vertrauen"]["rueckgabe"] is not None and not ctx["vertrauen"]["rueckgabe"]["vorbei"]
    html = antwort.content.decode()
    assert "Ersuchen um Rückgabe des Mandats" in html and "Keine Kandidatur nach § 7 Abs 1" in html
    rolle.refresh_from_db()
    assert rolle.beendet_grund == mm.BEENDIGUNGSGRUND  # Stufe 2 lief im selben Aufruf
    assert antrag.vertrauensfrage.wirkungen_endgueltig_am is not None


def test_erster_aufruf_von_register_und_bereich_nach_dem_fristende_traegt_das_ergebnis(client, ordnung, altmandat):  # noqa: F811
    antrag = _abstimmung_abgelaufen_ohne_aufruf(ordnung, altmandat, vor_tagen=1)
    einzeln = client.get(reverse("mandatare:rechenschaft_mandat", args=[altmandat.pk])).content.decode()
    assert '<tr class="vertrauensfrage">' in einzeln and "Vertrauensfrage verloren" in einzeln
    assert "Ersuchen um Rückgabe des Mandats" in einzeln
    zweiter = _abstimmung_abgelaufen_ohne_aufruf(ordnung, _weiteres_altmandat("zwei"), vor_tagen=1)
    alle = client.get(reverse("mandatare:rechenschaft")).content.decode()
    assert f'href="/antrag/{antrag.pk}/"' in alle and f'href="/antrag/{zweiter.pk}/"' in alle
    dritter = _abstimmung_abgelaufen_ohne_aufruf(ordnung, _weiteres_altmandat("drei"), vor_tagen=1)
    client.force_login(dritter.vertrauensfrage.mandat.mitglied)
    bereich = client.get(MEIN).content.decode()
    assert "Ersuchen um Rückgabe des Mandats" in bereich and 'name="abstimmung"' not in bereich


def test_erster_aufruf_nach_dem_ende_der_vertretung_rechnet_mit_dem_neuen_stand(client, ordnung, altmandat):  # noqa: F811
    """Die Abstimmung endete vor 48 Tagen, niemand rief eine Seite auf: Der erste Aufruf löst Stufe 1 und Stufe
    2b aus (Vertretung beendet vor 18 Tagen, lit f Z 8) und rechnet Ausstände und Sitzungstage mit diesem Stand —
    ein Sitzungstag nach dem Ende ist keine ausständige Rechenschaft (Begründung nicht mehr geschuldet), auf der
    Seite wie im Bereich. Liste, JSON und Register nennen das Ende im selben Aufruf, nicht erst im nächsten."""
    Aufgabe.objects.create(mandat=altmandat, titel="Sitzung nach dem Ende", frist=timezone.now() - tage(1), sitzungstag=True)
    antrag = _abstimmung_abgelaufen_ohne_aufruf(ordnung, altmandat, vor_tagen=48)
    antwort = client.get(reverse("mandatare:detail", args=[altmandat.pk]))
    altmandat.refresh_from_db()
    assert altmandat.vertretung_beendet_am == timezone.localdate() - tage(18)
    assert antwort.context["ausstaende"]["rechenschaften"] == [] and antwort.context["ausstaende"]["sammelberichte"] == []
    assert "Rechenschaft ausständig" not in antwort.content.decode()
    client.force_login(altmandat.mitglied)
    bereich = client.get(MEIN)
    assert bereich.context["sitzungstage"] == [] and bereich.context["ausstaende"]["rechenschaften"] == []
    assert "Die Vertretung endete am" in bereich.content.decode()
    # Liste, JSON und Gesamtregister als erster Aufruf: Stufe 2 läuft nach Stufe 1, nicht erst beim nächsten Mal
    zweiter = _abstimmung_abgelaufen_ohne_aufruf(ordnung, _weiteres_altmandat("zwei"), vor_tagen=48)
    eintrag = next(e for e in client.get(reverse("mandatare:rechenschaft_json")).json()["vertrauensfragen"] if e["antrag"] == zweiter.pk)
    assert eintrag["ergebnis"] == "verloren" and eintrag["vertretung_beendet_am"] == (timezone.localdate() - tage(18)).isoformat()
    dritter = _abstimmung_abgelaufen_ohne_aufruf(ordnung, _weiteres_altmandat("drei"), vor_tagen=48)
    assert client.get(LISTE).status_code == 200
    assert Mandat.objects.get(pk=dritter.vertrauensfrage.mandat_id).vertretung_beendet_am is not None
    vierter = _abstimmung_abgelaufen_ohne_aufruf(ordnung, _weiteres_altmandat("vier"), vor_tagen=48)
    assert f'href="/antrag/{vierter.pk}/"' in client.get(reverse("mandatare:rechenschaft")).content.decode()
    assert Mandat.objects.get(pk=vierter.vertrauensfrage.mandat_id).vertretung_beendet_am is not None
    assert antrag.pk


def test_verwaltung_sieht_das_ergebnis_auch_als_erster_aufruf_nach_dem_fristende(client, ordnung, altmandat):  # noqa: F811
    """Die Abstimmung endete vor zwei Tagen, niemand rief eine Seite auf, die Verwaltung will die Anfechtung
    vermerken (lit h): Die Karte nennt das Ergebnis und bietet das Formular; der Vermerk gelingt — nicht die
    Meldung, es gebe noch kein veröffentlichtes Ergebnis. Der Vermerk selbst holt den Stand nach, falls die
    Seite ihn nicht schon geholt hat."""
    antrag = _abstimmung_abgelaufen_ohne_aufruf(ordnung, altmandat, vor_tagen=2)
    vf = antrag.vertrauensfrage
    client.force_login(admin_anlegen())
    html = client.get(reverse("mandatare:verwaltung")).content.decode()
    karte = html.split(f'id="vertrauen-{altmandat.pk}"')[1]
    assert "Vertrauensfrage verloren" in karte and f'name="vertrauensfrage" value="{vf.pk}"' in karte
    assert 'value="anfechtung"' in karte
    zweiter = _abstimmung_abgelaufen_ohne_aufruf(ordnung, _weiteres_altmandat("zwei"), vor_tagen=2)
    antwort = client.post(VERWALTUNG_AKTION, {"aktion": "anfechtung", "vertrauensfrage": zweiter.vertrauensfrage.pk, "aktenkennung": "PSG 2"})
    assert "Anfechtung vermerkt" in meldungen(antwort), meldungen(antwort)
    zweiter.refresh_from_db()
    assert zweiter.phase == Phase.ANGENOMMEN.value and zweiter.vertrauensfrage.angefochten_am is not None


def test_rueckgabezusage_aus_der_bewerbung_und_im_wahlvorschlag(client, ordnung):  # noqa: F811
    from verfahren.models import antrag_einbringen

    anna = mitglied_anlegen("anna")
    kandidatur = antrag_einbringen(anna, "Listenreihung", "Reihung.", "", ordnung, art=Antragsart.MANDAT)
    Bewerbung.objects.create(antrag=kandidatur, mitglied=anna, vorstellung="Ich.", rueckgabezusage=Rueckgabezusage.ABGEGEBEN)
    mandat = mandat_anlegen(anna, kandidatur=kandidatur)
    html = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert "erklärt bei der Bewerbung" in html and ">abgegeben</strong>" in html
    kandidatur.phase = Phase.ABGELEHNT.value
    kandidatur.stimmberechtigte_anzahl = 10
    kandidatur.save(update_fields=["phase", "stimmberechtigte_anzahl"])
    export = client.get(reverse("mandatare:wahlvorschlag", args=[kandidatur.pk])).content.decode()
    assert "| Rückgabezusage |" in export and "| abgegeben |" in export


def test_abfragezahl_haengt_nicht_an_der_zahl_der_vertrauensfragen(client, ordnung, altmandat):  # noqa: F811
    """Prefetch und Zähler in einer Abfrage: eine entschiedene Vertrauensfrage oder drei — die Liste,
    das JSON und die Mandatar-Seite kosten gleich viele Abfragen."""

    def messen(url):
        with CaptureQueriesContext(connection) as erfasst:
            assert client.get(url).status_code == 200
        return len(erfasst)

    urls = (LISTE, reverse("mandatare:rechenschaft_json"), reverse("mandatare:detail", args=[altmandat.pk]))
    _verloren(ordnung, altmandat)
    eins = {u: messen(u) for u in urls}
    for _ in range(2):
        Mandat.objects.filter(pk=altmandat.pk).update(vertrauen_entzogen_am=None, bestaetigt_am=None)
        _verloren(ordnung, altmandat)
    assert Vertrauensfrage.objects.count() == 3
    drei = {u: messen(u) for u in urls}
    assert eins == drei, (eins, drei)


# ── Prüfung (gegnerisch): Ehrlichkeit der Anzeigen ─────────────────────────────────────────


def _sechs_monate_zurueck(antrag, mandat):
    frueher = timezone.now() - tage(200)
    Mandat.objects.filter(pk=mandat.pk).update(
        vertrauen_entzogen_am=frueher,
        rueckgabe_ersucht_bis=timezone.localdate(frueher) + tage(30),
        vertretung_beendet_am=timezone.localdate(frueher) + tage(30),
    )
    Vertrauensfrage.objects.filter(antrag=antrag).update(wirkungen_ab=frueher)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=frueher)
    mandat.refresh_from_db()


def test_bestaetigung_vor_der_abstimmung_zeigt_den_beginn_statt_null_von_null(client, ordnung, altmandat):  # noqa: F811
    """lit f Z 3: Der Bestätigungsantrag kennt keine Unterstützung — „0 von 0 Unterstützungen“ wäre eine Zahl
    ohne Sinn; die Seiten nennen stattdessen den Tag, an dem die Abstimmung beginnt."""
    antrag, ende = _verloren(ordnung, altmandat)
    _sechs_monate_zurueck(antrag, altmandat)
    b = vertrauensfrage_einbringen(altmandat.mitglied, altmandat, "", [], [], ordnung, art="bestaetigung")
    assert b.phase == Phase.UNTERSTUETZUNG.value
    beginn = (b.eingebracht_am + tage(7)).strftime("%d.%m.%Y")
    html = client.get(LISTE).content.decode()
    assert f"Abstimmung ab {beginn}" in html and "0 von 0 Unterstützungen" not in html
    detail = client.get(reverse("mandatare:detail", args=[altmandat.pk])).content.decode()
    assert f"Abstimmung ab {beginn}" in detail and ">Unterstützung<" not in detail


def test_nach_erreichter_schwelle_nennen_liste_und_seite_den_abstimmungsbeginn(client, ordnung, altmandat):  # noqa: F811
    """lit e: Die Abstimmung beginnt frühestens am siebten Tag nach Einbringung — Antragsseite und Kachel
    veröffentlichen den Tag; /vertrauensfragen/ und der Abschnitt „Vertrauen“ nennen dieselbe Zahl, hinter
    „Schwelle erreicht am“, und behalten Phase und Zähler der Unterstützung."""
    t0 = timezone.now() - tage(2)
    antrag = einbringen(mitglied_anlegen("anna"), altmandat, ordnung, jetzt=t0)
    vf = antrag.vertrauensfrage
    assert vf.schwelle_partei == 1
    liste = client.get(LISTE).content.decode()
    assert "Abstimmung ab" not in liste and "Schwelle erreicht am" not in liste
    antrag.unterstuetzungen.create(mitglied=mitglied_anlegen("bernd"), erklaert_am=t0 + tage(1))
    antrag.fortschreiben(t0 + tage(1))
    vf.refresh_from_db()
    assert vf.schwelle_erreicht_am is not None and antrag.phase == Phase.UNTERSTUETZUNG.value
    beginn = timezone.localtime(t0 + tage(7)).strftime("%d.%m.%Y")
    liste = client.get(LISTE).content.decode()
    assert f"Schwelle erreicht am {timezone.localtime(t0 + tage(1)):%d.%m.%Y} · Abstimmung ab {beginn}" in liste
    assert "1 von 1 Unterstützungen" in liste  # der Zähler bleibt — die Unterstützung läuft weiter
    detail = client.get(reverse("mandatare:detail", args=[altmandat.pk])).content.decode()
    assert f"Abstimmung ab {beginn}" in detail and "Schwelle erreicht am" in detail
    antragsseite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert f"Abstimmung ab {beginn}" in antragsseite  # eine Zahl an allen Stellen


def test_sperrhinweis_in_der_liste_nur_binnen_der_dreitagesfrist(client, ordnung):  # noqa: F811
    """lit b: unterbleibt der Beschluss drei Tage lang, gilt der Antrag als eröffnet — „der Integritätsrat
    prüft bis <vergangener Tag>“ wäre danach falsch."""
    mandat = mandat_anlegen(mitglied_anlegen("neu"), angetreten=timezone.localdate() - tage(10))
    antrag = einbringen(mitglied_anlegen("anna"), mandat, ordnung)
    assert antrag.vertrauensfrage.sperrhinweis
    assert "der Integritätsrat prüft bis" in client.get(LISTE).content.decode()
    Antrag.objects.filter(pk=antrag.pk).update(eingebracht_am=timezone.now() - tage(4), phase_beginn=timezone.now() - tage(4))
    html = client.get(LISTE).content.decode()
    assert "der Integritätsrat prüft bis" not in html and f'href="/antrag/{antrag.pk}/"' in html


def test_json_nennt_die_rueckgabezusage_aus_derselben_quelle_wie_die_seite(client, ordnung):  # noqa: F811
    from verfahren.models import antrag_einbringen

    anna = mitglied_anlegen("anna", tage=600)
    kandidatur = antrag_einbringen(anna, "Listenreihung", "Reihung.", "", ordnung, art=Antragsart.MANDAT)
    Bewerbung.objects.create(antrag=kandidatur, mitglied=anna, vorstellung="Ich.", rueckgabezusage=Rueckgabezusage.ABGEGEBEN)
    mandat = mandat_anlegen(anna, kandidatur=kandidatur, angetreten=timezone.localdate() - tage(400))
    _verloren(ordnung, mandat)
    eintrag = client.get(reverse("mandatare:rechenschaft_json")).json()["vertrauensfragen"][0]
    assert eintrag["rueckgabezusage"] == "abgegeben" and eintrag["rueckgabezusage_quelle"] == "bewerbung"
    html = client.get(reverse("mandatare:detail", args=[mandat.pk])).content.decode()
    assert "erklärt bei der Bewerbung" in html
    # der Vermerk der Verwaltung geht vor; ohne beides: keine Angabe
    mm.rueckgabezusage_vermerken(mandat, Rueckgabezusage.NICHT_ABGEGEBEN)
    mandat.refresh_from_db()
    assert _rueckgabezusagen_fuer([mandat])[mandat.pk] == ("nicht_abgegeben", "mandat")
    fremd = mandat_anlegen(mitglied_anlegen("ohne"))
    assert _rueckgabezusagen_fuer([fremd])[fremd.pk] == (Rueckgabezusage.UNBEKANNT.value, "")


def test_registervermerk_kostet_keine_abfrage_je_verlorener_vertrauensfrage(client, ordnung):  # noqa: F811
    """Zusage nur in der Bewerbung, Rückgabefrist abgelaufen: Liste, JSON und Register rechnen Zusage und
    Vermerk einmal je Mandat — eine oder drei verlorene Vertrauensfragen desselben Mandats kosten gleich
    viele Abfragen, und das JSON rechnet den Vermerk nicht ein zweites Mal."""
    from verfahren.models import antrag_einbringen

    anna = mitglied_anlegen("anna", tage=600)
    kandidatur = antrag_einbringen(anna, "Listenreihung", "Reihung.", "", ordnung, art=Antragsart.MANDAT)
    Bewerbung.objects.create(antrag=kandidatur, mitglied=anna, vorstellung="Ich.", rueckgabezusage=Rueckgabezusage.ABGEGEBEN)
    mandat = mandat_anlegen(anna, kandidatur=kandidatur, angetreten=timezone.localdate() - tage(400))
    urls = (LISTE, reverse("mandatare:rechenschaft_json"), reverse("mandatare:rechenschaft"))

    def verlieren(n):
        for _ in range(n):
            Mandat.objects.filter(pk=mandat.pk).update(vertrauen_entzogen_am=None, bestaetigt_am=None)
            _verloren(ordnung, mandat)
        Mandat.objects.filter(pk=mandat.pk).update(rueckgabe_ersucht_bis=timezone.localdate() - tage(2))

    def messen(url):
        with CaptureQueriesContext(connection) as erfasst:
            antwort = client.get(url)
        assert antwort.status_code == 200
        return len(erfasst), antwort

    verlieren(1)
    eine = {u: messen(u)[0] for u in urls}
    verlieren(2)
    drei = {u: messen(u) for u in urls}
    assert {u: n for u, (n, _) in drei.items()} == eine, (eine, {u: n for u, (n, _) in drei.items()})
    daten = drei[reverse("mandatare:rechenschaft_json")][1].json()["vertrauensfragen"]
    assert len(daten) == 3 and all(d["vermerk"] == "Rückgabezusage nicht eingehalten" for d in daten)
    assert all(d["rueckgabezusage"] == "abgegeben" and d["rueckgabezusage_quelle"] == "bewerbung" for d in daten)
    assert "Rückgabezusage nicht eingehalten" in drei[LISTE][1].content.decode()


def test_widerruf_der_rueckgabezusage_verdraengt_die_erklaerung_aus_der_bewerbung(client, ordnung):  # noqa: F811
    """§ 7 Abs 3 nennt „ihr Widerruf“ als eigenen Sachverhalt: Vermerkt die Verwaltung „widerrufen (keine
    Angabe)“, darf die Bewerbung nicht wieder durchscheinen — Seite, Helfer und JSON sagen „keine Angabe ·
    vermerkt am …“, nicht „abgegeben · erklärt bei der Bewerbung“."""
    from verfahren.models import antrag_einbringen

    anna = mitglied_anlegen("anna", tage=600)
    kandidatur = antrag_einbringen(anna, "Listenreihung", "Reihung.", "", ordnung, art=Antragsart.MANDAT)
    Bewerbung.objects.create(antrag=kandidatur, mitglied=anna, vorstellung="Ich.", rueckgabezusage=Rueckgabezusage.ABGEGEBEN)
    mandat = mandat_anlegen(anna, kandidatur=kandidatur, angetreten=timezone.localdate() - tage(400))
    url = reverse("mandatare:detail", args=[mandat.pk])
    assert "erklärt bei der Bewerbung" in client.get(url).content.decode()
    client.force_login(admin_anlegen())
    client.post(VERWALTUNG_AKTION, {"aktion": "rueckgabezusage", "mandat": mandat.pk, "wert": "abgegeben"})
    antwort = client.post(VERWALTUNG_AKTION, {"aktion": "rueckgabezusage", "mandat": mandat.pk, "wert": "widerrufen"})
    assert "keine Angabe" in meldungen(antwort)
    mandat.refresh_from_db()
    assert mandat.rueckgabezusage == "" and mandat.rueckgabezusage_am == timezone.localdate()
    assert _rueckgabezusagen_fuer([mandat])[mandat.pk] == ("", "mandat")
    html = client.get(url).content.decode()
    assert "erklärt bei der Bewerbung" not in html and ">abgegeben</strong>" not in html
    assert ">keine Angabe</strong>" in html and f"vermerkt am {timezone.localdate():%d.%m.%Y}" in html
    _verloren(ordnung, mandat)
    eintrag = client.get(reverse("mandatare:rechenschaft_json")).json()["vertrauensfragen"][0]
    assert eintrag["rueckgabezusage"] == "" and eintrag["rueckgabezusage_quelle"] == "mandat"


def test_register_und_abschnitt_vertrauen_weisen_die_beteiligung_aus(client, ordnung, altmandat):  # noqa: F811
    """lit e letzter Satz: „Ergebnis und Beteiligung werden … im Rechenschaftsregister nach Abs 5 sowie im
    öffentlichen Bereich nach Abs 9 dauerhaft ausgewiesen“ — nicht nur unter /vertrauensfragen/."""
    verloren, ende = _verloren(ordnung, altmandat)  # fünf Stimmberechtigte stimmen mit Ja
    beteiligung = f"5 Stimmen von {verloren.stimmberechtigte_anzahl} Stimmberechtigten"
    detail = client.get(reverse("mandatare:detail", args=[altmandat.pk])).content.decode()
    assert beteiligung in detail.split('id="vertrauen"')[1]
    for url in (reverse("mandatare:rechenschaft"), reverse("mandatare:rechenschaft_mandat", args=[altmandat.pk])):
        html = client.get(url).content.decode()
        zeile = html.split('<tr class="vertrauensfrage">')[1].split("</tr>")[0]
        assert "Ergebnis der Mitgliederversammlung (§ 7 Abs 10 lit e)" in zeile and beteiligung in zeile
    client.force_login(altmandat.mitglied)
    assert beteiligung in client.get(MEIN).content.decode()


def test_liste_und_kopf_der_seite_vermerken_das_ende_der_vertretung(client, ordnung, altmandat):  # noqa: F811
    """lit f Z 8: Die Person ist nicht mehr Mandatsträger der DDÖ; Bereich und Register werden fortgeführt
    und weisen das Ergebnis aus. Liste, Kopf der öffentlichen Seite und Register je Mandatar tragen den
    Vermerk oben — nicht erst im Abschnitt „Vertrauen“ weit unten."""
    antrag, ende = _verloren(ordnung, altmandat)
    _sechs_monate_zurueck(antrag, altmandat)
    tag = altmandat.vertretung_beendet_am.strftime("%d.%m.%Y")
    liste = client.get(reverse("mandatare:liste")).content.decode()
    assert altmandat.mitglied.anzeigename in liste and f"Vertretung beendet am {tag}" in liste
    detail = client.get(reverse("mandatare:detail", args=[altmandat.pk])).content.decode()
    kopf = detail.split('id="vertrauen"')[0]
    assert f"Vertretung beendet am {tag}" in kopf and 'href="#vertrauen"' in kopf
    register = client.get(reverse("mandatare:rechenschaft_mandat", args=[altmandat.pk])).content.decode()
    assert f"Vertretung beendet am {tag}" in register.split('id="vertrauen"')[0]
    # ohne Ende der Vertretung kein Vermerk
    Mandat.objects.filter(pk=altmandat.pk).update(vertretung_beendet_am=None)
    assert "Vertretung beendet am" not in client.get(reverse("mandatare:liste")).content.decode()


def test_oeffentliche_seite_fuehrt_die_betroffene_person_in_ihren_bereich(client, ordnung, altmandat):  # noqa: F811
    """lit f Z 3: Das Antragsrecht auf Bestätigung entsteht, wenn die Rolle „Mandatar“ nach Z 8 längst geendet
    hat — die Leiste führt „Mein Mandat“ dann nicht mehr. Die öffentliche Seite zeigt der Person selbst den
    Weg in ihren Bereich; vor Ablauf der sechs Monate ohne, danach mit „Bestätigung beantragen“."""
    antrag, ende = _verloren(ordnung, altmandat)
    url = reverse("mandatare:detail", args=[altmandat.pk])
    ziel = reverse("mandatare:mein_mandat", args=[altmandat.pk]) + "#vertrauen"
    assert f'href="{ziel}"' not in client.get(url).content.decode()  # Gast
    client.force_login(mitglied_anlegen("fremd"))
    assert f'href="{ziel}"' not in client.get(url).content.decode()  # fremde Person
    client.force_login(altmandat.mitglied)
    html = client.get(url).content.decode()
    assert f'href="{ziel}"' in html and "Zu meinem Bereich →" in html and "Bestätigung beantragen →" not in html
    _sechs_monate_zurueck(antrag, altmandat)
    assert not altmandat.mitglied.ist_mandatar
    html = client.get(url).content.decode()
    assert f'href="{ziel}"' in html and "Zu meinem Bereich — Bestätigung beantragen →" in html
    assert 'name="aktion" value="bestaetigung"' in client.get(ziel).content.decode()
    altmandat.bestaetigen("wahl")
    assert f'href="{ziel}"' not in client.get(url).content.decode()  # ohne Sperre kein Bereich mehr


def test_band_mitwirkung_ruht_nur_bei_wirklich_ruhendem_status(client, ordnung, altmandat):  # noqa: F811
    """Nach dem Ende der Vertretung (lit f Z 8) und der Nachfrist darf die Person nicht mehr schreiben —
    aber nicht, weil ihr Status ruht: Das Band „Ihre Mitwirkung ruht … mit aktivem Status“ wäre bei aktivem
    Status und geprüfter Identität eine falsche Aussage (lit i: Mitgliedschaft und Rechte bleiben unberührt).
    Bei pausiertem Status bleibt das Band — auch in der Nachfrist, dann ohne Berichtsformulare."""
    antrag, ende = _verloren(ordnung, altmandat)
    _sechs_monate_zurueck(antrag, altmandat)
    person = altmandat.mitglied
    assert person.darf_mitwirken and not altmandat.in_nachfrist()
    client.force_login(person)
    html = client.get(MEIN).content.decode()
    assert "Die Vertretung endete am" in html and 'name="aktion" value="bestaetigung"' in html
    assert "Ihre Mitwirkung ruht" not in html and "aktivem Status" not in html
    # Gegenprobe: pausiert nach der Nachfrist → das Band stimmt
    person.status = Mitgliedsstatus.PAUSIERT
    person.save(update_fields=["status"])
    html = client.get(MEIN).content.decode()
    assert "Ihre Mitwirkung ruht" in html and 'name="aktion" value="bestaetigung"' not in html
    # Gegenprobe: pausiert in der Nachfrist (Vertretung seit drei Tagen beendet) → Band da, keine Berichtsformulare
    frueher = timezone.now() - tage(13)
    Mandat.objects.filter(pk=altmandat.pk).update(
        vertrauen_entzogen_am=frueher, rueckgabe_ersucht_bis=timezone.localdate(frueher) + tage(10),
        vertretung_beendet_am=timezone.localdate(frueher) + tage(10),
    )
    altmandat.refresh_from_db()
    assert altmandat.in_nachfrist()
    html = client.get(MEIN).content.decode()
    assert "Ihre Mitwirkung ruht" in html and "sind noch bis" in html
    assert 'name="aktion" value="sammelbericht"' not in html and 'name="aktion" value="monatsbericht"' not in html


def test_verwaltung_liest_die_rueckgabezusage_aus_derselben_quelle_wie_die_seite(client, ordnung):  # noqa: F811
    """Ein Sachverhalt, eine Anzeige: Trägt die Bewerbung die Erklärung, sagt auch die Verwaltung „abgegeben ·
    erklärt bei der Bewerbung“ — sonst könnte sie grundlos „nicht abgegeben“ nachtragen. Nach einem Vermerk
    gilt der Vermerk, mit Datum."""
    from verfahren.models import antrag_einbringen

    anna = mitglied_anlegen("anna", tage=600)
    kandidatur = antrag_einbringen(anna, "Listenreihung", "Reihung.", "", ordnung, art=Antragsart.MANDAT)
    Bewerbung.objects.create(antrag=kandidatur, mitglied=anna, vorstellung="Ich.", rueckgabezusage=Rueckgabezusage.ABGEGEBEN)
    mandat = mandat_anlegen(anna, kandidatur=kandidatur)
    client.force_login(admin_anlegen())

    def zeile():  # die Zeile „Rückgabezusage: …“ der Karte, vor dem Formular (dessen Auswahl „keine Angabe“ nennt)
        html = client.get(reverse("mandatare:verwaltung")).content.decode()
        return html.split(f'id="vertrauen-{mandat.pk}"')[1].split("</p>")[0]

    assert ">abgegeben</strong>" in zeile() and "erklärt bei der Bewerbung" in zeile() and "keine Angabe" not in zeile()
    client.post(VERWALTUNG_AKTION, {"aktion": "rueckgabezusage", "mandat": mandat.pk, "wert": "nicht_abgegeben"})
    assert ">nicht abgegeben</strong>" in zeile() and f"vermerkt am {timezone.localdate():%d.%m.%Y}" in zeile()
    assert "erklärt bei der Bewerbung" not in zeile()


def test_band_nach_der_nachfrist_verspricht_keine_eintraege_mehr(client, ordnung, altmandat):  # noqa: F811
    antrag, ende = _verloren(ordnung, altmandat)
    _sechs_monate_zurueck(antrag, altmandat)
    assert not altmandat.in_nachfrist()
    client.force_login(altmandat.mitglied)
    html = client.get(MEIN).content.decode()
    assert "der Bereich bleibt lesbar" in html and "sind noch bis" not in html


def test_nach_dem_ende_der_vertretung_zaehlen_sitzungstage_danach_nicht_mehr(client, ordnung, altmandat):  # noqa: F811
    """Der Bereich rechnet mit derselben Grenze wie `offene_pflichten` (Mandat.pflichtende): ein Sitzungstag
    nach dem Ende der Vertretung erzeugt keine Pflicht und wird nicht zum Sammelbericht angeboten."""
    antrag, ende = _verloren(ordnung, altmandat)
    frueher = timezone.now() - tage(13)  # Vertretung seit drei Tagen beendet, Nachfrist (sieben Tage) läuft
    Mandat.objects.filter(pk=altmandat.pk).update(
        vertrauen_entzogen_am=frueher, rueckgabe_ersucht_bis=timezone.localdate(frueher) + tage(10),
        vertretung_beendet_am=timezone.localdate(frueher) + tage(10),
    )
    Vertrauensfrage.objects.filter(antrag=antrag).update(wirkungen_ab=frueher)
    altmandat.refresh_from_db()
    assert altmandat.in_nachfrist()
    davor = Aufgabe.objects.create(mandat=altmandat, titel="Davor", frist=timezone.now() - tage(5), sitzungstag=True)
    danach = Aufgabe.objects.create(mandat=altmandat, titel="Danach", frist=timezone.now() - tage(1), sitzungstag=True)
    client.force_login(altmandat.mitglied)
    html = client.get(MEIN).content.decode()
    assert f'<option value="{davor.pk}"' in html and f'<option value="{danach.pk}"' not in html
    antwort = client.post(
        MEIN_AKTION, {"aktion": "sammelbericht", "mandat": altmandat.pk, "aufgabe": danach.pk, "text": "Nachher."}, follow=True
    )
    assert antwort.status_code == 200 and not altmandat.berichte.filter(aufgabe=danach).exists()
