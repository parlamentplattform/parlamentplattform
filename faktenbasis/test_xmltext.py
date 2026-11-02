"""Echter kleiner Dokumenttext und defensive Gegenproben, ohne Netz und ORM."""

import hashlib
from pathlib import Path

import pytest

from faktenbasis.ris import HOECHSTBYTES, RisFehler
from faktenbasis.test_ris import beispiel
from faktenbasis.xmltext import xml_adresse, xmltext_parsen

RIS_ID = "NOR12006105"
NUMMER = "10000362"


def xml_beispiel():
    return (Path(__file__).with_name("testdaten") / "ris_NOR12006105.xml").read_bytes()


def test_wortlaut_und_original_bytes_bleiben_ohne_kopf_und_fuss_erhalten():
    xml = xml_beispiel()
    text = xmltext_parsen(xml, RIS_ID, NUMMER)
    assert text.xml == xml and text.xml_hash == hashlib.sha256(xml).hexdigest()
    assert "Artikel" in text.text and "Änderung des B-VG" in text.text
    assert "Kurztitel" not in text.text and "Seite" not in text.text
    assert "Gesetzesnummer" not in text.text


@pytest.mark.parametrize("ris_id,nummer", [
    ("NOR11000363", NUMMER), (RIS_ID, "10000138"), ("x", NUMMER),
])
def test_fremde_oder_ungueltige_identitaet_wird_abgewiesen(ris_id, nummer):
    with pytest.raises(RisFehler, match="kennung"):
        xmltext_parsen(xml_beispiel(), ris_id, nummer)


@pytest.mark.parametrize("vorsatz", [
    b'<!DOCTYPE risdok [<!ENTITY x "mehr">]>',
    b'<!DOCTYPE risdok SYSTEM "file:///nicht-lesen">',
    b'<?xml-stylesheet href="https://example.invalid/a.xsl"?>',
])
def test_keine_entitaeten_oder_externen_verarbeitungsanweisungen(vorsatz):
    xml = xml_beispiel().split(b"?>", 1)[1]
    with pytest.raises(RisFehler, match="xmldeklaration"):
        xmltext_parsen(vorsatz + xml, RIS_ID, NUMMER)


@pytest.mark.parametrize("inhalt", [b"<risdok>", b"\xff", b"<risdok/>"])
def test_kaputtes_xml_oder_falscher_namensraum_ist_kein_wortlaut(inhalt):
    with pytest.raises(RisFehler, match="volltextformat"):
        xmltext_parsen(inhalt, RIS_ID, NUMMER)


def test_ohne_markierten_normtext_oder_mit_zu_grosser_antwort_keine_uebernahme():
    with pytest.raises(RisFehler, match="volltextformat"):
        xmltext_parsen(xml_beispiel().replace(b'ct="text"', b'ct="unbekannt"'), RIS_ID, NUMMER)
    with pytest.raises(RisFehler, match="antwortgroesse"):
        xmltext_parsen(b"x" * (HOECHSTBYTES + 1), RIS_ID, NUMMER)


def test_xml_quelle_muss_in_den_metadaten_genannt_sein_und_genau_passen():
    roh = beispiel()["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]
    assert xml_adresse(roh, "NOR11000363") == (
        "https://ogd.ris.bka.gv.at/Dokumente/Bundesnormen/NOR11000363/NOR11000363.xml"
    )
    urls = roh["Dokumentliste"]["ContentReference"]["Urls"]["ContentUrl"]
    for url in [
        "https://evil.invalid/NOR11000363.xml",
        "https://ogd.ris.bka.gv.at/Dokumente/Bundesnormen/NOR11000363/NOR11000363.xml?x=1",
        "https://ogd.ris.bka.gv.at/Dokumente/Bundesnormen/NOR12006105/NOR12006105.xml",
    ]:
        urls[0]["Url"] = url
        with pytest.raises(RisFehler, match="volltextquelle"):
            xml_adresse(roh, "NOR11000363")
    with pytest.raises(RisFehler, match="volltextquelle"):
        xml_adresse({}, "NOR11000363")


def test_starke_verschachtelung_verbraucht_keinen_python_rekursionsstapel():
    xml = (
        '<risdok xmlns="http://www.bka.gv.at"><nutzdaten>'
        f'<absatz ct="doknr">{RIS_ID}</absatz><absatz ct="gesnr">{NUMMER}</absatz>'
        + "<span>" * 1500 + '<absatz ct="text">Amtlicher Testtext</absatz>'
        + "</span>" * 1500 + "</nutzdaten></risdok>"
    ).encode()
    assert xmltext_parsen(xml, RIS_ID, NUMMER).text == "Amtlicher Testtext"
