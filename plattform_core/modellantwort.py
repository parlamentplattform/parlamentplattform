"""Form der Rechtsbezug-Antwort prüfen, niemals ihren juristischen Inhalt.

Aktuelle Darstellungsprüfung, kein nachträglich behaupteter Laufnachweis.
Originalantworten bleiben unverändert. Die verwendete Teilmenge von JSON-Schema
wird hier vollständig geprüft; es gibt weder Schemaabrufe noch Modellaufrufe.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re

VERSION = 1
HOECHSTZEICHEN = 100_000  # technischer Schutz der Verarbeitung, kein Verfahrensparameter
HOECHSTFEHLER = 20
HOECHSTTIEFE = 32

_TEXT = {"type": "string"}
_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "$comment": "Zusätzlich gelten die dokumentierten technischen Grenzen für UTF-8, Textgröße, Tiefe und doppelte Schlüssel.",
    "title": "DDOE Rechtsbezug-Antwort, Fassung 1",
    "type": "object",
    "required": ["normen", "hinweis", "unsicherheit"],
    "additionalProperties": False,
    "properties": {
        "normen": {
            "type": "array", "maxItems": 8,
            "items": {
                "type": "object", "additionalProperties": False,
                "required": ["titel", "ebene", "kennung", "aenderung", "begruendung"],
                "properties": {
                    "titel": {**_TEXT, "minLength": 1, "maxLength": 200, "pattern": r"\S"},
                    "ebene": {**_TEXT, "enum": ["EU", "Bund", "Land"]},
                    "kennung": {**_TEXT, "maxLength": 120},
                    "aenderung": {**_TEXT, "enum": ["aendern", "aufheben", "neu", "beruehrt"]},
                    "begruendung": {**_TEXT, "maxLength": 600},
                },
            },
        },
        "hinweis": {**_TEXT, "maxLength": 2000},
        "unsicherheit": {**_TEXT, "enum": ["niedrig", "mittel", "hoch"]},
    },
}


def schema_als_dict():
    return copy.deepcopy(_SCHEMA)


def schema_hash():
    return hashlib.sha256(json.dumps(
        _SCHEMA, ensure_ascii=False, sort_keys=True, separators=(",", ":"),
    ).encode("utf-8")).hexdigest()


def _zu_tief(text):
    """Klammern in Zeichenketten zählen nicht; vor dem JSON-Parser begrenzen."""
    tiefe, zeichenkette, maskiert = 0, False, False
    for zeichen in text:
        if zeichenkette:
            if maskiert:
                maskiert = False
            elif zeichen == "\\":
                maskiert = True
            elif zeichen == '"':
                zeichenkette = False
        elif zeichen == '"':
            zeichenkette = True
        elif zeichen in "[{":
            tiefe += 1
            if tiefe > HOECHSTTIEFE:
                return True
        elif zeichen in "]}":
            # Ungültiger Vortext darf späteren JSON-Strukturen keinen Tiefenrabatt geben.
            tiefe = max(0, tiefe - 1)
    return False


def _pruefen(wert, schema, pfad, fehler):
    def melden(code, ort=pfad):
        if len(fehler) < HOECHSTFEHLER:
            fehler.append({"pfad": ort, "code": code})
    if len(fehler) >= HOECHSTFEHLER:
        return
    typ = schema["type"]
    if type(wert) is not {"object": dict, "array": list, "string": str}[typ]:
        melden("typ")
        return
    if typ == "object":
        for feld in schema["required"]:
            if feld not in wert:
                melden("pflichtfeld", f"{pfad}.{feld}")
        if set(wert) - schema["properties"].keys():
            # Ungeprüfte Feldnamen gehören nicht in öffentliche Diagnosepfade.
            melden("zusatzfelder")
        for feld, definition in schema["properties"].items():
            if feld in wert:
                _pruefen(wert[feld], definition, f"{pfad}.{feld}", fehler)
    elif typ == "array":
        if len(wert) > schema["maxItems"]:
            melden("anzahl")
        for i, eintrag in enumerate(wert[:schema["maxItems"]]):
            _pruefen(eintrag, schema["items"], f"{pfad}[{i}]", fehler)
    else:
        try:
            wert.encode("utf-8")
        except UnicodeEncodeError:
            melden("kodierung")
        if len(wert) < schema.get("minLength", 0):
            melden("laenge")
        if "maxLength" in schema and len(wert) > schema["maxLength"]:
            melden("laenge")
        if "enum" in schema and wert not in schema["enum"]:
            melden("wert")
        if "pattern" in schema and re.search(schema["pattern"], wert) is None:
            melden("muster")


def pruefen(text):
    """Deterministischer Formbefund mit Original- und Schemahash, ohne Rechtsurteil."""
    fehler = []
    ergebnis = {
        "fassung": VERSION, "zeitbezug": "darstellung", "schema_sha256": schema_hash(),
        "antwort_sha256": None, "gueltig": False, "fehler": fehler,
    }
    def ablehnen(code):
        fehler.append({"pfad": "$", "code": code})
        return ergebnis
    if not isinstance(text, str):
        return ablehnen("typ")
    if len(text) > HOECHSTZEICHEN:
        return ablehnen("groesse")
    try:
        roh = text.encode("utf-8")
    except UnicodeEncodeError:
        return ablehnen("kodierung")
    ergebnis["antwort_sha256"] = hashlib.sha256(roh).hexdigest()
    if _zu_tief(text):
        return ablehnen("tiefe")
    doppelt = []
    def objekt(paare):
        daten = {}
        for schluessel, wert in paare:
            if schluessel in daten:
                doppelt.append(True)
            daten[schluessel] = wert
        return daten
    def nicht_endlich(_):
        raise ValueError("Kein JSON-Zahlenwert")
    try:
        daten = json.loads(text, object_pairs_hook=objekt, parse_constant=nicht_endlich)
    except (ValueError, RecursionError):
        return ablehnen("json")
    if doppelt:
        fehler.append({"pfad": "$", "code": "doppelte_schluessel"})
    _pruefen(daten, _SCHEMA, "$", fehler)
    ergebnis["gueltig"] = not fehler
    return ergebnis
