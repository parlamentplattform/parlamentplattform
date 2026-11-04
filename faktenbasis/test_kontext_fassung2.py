"""Neue Herkunftsfelder ausdrücklich prüfen; der eingefrorene Vertrag1 bleibt separat."""

import hashlib
import json
from pathlib import Path

import pytest

from faktenbasis.kontext import QuellenkontextFehler, eingabe, pruefen
from plattform_core.quellenumfang import als_dict


def versiegeln(rahmen):
    daten = {k: v for k, v in rahmen.items() if k != "sha256"}
    rahmen["sha256"] = hashlib.sha256(json.dumps(
        daten, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    return rahmen


def beispiel(land=False):
    p = Path(__file__).with_name("testdaten") / "quellenkontext_v1_vertragsbeleg.json"
    rahmen = json.loads(p.read_text(encoding="utf-8"))["kontext"]
    rahmen.update(version=2, umfang=als_dict())
    q = rahmen["quellen"][0]
    q.update(ebene="Bund", bundesland="")
    if land:
        q.update(ebene="Land", bundesland="Oberösterreich", ris_id="LOO00000001")
        q["quelle"] = q["quelle"].replace("Bundesnormen", "Landesnormen").replace("NOR", "LOO")
        q["dokumenttext"]["quelle"] = q["dokumenttext"]["quelle"].replace("Bundesnormen", "Landesnormen").replace("NOR", "LOO")
    return versiegeln(rahmen)


@pytest.mark.parametrize("land", [False, True], ids=["bund", "land"])
def test_neue_quellenfassung_benennt_die_herkunft_ohne_datenbank(land):
    rahmen = beispiel(land)
    daten = pruefen(rahmen)
    assert daten["version"] == 2 and daten["umfang"] == als_dict()
    q = daten["quellen"][0]
    assert q["ebene"] == ("Land" if land else "Bund")
    text = eingabe(rahmen, text_sha256="a"*64)
    anbieter_daten = json.loads(text.split("\n", 1)[1])
    assert anbieter_daten["quellen"] == daten["quellen"]
    assert anbieter_daten["umfang"] == daten["umfang"]
    assert anbieter_daten["kontext_sha256"] == rahmen["sha256"]
    assert daten["quellen"][0]["dokumenttext"]["parser_fassung"] == 1  # Herkunft ist nicht Textparserfassung.


@pytest.mark.parametrize("fehler", ["umfang_fehlend", "umfang_unbekannt", "ebene_fehlend", "falsche_ebene",
    "bundesland_fehlend", "bundesland_alias", "falscher_xml_pfad", "falsche_kennung", "zusaetzliches_feld"])
def test_hash_ersetzt_keinen_gueltigen_herkunftsvertrag(fehler):
    rahmen = beispiel(True)
    q = rahmen["quellen"][0]
    if fehler == "umfang_fehlend":
        rahmen.pop("umfang")
    elif fehler == "umfang_unbekannt":
        rahmen["umfang"]["kennung"] = "alle_quellen_geheim_gefiltert"
    elif fehler == "ebene_fehlend":
        q.pop("ebene")
    elif fehler == "falsche_ebene":
        q["ebene"] = "Bund"
    elif fehler == "bundesland_fehlend":
        q.pop("bundesland")
    elif fehler == "bundesland_alias":
        q["bundesland"] = "Oberoesterreich"
    elif fehler == "falscher_xml_pfad":
        q["dokumenttext"]["quelle"] = q["dokumenttext"]["quelle"].replace("Landesnormen", "Bundesnormen")
    elif fehler == "falsche_kennung":
        q["ris_id"] = "NOR00000001"
    else:
        q["juristisch_geprueft"] = True
    with pytest.raises(QuellenkontextFehler):
        pruefen(versiegeln(rahmen))
