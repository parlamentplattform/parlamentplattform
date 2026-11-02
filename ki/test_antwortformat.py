"""Fehlerhafte Struktur wird weder zur Rechtswirkung noch zur Modellgewissheit."""

import json

import pytest

from ki.rechtsbezug import antwort_parsen
from plattform_core.modellantwort import HOECHSTTIEFE


def test_unbekannte_aenderung_und_unsicherheit_bleiben_ausdruecklich_unbekannt():
    ergebnis = antwort_parsen(json.dumps({
        "normen": [{"titel": "Testnorm", "aenderung": "unbekannt"}], "unsicherheit": "extrem",
    }))
    assert ergebnis["normen"][0]["aenderung"] == "unklar"
    assert ergebnis["unsicherheit"] == "unbekannt"
    assert not ergebnis["formatpruefung"]["gueltig"]


def test_widerspruechliche_doppelte_schluessel_werden_nicht_durch_letzten_wert_entschieden():
    roh = '{"normen":[],"normen":[{"titel":"Testnorm","aenderung":"aufheben"}]}'
    ergebnis = antwort_parsen(roh)
    assert ergebnis["roh"] and ergebnis["normen"] == []
    assert ergebnis["hinweis"] == roh
    assert ergebnis["formatpruefung"]["fehler"][0]["code"] == "doppelte_schluessel"


def test_tolerante_nachlese_umgeht_die_tiefengrenze_nicht():
    ergebnis = antwort_parsen('[' * (HOECHSTTIEFE + 1) + '{}' + ']' * (HOECHSTTIEFE + 1))
    assert ergebnis["normen"] == [] and ergebnis["roh"]
    assert ergebnis["formatpruefung"]["fehler"][0]["code"] == "tiefe"


def test_ungueltige_unicode_felder_bleiben_darstellbar_und_der_rohtext_erhalten():
    roh = '{"normen":[{"titel":"\\ud800","aenderung":"beruehrt"}]}'
    ergebnis = antwort_parsen(roh)
    assert not ergebnis["formatpruefung"]["gueltig"]
    assert ergebnis["normen"][0]["titel"].encode("utf-8") == b"?"
    assert "kodierung" in {f["code"] for f in ergebnis["formatpruefung"]["fehler"]}
@pytest.mark.parametrize("roh", [
    '```json\n{"normen":[],"normen":[{"titel":"zweite Angabe"}]}\n```',
    'Vorwort {"normen":[],"hinweis":NaN} Nachwort',
])
def test_tolerantes_lesen_umgeht_keine_mehrdeutigkeit_oder_nicht_json_zahl(roh):
    gelesen = antwort_parsen(roh)
    assert gelesen["roh"] and gelesen["normen"] == []
    assert not gelesen["formatpruefung"]["gueltig"]


def test_schliessklammern_im_vorwort_sind_kein_tiefenrabatt_fuer_die_nachlese():
    roh = ']' * 40 + '{"normen":[],"zusatz":' + '[' * (HOECHSTTIEFE + 1) + '0' + ']' * (HOECHSTTIEFE + 1) + '}'
    gelesen = antwort_parsen(roh)
    assert gelesen["roh"] and gelesen["normen"] == []
    assert gelesen["formatpruefung"]["fehler"][0]["code"] == "tiefe"

