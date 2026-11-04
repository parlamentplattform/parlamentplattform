"""Begrenzter amtlicher Metadaten-Abruf; keine Titelsuche und keine Modellzuordnung.

Genau eine Seite zu exakter Gesetzesnummer/Stichtag. Größen- und Zeitgrenzen sind
technische Schutzgrenzen. Kein automatischer oder periodischer Abruf.
Quelle: OGD-RIS-Handbuch V2.6, Juli 2025; https://data.bka.gv.at/ris/api/v2.6/
"""

from __future__ import annotations

import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import date

from django.utils.html import strip_tags

API = "https://data.bka.gv.at/ris/api/v2.6/Bundesrecht"
HOECHSTBYTES = 2 * 1024 * 1024
ZEITGRENZE = 15
QUELLHOSTS = frozenset({"ris.bka.gv.at", "www.ris.bka.gv.at", "ogd.ris.bka.gv.at"})
KENNUNG = re.compile(r"NOR[0-9]{8}\Z", re.ASCII)
GESETZESNUMMER = re.compile(r"[0-9]{8}\Z", re.ASCII)


class RisFehler(ValueError):
    """Öffentlich nur der feste Fehlercode; keine ungeprüften Servertexte."""

    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


def amtliche_url(url: object) -> str:
    if not isinstance(url, str) or len(url) > 2000 or any(c.isspace() for c in url):
        raise RisFehler("quelladresse")
    try:
        p = urllib.parse.urlsplit(url)
        if (
            p.scheme != "https" or p.hostname not in QUELLHOSTS
            or p.username is not None or p.password is not None or p.port is not None
            or p.fragment or "\\" in url
        ):
            raise RisFehler("quelladresse")
    except ValueError as fehler:
        raise RisFehler("quelladresse") from fehler
    return url


def _objekt(wert):
    if not isinstance(wert, dict):
        raise RisFehler("antwortformat")
    return wert


def _text(wert, grenze, *, leer=False):
    if leer and (wert is None or isinstance(wert, dict) and wert.get("@xsi:nil") == "true"):
        return ""
    if not isinstance(wert, str) or len(wert) > grenze or not (leer or wert.strip()):
        raise RisFehler("antwortformat")
    return wert.strip()


def _hash(daten) -> str:
    return hashlib.sha256(
        json.dumps(daten, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True)
class Normdaten:
    ris_id: str
    gesetzesnummer: str
    kurztitel: str
    titel: str
    typ: str
    abschnitt: str
    quelle: str
    rohdaten: dict
    inhalt_hash: str
    ebene: str = "Bund"
    bundesland: str = ""


@dataclass(frozen=True)
class ImportAntwort:
    normen: tuple[Normdaten, ...]
    treffer: int
    antwort_hash: str
    rohdaten: dict
    api_url: str = ""


def antwort_parsen(daten, gesetzesnummer: str) -> ImportAntwort:
    """Nur Metadaten passender Kennungen; ein einziger falscher Treffer bricht ab."""
    if not GESETZESNUMMER.fullmatch(gesetzesnummer):
        raise RisFehler("gesetzesnummer")
    wurzel = _objekt(_objekt(daten).get("OgdSearchResult"))
    ergebnisse = _objekt(wurzel.get("OgdDocumentResults"))
    hits = _objekt(ergebnisse.get("Hits"))
    try:
        treffer = int(hits["#text"])
        if not 0 <= treffer <= 2147483647 or str(hits["@pageNumber"]) != "1" or str(hits["@pageSize"]) != "10":
            raise ValueError
    except (KeyError, TypeError, ValueError) as fehler:
        raise RisFehler("antwortformat") from fehler
    referenzen = ergebnisse.get("OgdDocumentReference")
    if treffer == 0:
        if referenzen is None or referenzen == [] or (
            isinstance(referenzen, dict) and referenzen.get("@xsi:nil") == "true"
        ):
            return ImportAntwort((), 0, _hash(daten), daten)
        raise RisFehler("antwortformat")
    if isinstance(referenzen, dict):
        referenzen = [referenzen]
    if not isinstance(referenzen, list) or not 0 < len(referenzen) <= min(treffer, 10):
        raise RisFehler("antwortformat")
    normen = []
    kennungen = set()
    for referenz in referenzen:
        roh = _objekt(_objekt(referenz).get("Data"))
        meta = _objekt(roh.get("Metadaten"))
        technisch = _objekt(meta.get("Technisch"))
        bund = _objekt(meta.get("Bundesrecht"))
        brkons = _objekt(bund.get("BrKons"))
        ris_id = _text(technisch.get("ID"), 11)
        nummer = _text(brkons.get("Gesetzesnummer"), 8)
        if technisch.get("Applikation") != "BrKons" or not KENNUNG.fullmatch(ris_id):
            raise RisFehler("kennung")
        if nummer != gesetzesnummer or ris_id in kennungen:
            raise RisFehler("kennung")
        quelle = amtliche_url(_objekt(meta.get("Allgemein")).get("DokumentUrl"))
        url = urllib.parse.urlsplit(quelle)
        if ris_id not in url.path.split("/") and urllib.parse.parse_qs(url.query).get("Dokumentnummer") != [ris_id]:
            raise RisFehler("kennung")
        kennungen.add(ris_id)
        normen.append(Normdaten(
            ris_id=ris_id, gesetzesnummer=nummer,
            kurztitel=html.unescape(strip_tags(_text(bund.get("Kurztitel"), 1000))),
            titel=html.unescape(strip_tags(re.sub(
                r"<br\s*/?>", "\n", _text(bund.get("Titel"), 20000, leer=True), flags=re.IGNORECASE,
            ))),
            typ=_text(brkons.get("Typ"), 100, leer=True),
            abschnitt=_text(brkons.get("ArtikelParagraphAnlage"), 100, leer=True),
            quelle=quelle, rohdaten=roh, inhalt_hash=_hash(roh),
        ))
    return ImportAntwort(tuple(normen), treffer, _hash(daten), daten)


class _KeineUmleitung(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RisFehler("umleitung")


def begrenzt_lesen(antwort, beginn):
    """Auch tröpfelnde Antworten begrenzen; read1 macht höchstens einen Socket-Read.

    Der einzelne Socket-Read bleibt zusätzlich durch ZEITGRENZE begrenzt.
    Damit endet die Übertragung vor der technischen Reservierungsfrist.
    """
    teile, groesse = [], 0
    while True:
        if time.monotonic() - beginn >= ZEITGRENZE:
            raise RisFehler("abrufzeit")
        teil = antwort.read1(min(65536, HOECHSTBYTES + 1 - groesse))
        if time.monotonic() - beginn >= ZEITGRENZE:
            raise RisFehler("abrufzeit")
        if not teil:
            return b"".join(teile)
        groesse += len(teil)
        if groesse > HOECHSTBYTES:
            raise RisFehler("antwortgroesse")
        teile.append(teil)


def abrufen(gesetzesnummer: str, stand: date) -> ImportAntwort:
    if not GESETZESNUMMER.fullmatch(gesetzesnummer):
        raise RisFehler("gesetzesnummer")
    if type(stand) is not date:
        raise RisFehler("stichtag")
    parameter = {
        "Applikation": "BrKons", "Gesetzesnummer": gesetzesnummer,
        "Fassung.FassungVom": stand.isoformat(), "DokumenteProSeite": "Ten", "Seitennummer": "1",
    }
    url = API + "?" + urllib.parse.urlencode(parameter)
    anfrage = urllib.request.Request(url, headers={
        "Accept": "application/json",
        "User-Agent": "DDOE-ParlamentPlattform-Einzelimport (plattform@ddoe.at)",
    })
    try:
        opener = urllib.request.build_opener(_KeineUmleitung())
        beginn = time.monotonic()
        with opener.open(anfrage, timeout=ZEITGRENZE) as antwort:
            if antwort.headers.get_content_type() != "application/json":
                raise RisFehler("antwortformat")
            inhalt = begrenzt_lesen(antwort, beginn)
        daten = json.loads(inhalt.decode("utf-8-sig"))
        parsed = antwort_parsen(daten, gesetzesnummer)
    except RisFehler:
        raise
    except (OSError, urllib.error.URLError) as fehler:
        raise RisFehler("abruf") from fehler
    except (ValueError, RecursionError) as fehler:
        raise RisFehler("antwortformat") from fehler
    return ImportAntwort(parsed.normen, parsed.treffer, parsed.antwort_hash, parsed.rohdaten, url)
