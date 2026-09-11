"""Parametertests (§ 6 Abs 11 lit c, FB-J3) — die Rechnung hinter Test und Auswertung.

Die Satzung erlaubt dem Koordinationsrat „befristete, veröffentlichte und jederzeit rückholbare
Tests neuer Werte"; die Testergebnisse fließen in die Zukunftswerkstatt, die daraus Vorschläge
macht, und die **Einführung** braucht wieder einen Beschluss. Was hier steht, ist der rechnende
Teil davon: wann ein Test läuft, wann er um ist, und wie eine Messgröße vorher und nachher
gegenübergestellt wird.

Was hier bewusst **nicht** steht: ein Urteil. Ob eine Hypothese „bestätigt" ist, ob ein Wert
eingeführt oder verworfen wird, entscheidet ein Rat mit Namen und Begründung. Diese Datei
liefert die Zahlen; sie hat keine Meinung dazu — sonst entschiede am Ende doch ein Algorithmus
über eine Stellgröße des Verfahrens (§ 2 Abs 6, Grundregel 5).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

VERSION = 1


@dataclass(frozen=True)
class Gegenueberstellung:
    """Eine Messgröße vor und nach dem Test — ohne Bewertung.

    `anteil` ist die Veränderung in Prozent des Ausgangswerts, oder None, wenn vorher nichts
    da war (aus Null lässt sich kein Anteil bilden) oder ein Wert fehlt."""

    messgroesse: str
    vorher: float | int | None
    nachher: float | int | None

    @property
    def vollstaendig(self) -> bool:
        return self.vorher is not None and self.nachher is not None

    @property
    def differenz(self) -> float | int | None:
        if not self.vollstaendig:
            return None
        return _glatt(self.nachher - self.vorher)

    @property
    def anteil(self) -> float | None:
        if not self.vollstaendig or not self.vorher:
            return None
        return round((self.nachher - self.vorher) / abs(self.vorher) * 100, 1)


def flach(werte: dict, praefix: str = "") -> dict[str, float | int]:
    """Macht aus verschachtelten Kennzahlen eine flache Liste mit Punktpfaden.

    Aus `{"motions": {"by_phase": {"beratung": 3}}}` wird `{"motions.by_phase.beratung": 3}`.
    Nur Zahlen bleiben — Text, Listen und None sind keine Messgrößen. Wahrheitswerte auch
    nicht: `True` ist in Python zwar eine Eins, aber niemand will „Anbieter angeschlossen"
    als Kurve sehen."""
    ergebnis: dict[str, float | int] = {}
    for schluessel, wert in werte.items():
        pfad = f"{praefix}.{schluessel}" if praefix else str(schluessel)
        if isinstance(wert, dict):
            ergebnis.update(flach(wert, pfad))
        elif isinstance(wert, (int, float)) and not isinstance(wert, bool):
            ergebnis[pfad] = wert
    return ergebnis


def messgroessen(werte: dict) -> list[str]:
    """Die Kennungen, die sich als Messgröße eignen — alle Zahlen, alphabetisch."""
    return sorted(flach(werte))


def gegenueberstellen(vorher: dict, nachher: dict, messgroesse: str) -> Gegenueberstellung:
    """Stellt eine Messgröße aus zwei Kennzahlen-Schnappschüssen gegenüber."""
    return Gegenueberstellung(
        messgroesse=messgroesse,
        vorher=flach(vorher).get(messgroesse),
        nachher=flach(nachher).get(messgroesse),
    )


def laeuft(beginn: date | None, ende: date, heute: date) -> bool:
    """Ob ein Test an diesem Tag wirkt: vom Beginn bis einschließlich zum Ende.

    Ohne Beginn läuft nichts — ein Test, den niemand angeordnet hat, ist ein Plan."""
    return beginn is not None and beginn <= heute <= ende


def abgelaufen(ende: date, heute: date) -> bool:
    """Der Tag nach dem Ende ist der erste, an dem der Wert zurückfällt."""
    return heute > ende


def _glatt(zahl: float | int) -> float | int:
    """Ganze Zahlen bleiben ganz, Brüche werden auf vier Stellen gerundet."""
    if isinstance(zahl, int):
        return zahl
    gerundet = round(zahl, 4)
    return int(gerundet) if gerundet == int(gerundet) else gerundet
