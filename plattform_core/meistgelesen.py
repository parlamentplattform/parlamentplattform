"""Reihung „Meistgelesene Anträge“ der Übersichtsseite — offengelegt, wie sie ist (§ 2 Abs 6).

Die Liste gibt es seit dem 20.8.2026. Der Gründer hat am 28.9.2026 entschieden, dass sie bleibt
und als offengelegte, versionierte Regel im Regelverzeichnis geführt wird. Dieses Modul beschreibt
das Verhalten der Seite und ändert es nicht:

* Gezählt wird je Antrag und Tag jeder erfolgreiche Abruf der Antragsseite durch einen Browser.
* Gereiht wird nach der Summe dieser Tageszahlen über alle Tage, die höchste zuerst.
* Bei gleicher Summe steht die kleinere Antragsnummer vorn, also der ältere Antrag (seit dem
  21.11.2026, GP-134; vorher entschied die Datenbank).
* Gezeigt werden die ersten fünf.

Ob wiederholte Abrufe derselben Person zählen und ob Gleichstände anders aufgelöst werden sollen,
ist nicht entschieden; das steht als Lücke im Verzeichnis.
"""

from __future__ import annotations

from collections.abc import Iterable

VERSION = 1

#: Sortierung über die Summe der Aufrufe je Antrag, als ORM-Angabe ausführbar; bei gleicher Summe
#: entscheidet die Antragsnummer aufsteigend.
REIHUNG = ("-gesamt", "antrag")

#: So viele Anträge zeigt die Liste. Der Wert steht seit der ersten Fassung im Programm.
HOECHSTZAHL = 5


def meistgelesene(tageszahlen: Iterable[tuple[int, int]]) -> list[tuple[int, int]]:
    """Rechnet die Liste aus den Tageszahlen nach.

    `tageszahlen`: Folge von (antrag, aufrufe) — eine Zeile je Antrag und Tag. Ergebnis:
    (antrag, summe) absteigend nach der Summe, bei gleicher Summe nach der Antragsnummer
    aufsteigend, höchstens `HOECHSTZAHL` Einträge."""
    summen: dict[int, int] = {}
    for antrag, aufrufe in tageszahlen:
        summen[antrag] = summen.get(antrag, 0) + aufrufe
    return sorted(summen.items(), key=lambda paar: (-paar[1], paar[0]))[:HOECHSTZAHL]
