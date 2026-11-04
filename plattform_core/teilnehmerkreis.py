"""Örtlicher Kreis neuer Verfahren: Hauptwohnsitz als Selbstauskunft (A0-28/29).

Nur Gebietsrechnung, ohne Datenbank oder aktuelle Mitgliedschaftsrechte. Der Aufrufer
hält die örtlich zugehörigen Konten bei Einbringung fest und prüft zusätzlich die
allgemeinen Rechte zum jeweiligen bisherigen Stichtag. Eine spätere Profilangabe
ist deshalb ausdrücklich kein Ersatz für den festgehaltenen Kreis.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass

VERSION = 1
EBENEN = frozenset({"bund", "land", "bezirk", "gemeinde"})


class GebietsFehler(ValueError):
    """Unbekanntes, nicht eindeutiges oder noch nicht ausreichend erfasstes Gebiet."""


@dataclass(frozen=True)
class Gemeindestand:
    kennziffer: str
    name: str
    bezirk: str
    land: str

    def __post_init__(self):
        if (not isinstance(self.kennziffer, str) or len(self.kennziffer) != 5
                or not self.kennziffer.isascii() or not self.kennziffer.isdecimal()
                or not all(isinstance(v, str) and v.strip() for v in (self.name, self.bezirk, self.land))):
            raise GebietsFehler("Ungültiger Gemeindestand.")


@dataclass(frozen=True)
class Gebiet:
    ebene: str
    name: str
    land: str
    gemeinden: tuple[str, ...]

    def __post_init__(self):
        if (not isinstance(self.ebene, str) or self.ebene not in EBENEN
                or not isinstance(self.name, str) or not isinstance(self.land, str)):
            raise GebietsFehler("Ungültige Gebietsebene.")
        if not isinstance(self.gemeinden, tuple) or any(
            not isinstance(k, str) or len(k) != 5 or not k.isascii() or not k.isdecimal()
            for k in self.gemeinden
        ) or tuple(sorted(set(self.gemeinden))) != self.gemeinden:
            raise GebietsFehler("Ungültige Gemeindemenge.")
        if self.ebene == "bund":
            if self.name or self.land or self.gemeinden:
                raise GebietsFehler("Bund hat keine örtliche Begrenzung.")
        elif not self.name.strip() or not self.land.strip() or not self.gemeinden:
            raise GebietsFehler("Das örtliche Gebiet ist leer.")
        if self.ebene == "gemeinde" and len(self.gemeinden) != 1:
            raise GebietsFehler("Eine Gemeinde braucht genau eine Kennziffer.")
        if self.ebene == "bezirk" and self.land == "wien":
            raise GebietsFehler("Wiener Gemeindebezirke sind noch nicht getrennt erfasst.")

    @property
    def kennung(self) -> str:
        if self.ebene == "bund":
            return "bund"
        if self.ebene == "gemeinde":
            return f"gemeinde:{self.gemeinden[0]}"
        # Abgeleiteter Gebietsschlüssel, keine behauptete amtliche Bezirksnummer.
        # Auch Landesgebietsänderungen ergeben so einen anderen Stand.
        digest = hashlib.sha256(",".join(self.gemeinden).encode("ascii")).hexdigest()
        return f"{self.ebene}:{self.land}:{digest}"

    def als_dict(self) -> dict:
        return {"fassung": VERSION, "ebene": self.ebene, "name": self.name,
                "land": self.land, "gemeinden": list(self.gemeinden), "kennung": self.kennung}

    @classmethod
    def aus_dict(cls, daten: dict) -> Gebiet:
        if (not isinstance(daten, dict)
                or set(daten) != {"fassung", "ebene", "name", "land", "gemeinden", "kennung"}
                or type(daten["fassung"]) is not int or daten["fassung"] != VERSION
                or not isinstance(daten["gemeinden"], list)):
            raise GebietsFehler("Unbekannter Teilnehmerkreisstand.")
        gebiet = cls(daten["ebene"], daten["name"], daten["land"], tuple(daten["gemeinden"]))
        if daten["kennung"] != gebiet.kennung:
            raise GebietsFehler("Gebietskennung stimmt nicht mit der Gemeindemenge überein.")
        return gebiet


def gebiet_fuer(ebene: str, haupt: Gemeindestand | None, stamm: Iterable[Gemeindestand]) -> Gebiet:
    """Gemeinde/Land/Bezirk der eindeutigen Hauptgemeinde; kein Nebenwohnsitzparameter.

    Bezirke werden durch ihre Gemeindemenge innerhalb desselben Landes bestimmt.
    Die Namensangabe gruppiert nur den amtlichen Stamm, nie freie Profiltexte.
    """
    if not isinstance(ebene, str) or ebene not in EBENEN:
        raise GebietsFehler("Unbekannte Gebietsebene.")
    if ebene == "bund":
        return Gebiet("bund", "", "", ())
    if haupt is None:
        raise GebietsFehler("Ein tatsächlich gemeldeter Hauptwohnsitz fehlt.")
    eintraege = list(stamm)
    if len({g.kennziffer for g in eintraege}) != len(eintraege):
        raise GebietsFehler("Gemeindekennziffer ist nicht eindeutig.")
    if haupt not in eintraege:
        raise GebietsFehler("Hauptgemeinde gehört nicht zu diesem Gemeindestand.")
    if ebene == "gemeinde":
        return Gebiet(ebene, haupt.name, haupt.land, (haupt.kennziffer,))
    if ebene == "land":
        gemeinden = tuple(sorted(g.kennziffer for g in eintraege if g.land == haupt.land))
        return Gebiet(ebene, haupt.land, haupt.land, gemeinden)
    gemeinden = tuple(sorted(g.kennziffer for g in eintraege if g.land == haupt.land and g.bezirk == haupt.bezirk))
    return Gebiet(ebene, haupt.bezirk, haupt.land, gemeinden)


def hauptwohnsitz_gehoert_dazu(gebiet: Gebiet, wohnsitzart: str, kennziffer: str | None) -> bool:
    """Nur zum Festhalten des Kreises verwenden; danach den gespeicherten Kreis lesen."""
    if gebiet.ebene == "bund":
        return True
    return wohnsitzart == "oesterreich" and kennziffer in gebiet.gemeinden
