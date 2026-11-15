"""Amtlich bezeichnete Novelle eines gespeicherten Dokumentstands."""

import re
from dataclasses import dataclass
from datetime import date

VERSION = 4
_BUND = re.compile(r"NOR[0-9]{8}")
_OBEROESTERREICH = re.compile(r"LOO[0-9]{8}")
_FUNDSTELLE = re.compile(r"(?P<nummer>[1-9][0-9]{0,4})/(?P<jahr>[1-9][0-9]{3})")
_TEILE = {f"BGBl. {teil} Nr.": teil for teil in ("I", "II", "III")}
_BGBL_TEILE = {"I": "Teil1", "II": "Teil2", "III": "Teil3"}
_BERICHTSNUMMER = re.compile(r"[1-9][0-9]{0,7}")
_PERIODE = re.compile(r"[IVXLCDM]{1,12}")


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


@dataclass(frozen=True)
class Kundmachung:
    dokumentnummer: str
    datum: date
    eli: str
    gesetzgebungsperiode: str = ""
    ausschussberichte_nationalrat: tuple[str, ...] = ()
    ausschussberichte_bundesrat: tuple[str, ...] = ()


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


def _einzelmetadaten(antwort):
    if not isinstance(antwort, dict):
        return {}
    ergebnis = _objekt(_objekt(antwort, "OgdSearchResult"), "OgdDocumentResults")
    referenz = ergebnis.get("OgdDocumentReference")
    if isinstance(referenz, list) and len(referenz) == 1:
        referenz = referenz[0]
    if not isinstance(referenz, dict):
        return {}
    return _objekt(_objekt(referenz, "Data"), "Metadaten")


def _kundmachungsdatum(datum_roh, jahr: str, stand: date) -> date | None:
    if not isinstance(datum_roh, str) or type(stand) is not date:
        return None
    try:
        datum = date.fromisoformat(datum_roh)
    except ValueError:
        return None
    if datum.isoformat() != datum_roh or str(datum.year) != jahr or datum > stand:
        return None
    return datum


def _eli_aus_quelle(meta, eli, pfad):
    if eli not in (f"https://www.ris.bka.gv.at{pfad}", f"https://ris.bka.gv.at{pfad}"):
        return None
    dokumenturl = _objekt(meta, "Allgemein").get("DokumentUrl")
    return eli if dokumenturl in (eli, f"https://ogd.ris.bka.gv.at{pfad}") else None


def landeskundmachung(antwort, fundstelle: Fundstelle, stand: date) -> Kundmachung | None:
    """Einen einzelnen LgblAuth-Beleg mit der ausgewiesenen oberösterreichischen Fundstelle abgleichen."""
    if fundstelle.bundesland != "Oberösterreich":
        return None
    meta = _einzelmetadaten(antwort)
    technisch = _objekt(meta, "Technisch")
    land = _objekt(meta, "Landesrecht")
    if technisch.get("Applikation") != "LgblAuth" or land.get("Bundesland") != fundstelle.bundesland:
        return None
    blatt = _objekt(land, "LgblAuth")
    if blatt.get("Lgblnummer") != fundstelle.bezeichnung:
        return None
    datum = _kundmachungsdatum(land.get("Kundmachungsdatum"), fundstelle.jahr, stand)
    if datum is None:
        return None
    # Die vollständige Kennung und der ELI müssen in der amtlichen Antwort selbst stehen.
    kurzdatum = datum.isoformat().replace("-", "")
    erwartete_id = f"LGBLA_OB_{kurzdatum}_{fundstelle.nummer}"
    if technisch.get("ID") != erwartete_id:
        return None
    pfad = f"/eli/lgbl/OB/{fundstelle.jahr}/{fundstelle.nummer}/{kurzdatum}"
    eli = _eli_aus_quelle(meta, blatt.get("EuropeanLegislationIdentifier"), pfad)
    if eli is None:
        return None
    return Kundmachung(erwartete_id, datum, eli)


def _ausschussberichte(blatt, feld):
    nummern = _objekt(blatt, feld).get("item")
    if isinstance(nummern, str):
        nummern = [nummern]
    if not isinstance(nummern, list):
        return ()
    if not all(isinstance(nummer, str) and _BERICHTSNUMMER.fullmatch(nummer) for nummer in nummern):
        return ()
    return tuple(dict.fromkeys(nummern))


def bundeskundmachung(antwort, fundstelle: Fundstelle, stand: date) -> Kundmachung | None:
    """Einen BgblAuth-Beleg und die darin genannten Ausschussberichte zuordnen."""
    teil = _BGBL_TEILE.get(fundstelle.teil)
    if fundstelle.bundesland or teil is None:
        return None
    meta = _einzelmetadaten(antwort)
    technisch = _objekt(meta, "Technisch")
    erwartete_id = f"BGBLA_{fundstelle.jahr}_{fundstelle.teil}_{fundstelle.nummer}"
    if technisch.get("Applikation") != "BgblAuth" or technisch.get("ID") != erwartete_id:
        return None
    bund = _objekt(meta, "Bundesrecht")
    blatt = _objekt(bund, "BgblAuth")
    if blatt.get("Bgblnummer") != fundstelle.bezeichnung or blatt.get("Teil") != teil:
        return None
    if blatt.get("AlteDokumentnummer", erwartete_id) != erwartete_id:
        return None
    datum = _kundmachungsdatum(blatt.get("Ausgabedatum"), fundstelle.jahr, stand)
    if datum is None:
        return None
    kurzdatum = datum.isoformat().replace("-", "")
    pfad = f"/eli/bgbl/{fundstelle.teil}/{fundstelle.jahr}/{fundstelle.nummer}/{kurzdatum}"
    eli = _eli_aus_quelle(meta, bund.get("Eli"), pfad)
    if eli is None:
        return None
    periode = blatt.get("Gesetzgebungsperiode")
    return Kundmachung(
        erwartete_id, datum, eli,
        periode if isinstance(periode, str) and _PERIODE.fullmatch(periode) else "",
        _ausschussberichte(blatt, "AusschussberichtNationalrat"),
        _ausschussberichte(blatt, "AusschussberichtBundesrat"),
    )
