import hashlib
import itertools
import json

import pytest
from hypothesis import given
from hypothesis import strategies as st

from plattform_core.faktenbestand import (
    HASH_BEZUEGE,
    TECHNISCHE_HOECHSTZAHL,
    VERSION,
    BestandsFehler,
    kanonisch,
    nachweis,
)


def zeile(nummer=1, sammlung="norm", pruefsumme="a" * 64):
    return {"sammlung": sammlung, "nummer": nummer, "pruefsumme": pruefsumme}


def test_leerstand_und_hash_sind_mit_standard_json_nachrechenbar():
    d = nachweis([], 1)
    assert VERSION == d["inhalt"]["fassung"] == 1
    assert d["inhalt"]["eintraege"] == []
    assert {s["sammlung"]: s["hash_bezug"] for s in d["inhalt"]["sammlungen"]} == HASH_BEZUEGE
    assert all(s["anzahl"] == 0 for s in d["inhalt"]["sammlungen"])
    raw = json.dumps(d["inhalt"], sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode()
    assert hashlib.sha256(raw).hexdigest() == d["sha256"]


def test_inputreihenfolge_und_registergrenze_sind_keine_inhaltsaenderung():
    eingang = [zeile(11), zeile(2), zeile(1, "normtext")]
    erwartet = nachweis(eingang, 3)
    for reihung in itertools.permutations(eingang):
        assert nachweis(reihung, 50) == erwartet
    assert [e["nummer"] for e in erwartet["inhalt"]["eintraege"]] == [2, 11, 1]
    assert eingang[0]["nummer"] == 11  # Fremde Eingabe bleibt unverändert.


@given(st.integers(min_value=1, max_value=2**63 - 1))
def test_identitaet_oder_hash_aendern_den_nachweis(nummer):
    alt = nachweis([zeile(nummer)], 1)["sha256"]
    for neu in [zeile(nummer + 1), zeile(nummer, "normtext"), zeile(nummer, pruefsumme="b" * 64)]:
        assert nachweis([neu], 1)["sha256"] != alt


@pytest.mark.parametrize("grenze", [None, True, 0, -1, 1.5, "2", TECHNISCHE_HOECHSTZAHL + 1])
def test_ungueltige_grenze_oeffnet_keinen_nachweis(grenze):
    with pytest.raises(BestandsFehler, match="grenze"):
        nachweis([], grenze)


@pytest.mark.parametrize("d", [
    None, [], {}, {**zeile(), "name": "Privat"}, {"sammlung": "norm", "nummer": 1},
    zeile(sammlung="unbekannt"), zeile(sammlung=[]), zeile(True), zeile(0), zeile(-1), zeile("1"),
    zeile(pruefsumme=None), zeile(pruefsumme="a" * 63), zeile(pruefsumme="A" * 64),
    zeile(pruefsumme="a" * 64 + "\n"), zeile(pruefsumme="ö" * 64),
])
def test_unvollstaendige_oder_fremde_zuordnung_wird_nicht_fingerabgedruckt(d):
    with pytest.raises(BestandsFehler, match="daten"):
        nachweis([d], 2)


def test_doppelte_identitaet_auch_mit_anderem_hash_ist_fehler():
    with pytest.raises(BestandsFehler, match="daten"):
        nachweis([zeile(), zeile(pruefsumme="b" * 64)], 2)


def test_ueberlauf_liest_nur_einen_zusaetzlichen_eintrag_und_liefert_nichts():
    def quelle():
        yield zeile()
        yield zeile(2)
        pytest.fail("Nach dem Nachweis des Überlaufs nicht weiter lesen")
    with pytest.raises(BestandsFehler, match="umfang"):
        nachweis(quelle(), 1)


def test_kanonisches_utf8_hat_keine_ersatzescapes_oder_nan():
    assert kanonisch({"ä": "ö"}) == '{"ä":"ö"}'.encode()
    with pytest.raises(ValueError):
        kanonisch(float("nan"))
