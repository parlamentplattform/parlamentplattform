"""Personal-Bestandsrahmen ohne eigenen Modell-, Netz- oder Schreibzugriff.

Nur die bekannte Publikation und tatsächlich zuvor gespeicherte Schnappschüsse.
Ein vollständiger Bestandsrahmen ist weder vollständiges Österreich-Personal noch
eine Kapazitäts-/Personalfolgenprognose. Neue Rechtsfolgenaufträge halten ihn fest.
"""

import copy
import hashlib
import hmac
import json
from datetime import datetime

from django.utils import timezone

from faktenbasis.models import PersonalAggregat, PersonalRessorttabelle
from faktenbasis.personalbeleg import ORIGINAL_SHA256, QUELLE
from plattform_core.personalressorts import RESSORTS

VERSION = 1
UMFANG = "bundespersonal_bestand_ohne_folgenprognose"
PUBLIKATION = "Das Personal des Bundes 2026 – Daten und Fakten"
AGGREGAT_BEREICH = "Bundespersonal nach Art des Dienstverhältnisses"
_META = {"id", "datenjahr", "einheit", "quelle", "publikation", "seite", "tabelle",
         "original_sha256", "parser_fassung", "erfasst_am"}
_AGGREGAT = _META | {"bereich", "beamte", "vertragliches_personal", "gesamt"}
_RESSORT = _META | {"stichtag", "methodik_seite", "ressorts", "gesamt"}
_WURZEL = {"version", "umfang", "erfasst_am", "text_sha256", "zustand", "aggregat", "ressorttabelle", "fehler", "sha256"}


class PersonalrahmenFehler(ValueError):
    pass


def _hash(d):
    return hashlib.sha256(json.dumps(d, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _hex(s):
    return isinstance(s, str) and len(s) == 64 and all(c in "0123456789abcdef" for c in s)


def _zeit(s):
    if not isinstance(s, str):
        raise PersonalrahmenFehler("personalrahmen_zeit")
    try:
        d = datetime.fromisoformat(s)
    except ValueError as e:
        raise PersonalrahmenFehler("personalrahmen_zeit") from e
    if timezone.is_naive(d):
        raise PersonalrahmenFehler("personalrahmen_zeit")
    return d


def _zahl(n):
    return type(n) is int and 0 <= n <= 2**63 - 1


def _metadaten(d, *, ressort, erfasst):
    if (not isinstance(d, dict) or set(d) != (_RESSORT if ressort else _AGGREGAT)
            or not _zahl(d.get("id")) or not d["id"]
            or type(d["datenjahr"]) is not int or d["datenjahr"] != 2025
            or type(d["parser_fassung"]) is not int or d["parser_fassung"] != 1
            or d["einheit"] != "VBÄ" or d["quelle"] != QUELLE
            or d["publikation"] != PUBLIKATION or d["original_sha256"] != ORIGINAL_SHA256
            or type(d["seite"]) is not int or d["seite"] != (30 if ressort else 75)
            or type(d["tabelle"]) is not int or d["tabelle"] != (7 if ressort else 20)
            or _zeit(d["erfasst_am"]) > erfasst):
        raise PersonalrahmenFehler("personalrahmen_herkunft")
    if ressort:
        if d["stichtag"] != "2025-12-31" or type(d["methodik_seite"]) is not int or d["methodik_seite"] != 175:
            raise PersonalrahmenFehler("personalrahmen_methodik")
        if not isinstance(d["ressorts"], list) or len(d["ressorts"]) != len(RESSORTS):
            raise PersonalrahmenFehler("personalrahmen_ressorts")
        for i, (z, name) in enumerate(zip(d["ressorts"], RESSORTS, strict=True)):
            if (not isinstance(z, dict) or set(z) != {"ressort", "gesamt", "zentralstelle", "nachgeordnet"}
                    or z["ressort"] != name or not _zahl(z["gesamt"])
                    or (i == 0 and (z["zentralstelle"] is not None or z["nachgeordnet"] is not None))
                    or (i > 0 and (not _zahl(z["zentralstelle"]) or not _zahl(z["nachgeordnet"])))):
                raise PersonalrahmenFehler("personalrahmen_ressorts")
        if (not isinstance(d["gesamt"], dict) or set(d["gesamt"]) != {"gesamt", "zentralstelle", "nachgeordnet"}
                or any(not _zahl(v) for v in d["gesamt"].values())):
            raise PersonalrahmenFehler("personalrahmen_zahlen")
        # Originalrundungen ausdrücklich nicht mit einer Summengleichheit verändern.
    elif (d["bereich"] != AGGREGAT_BEREICH or any(not _zahl(d[k]) for k in ("beamte", "vertragliches_personal", "gesamt"))
          or not d["gesamt"] or d["beamte"] + d["vertragliches_personal"] != d["gesamt"]):
        raise PersonalrahmenFehler("personalrahmen_zahlen")


def _lesen(obj, felder):
    d = {k: getattr(obj, "pk" if k == "id" else k) for k in felder}
    for k in ("erfasst_am", "stichtag"):
        if k in d:
            d[k] = d[k].isoformat()
    return copy.deepcopy(d)


def festhalten(text_sha256, *, jetzt=None):
    """Zwei begrenzte lokale Abfragen, keine Auswahl vermeintlich betroffener Ressorts."""
    zeit = jetzt or timezone.now()
    if not _hex(text_sha256) or timezone.is_naive(zeit):
        raise PersonalrahmenFehler("personalrahmen_textbindung")
    d = {"version": VERSION, "umfang": UMFANG, "erfasst_am": zeit.isoformat(), "text_sha256": text_sha256,
         "aggregat": None, "ressorttabelle": None, "fehler": []}
    for key, modell, felder in (("aggregat", PersonalAggregat, _AGGREGAT), ("ressorttabelle", PersonalRessorttabelle, _RESSORT)):
        # Mehr als ein Stand derselben bekannten Original-/Parserfassung ist hier
        # mehrdeutig, keine Einladung zu einer stillen Auswahl oder Vollabfrage.
        zeilen = list(modell.objects.filter(original_sha256=ORIGINAL_SHA256, parser_fassung=1,
                                            erfasst_am__lte=zeit)[:2])
        if len(zeilen) > 1:
            d["fehler"].append(key)
        elif zeilen:
            beleg = _lesen(zeilen[0], felder)
            try:
                _metadaten(beleg, ressort=key == "ressorttabelle", erfasst=zeit)
            except PersonalrahmenFehler:
                d["fehler"].append(key)
            else:
                d[key] = beleg
    if d["fehler"]:
        d.update(aggregat=None, ressorttabelle=None, zustand="fehler")
    else:
        anzahl = sum(d[k] is not None for k in ("aggregat", "ressorttabelle"))
        d["zustand"] = ("leer", "teilweise", "vorhanden")[anzahl]
    rahmen = {**d, "sha256": _hash(d)}
    pruefen(rahmen, text_sha256=text_sha256)
    return rahmen


def pruefen(rahmen, *, text_sha256):
    """Exakten historischen Rahmen rekonstruieren, ohne heutige Quellen nachzuladen."""
    if not isinstance(rahmen, dict) or set(rahmen) != _WURZEL or not _hex(text_sha256):
        raise PersonalrahmenFehler("personalrahmen_form")
    d = copy.deepcopy(rahmen)
    sha = d.pop("sha256")
    try:
        gueltig = _hex(sha) and hmac.compare_digest(sha, _hash(d))
    except (TypeError, ValueError, UnicodeEncodeError) as e:
        raise PersonalrahmenFehler("personalrahmen_hash") from e
    if (not gueltig or type(d["version"]) is not int or d["version"] != VERSION
            or d["umfang"] != UMFANG or d["text_sha256"] != text_sha256):
        raise PersonalrahmenFehler("personalrahmen_bindung")
    zeit = _zeit(d["erfasst_am"])
    if not isinstance(d["fehler"], list) or d["fehler"] not in [[], ["aggregat"], ["ressorttabelle"], ["aggregat", "ressorttabelle"]]:
        raise PersonalrahmenFehler("personalrahmen_fehlerstand")
    if d["fehler"]:
        if d["zustand"] != "fehler" or d["aggregat"] is not None or d["ressorttabelle"] is not None:
            raise PersonalrahmenFehler("personalrahmen_fehlerstand")
    else:
        n = 0
        for key in ("aggregat", "ressorttabelle"):
            if d[key] is not None:
                _metadaten(d[key], ressort=key == "ressorttabelle", erfasst=zeit)
                n += 1
        if d["zustand"] != ("leer", "teilweise", "vorhanden")[n]:
            raise PersonalrahmenFehler("personalrahmen_vollstaendigkeit")
    return d
