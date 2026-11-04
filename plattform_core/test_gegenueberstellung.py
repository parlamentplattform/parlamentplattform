import copy
import hashlib
import json

import pytest

from plattform_core.gegenueberstellung import VERSION, pruefen

PAARE = [(17, 2), (8, 1)]
VERGLEICHE = [{"antrag": a, "fassung": f, "gemeinsamkeit": "Beide Texte behandeln ein gemeinsames Thema.",
    "unterschied": "Der zweite Text grenzt den Gegenstand enger ab."} for a, f in PAARE]


def _roh(daten):
    return json.dumps(daten, ensure_ascii=False)


def test_genau_der_vorgegebene_rahmen_ohne_inhaltliche_bestaetigung():
    roh = _roh({"vergleiche": VERGLEICHE})
    p = copy.deepcopy(PAARE)
    r = pruefen(roh, paare=p)
    assert VERSION == 1 and r["gueltig"] and not r["inhaltlich_geprueft"]
    assert r["antwort_sha256"] == hashlib.sha256(roh.encode()).hexdigest()
    assert r["vergleiche"] == VERGLEICHE and p == PAARE
    r["vergleiche"][0]["gemeinsamkeit"] = "Geändert"
    assert pruefen(roh, paare=p)["vergleiche"] == VERGLEICHE


@pytest.mark.parametrize("art", ["umgeordnet", "fremder_antrag", "andere_fassung", "bool", "float", "zusatzfeld", "empfehlung", "fehlendes_feld", "doppelt", "fehlt", "falsche_liste", "falsche_zeile"])
def test_keine_umreihung_oder_unbelegten_paarbeziehungen(art):
    d = {"vergleiche": copy.deepcopy(VERGLEICHE)}
    if art == "umgeordnet":
        d["vergleiche"].reverse()
    elif art == "fremder_antrag":
        d["vergleiche"][0]["antrag"] = 999
    elif art == "andere_fassung":
        d["vergleiche"][0]["fassung"] = 3
    elif art == "bool":
        d["vergleiche"][1]["fassung"] = True
    elif art == "float":
        d["vergleiche"][1]["fassung"] = 1.0
    elif art == "zusatzfeld":
        d["vergleiche"][0]["wichtigkeit"] = 100
    elif art == "empfehlung":
        d["empfehlung"] = "Wählen Sie"
    elif art == "fehlendes_feld":
        d["vergleiche"][0].pop("gemeinsamkeit")
    elif art == "doppelt":
        d["vergleiche"][1] = d["vergleiche"][0]
    elif art == "fehlt":
        d["vergleiche"].pop()
    elif art == "falsche_liste":
        d["vergleiche"] = {}
    else:
        d["vergleiche"][0] = None
    r = pruefen(_roh(d), paare=PAARE)
    assert not r["gueltig"] and not r["vergleiche"] and not r["inhaltlich_geprueft"]


@pytest.mark.parametrize("name,wert", [("leer", ""), ("leerraum", " "), ("rand", "Ein Text. "), ("mehrzeilig", "Ein\nText."),
    ("steuerzeichen", "Ein\x00Text."), ("zu_lang", "x"*401), ("zahl", 4), ("surrogat", "\ud800")], ids=lambda x: x if len(str(x)) < 20 else "langer-text")
def test_texte_bleiben_zwei_begrenzte_lesbare_felder(name, wert):
    d = copy.deepcopy(VERGLEICHE)
    d[0]["unterschied"] = wert
    r = pruefen(json.dumps({"vergleiche": d}), paare=PAARE)
    assert not r["gueltig"] and not r["vergleiche"]


@pytest.mark.parametrize("name,roh", [("typ", None), ("groesse", "x"*100001), ("kodierung", "\ud800"),
    ("wurzel", "[]"), ("json", "```json\n{}\n```"), ("doppelt", '{"vergleiche":[],"vergleiche":[]}'),
    ("nicht_endlich", '{"vergleiche":NaN}'), ("tiefe", "["*33+"0"+"]"*33)], ids=lambda x: x if len(str(x)) < 20 else "roh-rahmen")
def test_unbekannter_oder_mehrdeutiger_json_rahmen(name, roh):
    r = pruefen(roh, paare=PAARE)
    assert not r["gueltig"] and not r["vergleiche"]


@pytest.mark.parametrize("paare", [None, [], [(True, 1)], [(1, 0)], [(1, 1), (1, 2)], [(1, 1)]*21, [(1,)], [(1, 1.0)]])
def test_quellrahmen_muss_vor_jedem_modellvertrag_eindeutig_sein(paare):
    with pytest.raises(ValueError):
        pruefen("{}", paare=paare)


def test_klammern_und_escapete_zeichen_im_text_sind_keine_strukturtiefe():
    d = copy.deepcopy(VERGLEICHE)
    d[0]["gemeinsamkeit"] = 'Beide nennen "' + "["*35 + '" als Daten.'
    assert pruefen(_roh({"vergleiche": d}), paare=PAARE)["gueltig"]
