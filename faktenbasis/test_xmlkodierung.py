"""Ein UTF8-Vorscan darf keinen anders interpretierten XML-Bytestrom freigeben."""

import codecs
import hashlib

import pytest

from faktenbasis.ris import RisFehler
from faktenbasis.test_xmltext import NUMMER, RIS_ID, xml_beispiel
from faktenbasis.xmltext import xmltext_parsen


def dokument(kodierung, wortlaut, vorsatz=""):
    return (
        f'<?xml version="1.0" encoding="{kodierung}"?>{vorsatz}'
        '<risdok xmlns="http://www.bka.gv.at"><nutzdaten>'
        f'<absatz ct="doknr">{RIS_ID}</absatz><absatz ct="gesnr">{NUMMER}</absatz>'
        f'<absatz ct="text">{wortlaut}</absatz></nutzdaten></risdok>'
    )


@pytest.mark.parametrize("kodierung,bom", [
    ("UTF-16LE", b""), ("UTF-16BE", b""),
    ("UTF-16LE", codecs.BOM_UTF16_LE), ("UTF-16BE", codecs.BOM_UTF16_BE),
    ("UTF-32LE", b""), ("UTF-32BE", b""),
], ids=["16le-ohne-bom", "16be-ohne-bom", "16le-bom", "16be-bom", "32le", "32be"])
@pytest.mark.parametrize("vorsatz,wortlaut", [
    ('<!DOCTYPE risdok [<!ENTITY lokal "Lokaler Testinhalt">]>', "&lokal;"),
    ('<?xml-stylesheet href="https://beispiel.invalid/stil.xsl"?>', "Lokaler Testinhalt"),
    ("", "Lokaler Testinhalt"),
], ids=["interne-entitaet", "verarbeitungsanweisung", "nur-xml"])
def test_andere_bytebreite_umgeht_den_utf8_vertrag_nicht(kodierung, bom, vorsatz, wortlaut):
    # Ausschließlich winzige interne Testdaten; keine externe Entität/Lastprobe.
    xml = bom + dokument(kodierung, wortlaut, vorsatz).encode(kodierung)
    with pytest.raises(RisFehler, match="volltextformat"):
        xmltext_parsen(xml, RIS_ID, NUMMER)


@pytest.mark.parametrize("bom", [b"", codecs.BOM_UTF8], ids=["ohne-bom", "utf8-bom"])
def test_echte_utf8_originale_mit_umlauten_bleiben_unveraendert(bom):
    xml = bom + xml_beispiel().removeprefix(codecs.BOM_UTF8)
    ergebnis = xmltext_parsen(xml, RIS_ID, NUMMER)
    assert ergebnis.xml == xml and ergebnis.xml_hash == hashlib.sha256(xml).hexdigest()
    assert "Änderung des B-VG" in ergebnis.text


@pytest.mark.parametrize("stelle", [0, 2, -1])
def test_nullzeichen_in_utf8_ist_kein_gueltiger_dokumenttext(stelle):
    xml = dokument("UTF-8", "Gültiger Text").encode()
    xml = xml[:stelle] + b"\x00" + xml[stelle:]
    with pytest.raises(RisFehler):
        xmltext_parsen(xml, RIS_ID, NUMMER)
