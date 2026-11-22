"""Die Reihung der Listen im Parlament (§ 5 Abs 10, § 2 Abs 6) — ohne Django, nachrechenbar.

Das Parlament kennt nur zwei Ordnungen, beide ohne Beliebtheit, ohne Gewicht, ohne Auswahl:

* **neutral** — erst die Phase (Abstimmung, Beratung, Unterstützung; § 5 Abs 10 lit d), innerhalb
  der Phase das Fristende aufsteigend; ohne Frist der Phasenbeginn, bei Gleichstand die
  Antragsnummer. So reihen die Gruppen des WeicherFilters ohne Regler, „Meine Region“, die
  Anträge eines Lebensbereichs und die Titelsuche.
* **nach Fristende** — das Fristende aufsteigend, sonst der Phasenbeginn, dann die Antragsnummer.
  So reiht „Wichtige Abstimmungen“: Was zuerst endet, steht vorn.

Beendete Verfahren reihen nach dem Beginn ihrer letzten Phase absteigend, dann nach der
Antragsnummer absteigend — das zuletzt Entschiedene zuerst.

Lange Listen werden nicht still abgeschnitten: `seite` teilt eine geordnete Liste in Seiten
gleicher Größe und nennt Gesamtzahl und Seitenzahl.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

#: Fassung dieser Regel (Regelverzeichnis, § 2 Abs 6).
VERSION = 1

#: Rang der laufenden Phasen in der neutralen Ordnung; unbekannte Phasen stehen hinten.
PHASEN_RANG = {"abstimmung": 0, "beratung": 1, "unterstuetzung": 2}


def neutral(phase: str, frist: datetime | None, phase_beginn: datetime, nummer: int) -> tuple:
    """Schlüssel der neutralen Ordnung: Phase, Fristende (sonst Phasenbeginn), Antragsnummer."""
    return (PHASEN_RANG.get(phase, 9), frist or phase_beginn, nummer)


def nach_fristende(frist: datetime | None, phase_beginn: datetime, nummer: int) -> tuple:
    """Schlüssel „was zuerst endet, steht vorn“: Fristende (sonst Phasenbeginn), Antragsnummer."""
    return (frist or phase_beginn, nummer)


@dataclass(frozen=True)
class Seite:
    """Ein Ausschnitt einer geordneten Liste: Einträge `von` bis `bis` (ab 1 gezählt) von `gesamt`."""

    nummer: int
    seiten: int
    gesamt: int
    von: int
    bis: int

    @property
    def zurueck(self) -> int | None:
        return self.nummer - 1 if self.nummer > 1 else None

    @property
    def weiter(self) -> int | None:
        return self.nummer + 1 if self.nummer < self.seiten else None


def seite(gesamt: int, groesse: int, gewuenscht: int | None) -> Seite:
    """Die Seite `gewuenscht` einer Liste mit `gesamt` Einträgen zu je `groesse` — außerhalb des
    Bereichs die nächstgelegene gültige Seite. Eine Größe unter 1 zeigt alles auf einer Seite."""
    groesse = groesse if groesse >= 1 else max(gesamt, 1)
    seiten = max(1, -(-gesamt // groesse))
    nummer = min(max(gewuenscht or 1, 1), seiten)
    von = (nummer - 1) * groesse
    return Seite(nummer=nummer, seiten=seiten, gesamt=gesamt, von=von + 1, bis=min(von + groesse, gesamt))


def suchtext(roh, hoechstens: int | None = None) -> str:
    """Den Suchtext einer Anfrage lesen, bevor er in einen Datenbankvergleich geht — die eine Stelle
    für jede Seite, die Text aus der Adresse sucht (Titelsuche im Parlament, Antragsauswahl der Räte,
    Gemeindesuche, Archivwahl der Antragsseite). Keine Reihung; die Fassung dieser Datei bleibt.

    Von Hand: Nullzeichen entfernen, Leerraum an den Rändern entfernen, auf `hoechstens` Zeichen kürzen
    (ohne Angabe oder 0: nicht kürzen). Das Nullzeichen muss weg, weil PostgreSQL es in keinem Textwert
    annimmt: Eine Suche damit endete in einem Serverfehler statt in einer leeren Trefferliste."""
    text = str(roh or "").replace("\x00", "").strip()
    return text[:hoechstens] if hoechstens else text
