"""Lexikalische Ähnlichkeit — Stufe 1 des Ähnlichkeitshinweises (ADR-006).

Bewusst simpel und vollständig nachrechenbar: Texte werden normalisiert
(Kleinschreibung, Satzzeichen raus), in Trigramme (Dreizeichenfolgen) zerlegt
und über den Jaccard-Koeffizienten verglichen — die Größe der Schnittmenge
geteilt durch die Größe der Vereinigungsmenge, ein Wert zwischen 0 und 1.

Jedes Mitglied kann einen angezeigten Score mit Papier und Bleistift (oder
zehn Zeilen eigenem Code) überprüfen. Kein Modell, kein Zufall, kein Dienst.
"""

from __future__ import annotations

import re
import unicodedata


def normalisieren(text: str) -> str:
    """Kleinschreibung, Unicode-Normalform, alles außer Buchstaben/Ziffern wird Leerraum."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def trigramme(text: str) -> set[str]:
    """Menge aller Dreizeichenfolgen des normalisierten Texts (mit Randauffüllung
    je Wort, damit kurze Wörter nicht unter den Tisch fallen)."""
    ergebnis: set[str] = set()
    for wort in normalisieren(text).split(" "):
        if not wort:
            continue
        gepolstert = f"  {wort} "
        for i in range(len(gepolstert) - 2):
            ergebnis.add(gepolstert[i : i + 3])
    return ergebnis


def aehnlichkeit(a: str, b: str) -> float:
    """Jaccard-Koeffizient der Trigramm-Mengen beider Texte, 0.0 bis 1.0."""
    ta, tb = trigramme(a), trigramme(b)
    if not ta or not tb:
        return 0.0
    schnitt = len(ta & tb)
    vereinigung = len(ta | tb)
    return schnitt / vereinigung


def aehnlichste(
    neuer_text: str,
    kandidaten: list[tuple[int, str]],
    schwelle: float = 0.18,
    limit: int = 3,
) -> list[tuple[int, float]]:
    """Die `limit` ähnlichsten Kandidaten oberhalb der Schwelle, absteigend
    nach Score; bei Gleichstand entscheidet die kleinere ID (Determinismus).

    `kandidaten` ist eine Liste (id, text). Die Schwelle 0.18 ist ein
    Startwert für den Testbetrieb und steht hier offen im Code — Änderungen
    daran sind Verhaltensänderungen und brauchen Test plus CHANGELOG.
    """
    neu = trigramme(neuer_text)
    if not neu:
        return []
    treffer: list[tuple[int, float]] = []
    for kid, text in kandidaten:
        t = trigramme(text)
        if not t:
            continue
        score = len(neu & t) / len(neu | t)
        if score >= schwelle:
            treffer.append((kid, score))
    treffer.sort(key=lambda x: (-x[1], x[0]))
    return treffer[:limit]
