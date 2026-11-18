"""Amtlich bezeichnete Novelle eines gespeicherten Bundesdokumentstands."""

import re
from dataclasses import dataclass
from datetime import date

VERSION = 1
_DOKUMENT = re.compile(r"NOR[0-9]{8}")
_FUNDSTELLE = re.compile(r"(?P<nummer>[1-9][0-9]{0,4})/(?P<jahr>20[0-9]{2})")
_TEILE = {f"BGBl. {teil} Nr.": teil for teil in ("I", "II", "III")}


@dataclass(frozen=True)
class Fundstelle:
    teil: str
    nummer: str
    jahr: str

    @property
    def bezeichnung(self):
        return f"BGBl. {self.teil} Nr. {self.nummer}/{self.jahr}"

    @property
    def ziel(self):
        return f"https://www.ris.bka.gv.at/eli/bgbl/{self.teil}/{self.jahr}/{self.nummer}"


def _objekt(daten, feld):
    wert = daten.get(feld)
    return wert if isinstance(wert, dict) else {}


def novellenfundstelle(rohdaten, dokumentnummer, stand: date) -> Fundstelle | None:
    """Nur die explizite BrKons-Beziehung „zuletzt geändert durch“ auswerten."""
    if not isinstance(rohdaten, dict) or not isinstance(dokumentnummer, str) or not _DOKUMENT.fullmatch(dokumentnummer):
        return None
    meta = _objekt(rohdaten, "Metadaten")
    technisch = _objekt(meta, "Technisch")
    if technisch.get("ID") != dokumentnummer or technisch.get("Applikation") != "BrKons":
        return None
    norm = _objekt(_objekt(meta, "Bundesrecht"), "BrKons")
    if norm.get("NovellenBeziehung") != "zuletzt geändert durch":
        return None
    organ, nummer = norm.get("NovellenPublikationsorgan"), norm.get("NovellenBgblnummer")
    if not isinstance(organ, str) or not isinstance(nummer, str) or organ not in _TEILE:
        return None
    treffer = _FUNDSTELLE.fullmatch(nummer)
    if not treffer or not 2004 <= int(treffer["jahr"]) <= stand.year:
        return None
    return Fundstelle(_TEILE[organ], treffer["nummer"], treffer["jahr"])
