"""Auszählung: klein, deterministisch, reihenfolgeunabhängig.

Dieses Modul ist bewusst so geschrieben, dass es eine interessierte Laiin
nachvollziehen kann. Es gibt keine Gleitkomma-Tricks bei der Mehrheits- und
Beteiligungsprüfung: verglichen wird ausschließlich mit ganzzahliger
Arithmetik (Bruchvergleich per Kreuzmultiplikation), damit niemals ein
Rundungsfehler über einen Beschluss entscheidet.
"""

from __future__ import annotations

import enum
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from plattform_core.policy import Policy


class Stimme(enum.StrEnum):
    JA = "ja"
    NEIN = "nein"
    ENTHALTUNG = "enthaltung"


class AuszaehlungsFehler(ValueError):
    """Ungültige Eingaben, z. B. doppelte Pseudonyme oder unbekannte Stimmwerte."""


@dataclass(frozen=True)
class Auszaehlung:
    ja: int
    nein: int
    enthaltung: int
    stimmberechtigte: int
    mindestbeteiligung: float
    mehrheitsbasis: str
    angenommen: bool
    beteiligung_erreicht: bool
    begruendung: str

    @property
    def abgegeben(self) -> int:
        return self.ja + self.nein + self.enthaltung


def auszaehlen(
    stimmen: Iterable[tuple[str, Stimme | str]],
    stimmberechtigte: int,
    policy: Policy,
) -> Auszaehlung:
    """Zählt Stimmen aus und stellt das Ergebnis fest.

    `stimmen` ist eine Folge von (pseudonym, stimme). Jedes Pseudonym darf genau
    einmal vorkommen — Stimmänderungen sind vor der Auszählung aufzulösen (es
    zählt die letzte Stimme; das erledigt die Datenbank per Unique-Constraint,
    wird hier aber zusätzlich erzwungen, weil dieses Modul auch eigenständig
    mit exportierten Daten läuft).

    Regeln (aus der eingefrorenen Policy, § 5 Abs 4):
    - Beteiligung: (ja + nein + enthaltung) / stimmberechtigte >= mindestbeteiligung.
      Enthaltungen zählen zur Beteiligung — wer sich enthält, nimmt teil.
    - Mehrheit je nach Basis:
        "ja_nein":   ja > nein.
        "abgegeben": ja > (ja + nein + enthaltung) / 2 — Enthaltungen wirken
                     dann faktisch wie Nein. Diese Wahl trifft die
                     Verfahrensordnung, nicht der Code.
    """
    if stimmberechtigte < 1:
        raise AuszaehlungsFehler("stimmberechtigte muss >= 1 sein.")

    gesehen: set[str] = set()
    zaehler: Counter[Stimme] = Counter()
    for pseudonym, wert in stimmen:
        if pseudonym in gesehen:
            raise AuszaehlungsFehler(f"Pseudonym mehrfach in der Stimmliste: {pseudonym!r}")
        gesehen.add(pseudonym)
        try:
            zaehler[Stimme(wert)] += 1
        except ValueError as exc:
            raise AuszaehlungsFehler(f"Unbekannter Stimmwert: {wert!r}") from exc

    ja = zaehler[Stimme.JA]
    nein = zaehler[Stimme.NEIN]
    enthaltung = zaehler[Stimme.ENTHALTUNG]
    abgegeben = ja + nein + enthaltung

    # Beteiligungsprüfung ohne Gleitkomma: abgegeben/berechtigte >= schwelle
    schwelle = Fraction(policy.mindestbeteiligung).limit_denominator(10_000)
    beteiligung_erreicht = Fraction(abgegeben, stimmberechtigte) >= schwelle

    if policy.mehrheitsbasis == "ja_nein":
        mehrheit = ja > nein
        mehrheit_text = f"Ja {ja} : Nein {nein}"
    else:  # "abgegeben"
        mehrheit = 2 * ja > abgegeben
        mehrheit_text = f"Ja {ja} von {abgegeben} abgegebenen"

    angenommen = beteiligung_erreicht and mehrheit

    if not beteiligung_erreicht:
        begruendung = (
            f"Abgelehnt: Mindestbeteiligung verfehlt — {abgegeben}/{stimmberechtigte} "
            f"Stimmberechtigten, erforderlich {float(schwelle):.1%} (§ 5 Abs 4)."
        )
    elif angenommen:
        begruendung = (
            f"Angenommen: {mehrheit_text}, Enthaltungen {enthaltung}; Beteiligung "
            f"{abgegeben}/{stimmberechtigte} (§ 5 Abs 4)."
        )
    else:
        begruendung = (
            f"Abgelehnt: keine Mehrheit — {mehrheit_text}, Enthaltungen {enthaltung}; "
            f"Beteiligung {abgegeben}/{stimmberechtigte}."
        )

    return Auszaehlung(
        ja=ja,
        nein=nein,
        enthaltung=enthaltung,
        stimmberechtigte=stimmberechtigte,
        mindestbeteiligung=policy.mindestbeteiligung,
        mehrheitsbasis=policy.mehrheitsbasis,
        angenommen=angenommen,
        beteiligung_erreicht=beteiligung_erreicht,
        begruendung=begruendung,
    )


# ---------------------------------------------------------------------------
# Personenwahl (§ 7 Abs 1 E-2.5, F-70): Zustimmungswahl über Bewerbungen.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PersonenwahlPlatz:
    bewerbung_id: int
    stimmen: int
    platz: int


@dataclass(frozen=True)
class Personenwahl:
    """Ergebnis einer Mandats-Kandidatur: die Zustimmungsreihenfolge ergibt die
    Reihung des Wahlvorschlags; die Bewerbung mit der meisten Zustimmung gewinnt.
    Attribute `angenommen`/`beteiligung_erreicht`/`begruendung` sind bewusst
    kompatibel zur Sach-Auszählung, damit die Phasenmaschine beide versteht."""

    plaetze: tuple[PersonenwahlPlatz, ...]
    beteiligung: int
    stimmberechtigte: int
    mindestbeteiligung: float
    beteiligung_erreicht: bool
    angenommen: bool
    gewonnen_id: int | None
    begruendung: str


def personenwahl_auszaehlen(
    zustimmungen: Iterable[tuple[str, int]],
    bewerbungen: Iterable[int],
    stimmberechtigte: int,
    policy: Policy,
) -> Personenwahl:
    """Zählt eine Zustimmungswahl aus (§ 7 Abs 1 E-2.5).

    `zustimmungen`: Folge von (pseudonym, bewerbungs_id) — jedes Paar höchstens
    einmal (ein Mitglied kann mehreren Bewerbungen zustimmen, jeder Bewerbung
    aber nur einmal). `bewerbungen`: die wählbaren Bewerbungs-IDs in
    Einreichungsreihenfolge; bei Stimmengleichheit steht die früher
    eingereichte Bewerbung vorn — eine offene, nachrechenbare Regel.
    Beteiligung = Zahl der Pseudonyme mit mindestens einer Zustimmung; die
    Mindestbeteiligung der eingefrorenen Policy gilt wie bei Sachfragen."""
    reihenfolge = {b: i for i, b in enumerate(bewerbungen)}
    if len(reihenfolge) == 0:
        return Personenwahl(
            plaetze=(),
            beteiligung=0,
            stimmberechtigte=stimmberechtigte,
            mindestbeteiligung=policy.mindestbeteiligung,
            beteiligung_erreicht=False,
            angenommen=False,
            gewonnen_id=None,
            begruendung="Keine wählbare Bewerbung — die Kandidatur bleibt ohne Ergebnis (§ 7 Abs 1).",
        )
    gesehen: set[tuple[str, int]] = set()
    zaehler = dict.fromkeys(reihenfolge, 0)
    waehler: set[str] = set()
    for pseudonym, bid in zustimmungen:
        if bid not in reihenfolge:
            raise AuszaehlungsFehler(f"Zustimmung für unbekannte Bewerbung {bid!r}.")
        paar = (pseudonym, bid)
        if paar in gesehen:
            raise AuszaehlungsFehler(f"Doppelte Zustimmung desselben Pseudonyms: {paar!r}.")
        gesehen.add(paar)
        zaehler[bid] += 1
        waehler.add(pseudonym)
    if stimmberechtigte < 1:
        raise AuszaehlungsFehler("Stimmberechtigte müssen mindestens 1 sein.")
    reihung = sorted(reihenfolge, key=lambda b: (-zaehler[b], reihenfolge[b]))
    plaetze = tuple(
        PersonenwahlPlatz(bewerbung_id=b, stimmen=zaehler[b], platz=i + 1) for i, b in enumerate(reihung)
    )
    beteiligung = len(waehler)
    schwelle = Fraction(policy.mindestbeteiligung).limit_denominator(10_000)
    erreicht = Fraction(beteiligung, stimmberechtigte) >= schwelle
    gewonnen = reihung[0] if erreicht and zaehler[reihung[0]] > 0 else None
    if gewonnen is not None:
        begruendung = (
            f"Gewählt ist Bewerbung {gewonnen} mit {zaehler[gewonnen]} Zustimmungen; "
            f"Beteiligung {beteiligung}/{stimmberechtigte} erreicht die Mindestbeteiligung "
            f"von {policy.mindestbeteiligung:.0%} (§ 5 Abs 4, § 7 Abs 1)."
        )
    elif not erreicht:
        begruendung = (
            f"Mindestbeteiligung verfehlt: {beteiligung}/{stimmberechtigte} bei geforderten "
            f"{policy.mindestbeteiligung:.0%} (§ 5 Abs 4) — keine Bewerbung gilt als gewählt."
        )
    else:
        begruendung = "Keine Bewerbung erhielt eine Zustimmung — niemand gilt als gewählt."
    return Personenwahl(
        plaetze=plaetze,
        beteiligung=beteiligung,
        stimmberechtigte=stimmberechtigte,
        mindestbeteiligung=policy.mindestbeteiligung,
        beteiligung_erreicht=erreicht,
        angenommen=gewonnen is not None,
        gewonnen_id=gewonnen,
        begruendung=begruendung,
    )
