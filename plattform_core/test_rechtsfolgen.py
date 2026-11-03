"""Form und Quellenbindung sind keine rechtliche Bestätigung oder Personalprognose."""

import copy
import hashlib
import json

import pytest

from plattform_core.rechtsfolgen import pruefen

QUELLEN = ("norm:1", "personal_aggregat:2", "personal_ressorts:3")


def antwort():
    return {
        "normen": [{"ris_id": "NOR40000001", "titel": "Synthetische Norm", "aenderung": "beruehrt", "grund": "Nur ein Formbeispiel."}],
        "judikatur": {"text": "Ohne Verfahrensdaten nicht belegbar."},
        "exekutive": {"text": "Keine belastbare Vollzugsgrundlage vorhanden."},
        "personal": [{"bereich": "unbestimmt", "beamte_delta_min": None, "beamte_delta_max": None,
                      "vb_delta_min": None, "vb_delta_max": None, "grund": "Bestand ist kein zusätzlicher Personalbedarf."}],
        "unsicherheit": "hoch", "quellen": ["norm:1"],
    }


def pruefe(d, **kwargs):
    return pruefen(json.dumps(d, ensure_ascii=False), quellen=QUELLEN, **kwargs)


def test_passende_form_bleibt_inhaltlich_ungeprueft_und_hat_keine_zahlenspanne():
    d = antwort()
    roh = json.dumps(d)
    r = pruefen(roh, quellen=QUELLEN)
    assert r["gueltig"] and r["daten"] == d
    assert r["inhaltlich_geprueft"] is False and r["personalfolgen"] == "nicht_bestimmbar"
    assert r["antwort_sha256"] == hashlib.sha256(roh.encode()).hexdigest()
    assert r["daten"]["personal"][0]["beamte_delta_min"] is None
    r["daten"]["judikatur"]["text"] = "Geändert"
    assert d == antwort()


@pytest.mark.parametrize("feld", ["beamte_delta_min", "beamte_delta_max", "vb_delta_min", "vb_delta_max"])
@pytest.mark.parametrize("wert", [0, 1, -1, 1.2, False, "unbekannt"])
def test_kein_numerischer_bedarf_ohne_bedarfsgrundlage_auch_nullbedarf_nicht(feld, wert):
    d = antwort()
    d["personal"][0][feld] = wert
    r = pruefe(d)
    assert not r["gueltig"] and r["daten"] is None
    assert r["fehler"][0]["code"] == "personalbasis"


@pytest.mark.parametrize("mutation", ["wurzel", "normfeld", "judikatur", "exekutive", "personalbereich", "doppelbereich", "zuviele", "unsicherheit", "quelle", "doppelquelle", "quellenreihung", "neue_normkennung", "leer", "steuer", "unicode"])
def test_fehlerhafte_teile_liefern_keine_teilfreigabe(mutation):
    d = antwort()
    if mutation == "wurzel":
        d["abstimmungsempfehlung"] = "Keine Wirkung"
    elif mutation == "normfeld":
        d["normen"][0]["verifiziert"] = True
    elif mutation in ("judikatur", "exekutive"):
        d[mutation] = None
    elif mutation == "personalbereich":
        d["personal"][0]["bereich"] = "Nicht angebotenes Ressort"
    elif mutation == "doppelbereich":
        d["personal"] += copy.deepcopy(d["personal"])
    elif mutation == "zuviele":
        d["normen"] *= 9
    elif mutation == "unsicherheit":
        d["unsicherheit"] = True
    elif mutation == "quelle":
        d["quellen"] = ["norm:9999"]
    elif mutation == "doppelquelle":
        d["quellen"] *= 2
    elif mutation == "quellenreihung":
        d["quellen"] = ["personal_ressorts:3", "norm:1"]
    elif mutation == "neue_normkennung":
        d["normen"][0]["aenderung"] = "neu"
    elif mutation == "leer":
        d["judikatur"]["text"] = "   "
    elif mutation == "steuer":
        d["exekutive"]["text"] += "\x00"
    else:
        d["normen"][0]["titel"] = "\ud800"
        roh = json.dumps(d, ensure_ascii=True)
        assert not pruefen(roh, quellen=QUELLEN)["gueltig"]
        return
    r = pruefe(d)
    assert not r["gueltig"] and r["daten"] is None and r["fehler"]


def test_nur_tatsaechlich_angebotene_personalbereiche_sind_referenzierbar():
    d = antwort()
    d["personal"][0]["bereich"] = "Justiz"
    assert not pruefe(d)["gueltig"]
    assert pruefe(d, personalbereiche=["Justiz"])["gueltig"]


@pytest.mark.parametrize("roh", ["kein JSON", '{"normen":[],"normen":[]}', "NaN", "[" * 2000 + "]" * 2000,
                               "```json\n{}\n```", " " * 100001, None, "\ud800"],
                         ids=["kein-json", "doppelt", "nan", "rekursion", "markdown", "groesse", "typ", "utf8"])
def test_begrenzte_strikte_json_verarbeitung(roh):
    r = pruefen(roh)
    assert not r["gueltig"] and r["daten"] is None


@pytest.mark.parametrize("quellen,bereiche", [(["norm:1", "norm:1"], []), (["https://example.org"], []),
                                            ([True], []), ([], ["Justiz", "Justiz"]), ([], ["\ud800"])])
def test_unbrauchbarer_angebotsrahmen_ist_ein_aufruferfehler(quellen, bereiche):
    with pytest.raises(ValueError):
        pruefen(json.dumps(antwort()), quellen=quellen, personalbereiche=bereiche)


def test_fehlende_grundlagen_lassen_leere_listen_zu_aber_bestaetigen_keine_folgen():
    d = antwort()
    d.update(normen=[], personal=[], quellen=[])
    assert pruefen(json.dumps(d))["gueltig"]
