"""Was vom Audit-Log öffentlich ist (Schritt 2 · 0.52.0) — für den Export je Antrag und `/audit/`.

Die Kette ist vollständig, damit sie nachrechenbar bleibt; einige Einträge der Verwaltung nennen aber
die Kennung eines Mitglieds, und beim Pausieren oder Ausschließen steht die Begründung daneben. Öffentlich
wird ein solcher Wert durch „•“ ersetzt, der Eintrag ist dann als gekürzt markiert: Sein Hash lässt sich
von außen nicht nachrechnen — das leistet täglich `audit_pruefen` über die ganze Kette, dessen Ergebnis
und Kettenkopf in den Kennzahlen stehen. Jeder ungekürzte Eintrag bleibt einzeln nachrechenbar
(verify/nachrechnen.py).

Die Auswahl ist Empfehlung (a) des Bauplans 0.52.0 und hängt an der Entscheidung des Gründers (F2)."""

from __future__ import annotations

#: Das Zeichen, das einen ausgeblendeten Wert ersetzt.
MASKE = "•"

#: Schlüssel, deren Wert eine Mitgliedskennung ist (Zahl oder Liste von Zahlen). Ein Text wie
#: `durch: "verwaltung"` nennt niemanden und bleibt stehen.
KENNUNGEN = ("mitglied", "durch", "konten")

#: Ereignisarten, deren Begründung eine Person betrifft (Pausieren, Ausschluss, Adresswechsel).
PERSONENGRUENDE = ("verwaltung",)


def _ist_kennung(wert) -> bool:
    if isinstance(wert, bool):
        return False
    if isinstance(wert, int):
        return True
    return isinstance(wert, list) and any(isinstance(w, int) and not isinstance(w, bool) for w in wert)


def ereignis_oeffentlich(ereignis: dict) -> tuple[dict, bool]:
    """Das Ereignis, wie es öffentlich erscheint, und ob etwas ausgeblendet wurde."""
    oeffentlich, gekuerzt = dict(ereignis), False
    for schluessel in KENNUNGEN:
        if _ist_kennung(oeffentlich.get(schluessel)):
            oeffentlich[schluessel], gekuerzt = MASKE, True
    if art_von(ereignis) in PERSONENGRUENDE and oeffentlich.get("grund"):
        oeffentlich["grund"], gekuerzt = MASKE, True
    return oeffentlich, gekuerzt


def art_von(ereignis: dict) -> str:
    """Die Art des Eintrags. Zwei ältere Ereignisse tragen sie unter `art` statt `typ` (Beitrag
    gemeldet, Einschätzung beanstandet) — sie bleiben, wie sie sind, gelesen wird beides."""
    return str(ereignis.get("typ") or ereignis.get("art") or "")


def eintrag_oeffentlich(eintrag) -> dict:
    """Ein Audit-Eintrag für Export und Seite: voller Hash, Vorgänger und der öffentliche Inhalt."""
    ereignis, gekuerzt = ereignis_oeffentlich(eintrag.ereignis)
    return {
        "lfd": eintrag.lfd,
        "typ": art_von(eintrag.ereignis),
        "zeit": eintrag.zeit.isoformat(),
        "vorgaenger": eintrag.vorgaenger,
        "hash": eintrag.hash,
        "gekuerzt": gekuerzt,
        "grund": ereignis.get("grund", ""),
        "ereignis": ereignis,
    }
