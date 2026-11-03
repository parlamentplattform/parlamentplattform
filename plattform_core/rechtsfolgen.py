"""Rechtsfolgen-Antwortvertrag, keine rechtliche Verifikation.

Diese erste Fassung hat nur Personal-Bestandsbelege, keine belastbare quantitative
Bedarfsgrundlage. Deshalb bleiben alle numerischen Personalfolgen ausdrücklich
unbekannt (null). Kein Anbieter, keine Faktenänderung und keine Verfahrensentscheidung.
"""

import copy
import hashlib
import json
import re

VERSION = 2
HOECHSTZEICHEN = 100_000
HOECHSTNORMEN = 8
HOECHSTPERSONAL = 16
QUELLE = re.compile(r"(?:norm|personal_aggregat|personal_ressorts):[1-9][0-9]{0,18}\Z", re.ASCII)
_WURZEL = {"normen", "judikatur", "exekutive", "personal", "unsicherheit", "quellen"}
_NORM = {"ris_id", "titel", "aenderung", "grund"}
_DELTAS = {"beamte_delta_min", "beamte_delta_max", "vb_delta_min", "vb_delta_max"}


def schema_als_dict():
    """Öffentliche Form; tatsächliche Quellenangebote werden zusätzlich gebunden."""
    def text(limit, leer=False):
        d = {"type": "string", "minLength": 0 if leer else 1, "maxLength": limit,
             "pattern": r"^(?![\s\S]*[\u0000-\u0008\u000B-\u001F\u007F\uD800-\uDFFF])[\s\S]*$"}
        if not leer:
            d["allOf"] = [{"pattern": r"\S"}]
        return d

    norm = {"type": "object", "additionalProperties": False, "required": sorted(_NORM),
        "properties": {"ris_id": text(120, True), "titel": text(200), "grund": text(800),
                       "aenderung": {"enum": ["aendern", "aufheben", "neu", "beruehrt"]}},
        "allOf": [{"if": {"properties": {"aenderung": {"const": "neu"}}},
                   "then": {"properties": {"ris_id": {"const": ""}}}}]}
    personal = {"type": "object", "additionalProperties": False,
        "required": sorted({"bereich", "grund", *_DELTAS}),
        "properties": {"bereich": text(200), "grund": text(800), **{k: {"type": "null"} for k in sorted(_DELTAS)}}}
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object",
        "title": "Rechtsfolgenantwort", "additionalProperties": False, "required": sorted(_WURZEL),
        "properties": {"normen": {"type": "array", "maxItems": HOECHSTNORMEN, "items": norm},
            "judikatur": {"type": "object", "additionalProperties": False, "required": ["text"], "properties": {"text": text(2000)}},
            "exekutive": {"type": "object", "additionalProperties": False, "required": ["text"], "properties": {"text": text(2000)}},
            "personal": {"type": "array", "maxItems": HOECHSTPERSONAL, "items": personal},
            "unsicherheit": {"enum": ["niedrig", "mittel", "hoch"]},
            "quellen": {"type": "array", "maxItems": 22, "uniqueItems": True,
                        "items": {"type": "string", "pattern": r"^(norm|personal_aggregat|personal_ressorts):[1-9][0-9]{0,18}$"}}},
        "description": "Formprüfung. Quellen und Personalbereiche müssen zusätzlich zum damaligen Angebot passen; keine Inhaltsbestätigung."}


def schema_sha256():
    return hashlib.sha256(json.dumps(schema_als_dict(), ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()


def _text(wert, limit, *, leer=False):
    if (not isinstance(wert, str) or len(wert) > limit or not (leer or wert.strip())
            or any(ord(c) < 32 and c not in "\n\t" or ord(c) == 127 for c in wert)):
        return False
    try:
        wert.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def pruefen(text, *, quellen=(), personalbereiche=()):
    """Antwort nur auf Form und angebotene Referenzen prüfen; keine Teilfreigabe.

    Quellenreferenz ist kein Beweis, dass eine Deutung stimmt. Eine unbekannte
    Normkennung bleibt Behauptung, keine nachträglich gefundene Originalquelle.
    """
    if (not isinstance(quellen, (list, tuple)) or len(quellen) > 22
            or any(not isinstance(q, str) or QUELLE.fullmatch(q) is None for q in quellen)
            or len(set(quellen)) != len(quellen)
            or not isinstance(personalbereiche, (list, tuple)) or len(personalbereiche) > 15
            or any(not _text(b, 200) for b in personalbereiche)
            or len(set(personalbereiche)) != len(personalbereiche)):
        raise ValueError("Unklarer angebotener Quellen- oder Personalrahmen.")
    ausgang = {"fassung": VERSION, "gueltig": False, "inhaltlich_geprueft": False,
               "schema_sha256": schema_sha256(),
               "antwort_sha256": None, "fehler": [], "daten": None,
               "personalfolgen": "nicht_bestimmbar"}

    def ablehnen(code):
        return {**ausgang, "fehler": [{"pfad": "$", "code": code}]}

    if not isinstance(text, str):
        return ablehnen("typ")
    if len(text) > HOECHSTZEICHEN:
        return ablehnen("groesse")
    try:
        ausgang["antwort_sha256"] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeEncodeError:
        return ablehnen("kodierung")

    def objekt(paare):
        d = {}
        for k, v in paare:
            if k in d:
                raise ValueError("Doppelter Schlüssel")
            d[k] = v
        return d

    def keine_konstante(_):
        raise ValueError("Keine endliche JSON-Zahl")

    try:
        d = json.loads(text, object_pairs_hook=objekt, parse_constant=keine_konstante)
    except (ValueError, RecursionError):
        return ablehnen("json")
    if not isinstance(d, dict) or set(d) != _WURZEL:
        return ablehnen("wurzel")
    if d["unsicherheit"] not in ("niedrig", "mittel", "hoch"):
        return ablehnen("unsicherheit")
    for k in ("judikatur", "exekutive"):
        if not isinstance(d[k], dict) or set(d[k]) != {"text"} or not _text(d[k]["text"], 2000):
            return ablehnen("folgenform")
    if not isinstance(d["normen"], list) or len(d["normen"]) > HOECHSTNORMEN:
        return ablehnen("normenanzahl")
    for n in d["normen"]:
        if (not isinstance(n, dict) or set(n) != _NORM or not _text(n["ris_id"], 120, leer=True)
                or not _text(n["titel"], 200) or not _text(n["grund"], 800)
                or n["aenderung"] not in ("aendern", "aufheben", "neu", "beruehrt")
                or n["aenderung"] == "neu" and n["ris_id"] != ""):
            return ablehnen("normenform")
    if not isinstance(d["personal"], list) or len(d["personal"]) > HOECHSTPERSONAL:
        return ablehnen("personalanzahl")
    gesehen = set()
    erlaubt = {"unbestimmt", *personalbereiche}
    for p in d["personal"]:
        if (not isinstance(p, dict) or set(p) != {"bereich", "grund", *_DELTAS}
                or not isinstance(p["bereich"], str) or p["bereich"] not in erlaubt or p["bereich"] in gesehen
                or not _text(p["grund"], 800)):
            return ablehnen("personalform")
        gesehen.add(p["bereich"])
        # Ein damaliger Personalbestand belegt keine Stellenfolge. Auch 0 ist
        # eine Behauptung und darf die fehlende Bedarfsgrundlage nicht verdecken.
        if any(p[k] is not None for k in _DELTAS):
            return ablehnen("personalbasis")
    referenzen = d["quellen"]
    if (not isinstance(referenzen, list) or len(referenzen) > len(quellen)
            or any(not isinstance(q, str) or q not in quellen for q in referenzen)
            or len(set(referenzen)) != len(referenzen)):
        return ablehnen("quellenbindung")
    positionen = [quellen.index(q) for q in referenzen]
    if positionen != sorted(positionen):
        return ablehnen("quellenreihung")
    return {**ausgang, "gueltig": True, "daten": copy.deepcopy(d)}
