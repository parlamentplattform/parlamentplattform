"""SVG-Diagramme: wohlgeformt, beschriftet, sicher escaped — ohne Django."""

import re
import xml.etree.ElementTree as ET

from hypothesis import given, settings
from hypothesis import strategies as st

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
    assert svg.count("<rect") == 3  # zwei Segmente + der eigene Papiergrund (Dark-Mode-fest)


def test_anteils_balken_ohne_stimmen_zeigt_neutrale_flaeche():
    svg = anteils_balken([("Ja", 0, BLAU)], "Noch keine Stimmen")
    wohlgeformt(svg)
    assert "fill-opacity" in svg and "<title>" not in svg


def test_hochkomma_bricht_nicht_aus_dem_aria_attribut_aus():
    """Befund #0: Die Attribute sind mit einfachen Anführungszeichen gebaut, und der Antragstitel
    fließt in die Beschreibung. `xml.sax.saxutils.escape` ließ das Hochkomma stehen — ein Titel
    wie x' onload='alert(1)' hängte ein ausführbares Attribut an das Wurzelelement, das die
    Übersichtsseite mit |safe ausliefert. `html.escape` maskiert beide Anführungszeichen."""
    titel = "x' onload='alert(1)' data-x='"
    svg = anteils_balken([("Ja", 1, BLAU)], f"Ergebnis zu „{titel}“")
    assert "onload='" not in svg and "onload=" not in svg.split("aria-label=")[0]
    wurzel = wohlgeformt(svg)
    assert wurzel.get("onload") is None
    assert wurzel.get("aria-label") == f"Ergebnis zu „{titel}“"  # der Text bleibt vollständig lesbar
    # auch ohne eine einzige Stimme wird der Kopf mit der Beschreibung gebaut
    leer = anteils_balken([("Ja", 0, BLAU)], titel)
    assert wohlgeformt(leer).get("onload") is None


#: Steuerzeichen sind in XML nie erlaubt — sie sind kein Escaping-Thema, also nicht Teil der Eigenschaft.
_TEXT = st.text(st.characters(blacklist_categories=("Cc", "Cs")), min_size=1, max_size=60)


@settings(max_examples=200, deadline=None)
@given(_TEXT, _TEXT)
def test_beliebiger_text_hinterlaesst_kein_rohes_zeichen_im_svg(beschreibung, name):
    """Eigenschaft: Für jeden Text stehen im erzeugten SVG außerhalb des Markups selbst weder
    rohe Anführungszeichen noch < — Nutzertext kann also nie Markup werden. Geprüft wird über die
    eigene Bausprache: Alle Attribute sind einfach gequotet, jeder Textknoten ist maskiert."""
    svg = anteils_balken([(name, 2, BLAU), ("Nein", 1, ROT)], beschreibung)
    # Aus dem Markup alle Attributwerte und Tag-Namen entfernen — was übrig bleibt, ist Nutzertext.
    rest = re.sub(r"<[a-zA-Z/][^<>]*>", "", svg)
    assert "'" not in rest and '"' not in rest and "<" not in rest
    # Innerhalb der Tags darf kein Attributwert vorzeitig enden: kein ' außer als Begrenzer.
    for tag in re.findall(r"<[a-zA-Z][^<>]*>", svg):
        werte = re.findall(r"='([^']*)'", tag)
        assert "'" not in "".join(werte) and "<" not in "".join(werte)
    wohlgeformt(svg)
