"""Der Sitzungsmodus eines Mandatars (FB-L5, § 7 Abs 3 lit b, Abs 5, Abs 9) — die Rechenregeln.

Im Sitzungsmodus meldet der Mandatar vom Sitzungssaal aus je Tagesordnungspunkt, worum es geht,
wie er stimmen wird und wie abgestimmt wurde (der Ticker); er sieht dabei, was die Mitglieder
zu den Punkten beschlossen haben (die Live-Beschlusslage). Drei Regeln rechnen hier:

* **Beschlusslage je Punkt.** Aus dem Stand des verknüpften Antrags oder der Mandatsfrage:
  angenommen, abgelehnt, in Abstimmung (bis zum Fristende), noch nicht in Abstimmung, ohne
  Beschluss beendet — oder kein Antrag verknüpft. Eine laufende Abstimmung zeigt **keinen**
  Zwischenstand und keine Tendenz: Die Frist nach § 5 Abs 3 lit d bleibt ungekürzt, und der
  Mandatar sieht, was entschieden ist, nicht, wohin es sich neigt (D-D2).
* **Maßgebliche Meldung je Punkt.** Meldungen werden nie geändert; eine Korrektur ist eine neue
  Meldung, die auf die alte verweist — die alte gilt dann als berichtigt. Maßgeblich für die
  Rechenschaft ist die jüngste nicht berichtigte Meldung, die als „abgestimmt“ gekennzeichnet ist
  und eine Stimme trägt; gibt es keine, die jüngste nicht berichtigte mit Stimme (dann nur
  angekündigt); sonst keine. Aus ihr wird der Rechenschaftseintrag vorbefüllt (§ 7 Abs 5) —
  eingetragen wird er vom Mandatar, nicht von der Plattform.
* **Wirksames Ende einer Sitzung.** Der Mandatar beendet den Live-Modus selbst. Vergisst er es,
  gilt die Sitzung nach der Höchstdauer als beendet (Entscheidung E3 zum Bauplan 0.53.0); die
  Höchstdauer ist eine Stellgröße des Registers (`live-hoechstdauer-stunden`), die der Aufrufer
  als Zahl hereinreicht.

Reine Funktionen, Uhr als Parameter, keine Django-Importe."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, timedelta

#: Fassung dieser Regel (§ 2 Abs 6).
VERSION = 1

#: Längster Text einer Livemeldung — wie im Fahrtenbuch (FB-L5): kurz genug für den Saal.
MELDUNG_ZEICHEN = 280

LAGE_ANGENOMMEN = "angenommen"
LAGE_ABGELEHNT = "abgelehnt"
LAGE_ABSTIMMUNG = "abstimmung"
LAGE_VORHER = "vorher"
LAGE_OHNE_BESCHLUSS = "ohne_beschluss"
LAGE_KEIN_ANTRAG = "kein_antrag"

#: Phasen vor der Abstimmung — das Verfahren läuft, entschieden ist nichts.
_VOR_DER_ABSTIMMUNG = frozenset({"unterstuetzung", "beratung"})
#: Endphasen ohne Beschluss in der Sache: verfallen, zurückgewiesen, zurückgezogen.
_OHNE_BESCHLUSS = frozenset({"verfallen", "zurueckgewiesen", "zurueckgezogen"})


@dataclass(frozen=True)
class Beschlusslage:
    """Was die Plattform zu einem Tagesordnungspunkt beschlossen hat — ein Stand, kein Urteil.

    `status`: eine der `LAGE_*`-Kennungen. `bis`: Fristende der laufenden Abstimmung (sonst None) —
    die einzige Zahl, die eine laufende Abstimmung preisgibt."""

    status: str
    bis: datetime | None = None

    @property
    def entschieden(self) -> bool:
        return self.status in (LAGE_ANGENOMMEN, LAGE_ABGELEHNT)


def beschlusslage(phase: str | None, abstimmung_bis: datetime | None = None) -> Beschlusslage:
    """Die Beschlusslage aus der Phase des verknüpften Antrags (`None`: kein Antrag verknüpft).

    `abstimmung_bis` ist das Fristende einer laufenden Abstimmung; es wird nur in dieser Phase
    weitergegeben. Stimmenzahlen nimmt die Funktion gar nicht erst entgegen — was sie nicht kennt,
    kann sie nicht verraten."""
    if phase is None:
        return Beschlusslage(LAGE_KEIN_ANTRAG)
    if phase == LAGE_ANGENOMMEN:
        return Beschlusslage(LAGE_ANGENOMMEN)
    if phase == LAGE_ABGELEHNT:
        return Beschlusslage(LAGE_ABGELEHNT)
    if phase == "abstimmung":
        return Beschlusslage(LAGE_ABSTIMMUNG, abstimmung_bis)
    if phase in _VOR_DER_ABSTIMMUNG:
        return Beschlusslage(LAGE_VORHER)
    if phase in _OHNE_BESCHLUSS:
        return Beschlusslage(LAGE_OHNE_BESCHLUSS)
    raise ValueError(f"Unbekannte Phase: {phase!r}")


@dataclass(frozen=True)
class Meldung:
    """Was die Regel von einer Livemeldung braucht — Kennung, Punkt, Zeit, Stimme, Kennzeichnung
    und die Kennung der Meldung, die sie berichtigt (oder None)."""

    pk: int
    punkt: int | None
    zeitpunkt: datetime
    stimme: str = ""
    abgestimmt: bool = False
    berichtigt: int | None = None


def berichtigte(meldungen: Iterable[Meldung]) -> frozenset[int]:
    """Die Kennungen der Meldungen, die eine spätere Meldung berichtigt hat."""
    return frozenset(m.berichtigt for m in meldungen if m.berichtigt is not None)


def massgebliche_meldungen(meldungen: Iterable[Meldung]) -> dict[int, Meldung]:
    """Je Tagesordnungspunkt die Meldung, aus der die Rechenschaft vorbefüllt wird.

    Vorrang: jüngste nicht berichtigte Meldung mit Stimme und Kennzeichen „abgestimmt“; sonst die
    jüngste nicht berichtigte mit Stimme. Punkte ohne solche Meldung fehlen im Ergebnis. Bei
    gleichem Zeitpunkt entscheidet die höhere Kennung (die später gespeicherte)."""
    alle = list(meldungen)
    weg = berichtigte(alle)
    ergebnis: dict[int, tuple[tuple[int, datetime, int], Meldung]] = {}
    for m in alle:
        if m.punkt is None or m.pk in weg or not m.stimme:
            continue
        rang = (1 if m.abgestimmt else 0, m.zeitpunkt, m.pk)
        bisher = ergebnis.get(m.punkt)
        if bisher is None or rang > bisher[0]:
            ergebnis[m.punkt] = (rang, m)
    return {punkt: m for punkt, (_, m) in ergebnis.items()}


def wirksames_ende(
    beginn: datetime, ende: datetime | None, jetzt: datetime, hoechstdauer_stunden: int
) -> datetime | None:
    """Wann die Sitzung endete — None, solange sie läuft.

    Ein vom Mandatar gesetztes Ende gilt, wenn es vor der Höchstdauer liegt; sonst endet die Sitzung
    mit Ablauf der Höchstdauer, sobald die erreicht ist. Eine Höchstdauer unter einer Stunde wird
    als eine Stunde gerechnet — die Stellgröße kann den Ticker nicht abschalten."""
    grenze = beginn + timedelta(hours=max(1, hoechstdauer_stunden))
    if ende is not None:
        return min(ende, grenze)
    if jetzt >= grenze:
        return grenze
    return None


def laeuft(beginn: datetime, ende: datetime | None, jetzt: datetime, hoechstdauer_stunden: int) -> bool:
    """Die Sitzung hat begonnen und ist nicht zu Ende."""
    return beginn <= jetzt and wirksames_ende(beginn, ende, jetzt, hoechstdauer_stunden) is None
