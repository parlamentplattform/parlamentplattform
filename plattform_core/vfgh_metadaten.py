"""Nachprüfbare VfGH-Metadaten ohne inhaltliche Zuordnung von Normen."""

import re
from dataclasses import dataclass
from datetime import date

from plattform_core.ris_antwort import einzelmetadaten, objekt

VERSION = 1
REIHUNG = ("-entschieden_am", "dokumentnummer", "-pk")
_DOKUMENT = re.compile(r"JFT_(?P<tag>[0-9]{8})_[A-Z0-9]{1,24}_[0-9]{2}")
_ECLI = re.compile(r"ECLI:AT:VFGH:(?P<jahr>[0-9]{4}):[A-Z0-9.]{1,25}")


@dataclass(frozen=True)
class Entscheidung:
    dokumentnummer: str
    entschieden_am: date
    ecli: str
    geschaeftszahlen: tuple[str, ...]
    normangaben: tuple[str, ...]
    quelle: str


def _angaben(meta, feld, *, zeichen):
    rohdaten = meta.get(feld)
    if rohdaten is None or rohdaten == {}:
        return ()
    if not isinstance(rohdaten, dict):
        raise ValueError(feld)
    werte = rohdaten.get("item")
    if isinstance(werte, str):
        werte = [werte]
    if not isinstance(werte, list) or len(werte) > 500 or not all(
        isinstance(wert, str) and wert.strip() and wert.isprintable() and len(wert) <= zeichen
        for wert in werte
    ):
        raise ValueError(feld)
    return tuple(werte)


def entscheidung(antwort, erwartete_dokumentnummer: str) -> Entscheidung | None:
    """Einen einzelnen VfGH-Entscheidungstext und seine amtliche Identität abgleichen."""
    if not isinstance(erwartete_dokumentnummer, str):
        return None
    kennung = _DOKUMENT.fullmatch(erwartete_dokumentnummer)
    if not kennung:
        return None
    meta = einzelmetadaten(antwort)
    technisch = objekt(meta, "Technisch")
    judikatur = objekt(meta, "Judikatur")
    if (technisch.get("ID") != erwartete_dokumentnummer or technisch.get("Applikation") != "Vfgh"
            or judikatur.get("Dokumenttyp") != "Text"):
        return None
    rohdatum = judikatur.get("Entscheidungsdatum")
    if not isinstance(rohdatum, str):
        return None
    try:
        datum = date.fromisoformat(rohdatum)
    except ValueError:
        return None
    if datum.isoformat() != rohdatum or rohdatum.replace("-", "") != kennung["tag"]:
        return None
    ecli = judikatur.get("EuropeanCaseLawIdentifier")
    ecli_treffer = _ECLI.fullmatch(ecli) if isinstance(ecli, str) else None
    if not ecli_treffer or ecli_treffer["jahr"] != rohdatum[:4]:
        return None
    pfad = f"/Dokument.wxe?Abfrage=Vfgh&Dokumentnummer={erwartete_dokumentnummer}"
    if objekt(meta, "Allgemein").get("DokumentUrl") not in (
        f"https://ogd.ris.bka.gv.at{pfad}", f"https://www.ris.bka.gv.at{pfad}", f"https://ris.bka.gv.at{pfad}",
    ):
        return None
    try:
        geschaeftszahlen = _angaben(judikatur, "Geschaeftszahl", zeichen=256)
        normangaben = _angaben(judikatur, "Normen", zeichen=2000)
    except ValueError:
        return None
    if not geschaeftszahlen:
        return None
    return Entscheidung(erwartete_dokumentnummer, datum, ecli, geschaeftszahlen, normangaben,
                        f"https://www.ris.bka.gv.at{pfad}")
