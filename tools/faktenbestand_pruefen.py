"""Einen lokalen Bestandsdownload gegen einen zuvor notierten Hash nachrechnen.

python tools/faktenbestand_pruefen.py DATEI --sha256 HASH

Nur Standardbibliothek und die unveränderte Bestandsregel1; kein Django,
keine Datenbank, kein Netzwerk und keine Schreibwirkungen. Das Ergebnis ist
keine amtliche Signatur oder Bestätigung der Originale bzw. Rechtsvollständigkeit.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from plattform_core.faktenbestand import (  # noqa: E402
    HASH_BEZUEGE,
    HASH_MUSTER,
    TECHNISCHE_HOECHSTZAHL,
    VERSION,
    BestandsFehler,
    kanonisch,
    nachweis,
)

# Reine Parser-Schutzgrenze für lokale Dateien, kein Verfahrens-/Registerwert.
# Der vollständige bekannte Download mit10000Einträgen passt einschließlich Einrückung.
HOECHSTBYTES = 4 * 1024 * 1024
HOECHSTTIEFE = 16


class PruefFehler(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _objekt(paare):
    d = {}
    for k, v in paare:
        if k in d:
            raise PruefFehler("doppelte_schluessel")
        d[k] = v
    return d


def _keine_sonderzahl(_wert):
    raise PruefFehler("json")


def _tiefe_pruefen(text):
    # Vor dem JSON-Decoder begrenzen, unabhängig von dessen aktuellem Rekursionslimit.
    tiefe, in_text, maskiert = 0, False, False
    for zeichen in text:
        if in_text:
            if maskiert:
                maskiert = False
            elif zeichen == "\\":
                maskiert = True
            elif zeichen == '"':
                in_text = False
        elif zeichen == '"':
            in_text = True
        elif zeichen in "[{":
            tiefe += 1
            if tiefe > HOECHSTTIEFE:
                raise PruefFehler("json")
        elif zeichen in "]}":
            tiefe -= 1


def lesen(datei: Path):
    try:
        if not datei.is_file():
            raise PruefFehler("datei")
        with datei.open("rb") as f:
            roh = f.read(HOECHSTBYTES + 1)
    except OSError as exc:
        raise PruefFehler("datei") from exc
    if len(roh) > HOECHSTBYTES:
        raise PruefFehler("dateigroesse")
    try:
        text = roh.decode("utf-8")
    except UnicodeError as exc:
        raise PruefFehler("utf8") from exc
    try:
        _tiefe_pruefen(text)
        return json.loads(text, object_pairs_hook=_objekt, parse_constant=_keine_sonderzahl)
    except PruefFehler:
        raise
    except (ValueError, RecursionError) as exc:
        raise PruefFehler("json") from exc


def pruefen(daten, erwarteter_sha256):
    if not isinstance(erwarteter_sha256, str) or not HASH_MUSTER.fullmatch(erwarteter_sha256):
        raise PruefFehler("vergleichshash")
    if not isinstance(daten, dict) or set(daten) != {"inhalt", "sha256", "erstellt_am", "hoechstzahl"}:
        raise PruefFehler("format")
    if not isinstance(daten["sha256"], str) or not HASH_MUSTER.fullmatch(daten["sha256"]):
        raise PruefFehler("pruefsumme")
    if not isinstance(daten["erstellt_am"], str):
        raise PruefFehler("metadaten")
    try:
        zeit = datetime.fromisoformat(daten["erstellt_am"])
    except ValueError as exc:
        raise PruefFehler("metadaten") from exc
    if zeit.tzinfo is None or zeit.utcoffset() is None:
        raise PruefFehler("metadaten")
    inhalt = daten["inhalt"]
    if not isinstance(inhalt, dict) or set(inhalt) != {"fassung", "sammlungen", "eintraege"}:
        raise PruefFehler("inhalt")
    if type(inhalt["fassung"]) is not int or inhalt["fassung"] != VERSION:
        raise PruefFehler("fassung")
    eintraege, sammlungen = inhalt["eintraege"], inhalt["sammlungen"]
    if not isinstance(eintraege, list) or len(eintraege) > TECHNISCHE_HOECHSTZAHL:
        raise PruefFehler("umfang")
    if (not isinstance(sammlungen, list) or len(sammlungen) != len(HASH_BEZUEGE)
            or any(not isinstance(s, dict) or set(s) != {"sammlung", "hash_bezug", "anzahl"}
                   or not isinstance(s["sammlung"], str) or not isinstance(s["hash_bezug"], str)
                   or s["sammlung"] not in HASH_BEZUEGE or s["hash_bezug"] != HASH_BEZUEGE[s["sammlung"]]
                   or type(s["anzahl"]) is not int or s["anzahl"] < 0 for s in sammlungen)):
        raise PruefFehler("sammlungen")
    try:
        neu = nachweis(eintraege, daten["hoechstzahl"])
    except BestandsFehler as exc:
        raise PruefFehler(str(exc)) from exc
    # Kanonische Bytes unterscheiden auch1von1.0undtrue; keine stille Normalisierung.
    if kanonisch(neu["inhalt"]) != kanonisch(inhalt):
        raise PruefFehler("inhalt")
    if neu["sha256"] != daten["sha256"] or neu["sha256"] != erwarteter_sha256:
        raise PruefFehler("pruefsumme")
    return {"pruefung": "nachweisinhalt_und_vergleichshash", "bestandsregel_fassung": VERSION,
            "sha256": neu["sha256"],
            "schnappschuesse": len(eintraege), "sammlungen": neu["inhalt"]["sammlungen"],
            "originaldateien_geprueft": False, "amtliche_signatur_geprueft": False,
            "vollstaendigkeit_bestaetigt": False, "metadaten_im_hash": False}


def main(argv=None):
    parser = argparse.ArgumentParser(usage="%(prog)s DATEI --sha256 HASH")
    parser.add_argument("datei", metavar="DATEI")
    parser.add_argument("--sha256", required=True, metavar="HASH")
    args = parser.parse_args(argv)
    try:
        ergebnis = pruefen(lesen(Path(args.datei)), args.sha256)
    except PruefFehler as exc:
        print(json.dumps({"fehler": exc.code}), file=sys.stderr)
        return 1
    print(json.dumps(ergebnis, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
