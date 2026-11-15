"""Liest Dokumentreferenzen einer ausdrücklich vorgelegten RIS-Änderungsseite."""

import re
from dataclasses import dataclass
from datetime import date

from plattform_core.ris_antwort import objekt

VERSION = 3
PARSER_FASSUNG = 1
REIHUNG = ("-tag", "seite", "-pk")
NORM_REIHUNG = ("-stand", "-pk")
_DOKUMENTNUMMER = re.compile(r"NOR[0-9]{8}")
_GESETZESNUMMER = re.compile(r"[0-9]{8}")


@dataclass(frozen=True)
class Dokumentverweis:
    dokumentnummer: str
    gesetzesnummer: str
    quelle: str


def dokumente(referenzen, tag: date, anzahl: int) -> tuple[Dokumentverweis, ...] | None:
    """Eine vollständige, nicht leere Seite mit Bundes-Dokumentreferenzen prüfen."""
    if type(tag) is not date or type(anzahl) is not int or not 1 <= anzahl <= 10:
        return None
    if isinstance(referenzen, dict):
        referenzen = [referenzen]
    if not isinstance(referenzen, list) or len(referenzen) != anzahl:
        return None

    erwartet = tag.isoformat()
    kennungen = set()
    verweise = []
    for referenz in referenzen:
        if not isinstance(referenz, dict):
            return None
        meta = objekt(objekt(referenz, "Data"), "Metadaten")
        technisch = objekt(meta, "Technisch")
        allgemein = objekt(meta, "Allgemein")
        bund = objekt(objekt(meta, "Bundesrecht"), "BrKons")
        kennung, nummer = technisch.get("ID"), bund.get("Gesetzesnummer")
        quelle = allgemein.get("DokumentUrl")
        if technisch.get("Applikation") != "BrKons" or allgemein.get("Geaendert") != erwartet:
            return None
        if not isinstance(kennung, str) or not _DOKUMENTNUMMER.fullmatch(kennung) or kennung in kennungen:
            return None
        if not isinstance(nummer, str) or not _GESETZESNUMMER.fullmatch(nummer) or not isinstance(quelle, str):
            return None
        kennungen.add(kennung)
        verweise.append(Dokumentverweis(kennung, nummer, quelle))
    return tuple(verweise)
