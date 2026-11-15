"""Liest Dokumentreferenzen einer ausdrücklich vorgelegten RIS-Änderungsseite."""

import re
from dataclasses import dataclass
from datetime import date

from plattform_core.faktenbestand import HASH_MUSTER
from plattform_core.ris_antwort import objekt

VERSION = 5
PARSER_FASSUNG = 1
TAGESABGLEICH_FASSUNG = 1
REIHUNG = ("-tag", "seite", "-pk")
NORM_REIHUNG = ("-stand", "-pk")
_DOKUMENTNUMMER = re.compile(r"NOR[0-9]{8}")
_GESETZESNUMMER = re.compile(r"[0-9]{8}")


@dataclass(frozen=True)
class Dokumentverweis:
    dokumentnummer: str
    gesetzesnummer: str
    quelle: str


@dataclass(frozen=True)
class Tagesseite:
    datensatz: int
    tag: date
    seite: int
    treffer: int
    sha256: str
    dokumentnummern: tuple[str | None, ...]


class TagesabgleichFehler(ValueError):
    """Der ausgewählte Seitensatz erfüllt die Abgleichregel nicht."""


def tagesabgleich(tag: date, seiten: list[Tagesseite]) -> dict:
    """Prüft den Seitensatz gegen die Trefferzahl seiner eigenen Belege."""
    if not seiten or any(s.tag != tag for s in seiten):
        raise TagesabgleichFehler("tag")
    treffer = seiten[0].treffer
    if treffer < 1 or any(s.treffer != treffer for s in seiten):
        raise TagesabgleichFehler("trefferzahl")
    if len(seiten) != (treffer + 9) // 10:
        raise TagesabgleichFehler("seitenfolge")

    belege, gesehen = [], set()
    for nummer, s in enumerate(sorted(seiten, key=lambda s: s.seite), start=1):
        if s.seite != nummer:
            raise TagesabgleichFehler("seitenfolge")
        if s.datensatz < 1 or not isinstance(s.sha256, str) or not HASH_MUSTER.fullmatch(s.sha256):
            raise TagesabgleichFehler("beleg")
        dokumentnummern = s.dokumentnummern
        erwartet = min(10, treffer - (nummer - 1) * 10)
        if len(dokumentnummern) != erwartet or any(
            not isinstance(k, str) or not _DOKUMENTNUMMER.fullmatch(k) for k in dokumentnummern
        ):
            raise TagesabgleichFehler("referenzen")
        nummern = set(dokumentnummern)
        if len(nummern) != len(dokumentnummern) or gesehen.intersection(nummern):
            raise TagesabgleichFehler("dokument_doppelt")
        gesehen.update(nummern)
        belege.append({
            "seite": nummer, "datensatz": s.datensatz, "original_sha256": s.sha256,
            "dokumentnummern": list(dokumentnummern),
        })
    return {
        "fassung": TAGESABGLEICH_FASSUNG, "tag": tag.isoformat(),
        "gemeldete_treffer": treffer, "seiten": belege,
    }


def leere_trefferseite(antwort):
    """Erkennt die beobachtete RIS-Leermeldung für die erste Seite."""
    return antwort == {"OgdSearchResult": {"OgdDocumentResults": {
        "Hits": {"@pageNumber": "1", "@pageSize": "10", "#text": "0"},
    }}}


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
