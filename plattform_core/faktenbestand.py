"""Reproduzierbarer Nachweis der Datensatz-/Hash-Zuordnung, ohne I/O.

Der Nachweis zählt lokale Schnappschüsse, keine Gesetze oder Personen. Er prüft
nicht die Originale gegen ihre gespeicherten Hashes und bescheinigt kein Recht.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable, Mapping

VERSION = 1
# Technische Speicher-/Antwortschutzgrenze; die kleinere Betriebsgrenze steht im Register.
TECHNISCHE_HOECHSTZAHL = 10000
HASH_MUSTER = re.compile(r"[0-9a-f]{64}\Z")
HASH_BEZUEGE = {
    "norm": "kanonische_metadaten_json",
    "normtext": "original_xml_bytes",
    "personalaggregat": "original_pdf_bytes",
    "personalressorttabelle": "original_pdf_bytes",
}


class BestandsFehler(ValueError):
    """Kein vollständiger Nachweis; niemals einen Teilbestand als Ergebnis liefern."""


def kanonisch(daten: object) -> bytes:
    return json.dumps(daten, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def nachweis(eintraege: Iterable[Mapping], hoechstzahl: int) -> dict:
    if type(hoechstzahl) is not int or not 0 < hoechstzahl <= TECHNISCHE_HOECHSTZAHL:
        raise BestandsFehler("grenze")
    liste, gesehen = [], set()
    zaehler = dict.fromkeys(HASH_BEZUEGE, 0)
    for eintrag in eintraege:
        # Erst max+1 lesen; kein Verbrauch des gesamten, möglicherweise großen Iterators.
        if len(liste) >= hoechstzahl:
            raise BestandsFehler("umfang")
        if not isinstance(eintrag, Mapping) or set(eintrag) != {"sammlung", "nummer", "pruefsumme"}:
            raise BestandsFehler("daten")
        art, nummer, pruefsumme = (eintrag[k] for k in ("sammlung", "nummer", "pruefsumme"))
        if (not isinstance(art, str) or art not in HASH_BEZUEGE
                or type(nummer) is not int or nummer < 1
                or not isinstance(pruefsumme, str) or not HASH_MUSTER.fullmatch(pruefsumme)
                or (art, nummer) in gesehen):
            raise BestandsFehler("daten")
        gesehen.add((art, nummer))
        zaehler[art] += 1
        liste.append({"sammlung": art, "nummer": nummer, "pruefsumme": pruefsumme})
    liste.sort(key=lambda x: (x["sammlung"], x["nummer"]))
    inhalt = {
        "fassung": VERSION,
        "sammlungen": [{"sammlung": art, "hash_bezug": HASH_BEZUEGE[art], "anzahl": zaehler[art]}
                       for art in sorted(HASH_BEZUEGE)],
        "eintraege": liste,
    }
    return {"inhalt": inhalt, "sha256": hashlib.sha256(kanonisch(inhalt)).hexdigest()}
