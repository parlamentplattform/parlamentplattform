"""Eine nach Bundesland begrenzte Seite amtlicher LrKons-Metadaten, keine Titelsuche.

RIS-OGD-API-HandbuchV2.6, Juli2025, Seiten31/32. Keine automatische Aktualisierung,
juristische Relevanzprüfung oder Änderung des bestehenden Modellquellenkontexts.
"""

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date

from django.utils.html import strip_tags

from faktenbasis.ris import (
    GESETZESNUMMER,
    ZEITGRENZE,
    ImportAntwort,
    Normdaten,
    RisFehler,
    _hash,
    _KeineUmleitung,
    _objekt,
    _text,
    amtliche_url,
    begrenzt_lesen,
)
from plattform_core.quellenumfang import BUNDESLAENDER

API = "https://data.bka.gv.at/ris/api/v2.6/Landesrecht"
KENNUNG = re.compile(r"L[A-Z]{2}[0-9]{8}\Z", re.ASCII)


def argumente_pruefen(gesetzesnummer, stand, bundesland):
    if not isinstance(gesetzesnummer, str) or not GESETZESNUMMER.fullmatch(gesetzesnummer):
        raise RisFehler("gesetzesnummer")
    if type(stand) is not date:
        raise RisFehler("stichtag")
    if not isinstance(bundesland, str) or bundesland not in BUNDESLAENDER:
        raise RisFehler("bundesland")


def antwort_parsen(daten, gesetzesnummer, bundesland):
    argumente_pruefen(gesetzesnummer, date.min, bundesland)
    ergebnisse = _objekt(_objekt(_objekt(daten).get("OgdSearchResult")).get("OgdDocumentResults"))
    hits = _objekt(ergebnisse.get("Hits"))
    try:
        treffer = int(hits["#text"])
        if (not 0 <= treffer <= 2147483647 or str(hits["@pageNumber"]) != "1"
                or str(hits["@pageSize"]) != "10"):
            raise ValueError
    except (KeyError, TypeError, ValueError) as fehler:
        raise RisFehler("antwortformat") from fehler
    referenzen = ergebnisse.get("OgdDocumentReference")
    if treffer == 0:
        if referenzen is None or referenzen == [] or (
                isinstance(referenzen, dict) and referenzen.get("@xsi:nil") == "true"):
            return ImportAntwort((), 0, _hash(daten), daten)
        raise RisFehler("antwortformat")
    if isinstance(referenzen, dict):
        referenzen = [referenzen]
    if not isinstance(referenzen, list) or not 0 < len(referenzen) <= min(treffer, 10):
        raise RisFehler("antwortformat")
    normen, kennungen = [], set()
    for referenz in referenzen:
        roh = _objekt(_objekt(referenz).get("Data"))
        meta = _objekt(roh.get("Metadaten"))
        technisch = _objekt(meta.get("Technisch"))
        land = _objekt(meta.get("Landesrecht"))
        kons = _objekt(land.get("LrKons"))
        ris_id = _text(technisch.get("ID"), 11)
        nummer = _text(kons.get("Gesetzesnummer"), 8)
        if (technisch.get("Applikation") != "LrKons" or not KENNUNG.fullmatch(ris_id)
                or land.get("Bundesland") != BUNDESLAENDER[bundesland]
                or nummer != gesetzesnummer or ris_id in kennungen):
            raise RisFehler("kennung")
        quelle = amtliche_url(_objekt(meta.get("Allgemein")).get("DokumentUrl"))
        url = urllib.parse.urlsplit(quelle)
        if ris_id not in url.path.split("/") and urllib.parse.parse_qs(url.query).get("Dokumentnummer") != [ris_id]:
            raise RisFehler("kennung")
        kennungen.add(ris_id)
        normen.append(Normdaten(
            ris_id=ris_id, gesetzesnummer=nummer,
            kurztitel=html.unescape(strip_tags(_text(land.get("Kurztitel"), 1000))),
            titel=html.unescape(strip_tags(re.sub(
                r"<br\s*/?>", "\n", _text(land.get("Titel"), 20000, leer=True), flags=re.IGNORECASE,
            ))),
            typ=_text(kons.get("Typ"), 100, leer=True),
            abschnitt=_text(kons.get("ArtikelParagraphAnlage"), 100, leer=True),
            quelle=quelle, rohdaten=roh, inhalt_hash=_hash(roh),
            ebene="Land", bundesland=BUNDESLAENDER[bundesland],
        ))
    return ImportAntwort(tuple(normen), treffer, _hash(daten), daten)


def abrufen(gesetzesnummer, stand, bundesland):
    argumente_pruefen(gesetzesnummer, stand, bundesland)
    parameter = {
        "Applikation": "LrKons", "Gesetzesnummer": gesetzesnummer,
        f"Bundesland.SucheIn{bundesland}": "true", "Fassung.FassungVom": stand.isoformat(),
        "DokumenteProSeite": "Ten", "Seitennummer": "1",
    }
    url = API + "?" + urllib.parse.urlencode(parameter)
    request = urllib.request.Request(url, headers={
        "Accept": "application/json", "User-Agent": "DDOE-ParlamentPlattform-Einzelimport (plattform@ddoe.at)",
    })
    try:
        beginn = time.monotonic()
        with urllib.request.build_opener(_KeineUmleitung()).open(request, timeout=ZEITGRENZE) as antwort:
            if antwort.status != 200 or antwort.headers.get_content_type() != "application/json":
                raise RisFehler("antwortformat")
            inhalt = begrenzt_lesen(antwort, beginn)
        parsed = antwort_parsen(json.loads(inhalt.decode("utf-8-sig")), gesetzesnummer, bundesland)
    except RisFehler:
        raise
    except (OSError, urllib.error.URLError) as fehler:
        raise RisFehler("abruf") from fehler
    except (ValueError, RecursionError) as fehler:
        raise RisFehler("antwortformat") from fehler
    return ImportAntwort(parsed.normen, parsed.treffer, parsed.antwort_hash, parsed.rohdaten, url)
