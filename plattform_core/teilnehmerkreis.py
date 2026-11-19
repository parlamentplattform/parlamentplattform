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

VERSION = 2
EBENEN = frozenset({"bund", "land", "bezirk", "gemeinde"})
WIENER_GEMEINDE = "90001"
# Statistik Austria, Politische Bezirke, Gebietsstand 2026. Hier stehen die
# Bezirkscodes der Wiener Gemeindebezirke, jeweils mit gemeinsamer Kennziffer 900.
WIENER_BEZIRKE = {
    "901": "Wien 1., Innere Stadt",
    "902": "Wien 2., Leopoldstadt",
    "903": "Wien 3., Landstraße",
    "904": "Wien 4., Wieden",
    "905": "Wien 5., Margareten",
    "906": "Wien 6., Mariahilf",
    "907": "Wien 7., Neubau",
    "908": "Wien 8., Josefstadt",
    "909": "Wien 9., Alsergrund",
    "910": "Wien 10., Favoriten",
    "911": "Wien 11., Simmering",
    "912": "Wien 12., Meidling",
    "913": "Wien 13., Hietzing",
    "914": "Wien 14., Penzing",
    "915": "Wien 15., Rudolfsheim-Fünfhaus",
    "916": "Wien 16., Ottakring",
    "917": "Wien 17., Hernals",
    "918": "Wien 18., Währing",
    "919": "Wien 19., Döbling",
    "920": "Wien 20., Brigittenau",
    "921": "Wien 21., Floridsdorf",
    "922": "Wien 22., Donaustadt",
    "923": "Wien 23., Liesing",
}


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
    wiener_bezirk: str = ""

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
            if (self.gemeinden != (WIENER_GEMEINDE,) or not isinstance(self.wiener_bezirk, str)
                    or self.wiener_bezirk not in WIENER_BEZIRKE):
                raise GebietsFehler("Wiener Gemeindebezirke brauchen einen eindeutigen Bezirkscode.")
        elif self.wiener_bezirk != "":
            raise GebietsFehler("Ein Wiener Bezirkscode gehört zu einem Wiener Bezirksverfahren.")

    @property
    def kennung(self) -> str:
        if self.ebene == "bund":
            return "bund"
        if self.ebene == "gemeinde":
            return f"gemeinde:{self.gemeinden[0]}"
        if self.wiener_bezirk:
            return f"bezirk:wien:{self.wiener_bezirk}"
        # Abgeleiteter Gebietsschlüssel, keine behauptete amtliche Bezirksnummer.
        # Auch Landesgebietsänderungen ergeben so einen anderen Stand.
        digest = hashlib.sha256(",".join(self.gemeinden).encode("ascii")).hexdigest()
        return f"{self.ebene}:{self.land}:{digest}"

    def als_dict(self) -> dict:
        daten = {"fassung": 1, "ebene": self.ebene, "name": self.name,
                 "land": self.land, "gemeinden": list(self.gemeinden), "kennung": self.kennung}
        if self.wiener_bezirk:
            daten.update(fassung=VERSION, wiener_bezirk=self.wiener_bezirk)
        return daten

    @classmethod
    def aus_dict(cls, daten: dict) -> Gebiet:
        grundfelder = {"fassung", "ebene", "name", "land", "gemeinden", "kennung"}
        if not isinstance(daten, dict) or type(daten.get("fassung")) is not int:
            raise GebietsFehler("Unbekannter Teilnehmerkreisstand.")
        fassung = daten["fassung"]
        if fassung == VERSION:
            grundfelder.add("wiener_bezirk")
        if fassung not in (1, VERSION) or set(daten) != grundfelder or not isinstance(daten["gemeinden"], list):
            raise GebietsFehler("Unbekannter Teilnehmerkreisstand.")
        gebiet = cls(daten["ebene"], daten["name"], daten["land"], tuple(daten["gemeinden"]),
                     daten.get("wiener_bezirk", ""))
        if gebiet.als_dict() != daten:
            raise GebietsFehler("Gebietskennung stimmt nicht mit der Gemeindemenge überein.")
        return gebiet


def gebiet_fuer(
    ebene: str, haupt: Gemeindestand | None, stamm: Iterable[Gemeindestand], *, wiener_bezirk: str = "",
) -> Gebiet:
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
    if haupt.land == "wien":
        if not isinstance(wiener_bezirk, str):
            raise GebietsFehler("Wiener Gemeindebezirke brauchen einen eindeutigen Bezirkscode.")
        name = WIENER_BEZIRKE.get(wiener_bezirk, "Wien")
        return Gebiet(ebene, name, haupt.land, (haupt.kennziffer,), wiener_bezirk)
    gemeinden = tuple(sorted(g.kennziffer for g in eintraege if g.land == haupt.land and g.bezirk == haupt.bezirk))
    return Gebiet(ebene, haupt.bezirk, haupt.land, gemeinden)


def hauptwohnsitz_gehoert_dazu(
    gebiet: Gebiet, wohnsitzart: str, kennziffer: str | None, *, wiener_bezirk: str = "",
) -> bool:
    """Nur zum Festhalten des Kreises verwenden; danach den gespeicherten Kreis lesen."""
    if gebiet.ebene == "bund":
        return True
    return (wohnsitzart == "oesterreich" and kennziffer in gebiet.gemeinden
            and (not gebiet.wiener_bezirk or gebiet.wiener_bezirk == wiener_bezirk))
