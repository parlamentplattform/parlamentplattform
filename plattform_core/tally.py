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
