"""Die Aussetzung nach § 6 Abs 3 lit d — und was sie mit den Fristen macht.

Die Satzung: *„Er kann den Vollzug eines Beschlusses oder eine laufende Abstimmung aussetzen,
wenn ein begründeter Verdacht auf Manipulation oder auf einen Verstoß gegen § 3 besteht. Die
Aussetzung ist zu begründen, zu veröffentlichen und binnen sieben Tagen durch Antrag an das
Parteischiedsgericht zu bestätigen; unterbleibt der Antrag, endet die Aussetzung von selbst."*

Drei Dinge stehen darin, die dieses Modul rechnet:

1. **Sieben Tage.** Sie sind satzungsfest und deshalb eine Konstante, keine Stellgröße: Wer sie
   im Register verlängern könnte, könnte eine Abstimmung beliebig lange anhalten, ohne je ein
   Gericht anzurufen.
2. **Von selbst enden.** Bleibt der Antrag ans Schiedsgericht aus, endet die Aussetzung mit
   Fristablauf — ohne dass jemand etwas tun muss. Ein Zustand, der nur durch Handeln endet,
   wäre eine Blockademacht auf Vorrat.
3. **Die Hemmung.** Eine ausgesetzte Abstimmung darf keine Zeit verlieren. Gerechnet wird
   deshalb nicht mit dem gespeicherten Phasenbeginn, sondern mit dem **wirksamen**: Er rückt um
   die Zeit nach hinten, die das Verfahren stillstand.

Die Hemmung wird **nicht gespeichert**, sondern aus den Abschnitten gerechnet. Eine gespeicherte
Summe am Antrag wäre der naheliegende Weg und der falsche: Der Phasenbeginn wird bei jedem
Phasenwechsel neu geschrieben, eine Lebenssumme bekäme also jede Folgephase erneut geschenkt.
Hier zählt nur, was **innerhalb der laufenden Phase** stillstand.
"""

from __future__ import annotations

from collections.abc import Iterable
from datetime import datetime, timedelta

#: Fassung dieser Regel (§ 2 Abs 6).
VERSION = 1

#: § 6 Abs 3 lit d, wörtlich: „binnen sieben Tagen". Satzungsfest — bewusst keine Stellgröße.
SCHIEDSGERICHT_TAGE = 7

#: Ein Abschnitt: (Beginn, Ende). Ein offenes Ende (None) heißt „läuft noch".
Abschnitt = tuple[datetime, datetime | None]


def frist_ende(beginn: datetime) -> datetime:
    """Bis wann der Antrag ans Parteischiedsgericht gestellt sein muss."""
    return beginn + timedelta(days=SCHIEDSGERICHT_TAGE)


def laeuft(
    beginn: datetime,
    jetzt: datetime,
    schiedsgericht_am: datetime | None = None,
    beendet_am: datetime | None = None,
) -> bool:
    """Ob die Aussetzung zu diesem Zeitpunkt noch wirkt.

    Sie endet auf drei Weisen: ausdrücklich aufgehoben, vom Schiedsgericht erledigt, oder — der
    wichtigste Fall — von selbst, weil binnen sieben Tagen kein Antrag gestellt wurde."""
    if jetzt < beginn:
        return False
    if beendet_am is not None and jetzt >= beendet_am:
        return False
    if schiedsgericht_am is None and jetzt >= frist_ende(beginn):
        return False
    return True


def ende_von(
    beginn: datetime,
    schiedsgericht_am: datetime | None = None,
    beendet_am: datetime | None = None,
) -> datetime | None:
    """Wann die Aussetzung endet(e) — oder None, solange sie offen weiterläuft."""
    if beendet_am is not None:
        return beendet_am
    if schiedsgericht_am is None:
        return frist_ende(beginn)
    return None


def grund_des_endes(
    beginn: datetime,
    jetzt: datetime,
    schiedsgericht_am: datetime | None = None,
    beendet_am: datetime | None = None,
) -> str:
    """Ein Satz, warum die Aussetzung nicht mehr wirkt — für die Anzeige und das Archiv."""
    if jetzt < beginn:
        return "noch nicht begonnen"
    if laeuft(beginn, jetzt, schiedsgericht_am, beendet_am):
        return ""
    if beendet_am is not None:
        return "durch Beschluss aufgehoben"
    if schiedsgericht_am is None:
        return (
            f"von selbst geendet: binnen {SCHIEDSGERICHT_TAGE} Tagen kein Antrag an das "
            "Parteischiedsgericht (§ 6 Abs 3 lit d)"
        )
    # Angerufen und nicht aufgehoben heißt: Sie läuft — dann ist sie oben schon abgefangen.
    return ""


def hemmung_sekunden(abschnitte: Iterable[Abschnitt], ab: datetime, jetzt: datetime) -> int:
    """Wie viele Sekunden das Verfahren seit `ab` stillstand.

    Gezählt wird nur die Überschneidung mit dem Zeitraum [ab, jetzt]. Überlappende Abschnitte
    werden zusammengelegt, damit zwei gleichzeitige Aussetzungen die Zeit nicht doppelt hemmen —
    das käme einer Verdopplung der Frist gleich, und die stünde in keiner Satzung."""
    fenster = []
    for beginn, ende in abschnitte:
        von = max(beginn, ab)
        bis = min(ende or jetzt, jetzt)
        if bis > von:
            fenster.append((von, bis))
    if not fenster:
        return 0
    fenster.sort()
    sekunden = 0.0
    laufend_von, laufend_bis = fenster[0]
    for von, bis in fenster[1:]:
        if von <= laufend_bis:
            laufend_bis = max(laufend_bis, bis)
        else:
            sekunden += (laufend_bis - laufend_von).total_seconds()
            laufend_von, laufend_bis = von, bis
    sekunden += (laufend_bis - laufend_von).total_seconds()
    return int(sekunden)


def wirksamer_beginn(
    phase_beginn: datetime, abschnitte: Iterable[Abschnitt], jetzt: datetime
) -> datetime:
    """Der Phasenbeginn, mit dem gerechnet wird — um die Stillstandszeit nach hinten gerückt.

    Läuft gerade eine Aussetzung, wächst die Hemmung mit der Uhr: Der wirksame Beginn wandert
    mit, die Frist rückt nie näher. Genau das soll eine Aussetzung bewirken."""
    return phase_beginn + timedelta(
        seconds=hemmung_sekunden(abschnitte, phase_beginn, jetzt)
    )
