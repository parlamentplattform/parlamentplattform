import copy

import pytest

from plattform_core.personalressorts import RESSORTS, VERSION, aus_text

TABELLE = """Das Personal des Bundes 202630
Tabelle 7: Verteilung des Bundespersonals in den Ressorts, Stichtag 31.12.2025
Ressort Gesamt in der Zentralstelle in nachge ordneten Dienststellen
Sonstige oberste Organe 1.239
Bundeskanzleramt 968 802 166
Inneres 37.900 5.338 32.561
Europäische und internationale Angelegenheiten 1.151 597 554
Justiz 12.297 408 11.889
Landesverteidigung 20.507 811 19.696
Finanzen 10.702 847 9.855
Wohnen, Kunst, Kultur, Medien und Sport 631 433 198
Arbeit, Soziales, Gesundheit, Pflege und Konsumentenschutz 1.901 1.000 901
Bildung 44.938 641 44.296
Frauen, Wissenschaft und For -
schung 656 399 257
Wirtschaft, Energie und Tourismus 1.935 727 1.208
Innovation, Mobilität und Infra-
struktur 854 572 282
Land- und Forstwirtschaft, Klima-
und Umweltschutz, Regionen und Wasserwirtschaft 2.422 841 1.582
Gesamt 138.100 13.416 123.445
Die strategische Planung, Steuerung und Koordination ...
"""
METHODIK = """175Das Personal des Bundes 2025
9 Technischer Annex
Aufgrund von Rundungen ergeben sich an einigen Stellen leichte Unterschiede zur Gesamtsumme.
9.1 Bezugszeitraum Daten zum Bundespersonal beziehen sich, sofern nicht anders angemerkt auf den 31.12.2025.
9.2 Datenabgrenzung
9.3 Messgröße Zur Messung von Personalkapazitäten wurden grundsätzlich Vollbeschäftigtenäqui -
valente herangezogen. Auch andere Kennzahlen wurden, sofern nicht ausdrücklich anders angemerkt, auf Basis von VBÄ berechnet.
"""


def test_originalwerte_rundung_und_nicht_angegebene_teilspalten_bleiben_erhalten():
    d = aus_text(TABELLE, METHODIK)
    assert VERSION == 1 and d["einheit"] == "VBÄ" and d["stichtag"] == "2025-12-31"
    assert tuple(z["ressort"] for z in d["ressorts"]) == RESSORTS and len(d["ressorts"]) == 14
    assert d["ressorts"][0] == {"ressort": "Sonstige oberste Organe", "gesamt": 1239, "zentralstelle": None, "nachgeordnet": None}
    assert d["ressorts"][2] == {"ressort": "Inneres", "gesamt": 37900, "zentralstelle": 5338, "nachgeordnet": 32561}
    assert d["gesamt"] == {"gesamt": 138100, "zentralstelle": 13416, "nachgeordnet": 123445}
    # Die Originalwerte weisen Rundungsdifferenzen auf; nichts wird heimlich repariert.
    inneres = d["ressorts"][2]
    assert inneres["gesamt"] != inneres["zentralstelle"] + inneres["nachgeordnet"]
    vorher = copy.deepcopy(d)
    d["ressorts"][0]["gesamt"] = 0
    assert aus_text(TABELLE, METHODIK) == vorher


@pytest.mark.parametrize("alt,neu", [
    ("202630", "202631"), ("Tabelle 7:", "Tabelle 8:"), ("31.12.2025", "31.12.2024"),
    ("Gesamt in der Zentralstelle", "Zentralstelle in der Gesamt"),
    ("Inneres 37.900", "Inneres 37900"), ("Inneres 37.900", "Inneres 37,900"),
    ("Inneres 37.900", "Inneres -37.900"), ("968 802 166", "968 802"),
    ("Sonstige oberste Organe 1.239", "Sonstige oberste Organe 1.239 0 0"),
    ("Justiz 12.297 408 11.889", ""), ("Justiz 12.297 408 11.889", "Justiz 12.297 408 11.889 Justiz 12.297 408 11.889"),
    ("Gesamt 138.100", "Noch ein Ressort 500 Gesamt 138.100"),
    ("Gesamt 138.100 13.416 123.445", "Gesamt 138.100 13.416"),
    ("Die strategische Planung", "Ende"),
])
def test_keine_fremde_tabelle_umgestellte_spalte_oder_erganzte_zeile(alt, neu):
    with pytest.raises(ValueError):
        aus_text(TABELLE.replace(alt, neu), METHODIK)


@pytest.mark.parametrize("alt,neu", [
    ("9 Technischer Annex", "8 Anhang"), ("31.12.2025", "31.12.2024"),
    ("9.2 Datenabgrenzung", ""), ("9.3 Messgröße", ""), ("VBÄ", "Personen"),
    ("Vollbeschäftigtenäqui -\nvalente", "Kopfzahlen"), ("Aufgrund von Rundungen", "Ohne Rundungen"),
])
def test_ohne_belegte_methodik_keine_angeblich_bestaetigte_einheit(alt, neu):
    with pytest.raises(ValueError, match="methodik"):
        aus_text(TABELLE, METHODIK.replace(alt, neu))


@pytest.mark.parametrize("text", [None, "", "x"*20001])
def test_unbekannte_texte_sind_keine_belege(text):
    with pytest.raises(ValueError):
        aus_text(text, METHODIK)
