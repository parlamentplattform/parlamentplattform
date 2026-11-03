"""Technische Auswertung eines einzelnen amtlichen RIS-Dokumenttexts.

Keine Netzaufrufe und keine Rechtsfolgen-/Verweisinterpretation. Quelladresse
und die im Dokument enthaltene Identität müssen exakt zu den Metadaten passen.
"""

import hashlib
import re
from dataclasses import dataclass
from xml.etree import ElementTree

from faktenbasis.ris import GESETZESNUMMER, HOECHSTBYTES, KENNUNG, RisFehler

NAMENSRAUM = "http://www.bka.gv.at"
PARSER_FASSUNG = 2


def _liste(wert):
    if isinstance(wert, dict):
        return [wert]
    if isinstance(wert, list):
        return wert
    raise RisFehler("volltextquelle")


def _dokumentart(ris_id, bundesland):
    if not isinstance(ris_id, str):
        raise RisFehler("kennung")
    if bundesland == "":
        if KENNUNG.fullmatch(ris_id):
            return "Bundesnormen"
    else:
        from faktenbasis.landesrecht import BUNDESLAENDER
        from faktenbasis.landesrecht import KENNUNG as LANDKENNUNG

        if isinstance(bundesland, str) and bundesland in BUNDESLAENDER.values() and LANDKENNUNG.fullmatch(ris_id):
            return "Landesnormen"
    raise RisFehler("kennung")


def xml_adresse(rohdaten, ris_id, *, bundesland=""):
    """Nur die ausdrücklich in den Metadaten benannte Original-XML-Adresse."""
    dokumentart = _dokumentart(ris_id, bundesland)
    try:
        if bundesland:
            meta = rohdaten["Metadaten"]
            if (meta["Technisch"]["Applikation"] != "LrKons" or meta["Technisch"]["ID"] != ris_id
                    or meta["Landesrecht"]["Bundesland"] != bundesland):
                raise RisFehler("kennung")
        referenzen = _liste(rohdaten["Dokumentliste"]["ContentReference"])
        urls = []
        for ref in referenzen:
            if ref.get("ContentType") == "MainDocument":
                for inhalt in _liste(ref["Urls"]["ContentUrl"]):
                    if inhalt.get("DataType") == "Xml":
                        urls.append(inhalt["Url"])
        erwartet = f"https://ogd.ris.bka.gv.at/Dokumente/{dokumentart}/{ris_id}/{ris_id}.xml"
        if not urls or any(url != erwartet for url in urls):
            raise RisFehler("volltextquelle")
    except (KeyError, TypeError, AttributeError) as fehler:
        raise RisFehler("volltextquelle") from fehler
    return erwartet


@dataclass(frozen=True)
class Textdaten:
    xml: bytes
    text: str
    xml_hash: str


def xmltext_parsen(inhalt: bytes, ris_id: str, gesetzesnummer: str, *, bundesland="") -> Textdaten:
    _dokumentart(ris_id, bundesland)
    if (
        not isinstance(gesetzesnummer, str) or not GESETZESNUMMER.fullmatch(gesetzesnummer)
    ):
        raise RisFehler("kennung")
    if not isinstance(inhalt, bytes) or not inhalt or len(inhalt) > HOECHSTBYTES:
        raise RisFehler("antwortgroesse")
    try:
        xml = inhalt.decode("utf-8-sig")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)\b", xml, flags=re.IGNORECASE):
            raise RisFehler("xmldeklaration")
        # Keine Verarbeitungsanweisung außer der eigentlichen XML-Deklaration.
        if re.search(r"<\?(?!xml\s)", xml, flags=re.IGNORECASE):
            raise RisFehler("xmldeklaration")
        wurzel = ElementTree.fromstring(xml)
    except (UnicodeError, ElementTree.ParseError, ValueError) as fehler:
        if isinstance(fehler, RisFehler):
            raise
        raise RisFehler("volltextformat") from fehler
    if wurzel.tag != f"{{{NAMENSRAUM}}}risdok":
        raise RisFehler("volltextformat")

    def angaben(ct):
        return {
            "".join(e.itertext()).strip()
            for e in wurzel.iter(f"{{{NAMENSRAUM}}}absatz") if e.get("ct") == ct
        }

    if angaben("doknr") != {ris_id} or angaben("gesnr") != {gesetzesnummer}:
        raise RisFehler("kennung")
    if bundesland and angaben("bundesland") != {bundesland}:
        raise RisFehler("kennung")
    teile = []

    # Kopf, Fuß und bibliografische Metadaten sind kein Normwortlaut.
    for nutzdaten in wurzel.findall(f"{{{NAMENSRAUM}}}nutzdaten"):
        stapel = [nutzdaten]
        while stapel:
            element = stapel.pop()
            if element.get("ct") == "text":
                # Nur die neue Textprojektion ändern, niemals die erhaltenen
                # Originalbytes. Sonst würde etwa „§1<br/>Begriff“ zusammenkleben.
                for kind in element.iter():
                    if kind.tag in {f"{{{NAMENSRAUM}}}br", f"{{{NAMENSRAUM}}}tab"} and not len(kind) and not kind.text:
                        kind.text = "\n" if kind.tag.endswith("}br") else "\t"
                text = "".join(element.itertext()).strip()
                if text:
                    teile.append(text)
            else:
                stapel.extend(reversed(element))
    if not teile:
        raise RisFehler("volltextformat")
    return Textdaten(inhalt, "\n\n".join(teile), hashlib.sha256(inhalt).hexdigest())
