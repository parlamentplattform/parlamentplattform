"""Neue Folgenkorrekturen behalten ursprüngliche Grundlagen und alte Korrekturverträge."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import copy
import hashlib
import json
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from faktenbasis.test_volltext import norm  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from gremien.models import Gremium, Rolle
from ki.anbieter import AnbieterFehler, Antwort, AttrappenAnbieter
from ki.eingabevertrag import korrektur
from ki.folgenberichte import fuer_lauf, vertrag
from ki.kontext import _hash
from ki.korrekturen import anfordern, export, hinzufuegen, stand
from ki.models import KIAuftrag, KILauf
from ki.test_folgenauftraege import ANTWORT, attrappe, neu  # noqa: F401
from ki.test_kontext import antrag  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren
from verfahren.models import Beanstandung
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


@pytest.fixture
def fall(antrag, attrappe):
    m = antrag.eingebracht_von
    r = Rolle.objects.create(mitglied=m, antrag=antrag, gremium=Gremium.EXPERTENRAT_1,
        bestaetigt=True, endet_am=timezone.localdate() + timedelta(days=30))
    alt = neu(antrag)
    assert auftrag_ausfuehren(alt.pk) == "erledigt"
    alt.refresh_from_db()
    b = Beanstandung.objects.create(antrag=antrag, lauf=alt.lauf, mitglied=m, text="Die Folgen sind nicht ausreichend belegt.")
    return antrag, m, r, alt, b


def neu_hashen(d):
    d.pop("sha256", None)
    return {**d, "sha256": _hash(d)}


def test_folgenkorrektur_hat_eigenen_prompt_und_genau_den_urspruenglichen_input(fall, attrappe):
    a, m, r, alt, b = fall
    vorher = KILauf.objects.values().get(pk=alt.lauf_id)
    job = anfordern(b, m)
    assert job.korrekturkontext["version"] == 2 and job.korrekturkontext["ursprungsauftrag"] == "rechtsfolgen-v1"
    assert job.folgenkontext == alt.folgenkontext and anfordern(b, m).pk == job.pk
    nummer, wortlaut = korrektur(job.korrekturkontext)
    assert nummer == 3 and json.loads(wortlaut)["urspruengliche_eingabe"] == alt.lauf.eingabe
    a.titel = "Spätere Änderung"
    a.save(update_fields=["titel"])
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    assert job.lauf.auftrag_version == "korrektur-v3" and job.lauf.eingabe == wortlaut
    assert job.lauf.kontext["folgen"] == alt.folgenkontext and len(attrappe) == 2
    assert KILauf.objects.values().get(pk=alt.lauf_id) == vorher
    b.refresh_from_db()
    assert b.erledigt_am is None and b.erledigt_vermerk == ""
    assert stand(job)["ergebnis"]["personalfolgen"] == "nicht_bestimmbar"
    e = export(a)[0]
    assert e["kontext"]["folgen"] == alt.folgenkontext and e["lauf"]["antwortformat"]["gueltig"]


def test_quellenidentitaet_ist_keine_bestaetigte_normaussage(antrag, norm, attrappe, monkeypatch):
    a = antrag
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    d = json.loads(ANTWORT)
    d["normen"] = [{"ris_id": norm.ris_id, "titel": "UNBESTAETIGTER_MODELLTITEL", "aenderung": "aendern", "grund": "Ungeprüfte Deutung"}]
    d["quellen"] = [f"norm:{norm.pk}"]
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort(json.dumps(d), "test", 2, 3))
    job = neu(a)
    auftrag_ausfuehren(job.pk)
    job.refresh_from_db()
    ergebnis = fuer_lauf(job.lauf)
    n, = ergebnis["normen"]
    assert not n["verifiziert"] and n["titel"] == "UNBESTAETIGTER_MODELLTITEL"
    z = n["kennungsabgleich"]
    assert z["zustand"] == "gleich" and z["quelle"]["kurztitel"] == norm.kurztitel
    assert z["quelle"]["norm_id"] == norm.pk and not z["rechtlich_verifiziert"]
    assert ergebnis["quellen"] == [f"norm:{norm.pk}"]


def test_unbekannte_norm_oder_neues_recht_erhaelt_keinen_amtlichen_link(antrag, norm, attrappe, monkeypatch):
    a = antrag
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    d = json.loads(ANTWORT)
    d["normen"] = [{"ris_id": "NOR99999999", "titel": "Unbekannt", "aenderung": "aendern", "grund": "Unbelegt"},
                   {"ris_id": "", "titel": "Neues Recht", "aenderung": "neu", "grund": "Nur ein Vorschlag"}]
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort(json.dumps(d), "test", 2, 3))
    job = neu(a)
    auftrag_ausfuehren(job.pk)
    job.refresh_from_db()
    assert all(n["kennungsabgleich"]["quelle"] is None for n in fuer_lauf(job.lauf)["normen"])


@pytest.mark.parametrize("feld", ["ursprungszweck", "ursprungsauftrag", "eingabe", "antwort", "text", "quellen", "folgen", "beanstandung"])
def test_beschaedigter_korrekturrahmen_wird_nicht_verwendet(fall, feld):
    a, m, r, alt, b = fall
    d = copy.deepcopy(anfordern(b, m).korrekturkontext)
    d[feld] = None
    with pytest.raises(ValueError):
        korrektur(d)


def test_neu_gehashte_abweichende_eingabe_bleibt_abgewiesen(fall):
    a, m, r, alt, b = fall
    d = copy.deepcopy(anfordern(b, m).korrekturkontext)
    d["eingabe"] += " Andere Quelle"
    d["eingabe_sha256"] = hashlib.sha256(d["eingabe"].encode()).hexdigest()
    with pytest.raises(ValueError):
        korrektur(neu_hashen(d))


def test_fremder_kontextbeifang_wird_weder_angezeigt_noch_exportiert(fall):
    a, m, r, alt, b = fall
    job = anfordern(b, m)
    auftrag_ausfuehren(job.pk)
    job.refresh_from_db()
    daten = {f.name: getattr(job.lauf, f.name) for f in KILauf._meta.fields if f.name != "id"}
    daten["kontext"] = {**daten["kontext"], "privat": "KEIN_OEFFENTLICHER_BEIFANG"}
    fremd = KILauf.objects.create(**daten)
    KIAuftrag.objects.filter(pk=job.pk).update(lauf=fremd)
    job.refresh_from_db()
    assert stand(job) == {"zustand": "fehler"}
    assert "KEIN_OEFFENTLICHER_BEIFANG" not in json.dumps(export(a))


@pytest.mark.parametrize("sperre", ["ruht", "fremd", "testkonto", "ungeprueft"])
def test_neuer_korrekturweg_hat_dieselben_rechtegrenzen(fall, sperre):
    a, m, r, alt, b = fall
    if sperre == "ruht":
        r.ruht_seit = timezone.now()
        r.save()
    elif sperre == "fremd":
        m = mitglied_anlegen("fremde-folgenfachkraft")
    elif sperre == "testkonto":
        m.testkonto = True
        m.save()
    else:
        m.identitaetsstufe = "ungeprueft"
        m.save(update_fields=["identitaetsstufe"])
    with pytest.raises(PermissionError):
        anfordern(b, m)


def test_kopie_eines_fremden_laufs_ohne_zugehoerigen_auftrag_darf_nicht_korrigiert_werden(fall):
    a, m, r, alt, b = fall
    daten = {f.name: getattr(alt.lauf, f.name) for f in KILauf._meta.fields if f.name != "id"}
    kopie = KILauf.objects.create(**daten)
    b2 = Beanstandung.objects.create(antrag=a, lauf=kopie, mitglied=m, text="Keine belegte Ursprungszuordnung")
    with pytest.raises(ValidationError):
        anfordern(b2, m)


def test_folgenfehler_wird_nicht_als_teilbericht_ausgegeben_und_kann_korrigiert_werden(fall, monkeypatch):
    a, m, r, alt, b = fall
    d = json.loads(ANTWORT)
    d["personal"][0]["vb_delta_min"] = 0
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort(json.dumps(d), "test", 2, 3))
    job = anfordern(b, m)
    auftrag_ausfuehren(job.pk)
    job.refresh_from_db()
    s = stand(job)
    assert not s["ergebnis"]["formatpruefung"]["gueltig"]
    assert s["ergebnis"]["normen"] == [] and s["ergebnis"]["judikatur"] == "" and s["ergebnis"]["personal"] == []
    assert export(a)[0]["lauf"]["antwortformat"]["fehler"][0]["code"] == "personalbasis"


def test_anzeige_und_nachrechnung_sind_auch_ohne_browser_sicher_escaped(fall, client, monkeypatch):
    a, m, r, alt, b = fall
    d = json.loads(ANTWORT)
    d["judikatur"]["text"] = '<script>alert("nicht ausführen")</script>'
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort(json.dumps(d), "test", 2, 3))
    job = anfordern(b, m)
    auftrag_ausfuehren(job.pk)
    job.refresh_from_db()
    hinzufuegen(a, [b], m)
    assert b.korrekturstand["ergebnis"]["folgenbericht"]
    from django.template.loader import render_to_string
    html = render_to_string("verfahren/_ki_korrektur.html", {"b": b, "antrag": a})
    assert "Folgen für Judikatur" in html and "nicht bestimmbar" in html
    assert "&lt;script&gt;" in html and '<script>alert(' not in html
    # Der reale HTTP-Aufruf nutzt dieselbe geschützte Fachoperation.
    client.force_login(m)
    url = reverse("verfahren:korrektur_anfordern", kwargs={"pk": a.pk, "beanstandung_pk": b.pk})
    assert client.get(url).status_code == 405
    assert client.post(url).status_code in (302, 200)
    assert KIAuftrag.objects.filter(beanstandung=b).count() == 1


def test_fehlerarchiv_und_erfolgreicher_zweiter_versuch_bleiben_getrennt(fall, monkeypatch):
    a, m, r, alt, b = fall
    job = anfordern(b, m)
    def fehler(*a):
        raise AnbieterFehler("Testfehler")
    monkeypatch.setattr(AttrappenAnbieter, "frage", fehler)
    assert auftrag_ausfuehren(job.pk) == "verschoben"
    job.refresh_from_db()
    erster = job.lauf_id
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort(ANTWORT, "test", 1, 2))
    assert auftrag_ausfuehren(job.pk, jetzt=job.naechster_versuch) == "erledigt"
    daten = export(a)[0]
    assert [lauf["erfolgreich"] for lauf in daten["laeufe"]] == [False, True]
    assert daten["laeufe"][0]["id"] == erster and daten["laeufe"][0]["antwortformat"] is None
    assert daten["laeufe"][1]["antwortformat"]["gueltig"] and not Beanstandung.objects.get(pk=b.pk).erledigt_am


@pytest.mark.parametrize("feld", ["auftrag_version", "eingabe", "antrag_id", "kontext", "zweck", "erfolgreich"])
def test_lesevertrag_lehnt_fremde_korrekturlaufteile_ab(fall, feld):
    a, m, r, alt, b = fall
    job = anfordern(b, m)
    auftrag_ausfuehren(job.pk)
    job.refresh_from_db()
    k = job.lauf
    setattr(k, feld, {} if feld == "kontext" else False if feld == "erfolgreich" else 12345)
    with pytest.raises(ValueError):
        vertrag(k)
