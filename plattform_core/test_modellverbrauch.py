import pytest

from plattform_core.modellverbrauch import zusammenfassen


def zeile(zweck, **aenderung):
    return {"zweck": zweck, "laeufe": 1, "fehlversuche": 0, "tokens_ein": 100,
            "tokens_aus": 20, "dauer_ms": 80, **aenderung}


def test_vollstaendige_gruppen_werden_ohne_auswahl_zusammengezaehlt():
    original = [zeile("rechtsbezug", laeufe=2, fehlversuche=1), zeile("aehnlichkeit", tokens_aus=0)]
    d = zusammenfassen(original)
    assert [z["zweck"] for z in d["zeilen"]] == ["aehnlichkeit", "rechtsbezug"]
    assert d["summe"] == {"laeufe": 3, "fehlversuche": 1, "tokens_ein": 200, "tokens_aus": 20, "dauer_ms": 160}
    assert original[0]["zweck"] == "rechtsbezug"  # Eingabe unverändert
    assert d["kosten"] == {"betrag": None, "waehrung": None, "nachweis": "nicht_erfasst"}


def test_leere_oder_nulltoken_bedeuten_keinen_kostenbetrag_null():
    for zeilen in ([], [zeile("rechtsbezug", tokens_ein=0, tokens_aus=0)]):
        assert zusammenfassen(zeilen)["kosten"]["betrag"] is None


def test_fassung_zwei_zaehlt_korrektur_und_sonstige_als_sechste_gruppe():
    from plattform_core.modellverbrauch import VERSION

    zwecke = ["einschaetzung", "parametervorschlag", "aehnlichkeit", "rechtsbezug", "korrektur", "sonstige"]
    d = zusammenfassen([zeile(z) for z in zwecke])
    assert d["version"] == VERSION == 2 and d["summe"]["laeufe"] == 6
    assert [z["zweck"] for z in d["zeilen"]] == sorted(zwecke)
    with pytest.raises(ValueError):
        zusammenfassen([zeile(z) for z in [*zwecke, "siebte"]])


@pytest.mark.parametrize("zeilen", [None, [zeile("x")] * 6, [zeile("x")] * 2,
                                     [zeile("x", laeufe=True)], [zeile("x", tokens_ein=-1)],
                                     [zeile("x", fehlversuche=2)], [zeile("", tokens_ein=10)]])
def test_fremde_oder_widerspruechliche_zaehlungen_werden_nicht_still_ausgegeben(zeilen):
    with pytest.raises(ValueError):
        zusammenfassen(zeilen)
