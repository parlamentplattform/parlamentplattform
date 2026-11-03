"""Form sagt nichts über rechtliche Wahrheit; Grenzen und Herkunft bleiben prüfbar."""

import hashlib
import json

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from plattform_core.modellantwort import (
    HOECHSTFEHLER,
    HOECHSTTIEFE,
    HOECHSTZEICHEN,
    VERSION,
    pruefen,
    schema_als_dict,
    schema_hash,
)


def antwort():
    return {"normen": [{
        "titel": "Testnorm", "ebene": "Bund", "kennung": "", "aenderung": "beruehrt", "begruendung": "Ungeprüft.",
    }], "hinweis": "", "unsicherheit": "hoch"}


def text(daten):
    return json.dumps(daten, ensure_ascii=False)


def test_formale_gueltigkeit_ist_nur_ein_aktueller_formbefund_mit_unveraendertem_hash():
    roh = text(antwort())
    bef = pruefen(roh)
    assert bef["gueltig"] and bef["fehler"] == [] and bef["fassung"] == VERSION
    assert bef["zeitbezug"] == "darstellung"
    assert bef["antwort_sha256"] == hashlib.sha256(roh.encode()).hexdigest()
    assert "verifiziert" not in bef and "rechtlich" not in bef
    schema = schema_als_dict()
    kanonisch = json.dumps(schema, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    assert bef["schema_sha256"] == hashlib.sha256(kanonisch).hexdigest() == schema_hash()
    schema["properties"].clear()
    assert schema_als_dict()["properties"] and pruefen(roh) == bef


def test_gueltig_leer_braucht_ebenfalls_die_bekannte_antwortstruktur():
    daten = antwort()
    daten["normen"] = []
    assert pruefen(text(daten))["gueltig"]
    assert not pruefen('{"normen": "keine Liste"}')["gueltig"]


@pytest.mark.parametrize("daten,code", [
    ([], "typ"), ({}, "pflichtfeld"),
    ({**antwort(), "normen": "nein"}, "typ"),
    ({**antwort(), "unsicherheit": "extrem"}, "wert"),
    ({**antwort(), "hinweis": False}, "typ"),
    ({**antwort(), "modell_link": "https://evil.invalid"}, "zusatzfelder"),
])
def test_falsche_antwortform_ist_keine_leere_inhaltliche_aussage(daten, code):
    bef = pruefen(text(daten))
    assert not bef["gueltig"] and code in {f["code"] for f in bef["fehler"]}


@pytest.mark.parametrize("feld,wert,code", [
    ("titel", 5, "typ"), ("titel", "   ", "muster"), ("titel", "x" * 201, "laenge"),
    ("ebene", "Welt", "wert"), ("kennung", [], "typ"),
    ("aenderung", "unbekannt", "wert"), ("begruendung", "x" * 601, "laenge"),
])
def test_unbekannte_normfelder_bleiben_formabweichungen(feld, wert, code):
    daten = antwort()
    daten["normen"][0][feld] = wert
    bef = pruefen(text(daten))
    assert not bef["gueltig"] and {"pfad": f"$.normen[0].{feld}", "code": code} in bef["fehler"]


@pytest.mark.parametrize("ebene", ["EU", "Bund", "Land"])
@pytest.mark.parametrize("aenderung", ["aendern", "aufheben", "neu", "beruehrt"])
def test_alle_bekannten_ebenen_und_aenderungen_sind_formal_moeglich(ebene, aenderung):
    daten = antwort()
    daten["normen"][0].update(ebene=ebene, aenderung=aenderung)
    assert pruefen(text(daten))["gueltig"]


@pytest.mark.parametrize("roh,code", [
    ('{"normen":[],"normen":[],"hinweis":"","unsicherheit":"hoch"}', "doppelte_schluessel"),
    ('{"normen": NaN}', "json"), ('{"normen": Infinity}', "json"),
    ('```json\n{}\n```', "json"), ('Vorwort {} Nachwort', "json"),
    ('{"normen": [', "json"), ('[' * 1500 + ']' * 1500, "tiefe"),
    ("\ud800", "kodierung"), (None, "typ"), ("x" * (HOECHSTZEICHEN + 1), "groesse"),
], ids=["doppelt", "nan", "infinity", "zaun", "vorwort", "abbruch", "tiefe", "surrogat", "null", "groesse"])
def test_technische_fehler_werden_begrenzt_ohne_ausnahme_gemeldet(roh, code):
    bef = pruefen(roh)
    assert not bef["gueltig"] and bef["fehler"][0]["code"] == code


def test_klammern_und_maskierte_anführungszeichen_im_text_sind_keine_verschachtelung():
    daten = antwort()
    daten["hinweis"] = '[' * 200 + '\\"' + '{' * 200
    assert pruefen(text(daten))["gueltig"]


def test_zu_viele_normen_und_ungepruefte_feldnamen_werden_nicht_versteckt():
    daten = antwort()
    daten["normen"] *= 9
    daten["unbekannt_mit_private@example.org"] = "nicht in Diagnose kopieren"
    bef = pruefen(text(daten))
    assert "anzahl" in {f["code"] for f in bef["fehler"]}
    assert "private@example.org" not in str(bef["fehler"])


def test_diagnosegrenze_ist_auch_bei_vielen_kaputten_normen_exakt_begrenzt():
    daten = antwort()
    daten["normen"] = [{} for _ in range(8)]
    bef = pruefen(text(daten))
    assert not bef["gueltig"] and len(bef["fehler"]) == HOECHSTFEHLER


def test_maskiertes_unpaariges_unicode_ist_ebenfalls_keine_gueltige_textangabe():
    daten = antwort()
    daten["hinweis"] = "\ud800"
    bef = pruefen(json.dumps(daten))
    assert {"pfad": "$.hinweis", "code": "kodierung"} in bef["fehler"]
    assert bef["antwort_sha256"] and not bef["gueltig"]


@pytest.mark.parametrize("vorwort", ["]" * 40, "}" * 40])
def test_falsche_schliessklammern_im_vortext_senken_die_tiefe_nicht(vorwort):
    roh = vorwort + '{"normen":[],"zusatz":' + '[' * (HOECHSTTIEFE + 1) + '0' + ']' * (HOECHSTTIEFE + 1) + '}'
    bef = pruefen(roh)
    assert not bef["gueltig"] and bef["fehler"][0]["code"] == "tiefe"


_json = st.recursive(st.none() | st.booleans() | st.integers() | st.text(max_size=25),
                     lambda kind: st.lists(kind, max_size=4) | st.dictionaries(st.text(max_size=12), kind, max_size=4),
                     max_leaves=20)


@settings(max_examples=40, deadline=None)
@given(_json)
def test_formpruefung_ist_deterministisch_und_die_diagnose_ist_begrenzt(daten):
    roh = text(daten)
    bef = pruefen(roh)
    assert bef == pruefen(roh)
    assert len(bef["fehler"]) <= HOECHSTFEHLER
