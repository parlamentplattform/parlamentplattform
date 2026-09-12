"""Fristen der Rechenschaft und der Berichte eines Mandatars (§ 7 Abs 3 lit b, § 7 Abs 5).

Die Satzung verpflichtet den Mandatar auf zwei Arten des Berichtens:

* **§ 7 Abs 5 — Rechenschaft.** Nach jeder Abstimmung des Vertretungskörpers, die auf der
  Plattform als Sitzungstag angekündigt war, trägt der Mandatar binnen sieben Tagen ein, was
  der Vertretungskörper beschlossen hat, wie er selbst gestimmt hat und warum — neben dem
  Beschluss der Plattform, falls es einen gab. Die Plattform stellt beides nebeneinander;
  sie bewertet nicht.
* **§ 7 Abs 3 lit b — Berichte.** Ein Sammelbericht binnen sieben Tagen nach jedem
  Sitzungstag und ein Monatsbericht für jeden vollen Kalendermonat des Mandats.

Dieses Modul rechnet nur die Fristen und den Stand („offen", „fristgerecht", „verspätet",
„ausständig") — Zahlen, kein Urteil. Ob und wie ein Ausstand angezeigt wird, entscheidet die
Ansicht; eine Sanktion gibt es nicht (§ 7 Abs 2 und 4: die Mandatsvereinbarung bindet, die
Plattform macht sichtbar).

**Warum sieben Tage satzungsfest sind und die Monatskarenz eine Stellgröße.** Die sieben Tage
der Rechenschaft und des Sammelberichts stehen wörtlich in der Satzung. Wer sie im Register
verlängern könnte, könnte die Rechenschaftspflicht eines Mandatars still aushöhlen — die Frist
gehört deshalb als Konstante hierher, wie die sieben Tage der Aussetzung in `aussetzung.py`.
Der Monatsbericht dagegen ist satzungsgemäß „monatlich"; **wann** im Folgemonat er als
fristgerecht gilt, sagt die Satzung nicht. Diese Karenz ist eine Gebrauchsgrenze und darum eine
Stellgröße des Registers (`mandatar-monatsbericht-frist-tage`), die der Aufrufer als Zahl
hereinreicht — das Modul selbst liest kein Register und kennt kein Django.

Die Berichtspflicht für Monate beginnt mit `BERICHTSPFLICHT_AB`: Mandate, die vorher bestanden,
schulden keine Monatsberichte für die Zeit, in der es das Werkzeug dafür noch nicht gab.

Reine Funktionen, Uhr als Parameter (`heute`), keine Django-Importe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

#: Fassung dieser Regel (§ 2 Abs 6).
VERSION = 1

#: § 7 Abs 5, wörtlich: binnen sieben Tagen nach dem Sitzungstag. Satzungsfest — keine Stellgröße.
RECHENSCHAFT_TAGE = 7
#: § 7 Abs 3 lit b: Sammelbericht binnen sieben Tagen nach dem Sitzungstag. Satzungsfest.
SAMMELBERICHT_TAGE = 7
#: Erster Kalendermonat, für den ein Monatsbericht geschuldet ist.
BERICHTSPFLICHT_AB = date(2026, 10, 1)

STATUS_OFFEN = "offen"
STATUS_FRISTGERECHT = "fristgerecht"
STATUS_VERSPAETET = "verspaetet"
STATUS_AUSSTAENDIG = "ausstaendig"


@dataclass(frozen=True)
class Lage:
    """Der Stand einer Pflicht gegenüber ihrer Frist — Zahlen, kein Urteil.

    `status`: offen (Frist läuft), fristgerecht (erledigt bis zur Frist), verspaetet (erledigt
    nach der Frist), ausstaendig (Frist um, nichts eingetragen).
    `resttage`: Tage bis zur Frist, solange sie läuft; sonst 0.
    `seit_tagen`: Tage seit der Frist bei Ausstand bzw. Tage der Verspätung; sonst 0."""

    status: str
    resttage: int
    seit_tagen: int

    @property
    def erledigt(self) -> bool:
        return self.status in (STATUS_FRISTGERECHT, STATUS_VERSPAETET)


def faellig_am(sitzungstag: date, tage: int) -> date:
    """Der letzte Tag der Frist, gerechnet ab dem Sitzungstag."""
    return sitzungstag + timedelta(days=tage)


def monatsanfang(tag: date) -> date:
    return tag.replace(day=1)


def folgemonat(monat: date) -> date:
    """Der erste Tag des Monats nach `monat` — Jahreswechsel eingeschlossen."""
    if monat.month == 12:
        return date(monat.year + 1, 1, 1)
    return date(monat.year, monat.month + 1, 1)


def berichtsmonate(
    angetreten: date,
    beendet: date | None,
    heute: date,
    ab: date = BERICHTSPFLICHT_AB,
) -> list[date]:
    """Erste Tage aller vollen Kalendermonate, für die ein Monatsbericht geschuldet ist.

    Ein Monat zählt, wenn das Mandat an seinem ersten Tag schon lief (nicht vor `ab`) und an
    seinem letzten Tag noch lief — und wenn er heute vorbei ist. Ein angebrochener erster oder
    letzter Monat zählt nicht: Ein „Monatsbericht" über neun Tage wäre keiner."""
    beginn = max(angetreten, ab)
    monat = beginn if beginn.day == 1 else folgemonat(monatsanfang(beginn))
    monate: list[date] = []
    while True:
        naechster = folgemonat(monat)
        if naechster > heute:
            break  # der Monat ist noch nicht vorbei
        letzter_tag = naechster - timedelta(days=1)
        if beendet is not None and beendet < letzter_tag:
            break  # das Mandat endete, bevor der Monat voll war
        monate.append(monat)
        monat = naechster
    return monate


def monatsbericht_faellig_am(monat: date, karenz_tage: int) -> date:
    """Bis zu welchem Tag des Folgemonats der Monatsbericht als fristgerecht gilt.

    `karenz_tage` 7 heißt: der 7. Tag des Folgemonats. Werte unter 1 wirken wie 1 — eine Frist,
    die vor dem Monatsende läge, gäbe es sonst."""
    return folgemonat(monat) + timedelta(days=max(karenz_tage, 1) - 1)


def lage(faellig: date, erledigt_am: date | None, heute: date) -> Lage:
    """Der Stand einer Pflicht: erledigt (fristgerecht oder verspätet), noch offen oder ausständig."""
    if erledigt_am is not None:
        if erledigt_am <= faellig:
            return Lage(STATUS_FRISTGERECHT, 0, 0)
        return Lage(STATUS_VERSPAETET, 0, (erledigt_am - faellig).days)
    if heute <= faellig:
        return Lage(STATUS_OFFEN, (faellig - heute).days, 0)
    return Lage(STATUS_AUSSTAENDIG, 0, (heute - faellig).days)
