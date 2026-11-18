"""Amtlich bezeichnete Novelle eines gespeicherten Dokumentstands."""

import re
from dataclasses import dataclass
from datetime import date

VERSION = 2
_BUND = re.compile(r"NOR[0-9]{8}")
_OBEROESTERREICH = re.compile(r"LOO[0-9]{8}")
_FUNDSTELLE = re.compile(r"(?P<nummer>[1-9][0-9]{0,4})/(?P<jahr>[1-9][0-9]{3})")
_TEILE = {f"BGBl. {teil} Nr.": teil for teil in ("I", "II", "III")}


@dataclass(frozen=True)
class Fundstelle:
    teil: str
    nummer: str
    jahr: str
    bundesland: str = ""

    @property
    def bezeichnung(self):
        if self.bundesland:
            return f"LGBl. Nr. {self.nummer}/{self.jahr}"
        return f"BGBl. {self.teil} Nr. {self.nummer}/{self.jahr}"

    @property
    def ziel(self):
        if self.bundesland:
            return None
        return f"https://www.ris.bka.gv.at/eli/bgbl/{self.teil}/{self.jahr}/{self.nummer}"


def _objekt(daten, feld):
    wert = daten.get(feld)
    return wert if isinstance(wert, dict) else {}


def novellenfundstelle(rohdaten, dokumentnummer, stand: date, *, bundesland="") -> Fundstelle | None:
    """Nur die ausdrückliche Relation „zuletzt geändert durch“ auswerten."""
    if not isinstance(rohdaten, dict) or not isinstance(dokumentnummer, str):
        return None
    meta = _objekt(rohdaten, "Metadaten")
    technisch = _objekt(meta, "Technisch")
    if technisch.get("ID") != dokumentnummer:
        return None
    applikation = technisch.get("Applikation")
    if not bundesland and applikation == "BrKons" and _BUND.fullmatch(dokumentnummer):
        norm = _objekt(_objekt(meta, "Bundesrecht"), "BrKons")
    elif bundesland == "Oberösterreich" and applikation == "LrKons" and _OBEROESTERREICH.fullmatch(dokumentnummer):
        land = _objekt(meta, "Landesrecht")
        if land.get("Bundesland") != bundesland:
            return None
        norm = _objekt(land, "LrKons")
    else:
        return None
    if norm.get("NovellenBeziehung") != "zuletzt geändert durch":
        return None
    organ, nummer = norm.get("NovellenPublikationsorgan"), norm.get("NovellenBgblnummer")
    if not isinstance(organ, str) or not isinstance(nummer, str):
        return None
    treffer = _FUNDSTELLE.fullmatch(nummer)
    if not treffer or int(treffer["jahr"]) > stand.year:
        return None
    if bundesland and organ == "LGBl.Nr.":
        return Fundstelle("", treffer["nummer"], treffer["jahr"], bundesland=bundesland)
    if not bundesland and organ in _TEILE and 2004 <= int(treffer["jahr"]) <= 2099:
        return Fundstelle(_TEILE[organ], treffer["nummer"], treffer["jahr"])
    return None
