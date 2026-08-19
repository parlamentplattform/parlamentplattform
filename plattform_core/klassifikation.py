"""Automatische Zuordnung von Anträgen im Kategorienbaum — Stufe 1 (F-47, ADR-007).

Bewusst deterministisch und mit Papier nachrechenbar: Jeder Knoten des
Kategorienbaums (Haupt-, Unter-, Detailkategorie) bringt eine gepflegte
Schlagwortliste mit (policies/kategorien-v*.yaml). Ein Schlagwort trifft, wenn
ein Wort des Antragstexts damit BEGINNT („Rohrmaße" trifft „rohr",
„Photovoltaikanlage" trifft „photovoltaik") oder — bei Mehrwort-Schlagworten —
die Wortfolge im Text vorkommt. Punktestand je Knoten = Zahl der getroffenen
unterschiedlichen Schlagworte.

Die Zuordnung bevorzugt die TIEFSTE passende Ebene: Trifft „Installateur"
(Detail) und zugleich sein Ast „Bauwirtschaft" (Unterkategorie), wird der
Detailknoten zugeordnet — die Elternknoten sind über den Baum impliziert und
werden nicht doppelt vergeben.

Stufe 2 ersetzt die Schlagwortlisten durch ein lokal betriebenes
Embedding-Modell; die Schnittstelle bleibt gleich. Wie überall gilt: Die
Zuordnung ist Vorschlag und durch Menschen korrigierbar (Integritätsrat,
protokolliert); sie hat keine Sperrwirkung.
"""

from __future__ import annotations

from plattform_core.similarity import normalisieren


def schlagwort_trifft(textworte: list[str], text_norm: str, schlagwort: str) -> bool:
    """True, wenn das (normalisierte) Schlagwort im Text vorkommt."""
    s = normalisieren(schlagwort)
    if not s:
        return False
    if " " in s:
        return f" {s} " in f" {text_norm} "
    return any(wort.startswith(s) for wort in textworte)


def zuordnen(
    text: str,
    knoten: list[tuple[int, int | None, list[str]]],
    limit: int = 3,
) -> list[tuple[int, int]]:
    """Ordnet einen Text Knoten des Kategorienbaums zu.

    `knoten` ist eine Liste (id, eltern_id, schlagworte). Ergebnis: bis zu
    `limit` Knoten-IDs mit Punktestand, tiefste passende Ebene bevorzugt —
    sortiert nach Punkten (absteigend), dann Tiefe (tiefer zuerst), dann ID
    (Determinismus). Vorfahren eines gewählten Knotens werden entfernt.
    Kein Treffer -> leere Liste: ein Arbeitsauftrag an das Kategoriesystem,
    keine Fehlermeldung.
    """
    text_norm = normalisieren(text)
    worte = text_norm.split(" ")
    eltern = {kid: eid for kid, eid, _ in knoten}

    def tiefe(kid: int) -> int:
        t, k = 0, eltern.get(kid)
        while k is not None:
            t += 1
            k = eltern.get(k)
        return t

    def vorfahren(kid: int) -> set[int]:
        v, k = set(), eltern.get(kid)
        while k is not None:
            v.add(k)
            k = eltern.get(k)
        return v

    treffer: list[tuple[int, int]] = []
    for kid, _, schlagworte in knoten:
        punkte = sum(1 for s in set(schlagworte) if schlagwort_trifft(worte, text_norm, s))
        if punkte > 0:
            treffer.append((kid, punkte))

    # Tiefste passende Ebene gewinnt: Ein Knoten fliegt raus, wenn auf seinem
    # Ast ein getroffener NACHFAHRE existiert — der ist spezifischer.
    getroffen = {kid for kid, _ in treffer}
    spezifisch = [
        (kid, punkte)
        for kid, punkte in treffer
        if not any(kid in vorfahren(anderer) for anderer in getroffen if anderer != kid)
    ]
    spezifisch.sort(key=lambda x: (-x[1], -tiefe(x[0]), x[0]))
    return spezifisch[:limit]
