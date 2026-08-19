"""Audit-Log als Hash-Kette: Manipulationserkennung ohne Blockchain-Theater.

Jedes verfahrensrelevante Ereignis wird als Eintrag protokolliert. Der Hash
eines Eintrags versiegelt den Hash des Vorgängers plus den kanonisch
serialisierten Ereignisinhalt. Wer irgendeinen alten Eintrag verändert,
verändert damit zwangsläufig alle nachfolgenden Hashes — und der täglich
veröffentlichte Kettenkopf (Website und Repository) passt nicht mehr.

Das Verfahren ist absichtlich in ~60 Zeilen erklärbar: "Jeder Eintrag
versiegelt alle vorherigen." Mehr Kryptografie braucht es für diesen Zweck
nicht (ADR-005).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

GENESIS = "0" * 64


def _kanonisch(ereignis: dict[str, Any]) -> bytes:
    """Kanonische JSON-Serialisierung: sortierte Schlüssel, keine Leerzeichen,
    UTF-8 unverändert. Zwei inhaltsgleiche Ereignisse ergeben byte-identische
    Serialisierungen — die Grundvoraussetzung reproduzierbarer Hashes."""
    return json.dumps(ereignis, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def ereignis_hash(vorgaenger_hash: str, ereignis: dict[str, Any]) -> str:
    """SHA-256 über Vorgänger-Hash und kanonisches Ereignis."""
    h = hashlib.sha256()
    h.update(vorgaenger_hash.encode("ascii"))
    h.update(_kanonisch(ereignis))
    return h.hexdigest()


def kette_pruefen(
    eintraege: Iterable[tuple[dict[str, Any], str]],
    start_hash: str = GENESIS,
) -> tuple[bool, int | None]:
    """Prüft eine Kette aus (ereignis, gespeicherter_hash)-Paaren.

    Rückgabe: (True, None) wenn alles stimmt, sonst (False, index) mit dem
    Index des ersten Eintrags, dessen Hash nicht zum Inhalt passt.
    """
    aktuell = start_hash
    for index, (ereignis, gespeichert) in enumerate(eintraege):
        erwartet = ereignis_hash(aktuell, ereignis)
        if erwartet != gespeichert:
            return False, index
        aktuell = gespeichert
    return True, None
