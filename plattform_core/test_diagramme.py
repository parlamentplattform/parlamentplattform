"""SVG-Diagramme: wohlgeformt, beschriftet, sicher escaped — ohne Django."""

import xml.etree.ElementTree as ET

from plattform_core.diagramme import BLAU, GOLD, ROT, anteils_balken, balken_diagramm, linien_diagramm


def wohlgeformt(svg: str) -> ET.Element:
    return ET.fromstring(svg)


def test_linien_diagramm_zeichnet_verlauf_und_endwert():
    svg = linien_diagramm([("01.01.", 1), ("02.01.", 3), ("03.01.", 6)], "Mitglieder im Verlauf")
    wurzel = wohlgeformt(svg)
    assert wurzel.get("aria-label") == "Mitglieder im Verlauf"
    assert "<path" in svg and "stroke-width='2'" in svg
    assert ">6<" in svg  # Endwert direkt beschriftet
    assert svg.count("<title>") == 3  # ein Tooltip je Punkt, ohne JavaScript


def test_leere_daten_ergeben_leere_zeichnung():
    assert linien_diagramm([], "x") == ""
    assert balken_diagramm([], "x") == ""


def test_balken_diagramm_beschriftet_nur_maximum_und_letzten_wert():
    svg = balken_diagramm([("KW 1", 2), ("KW 2", 9), ("KW 3", 4)], "Neue Anträge")
    wohlgeformt(svg)
    assert ">9<" in svg and ">4<" in svg  # Maximum + letzter Wert …
    assert ">2<" not in svg  # … aber nicht jeder Balken (Lesbarkeit)
    assert "KW 2: 9" in svg  # Tooltip


def test_beschriftungen_werden_escaped():
    svg = balken_diagramm([("<böse>&", 1)], "Test & <mehr>")
    wurzel = wohlgeformt(svg)  # ungültiges XML würde hier scheitern
    assert wurzel.get("aria-label") == "Test & <mehr>"


def test_anteils_balken_teilt_proportional_und_traegt_tooltips():
    svg = anteils_balken([("Ja", 3, BLAU), ("Nein", 1, ROT), ("Enthaltung", 0, GOLD)], "Ergebnis")
    wohlgeformt(svg)
    assert "Ja: 3 (75 %)" in svg and "Nein: 1 (25 %)" in svg
    assert "Enthaltung" not in svg  # leere Segmente entfallen (kein 0-Pixel-Rauschen)
    assert svg.count("<rect") == 2


def test_anteils_balken_ohne_stimmen_zeigt_neutrale_flaeche():
    svg = anteils_balken([("Ja", 0, BLAU)], "Noch keine Stimmen")
    wohlgeformt(svg)
    assert "fill-opacity" in svg and "<title>" not in svg
