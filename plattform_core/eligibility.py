"""Stimmberechtigung nach § 4 Abs 4 des Satzungsentwurfs 2.1.

Anwartschaft:
- Sachfragen: 3 Monate ununterbrochene Mitgliedschaft
- Personenwahlen, Mandatsnominierungen, Satzungsänderungen, Auflösung: 12 Monate
- Übergangsregel (§ 4 Abs 4 lit d): Für die erste Organbestellung und die erste
  Verfahrensordnung entfällt die Anwartschaft — dafür der Parameter `uebergang`.

Stichtag ist der Beginn der Abstimmung (§ 4 Abs 4 lit a). Monatsarithmetik ist
kalendarisch: Beitritt am 31. Jänner + 3 Monate ⇒ Stichtag 30. April genügt
nicht, 1. Mai genügt (der 31. April existiert nicht; es gilt der letzte Tag des
Zielmonats als Erfüllungstag). Diese Regel steht hier ausformuliert, damit sie
nie von einer Bibliotheksversion abhängt.
"""

from __future__ import annotations

import calendar
import enum
from datetime import date


class Gegenstand(enum.StrEnum):
    SACHFRAGE = "sachfrage"
    PERSONENWAHL = "personenwahl"
    MANDATSNOMINIERUNG = "mandatsnominierung"
    SATZUNGSAENDERUNG = "satzungsaenderung"
    AUFLOESUNG = "aufloesung"


ANWARTSCHAFT_MONATE = {
    Gegenstand.SACHFRAGE: 3,
    Gegenstand.PERSONENWAHL: 12,
    Gegenstand.MANDATSNOMINIERUNG: 12,
    Gegenstand.SATZUNGSAENDERUNG: 12,
    Gegenstand.AUFLOESUNG: 12,
}


def monate_addieren(d: date, monate: int) -> date:
    """Kalendarische Monatsaddition mit Klemmung auf den Monatsletzten."""
    monat_index = d.month - 1 + monate
    jahr = d.year + monat_index // 12
    monat = monat_index % 12 + 1
    tag = min(d.day, calendar.monthrange(jahr, monat)[1])
    return date(jahr, monat, tag)


def stimmberechtigt(
    beitritt: date,
    gegenstand: Gegenstand | str,
    stichtag: date,
    uebergang: bool = False,
) -> bool:
    """True, wenn das Mitglied am Stichtag für den Gegenstand stimmberechtigt ist.

    `beitritt` ist der Beginn der aktuellen, ununterbrochenen Mitgliedschaft.
    Ruht oder endete die Mitgliedschaft zwischenzeitlich, muss der Aufrufer den
    Wiederbeginn übergeben — diese Funktion kennt nur ein Datum und bleibt
    dadurch trivial prüfbar.
    """
    gegenstand = Gegenstand(gegenstand)
    if beitritt > stichtag:
        return False
    if uebergang:
        return True
    erforderlich = ANWARTSCHAFT_MONATE[gegenstand]
    return monate_addieren(beitritt, erforderlich) <= stichtag
