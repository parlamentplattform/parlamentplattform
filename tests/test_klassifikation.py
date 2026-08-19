"""Automatische Baum-Zuordnung (F-47, Stufe 1): deterministisch, tiefste Ebene gewinnt."""

from plattform_core.klassifikation import schlagwort_trifft, zuordnen

# Beispielbaum: 1 Wirtschaft -> 2 Bauwirtschaft -> 3 Installateur; 4 Energie
BAUM = [
    (1, None, ["wirtschaft", "unternehmen", "norm"]),
    (2, 1, ["baufirma", "baustelle", "baunorm"]),
    (3, 2, ["installateur", "rohr", "sanitär"]),
    (4, None, ["energie", "strom", "photovoltaik"]),
]


def test_wortanfang_und_mehrwort_treffen():
    from plattform_core.similarity import normalisieren

    text = normalisieren("Die Norm über zulässige Rohrmaße wird ausgesetzt.")
    worte = text.split(" ")
    assert schlagwort_trifft(worte, text, "rohr")  # „Rohrmaße" beginnt mit „rohr"
    assert schlagwort_trifft(worte, text, "zulässige rohrmaße")  # Mehrwort als Wortfolge
    assert not schlagwort_trifft(worte, text, "photovoltaik")
    assert not schlagwort_trifft(worte, text, "")


def test_tiefste_passende_ebene_gewinnt():
    treffer = zuordnen("Aussetzung der Norm für Rohrmaße für Installateure", BAUM)
    ids = [kid for kid, _ in treffer]
    assert ids[0] == 3  # Installateur (Detail), nicht Wirtschaft (Haupt)
    assert 1 not in ids  # Vorfahre ist impliziert, wird nicht doppelt vergeben
    assert 2 not in ids


def test_unabhaengige_aeste_bleiben_nebeneinander():
    treffer = zuordnen("Photovoltaik auf jeder Baustelle", BAUM)
    ids = {kid for kid, _ in treffer}
    assert ids == {2, 4}  # Bauwirtschaft und Energie — verschiedene Äste


def test_kein_treffer_ergibt_leere_liste_und_limit_greift():
    assert zuordnen("Völlig anderes Thema ohne Begriffe", BAUM) == []
    viele = [(i, None, ["gemeinsam"]) for i in range(10)]
    treffer = zuordnen("gemeinsame Sache", viele, limit=3)
    assert [kid for kid, _ in treffer] == [0, 1, 2]  # Gleichstand: kleinere ID zuerst, Limit hält
