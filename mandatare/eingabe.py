"""Zahlen aus Adresse und Formular (GP-109): `str.isdigit` ließ hochgestellte und eingekreiste Ziffern
(„²“, „①“) durch, an denen `int()` dann scheiterte — ein Serverfehler, den jeder ohne Anmeldung auslösen
konnte. Hier gilt nur, was eine Datenbankkennung sein kann."""

from __future__ import annotations

#: Höchste Stellenzahl einer Kennung — 18 Stellen passen in jede 64-Bit-Ganzzahl der Datenbank.
KENNUNG_STELLEN = 18


def kennung(roh) -> int | None:
    """Eine Kennung aus ASCII-Ziffern, höchstens `KENNUNG_STELLEN` Stellen; alles andere (auch leer,
    Vorzeichen, hochgestellte, vollbreite oder fremde Ziffern) ergibt None."""
    wert = str(roh if roh is not None else "").strip()
    if wert and wert.isascii() and wert.isdecimal() and len(wert) <= KENNUNG_STELLEN:
        return int(wert)
    return None
