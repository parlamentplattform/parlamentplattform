"""Reihung „Meistgelesene Anträge“ der Übersichtsseite — offengelegt, wie sie ist (§ 2 Abs 6).

Die Liste gibt es seit dem 20.8.2026. Der Gründer hat am 28.9.2026 entschieden, dass sie bleibt
und als offengelegte, versionierte Regel im Regelverzeichnis geführt wird. Dieses Modul beschreibt
das Verhalten der Seite und ändert es nicht:

* Gezählt wird je Antrag und Tag jeder erfolgreiche Abruf der Antragsseite durch einen Browser.
* Gereiht wird nach der Summe dieser Tageszahlen über alle Tage, die höchste zuerst.
* Gezeigt werden die ersten fünf.

Bei gleicher Summe legt die Regel keine Reihenfolge fest; auf der Seite entscheidet dann die
Datenbank. Das steht als Lücke im Verzeichnis.
"""

from __future__ import annotations

from collections.abc import Iterable

VERSION = 1

#: Sortierung über die Summe der Aufrufe je Antrag, als ORM-Angabe ausführbar.
REIHUNG = ("-gesamt",)

#: So viele Anträge zeigt die Liste. Der Wert steht seit der ersten Fassung im Programm.
HOECHSTZAHL = 5


def meistgelesene(tageszahlen: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Rechnet die Liste aus den Tageszahlen nach.

    `tageszahlen`: Folge von (antrag, aufrufe) — eine Zeile je Antrag und Tag. Ergebnis:
    (antrag, summe) absteigend nach der Summe, höchstens `HOECHSTZAHL` Einträge. Anträge mit
    gleicher Summe bleiben hier in der Reihenfolge ihres ersten Auftretens; Teil der Regel ist
    diese Reihenfolge nicht."""
    summen: dict[int, int] = {}
    for antrag, aufrufe in tageszahlen:
        summen[antrag] = summen.get(antrag, 0) + aufrufe
    return sorted(summen.items(), key=lambda paar: -paar[1])[:HOECHSTZAHL]
