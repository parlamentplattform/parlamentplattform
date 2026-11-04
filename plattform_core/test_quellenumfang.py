"""Herkunftstyp statt politischer oder geografischer Relevanzentscheidung."""

import pytest

from plattform_core.quellenumfang import BUNDESLAENDER, UMFANG, VERSION, als_dict, dokumentart, pruefen


def test_bund_bleibt_ohne_bundesland_und_mit_eigener_kennung():
    assert VERSION == 1 and UMFANG == "bund_land_ohne_gebietspruefung"
    assert dokumentart("Bund", "", "NOR00000001") == "Bundesnormen"
    assert pruefen(als_dict()) is None


@pytest.mark.parametrize("land", list(BUNDESLAENDER.values()))
def test_ausdrueckliche_landherkunft_ist_ein_kandidat_kein_zustaendigkeitsurteil(land):
    assert dokumentart("Land", land, "LOO00000001") == "Landesnormen"


@pytest.mark.parametrize("ebene,land,kennung", [
    ("Bund", "Oberösterreich", "NOR00000001"), ("Bund", "", "LOO00000001"),
    ("Land", "", "LOO00000001"), ("Land", "Oberoesterreich", "LOO00000001"),
    ("Land", "Unbekannt", "LOO00000001"), ("Land", "Wien", "NOR00000001"),
    ("EU", "", "NOR00000001"), ("bund", "", "NOR00000001"),
    ("Bund", "", "NOR00000001\n"), ("Bund", "", "NOR１２３４５６７８"),
    ("Land", "Wien", "https://ris.bka.gv.at/LOO00000001"),
    (None, "", "NOR00000001"), ("Bund", None, "NOR00000001"), ("Bund", "", None),
])
def test_keine_stille_herkunftsumdeutung_oder_titelsuche(ebene, land, kennung):
    with pytest.raises(ValueError, match="Quellenherkunft"):
        dokumentart(ebene, land, kennung)


@pytest.mark.parametrize("wert", [None, [], {}, {"regel_fassung": True, "kennung": UMFANG},
    {"regel_fassung": 2, "kennung": UMFANG}, {"regel_fassung": 1, "kennung": "gefiltert"},
    {"regel_fassung": 1, "kennung": UMFANG, "gebiet": "geheim"}])
def test_unbekannte_oder_still_veraenderte_umfangsregel_wird_abgewiesen(wert):
    with pytest.raises(ValueError, match="Quellenumfang"):
        pruefen(wert)
