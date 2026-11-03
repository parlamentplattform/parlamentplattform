"""Die versionierten Auftragstexte des Steckplatzes (FB-H1: Prompt-Versionierung).

Jeder Auftragstext liegt als Datei `ki/auftraege/<zweck>-v<n>.md` im Repository; ein Lauf
speichert, mit welcher Fassung er gerechnet wurde (`KILauf.auftrag_version`). Eine neue
Fassung ist eine neue Datei — die alte bleibt, damit ein archivierter Lauf lesbar bleibt.
Ohne ausdrückliche Auswahl wird die höchste Nummer geladen. Festgehaltene ältere
Aufträge können gezielt ihre damalige Fassung verlangen; fehlt sie, gibt es keinen Rückfall."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

ORDNER = Path(__file__).resolve().parent / "auftraege"
MUSTER = re.compile(r"^(?P<zweck>[a-z_]+)-v(?P<nummer>\d+)\.md$")


@dataclass(frozen=True)
class Auftragstext:
    zweck: str
    nummer: int
    text: str

    @property
    def version(self) -> str:
        """Die Kennzeichnung, die der Lauf trägt: `rechtsbezug-v1`."""
        return f"{self.zweck}-v{self.nummer}"


def auftragsversionen() -> list[Auftragstext]:
    """Alle Auftragstexte im Ordner, nach Zweck und Nummer geordnet — für die öffentliche Seite."""
    treffer = []
    for pfad in sorted(ORDNER.glob("*.md")):
        m = MUSTER.match(pfad.name)
        if m:
            treffer.append(Auftragstext(m["zweck"], int(m["nummer"]), pfad.read_text(encoding="utf-8")))
    return sorted(treffer, key=lambda a: (a.zweck, a.nummer))


def auftrag_laden(zweck: str, *, nummer: int | None = None) -> Auftragstext:
    """Die verlangte oder höchste Fassung. Fehlende Nummern nie durch neuere ersetzen."""
    if nummer is not None and (type(nummer) is not int or nummer < 1):
        raise ValueError("Eine Auftragsfassung braucht eine positive ganze Nummer.")
    passende = [a for a in auftragsversionen() if a.zweck == zweck]
    if nummer is not None:
        passende = [a for a in passende if a.nummer == nummer]
    if not passende:
        raise KeyError(f"Kein Auftragstext für den Zweck „{zweck}“, Fassung {nummer}, in {ORDNER}")
    return passende[-1]
