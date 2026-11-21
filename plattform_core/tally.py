"""Auszählung: klein, deterministisch, reihenfolgeunabhängig.

Dieses Modul ist bewusst so geschrieben, dass es eine interessierte Laiin
nachvollziehen kann. Es gibt keine Gleitkomma-Tricks bei der Mehrheits- und
Beteiligungsprüfung: verglichen wird ausschließlich mit ganzzahliger
Arithmetik (Bruchvergleich per Kreuzmultiplikation), damit niemals ein
Rundungsfehler über einen Beschluss entscheidet.
"""

from __future__ import annotations

import enum
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction

from plattform_core.policy import Policy

#: Fassung der Auszählregel (§ 2 Abs 6). Sie beziffert das **Verfahren**, nicht die
#: Schwellenwerte: Wie ausgezählt wird, steht hier; mit welchen Zahlen, in der am Antrag
#: eingefrorenen Verfahrensordnung. Steigt diese Zahl, hat sich die Rechnung geändert —
#: und dann muss im Regelverzeichnis stehen, warum.
#: Fassung 3 (18.11.2026) rechnet wie Fassung 2. Neu ist die Mindestbeteiligung als Kopfzahl
#: (`mindeststimmen`): Die Begründungssätze nennen „erforderlich N Stimmen (P %)“ statt eines
#: Prozentwerts allein. Kein Ergebnis ändert sich.
VERSION = 3


class Stimme(enum.StrEnum):
    JA = "ja"
    NEIN = "nein"
    ENTHALTUNG = "enthaltung"


def mindestbeteiligung_erreicht(abgegeben: int, stimmberechtigte: int, mindestbeteiligung: float) -> bool:
    """Ob die Mindestbeteiligung erreicht ist (§ 5 Abs 4) — als Bruchvergleich ohne Gleitkomma.

    Die eine Stelle, die Auszählung und Anzeige gemeinsam lesen: Sonst könnte eine Seite „erreicht“
    zeigen, wo die Auszählung es verneint."""
    if stimmberechtigte < 1:
        return False
    schwelle = Fraction(mindestbeteiligung).limit_denominator(10_000)
    return Fraction(abgegeben, stimmberechtigte) >= schwelle


def mindeststimmen(stimmberechtigte: int, mindestbeteiligung: float) -> int:
    """Die Mindestbeteiligung als Kopfzahl: die kleinste Zahl abgegebener Stimmen, mit der
    `mindestbeteiligung_erreicht` wahr ist — der Anteil der Stimmberechtigten, aufgerundet.

    Von Hand: Stimmberechtigte mal Anteil, auf die nächste ganze Zahl aufrunden. 5 % von 100
    sind 5; 5 % von 20 sind 1; 5 % von 21 sind 1,05, also 2. Gerechnet wird mit demselben Bruch
    wie in der Auszählung, damit Anzeige und Ergebnis nie auseinanderfallen. Bei einem Kreis ohne
    Stimmberechtigte gibt es keine Kopfzahl: 0."""
    if stimmberechtigte < 1:
        return 0
    schwelle = Fraction(mindestbeteiligung).limit_denominator(10_000)
    return max(0, -(-schwelle.numerator * stimmberechtigte // schwelle.denominator))


def _mindestbeteiligung_text(stimmberechtigte: int, mindestbeteiligung: float) -> str:
    """„5 Stimmen (5 %)“ — Kopfzahl und Anteil für die Begründungssätze, Komma als Dezimalzeichen."""
    kopfzahl = mindeststimmen(stimmberechtigte, mindestbeteiligung)
    prozent = Fraction(mindestbeteiligung).limit_denominator(10_000) * 100
    if prozent.denominator == 1:
        anteil = str(prozent.numerator)
    else:
        anteil = f"{float(prozent):.2f}".rstrip("0").rstrip(".").replace(".", ",")
    return f"{kopfzahl} {'Stimme' if kopfzahl == 1 else 'Stimmen'} ({anteil} %)"


def tendenz_sichtbar(policy: Policy, abgegeben: int, stimmberechtigte: int) -> bool:
    """Ob eine laufende Abstimmung ihre Tendenz zeigen darf (D-D2): nur wenn die eingefrorene Ordnung
    es ab erreichter Mindestbeteiligung freigibt (Schalter 1) und diese erreicht ist. Bei 0 nie —
    die Voreinstellung (§ 5 Abs 3 lit e: veröffentlicht wird nach der Abstimmung). Welche Antragsarten
    es überhaupt betrifft, entscheidet der Aufrufer (nur Sachanträge). Ändert die Auszählung nicht."""
    if policy.tendenz_ab_mindestbeteiligung != 1:
        return False
    return mindestbeteiligung_erreicht(abgegeben, stimmberechtigte, policy.mindestbeteiligung)


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
    *,
    leerer_oertlicher_kreis: bool = False,
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
    if stimmberechtigte < 0 or (stimmberechtigte == 0 and not leerer_oertlicher_kreis):
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
    if stimmberechtigte == 0 and abgegeben:
        raise AuszaehlungsFehler("Keine Stimmen bei leerem örtlichem Teilnehmerkreis zulässig.")

    # Beteiligungsprüfung ohne Gleitkomma: abgegeben/berechtigte >= schwelle
    beteiligung_erreicht = mindestbeteiligung_erreicht(abgegeben, stimmberechtigte, policy.mindestbeteiligung)

    if policy.mehrheitsbasis == "ja_nein":
        mehrheit = ja > nein
        mehrheit_text = f"Ja {ja} : Nein {nein}"
    else:  # "abgegeben"
        mehrheit = 2 * ja > abgegeben
        mehrheit_text = f"Ja {ja} von {abgegeben} abgegebenen"

    angenommen = beteiligung_erreicht and mehrheit

    if stimmberechtigte == 0:
        begruendung = "Keine Stimmberechtigten im festgehaltenen örtlichen Kreis — kein Beschluss."
    elif not beteiligung_erreicht:
        begruendung = (
            f"Abgelehnt: Mindestbeteiligung verfehlt — {abgegeben}/{stimmberechtigte} "
            f"Stimmberechtigten, erforderlich "
            f"{_mindestbeteiligung_text(stimmberechtigte, policy.mindestbeteiligung)} (§ 5 Abs 4)."
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
    *,
    leerer_oertlicher_kreis: bool = False,
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
    if stimmberechtigte < 0 or (stimmberechtigte == 0 and not leerer_oertlicher_kreis):
        raise AuszaehlungsFehler("Stimmberechtigte müssen mindestens 1 sein.")
    if stimmberechtigte == 0 and waehler:
        raise AuszaehlungsFehler("Keine Zustimmungen bei leerem örtlichem Teilnehmerkreis zulässig.")
    reihung = sorted(reihenfolge, key=lambda b: (-zaehler[b], reihenfolge[b]))
    plaetze = tuple(
        PersonenwahlPlatz(bewerbung_id=b, stimmen=zaehler[b], platz=i + 1) for i, b in enumerate(reihung)
    )
    beteiligung = len(waehler)
    erreicht = mindestbeteiligung_erreicht(beteiligung, stimmberechtigte, policy.mindestbeteiligung)
    gewonnen = reihung[0] if erreicht and zaehler[reihung[0]] > 0 else None
    if stimmberechtigte == 0:
        begruendung = "Keine Stimmberechtigten im festgehaltenen örtlichen Kreis — niemand gewählt."
    elif gewonnen is not None:
        begruendung = (
            f"Gewählt ist Bewerbung {gewonnen} mit {zaehler[gewonnen]} Zustimmungen; "
            f"Beteiligung {beteiligung}/{stimmberechtigte} erreicht die Mindestbeteiligung "
            f"von {_mindestbeteiligung_text(stimmberechtigte, policy.mindestbeteiligung)} "
            f"(§ 5 Abs 4, § 7 Abs 1)."
        )
    elif not erreicht:
        begruendung = (
            f"Mindestbeteiligung verfehlt: {beteiligung}/{stimmberechtigte}, erforderlich "
            f"{_mindestbeteiligung_text(stimmberechtigte, policy.mindestbeteiligung)} (§ 5 Abs 4) "
            f"— keine Bewerbung gilt als gewählt."
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


# ---------------------------------------------------------------------------
# Gegenprobe und Prüfsumme der Stimmliste (Gesamtprüfung GP-138).
# Beides steht NEBEN der Auszählung: Ob eine Liste gezählt werden darf, entscheidet die
# Gegenprobe; wie gezählt wird, bleibt oben unverändert — kein Ergebnis ändert sich.
# ---------------------------------------------------------------------------

#: Ein Stimmzettel steht in der Liste, zu dem das Stimmregister keinen Eintrag führt.
OHNE_REGISTERZEILE = "stimmzettel_ohne_registerzeile"
#: Es haben mehr Menschen gestimmt, als bei Abstimmungsbeginn als stimmberechtigt festgestellt wurden.
UEBERZAHL = "mehr_stimmen_als_stimmberechtigte"
#: Die Audit-Kette führt nicht so viele Stimm-Ereignisse, wie Stimmzettel in der Liste stehen.
EREIGNISSE_WEICHEN_AB = "stimmereignisse_weichen_ab"


def gegenprobe(
    *,
    stimmzettel: int,
    waehler: int,
    ohne_registerzeile: int,
    stimmberechtigte: int | None,
    stimmereignisse: int | None,
) -> tuple[str, ...]:
    """Prüft eine Stimmliste gegen das, was unabhängig von ihr feststeht — bevor ein Ergebnis
    festgestellt wird. Rückgabe: die Abweichungen als Kennungen, leer, wenn alles stimmt.

    Von Hand, mit vier Zahlen:
    - `ohne_registerzeile`: Stimmzettel, deren Pseudonym im Stimmregister des Antrags fehlt. Jede
      Stimme entsteht mit ihrem Registereintrag; fehlt er, kam der Zettel nicht aus einer Stimmabgabe.
    - `waehler` gegen `stimmberechtigte`: Es können nicht mehr Menschen stimmen, als bei
      Abstimmungsbeginn festgestellt wurden (§ 4 Abs 4 lit a). `None` heißt: nie festgestellt
      (Altbestand) — dann entfällt der Vergleich.
    - `stimmzettel` gegen `stimmereignisse`: Jede Stimmabgabe schreibt ein Ereignis in die
      Audit-Kette. Bei Sachfragen ist das die Zahl der Ereignisse „stimme“; bei der Zustimmungswahl
      die der gegebenen abzüglich der zurückgenommenen Zustimmungen. `None` heißt: Die Abstimmung
      begann vor dieser Prüfung — dann entfällt der Vergleich.

    Bei Sachfragen ist `waehler` gleich `stimmzettel`; bei der Zustimmungswahl zählt `stimmzettel`
    die geltenden Zustimmungen und `waehler` die Menschen dahinter."""
    abweichungen = []
    if ohne_registerzeile > 0:
        abweichungen.append(OHNE_REGISTERZEILE)
    if stimmberechtigte is not None and waehler > stimmberechtigte:
        abweichungen.append(UEBERZAHL)
    if stimmereignisse is not None and stimmereignisse != stimmzettel:
        abweichungen.append(EREIGNISSE_WEICHEN_AB)
    return tuple(abweichungen)


def stimmliste_pruefsumme(zeilen: Iterable[Iterable]) -> str:
    """SHA-256 über die sortierte Stimmliste — das Siegel, das mit dem Ergebnis in die Audit-Kette
    kommt. Wer die veröffentlichte Liste später ändert, ändert diese Zahl.

    `zeilen`: je Stimmzettel eine Liste einfacher Werte, bei Sachfragen `[pseudonym, stimme]`.
    Von Hand: die Zeilen sortieren, als JSON ohne Leerzeichen schreiben (UTF-8), SHA-256 bilden.
    Die Reihenfolge der Eingabe spielt keine Rolle."""
    text = json.dumps(sorted(list(zeile) for zeile in zeilen), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()
