import pytest

from plattform_core.quellenauswahl import TECHNISCHE_TEXTGRENZE, auswaehlen, woerter


def test_wortanfang_ist_symmetrisch_aber_keine_beliebige_teilzeichenfolge():
    bestand = [(9, "NOR9", "Datenschutzgesetz"), (2, "NOR2", "Daten"), (1, "NOR1", "Metadaten")]
    d = auswaehlen("DATENSCHUTZ", bestand, hoechstzahl=1, mindestlaenge=3)
    assert d["treffer_ids"] == [2, 9] and d["ausgewaehlt"] == [2] and d["treffer_begrenzt"]
    assert auswaehlen("datenschutz", bestand[::-1], hoechstzahl=1, mindestlaenge=3) == d


def test_unicode_stoppwoerter_kurze_woerter_und_zahlen():
    assert woerter("Ｆｒａｇｅ Frage FÜR und für A 1234 Straße STRASSE", 3) == ["frage", "strasse"]
    assert not auswaehlen("Ein Antrag für alle Gesetze", [(1, "NOR1", "Gesetz über alle Anträge")], hoechstzahl=3, mindestlaenge=3)["ausgewaehlt"]


def test_quellengrenze_null_ist_ehrliche_leere_auswahl_mit_treffern():
    d = auswaehlen("Wald", [(1, "NOR1", "Waldgesetz")], hoechstzahl=0, mindestlaenge=3)
    assert d["treffer_ids"] == [1] and not d["ausgewaehlt"] and d["treffer_begrenzt"]


@pytest.mark.parametrize("feld,wert", [("hoechstzahl", True), ("hoechstzahl", -1), ("mindestlaenge", 1), ("mindestlaenge", 13)])
def test_ungueltige_grenzen_werden_nicht_still_verwendet(feld, wert):
    with pytest.raises(ValueError):
        auswaehlen("Test", [], **{**dict(hoechstzahl=3, mindestlaenge=3), feld: wert})


def test_groessen_und_doppelte_ids_werden_ausdruecklich_abgewiesen():
    for text, bestand in [("x" * (TECHNISCHE_TEXTGRENZE + 1), []), ("Wald", [(1, "NOR1", "Wald")] * 2), ("", [(1, "NOR1", "")] * 2001)]:
        with pytest.raises(ValueError):
            auswaehlen(text, bestand, hoechstzahl=3, mindestlaenge=3)
