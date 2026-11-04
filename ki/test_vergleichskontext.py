"""Privater Entwurf, echte öffentliche Fassung und unveränderlicher Anbietertext."""

import copy
import json

import pytest

from gremien.models import Entwurf, EntwurfsFassung
from ki.kontext import _hash
from ki.vergleichskontext import eingabe, eingabe_hash, festhalten, pruefen
from verfahren.aehnlichkeit import Ergebnis
from verfahren.einbringwahl import pruefstand_fuer
from verfahren.models import Antrag, AntragsFassung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def lage(ordnung):  # noqa: F811
    autor = mitglied_anlegen("oeffentlich")
    bestehend = antrag_einbringen(autor, "Öffentlicher Titel", "Öffentlicher Wortlaut", "Öffentlicher Grund", ordnung)
    konto = mitglied_anlegen("privat")
    daten = {**ANTRAG, "art": "sache", "titel": "Mein Entwurf", "wortlaut": "Nicht veröffentlichter Wortlaut",
             "begruendung": "Vertraulicher Grund", "gebiet": "Privater Gebietsname"}
    ergebnis = Ergebnis(treffer=[{"antrag": bestehend, "prozent": 80, "bedeutung_prozent": 95}])
    token = pruefstand_fuer(daten, konto, ergebnis)
    return daten, konto, bestehend, token


def snapshot(lage, **kwargs):
    daten, konto, _, token = lage
    return festhalten(daten, konto, token, hoechstzeichen=kwargs.get("zeichen", 20000), hoechstpaare=kwargs.get("paare", 3))


def neu_signieren(d):
    d.pop("sha256", None)
    return {**d, "sha256": _hash(d)}


def test_projektion_hat_nur_texte_und_oeffentliche_paarreferenzen(lage):
    daten, konto, a, _ = lage
    kontext = snapshot(lage)
    assert kontext["konto"] == konto.pk and len(kontext["formular_sha256"]) == 64
    text = eingabe(kontext)
    d = json.loads(text)
    assert set(d) == {"version", "entwurf", "gegenueber"}
    assert d["entwurf"] == {"titel": daten["titel"], "wortlaut": daten["wortlaut"]}
    assert d["gegenueber"][0]["antrag"] == a.pk
    assert d["gegenueber"][0]["fassung"] == 1
    assert d["gegenueber"][0]["wortlaut"] == "Öffentlicher Wortlaut"
    assert not any(x in text for x in (konto.username, konto.email, "Vertraulicher Grund", "Privater Gebietsname", "prozent"))
    assert len(eingabe_hash(kontext)) == 64
    assert Antrag.objects.count() == 1


def test_internen_gremienentwurf_nie_als_beifang_vergleichen(lage):
    _, _, a, _ = lage
    e, _ = Entwurf.objects.get_or_create(antrag=a)
    EntwurfsFassung.objects.create(entwurf=e, nummer=2, wortlaut="Geheimer Arbeitsentwurf", verfasst_von=a.eingebracht_von)
    assert "Geheimer Arbeitsentwurf" not in eingabe(snapshot(lage))


@pytest.mark.parametrize("art", ["fremdkonto", "titel", "wortlaut", "begruendung", "gebiet", "signatur", "personenwahl"])
def test_fremdes_konto_und_formularwechsel_bauen_keinen_kontext(lage, art):
    daten, konto, _, token = lage
    daten = dict(daten)
    if art == "fremdkonto":
        konto = mitglied_anlegen("fremd")
    elif art == "signatur":
        token += "x"
    elif art == "personenwahl":
        daten["art"] = "personenwahl"
        token = pruefstand_fuer(daten, konto, Ergebnis(treffer=[]))
    else:
        daten[art] += " Änderung"
    with pytest.raises(ValueError):
        festhalten(daten, konto, token, hoechstzeichen=20000, hoechstpaare=3)


@pytest.mark.parametrize("art", ["titel", "fassung", "phase", "personenwahl"])
def test_geaenderte_gegenfassungen_muessen_neu_angeboten_werden(lage, art):
    _, _, a, _ = lage
    if art == "fassung":
        AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut="Neue Fassung")
    else:
        setattr(a, {"phase": "phase", "personenwahl": "art"}.get(art, "titel"),
                {"phase": "abgeschlossen", "personenwahl": "personenwahl"}.get(art, "Neuer Titel"))
        a.save()
    with pytest.raises(ValueError, match="geändert oder fehlt"):
        snapshot(lage)


def test_historische_eingabe_liest_spaeter_keinen_neuen_datenbanktext(lage, django_assert_num_queries):
    kontext = snapshot(lage)
    vorher = eingabe(kontext)
    a = lage[2]
    a.titel = "Späterer Titel"
    a.save(update_fields=["titel"])
    AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut="Späterer Wortlaut")
    with django_assert_num_queries(0):
        assert eingabe(kontext) == vorher


def test_eingabezeilenenden_werden_wie_der_signierte_formularstand_normalisiert(lage):
    daten, konto, a, _ = lage
    daten["wortlaut"] = "Erster Absatz\nZweiter Absatz"
    token = pruefstand_fuer(daten, konto, Ergebnis(treffer=[{"antrag": a, "prozent": 80, "bedeutung_prozent": None}]))
    daten["wortlaut"] = daten["wortlaut"].replace("\n", "\r\n")
    kontext = festhalten(daten, konto, token, hoechstzeichen=20000, hoechstpaare=3)
    assert kontext["entwurf"]["wortlaut"] == "Erster Absatz\nZweiter Absatz"


def test_laenge_ist_gesamtgrenze_ohne_stilles_kuerzen(lage):
    k = snapshot(lage)
    n = sum(len(v) for v in k["entwurf"].values()) + sum(len(p[s]) for p in k["gegenueber"] for s in ("titel", "wortlaut"))
    assert snapshot(lage, zeichen=n)["entwurf"] == k["entwurf"]
    with pytest.raises(ValueError, match="zu lang"):
        snapshot(lage, zeichen=n-1)


@pytest.mark.parametrize("feld", ["entwurf", "gegenueber", "konto", "formular_sha256", "erfasst_am", "rahmen"])
def test_pruefsumme_bemerkt_jeden_ausgetauschten_teil(lage, feld):
    k = snapshot(lage)
    k[feld] = None
    with pytest.raises(ValueError):
        eingabe(k)


@pytest.mark.parametrize("mutation", ["root", "version", "konto", "formular", "zeit", "naiv", "rahmen", "leer", "fremdfeld", "doppel", "bool", "paarhash", "steuer", "paartyp"])
def test_auch_neu_gehashte_fehlerhafte_rahmen_werden_abgewiesen(lage, mutation):
    k = snapshot(lage)
    if mutation == "root":
        k["fremd"] = "kein Beifang"
    elif mutation == "version":
        k["version"] = True
    elif mutation == "konto":
        k["konto"] = True
    elif mutation == "formular":
        k["formular_sha256"] = "ä" * 64
    elif mutation == "zeit":
        k["erfasst_am"] = "falsch"
    elif mutation == "naiv":
        k["erfasst_am"] = "2026-11-03T12:00:00"
    elif mutation == "rahmen":
        k["rahmen"]["hoechstzeichen"] = 100001
    elif mutation == "leer":
        k["entwurf"]["wortlaut"] = "  "
    elif mutation == "fremdfeld":
        k["gegenueber"][0]["intern"] = "Arbeitsentwurf"
    elif mutation == "doppel":
        k["gegenueber"] += copy.deepcopy(k["gegenueber"])
    elif mutation == "bool":
        k["gegenueber"][0]["fassung"] = True
    elif mutation == "paarhash":
        k["gegenueber"][0]["wortlaut"] += " Austausch"
    elif mutation == "steuer":
        k["entwurf"]["wortlaut"] += "\x00"
    else:
        k["gegenueber"] = None
    with pytest.raises(ValueError):
        pruefen(neu_signieren(k))


@pytest.mark.parametrize("zeichen,paare", [(0, 3), (20000, 0), (20000, 21), (True, 3)])
def test_technischer_rahmen_verhindert_unbegrenzte_verarbeitung(lage, zeichen, paare):
    with pytest.raises(ValueError):
        snapshot(lage, zeichen=zeichen, paare=paare)
