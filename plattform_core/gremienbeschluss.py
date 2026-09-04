"""Interne Beschlüsse der Räte: beschlussfähig, ausgezählt, nachrechenbar (§ 6 Abs 2 lit e).

Die Satzung sagt für den Koordinationsrat — und über Verweise für Integritätsrat und
Gliederungen — einen einzigen Satz: *„… bei Anwesenheit der Hälfte seiner Mitglieder
beschlussfähig und entscheidet mit einfacher Mehrheit der abgegebenen Stimmen."*

Für ein Gremium, das sich nicht in einem Raum trifft, muss „Anwesenheit" übersetzt werden.
Diese Übersetzung ist eine Entscheidung und steht deshalb hier, versioniert und lesbar, statt
verstreut in Ansichten: **Anwesend ist, wer abgestimmt hat.** Wer eine Rolle hat und schweigt,
ist abwesend — nicht dagegen. Das ist strenger als „alle, die zusehen" und milder als „alle
Rolleninhaber müssen zustimmen"; beides wäre eine andere Satzung.

Ausgezählt wird mit ganzen Zahlen. Ein Gleichstand ist **kein** Beschluss: Er ergibt kein
Ergebnis, statt eines zufällig zu wählen — die Reihenfolge der Optionen darf nicht entscheiden.
Ebenso wenig beschließt ein Gremium ohne besetzte Rollen: Die Hälfte von null ist null, und ohne
diese Schranke entschiede eine einzelne, längst abgelaufene Stimme allein.

Enthaltungen sind hier bewusst **keine** eigene Option des Kerns. Ob ein Gremium eine Option
„Enthaltung" führt, entscheidet der Beschluss selbst über seine Optionsliste; für die
Beschlussfähigkeit zählt sie dann mit (der Mensch war anwesend), für die Mehrheit gegen die
anderen Optionen an. Das entspricht der Sitzung, in der jemand den Arm nicht hebt.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass

#: Fassung dieser Regel. Ändert sich die Auszählung, steigt die Zahl — Beschlüsse tragen sie
#: mit, damit ein alter Beschluss nach seiner eigenen Regel nachgerechnet werden kann.
VERSION = 1


class BeschlussFehler(ValueError):
    """Unbrauchbare Eingaben: keine Optionen, doppelte Stimme, unbekannte Option."""


@dataclass(frozen=True)
class Auswertung:
    """Das Ergebnis einer internen Abstimmung — vollständig, auch wenn es keines gibt."""

    zaehlung: dict[str, int]
    abgegeben: int
    aktive: int
    noetig: int
    beschlussfaehig: bool
    ergebnis: str | None
    gleichstand: bool
    version: int

    @property
    def offen(self) -> bool:
        """Wahr, solange kein Ergebnis feststeht — zu wenige Stimmen oder Gleichstand."""
        return self.ergebnis is None


def noetige_stimmen(aktive: int) -> int:
    """Wie viele Rolleninhaber abgestimmt haben müssen (§ 6 Abs 2 lit e).

    „Die Hälfte" heißt aufgerundet: Bei fünf aktiven Rollen sind es drei, nicht zweieinhalb.
    Bei einem einzigen Rolleninhaber ist es einer — ein Gremium aus einer Person ist ein
    Satzungsproblem, kein Rechenproblem, und wird hier nicht stillschweigend geheilt."""
    if aktive <= 0:
        return 0
    return -(-aktive // 2)  # aufgerundete Hälfte, ohne Gleitkomma


def auswerten(stimmen: Iterable[str], optionen: Iterable[str], aktive: int) -> Auswertung:
    """Zählt eine interne Abstimmung aus.

    `stimmen` ist die Folge der abgegebenen Optionen (eine je Rolleninhaber, die Ansicht sorgt
    dafür), `optionen` die zulässige Liste, `aktive` die Zahl der Rollen, die zum Zeitpunkt der
    Auszählung aktiv sind. Eine Stimme für eine unbekannte Option ist ein Fehler und wird nicht
    stillschweigend verworfen — sonst verschöbe ein Tippfehler ein Ergebnis."""
    zulaessig = list(dict.fromkeys(optionen))  # Reihenfolge erhalten, Doppelte entfernen
    if not zulaessig:
        raise BeschlussFehler("Ein Beschluss ohne Optionen ist keiner.")
    if aktive < 0:
        raise BeschlussFehler("Negative Zahl aktiver Rollen.")

    gezaehlt = Counter()
    abgegeben = 0
    for stimme in stimmen:
        if stimme not in zulaessig:
            raise BeschlussFehler(f"Unbekannte Option: {stimme!r}")
        gezaehlt[stimme] += 1
        abgegeben += 1

    noetig = noetige_stimmen(aktive)
    # `aktive > 0` ist keine Formsache: Ohne besetzte Rollen ist die noetige Haelfte null, und
    # ohne diese Bedingung entschiede eine einzelne Stimme allein — auch die eines Menschen,
    # dessen Berufung inzwischen geendet hat. Ein Gremium ohne Mitglieder beschliesst nichts.
    beschlussfaehig = aktive > 0 and abgegeben >= noetig and abgegeben > 0
    zaehlung = {option: gezaehlt.get(option, 0) for option in zulaessig}

    ergebnis: str | None = None
    gleichstand = False
    if beschlussfaehig:
        hoechste = max(zaehlung.values())
        vorn = [option for option, anzahl in zaehlung.items() if anzahl == hoechste]
        if len(vorn) == 1 and hoechste > 0:
            ergebnis = vorn[0]
        else:
            gleichstand = True

    return Auswertung(
        zaehlung=zaehlung,
        abgegeben=abgegeben,
        aktive=aktive,
        noetig=noetig,
        beschlussfaehig=beschlussfaehig,
        ergebnis=ergebnis,
        gleichstand=gleichstand,
        version=VERSION,
    )
