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


def _liste(wert):
    if isinstance(wert, dict):
        return [wert]
    if isinstance(wert, list):
        return wert
    raise RisFehler("volltextquelle")


def xml_adresse(rohdaten, ris_id):
    """Nur die ausdrücklich in den Metadaten benannte Original-XML-Adresse."""
    if not isinstance(ris_id, str) or not KENNUNG.fullmatch(ris_id):
        raise RisFehler("kennung")
    try:
        referenzen = _liste(rohdaten["Dokumentliste"]["ContentReference"])
        urls = []
        for ref in referenzen:
            if ref.get("ContentType") == "MainDocument":
                for inhalt in _liste(ref["Urls"]["ContentUrl"]):
                    if inhalt.get("DataType") == "Xml":
                        urls.append(inhalt["Url"])
        erwartet = f"https://ogd.ris.bka.gv.at/Dokumente/Bundesnormen/{ris_id}/{ris_id}.xml"
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


def xmltext_parsen(inhalt: bytes, ris_id: str, gesetzesnummer: str) -> Textdaten:
    if (
        not isinstance(ris_id, str) or not KENNUNG.fullmatch(ris_id)
        or not isinstance(gesetzesnummer, str) or not GESETZESNUMMER.fullmatch(gesetzesnummer)
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
    teile = []

    # Kopf, Fuß und bibliografische Metadaten sind kein Normwortlaut.
    for nutzdaten in wurzel.findall(f"{{{NAMENSRAUM}}}nutzdaten"):
        stapel = [nutzdaten]
        while stapel:
            element = stapel.pop()
            if element.get("ct") == "text":
                text = "".join(element.itertext()).strip()
                if text:
                    teile.append(text)
            else:
                stapel.extend(reversed(element))
    if not teile:
        raise RisFehler("volltextformat")
    return Textdaten(inhalt, "\n\n".join(teile), hashlib.sha256(inhalt).hexdigest())
