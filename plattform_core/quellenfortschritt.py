"""Später erfasste lokale Quellenstände erkennen, keine rechtliche Aktualität prüfen."""

import re
from dataclasses import dataclass
from datetime import date, datetime

VERSION = 1


def _zeit(wert):
    return isinstance(wert, datetime) and wert.utcoffset() is not None


def _hash(wert):
    return isinstance(wert, str) and re.fullmatch(r"[a-f0-9]{64}", wert, re.ASCII) is not None


@dataclass(frozen=True)
class Quelle:
    kennung: str
    norm_id: int
    stand: date
    metadaten_hash: str
    importiert: datetime
    text_id: int | None = None
    text_hash: str | None = None
    text_parser: int | None = None
    text_erfasst: datetime | None = None

    def __post_init__(self):
        if (
            not isinstance(self.kennung, str) or re.fullmatch(r"NOR[0-9]{8}", self.kennung, re.ASCII) is None
            or type(self.norm_id) is not int or self.norm_id <= 0
            or type(self.stand) is not date or not _hash(self.metadaten_hash) or not _zeit(self.importiert)
        ):
            raise ValueError("Quellenangaben")
        if self.text_id is None:
            if any(v is not None for v in (self.text_hash, self.text_parser, self.text_erfasst)):
                raise ValueError("Unvollständiger Textstand")
        elif (
            type(self.text_id) is not int or self.text_id <= 0 or not _hash(self.text_hash)
            or type(self.text_parser) is not int or self.text_parser <= 0 or not _zeit(self.text_erfasst)
        ):
            raise ValueError("Textangaben")


@dataclass(frozen=True)
class Befund:
    kennung: str
    verwendet: int
    gegenuebergestellt: int | None
    vergleichbar: bool
    metadaten_spaeter: bool
    dokument_spaeter: bool
    verwendeter_text: int | None
    spaeterer_text: int | None


def vergleichen(verwendet, vorhanden, *, aufnahme: datetime, jetzt: datetime) -> tuple[Befund, ...]:
    """Kennungsreihung, keine Gewichtung. Nur Erfassungen nach dem damaligen Rahmen zählen.

    Ein älterer historischer Stichtag ist kein Fortschritt. Neue ID allein ist
    keine Inhaltsänderung. Auch ein neuer Parser kann einen späteren Textstand
    ergeben. Fehlender lokaler Vergleichsstand bedeutet keine Entwarnung.
    """
    if not _zeit(aufnahme) or not _zeit(jetzt) or jetzt < aufnahme:
        raise ValueError("Vergleichszeit")
    alt, neu = tuple(verwendet), tuple(vorhanden)
    if len({q.kennung for q in alt}) != len(alt) or len({q.kennung for q in neu}) != len(neu):
        raise ValueError("Kennungen nicht eindeutig")
    for gruppe, grenze in [(alt, aufnahme), (neu, jetzt)]:
        if any(q.importiert > grenze or q.text_erfasst is not None and q.text_erfasst > grenze for q in gruppe):
            raise ValueError("Zukünftige Erfassung")
    index = {q.kennung: q for q in neu}
    befunde = []
    for q in sorted(alt, key=lambda quelle: quelle.kennung):
        n = index.get(q.kennung)
        vergleichbar = n is not None and n.stand >= q.stand
        metadaten = bool(vergleichbar and n.importiert > aufnahme and (
            n.stand > q.stand or n.metadaten_hash != q.metadaten_hash
        ))
        dokument = bool(vergleichbar and n.text_id is not None and n.text_erfasst > aufnahme and (
            q.text_id is None or (n.text_hash, n.text_parser) != (q.text_hash, q.text_parser)
        ))
        befunde.append(Befund(q.kennung, q.norm_id, n.norm_id if n else None, vergleichbar,
                             metadaten, dokument, q.text_id, n.text_id if dokument else None))
    return tuple(befunde)
