"""Vorbereiteter Antwortvertrag für zwei kurze Textteile je angebotenem Paar.

Kein Anbieteraufruf und keine inhaltliche Beurteilung. Eine passende Form darf
weder die menschliche Wahl ersetzen noch neue Treffer oder Fassungen auswählen.
"""

import copy
import hashlib
import json

VERSION = 1
HOECHSTPAARE = 20  # Technischer Verarbeitungsrahmen, keine Treffer-Voreinstellung.
HOECHSTTEXT = 400
HOECHSTZEICHEN = 100_000


def _paare(paare):
    if not isinstance(paare, (list, tuple)) or not 1 <= len(paare) <= HOECHSTPAARE:
        raise ValueError("paarrahmen")
    gesehen, ergebnis = set(), []
    for p in paare:
        if (not isinstance(p, (list, tuple)) or len(p) != 2
                or any(type(n) is not int or not 1 <= n <= 2**63-1 for n in p) or p[0] in gesehen):
            raise ValueError("paarbindung")
        gesehen.add(p[0])
        ergebnis.append(tuple(p))
    return ergebnis


def _zu_tief(text):
    tiefe, zeichenkette, maskiert = 0, False, False
    for c in text:
        if zeichenkette:
            if maskiert:
                maskiert = False
            elif c == "\\":
                maskiert = True
            elif c == '"':
                zeichenkette = False
        elif c == '"':
            zeichenkette = True
        elif c in "[{":
            tiefe += 1
            if tiefe > 32:
                return True
        elif c in "]}":
            tiefe = max(0, tiefe - 1)
    return False


def _textteil(text):
    if (not isinstance(text, str) or not text or text != text.strip() or len(text) > HOECHSTTEXT
            or any(ord(c) < 32 or ord(c) == 127 for c in text)):
        return False
    try:
        text.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


def pruefen(text, *, paare):
    """Genau die vorgegebenen Paar-IDs und ihre Reihenfolge erhalten, nichts priorisieren.

    Der Aufrufer muss den tatsächlichen Eingabestand belegen. Hier werden keine
    Fassungen aus einer Datenbank gelesen oder fehlende Treffer nachträglich ergänzt.
    """
    erwartet = _paare(paare)
    ausgang = {"regel_fassung": VERSION, "inhaltlich_geprueft": False, "antwort_sha256": None,
        "gueltig": False, "fehler": [], "vergleiche": []}
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
    if _zu_tief(text):
        return ablehnen("tiefe")
    def objekt(paare):
        d = {}
        for k, v in paare:
            if k in d:
                raise ValueError("Doppeltes Feld")
            d[k] = v
        return d
    def keine_konstante(_):
        raise ValueError("Kein endlicher JSON-Wert")
    try:
        daten = json.loads(text, object_pairs_hook=objekt, parse_constant=keine_konstante)
    except (ValueError, RecursionError):
        return ablehnen("json")
    if not isinstance(daten, dict) or set(daten) != {"vergleiche"}:
        return ablehnen("wurzel")
    vergleiche = daten["vergleiche"]
    if not isinstance(vergleiche, list) or len(vergleiche) != len(erwartet):
        return ablehnen("paarzahl")
    for v, p in zip(vergleiche, erwartet, strict=True):
        if not isinstance(v, dict) or set(v) != {"antrag", "fassung", "gemeinsamkeit", "unterschied"}:
            return ablehnen("felder")
        if type(v["antrag"]) is not int or type(v["fassung"]) is not int or (v["antrag"], v["fassung"]) != p:
            return ablehnen("paarbindung")
        if not _textteil(v["gemeinsamkeit"]) or not _textteil(v["unterschied"]):
            return ablehnen("textform")
    return {**ausgang, "gueltig": True, "vergleiche": copy.deepcopy(vergleiche)}
