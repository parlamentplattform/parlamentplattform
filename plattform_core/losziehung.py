"""Die Auslosung des Expertenrats aus der öffentlichen Fachliste (§ 6 Abs 7).

Die Satzung: *„Für die Beratung zu einzelnen Anträgen werden Fachleute aus einer öffentlich
geführten Liste nach einem offengelegten Zufallsverfahren ausgewählt. … Bei Aufgaben mit
unmittelbarem Vollzugs- oder Beschaffungsbezug wird er in zwei unabhängig voneinander besetzten
Gruppen tätig."*

Zwei Forderungen stehen darin, die einander widersprechen könnten:

* **Offengelegt und nachrechenbar** (§ 2 Abs 6): Jeder muss das Ergebnis selbst nachrechnen
  können — sonst ist „Zufallsverfahren" nur ein Wort.
* **Unvorhersehbar**: Wer das Ergebnis vorher ausrechnen kann, kann die Liste danach richten.

Beides zugleich geht nur, wenn der Zufall aus etwas kommt, das **im Augenblick der Ziehung**
feststeht und vorher niemand kennt. Der Anker ist deshalb der Kopf der Audit-Kette zum Zeitpunkt
der Ziehung: eine Prüfsumme, die von jeder Handlung auf der Plattform abhängt und die niemand
vorausberechnen kann, ohne die Zukunft zu kennen. Veröffentlicht wird sie mit dem Ergebnis —
danach ist jede Ziehung mit einem Prüfsummenwerkzeug nachzurechnen.

**Nicht** genommen wird der früheste Eintrag eines Antrags: Der entsteht beim Einbringen, also
zwei Monate vor der Ziehung, und wäre die ganze Zeit bekannt.

Das Losverfahren selbst ist so einfach wie möglich gehalten, damit es nachvollziehbar bleibt:
Jede Kandidatin bekommt einen Loswert `sha256(anker + ihr Schlüssel)`; die kleinsten Werte
kommen zuerst in Gruppe 1, dann in Gruppe 2. Kein Gewicht, keine Reihung nach Verdienst — die
Satzung will das Los, nicht eine Auswahl.
"""

from __future__ import annotations

import hashlib
from collections.abc import Iterable
from dataclasses import dataclass, field

#: Fassung dieser Regel (§ 2 Abs 6). Ändert sich die Ziehung, steigt die Zahl — und jede
#: bereits vollzogene Ziehung bleibt nach ihrer eigenen Fassung nachrechenbar.
VERSION = 1

#: § 6 Abs 8: „Jeder Rat besteht aus mindestens drei Mitgliedern." Satzungsfest — eine
#: Stellgröße darf die Gruppen vergrößern, nie unter diese Zahl drücken.
SATZUNG_MIN_RATSGROESSE = 3


class LosFehler(ValueError):
    """Die Ziehung ist nicht durchführbar — zu wenige Kandidaten, unbrauchbare Größen."""


@dataclass(frozen=True)
class Kandidat:
    """Ein Eintrag der Fachliste, wie ihn die Ziehung sieht.

    `schluessel` ist eine stabile, pseudonyme Kennung — der Name steht auf der öffentlichen
    Fachliste, in der Rechnung hat er nichts verloren: So bleibt die Ziehung auch dann
    nachrechenbar, wenn jemand seine Einwilligung zur Namensnennung widerruft (§ 8 Abs 4)."""

    schluessel: str
    fachgebiete: frozenset[str] = field(default_factory=frozenset)
    ausgeschlossen: bool = False
    ausschlussgrund: str = ""


@dataclass(frozen=True)
class Platz:
    schluessel: str
    gruppe: int
    loswert: str
    rang: int


@dataclass(frozen=True)
class Ziehung:
    """Das vollständige Ergebnis — alles, was zum Nachrechnen nötig ist."""

    anker: str
    gruppen: tuple[tuple[Platz, ...], ...]
    lostopf: tuple[str, ...]
    ausgeschlossen: tuple[tuple[str, str], ...]
    version: int

    @property
    def plaetze(self) -> tuple[Platz, ...]:
        return tuple(platz for gruppe in self.gruppen for platz in gruppe)


def loswert(anker: str, schluessel: str) -> str:
    """Der Loswert einer Kandidatin: `sha256(anker + "|" + schlüssel)`.

    Mit jedem Prüfsummenwerkzeug nachzurechnen — das senkrechte Strichzeichen ist Absicht,
    damit zwei verschiedene Paare nie dieselbe Zeichenfolge ergeben."""
    return hashlib.sha256(f"{anker}|{schluessel}".encode()).hexdigest()


def lostopf(kandidaten: Iterable[Kandidat], fachgebiete: Iterable[str] = ()) -> tuple[list[Kandidat], list[tuple[str, str]]]:
    """Wer mitlost und wer nicht — mit dem Grund für jeden Ausschluss.

    Sind Fachgebiete angegeben, kommt nur in den Topf, wer mindestens eines davon führt
    (§ 6 Abs 7: „Fachleute"). Ohne Angabe lost die ganze Liste mit."""
    verlangt = frozenset(fachgebiete)
    drin, draussen = [], []
    for kandidat in kandidaten:
        if kandidat.ausgeschlossen:
            draussen.append((kandidat.schluessel, kandidat.ausschlussgrund or "ausgeschlossen"))
        elif verlangt and not (kandidat.fachgebiete & verlangt):
            draussen.append((kandidat.schluessel, "kein passendes Fachgebiet"))
        else:
            drin.append(kandidat)
    return drin, draussen


def ziehen(
    anker: str,
    kandidaten: Iterable[Kandidat],
    groessen: Iterable[int],
    fachgebiete: Iterable[str] = (),
) -> Ziehung:
    """Zieht die Gruppen des Expertenrats (§ 6 Abs 7).

    `groessen` nennt die Gruppen der Reihe nach — für einen Antrag mit Vollzugsbezug zwei,
    sonst eine. Die Gruppen sind **durch die Konstruktion** getrennt: Gruppe 2 wird aus dem
    Rest gezogen, nicht aus dem ganzen Topf. Eine Prüfung, die man vergessen kann, gibt es
    hier deshalb nicht.

    Reicht der Topf nicht für alle Gruppen, wirft diese Funktion. Eine halb besetzte zweite
    Gruppe wäre schlimmer als gar keine Ziehung: Sie sähe nach Prüfung aus und wäre keine."""
    groessen = list(groessen)
    if not groessen:
        raise LosFehler("Eine Ziehung ohne Gruppen ist keine.")
    zu_klein = [g for g in groessen if g < SATZUNG_MIN_RATSGROESSE]
    if zu_klein:
        raise LosFehler(
            f"Gruppengröße {zu_klein[0]} unterschreitet das Satzungsminimum "
            f"{SATZUNG_MIN_RATSGROESSE} (§ 6 Abs 8)."
        )
    if not anker:
        raise LosFehler("Ohne Anker keine nachrechenbare Ziehung.")

    drin, draussen = lostopf(kandidaten, fachgebiete)
    schluessel = [k.schluessel for k in drin]
    if len(set(schluessel)) != len(schluessel):
        raise LosFehler("Ein Schlüssel kommt zweimal vor — die Ziehung wäre nicht eindeutig.")
    if len(drin) < sum(groessen):
        raise LosFehler(
            f"Der Lostopf hat {len(drin)} Kandidaten, gebraucht werden {sum(groessen)}."
        )

    # Sortiert wird nach dem Loswert; der Schlüssel bricht den (praktisch unmöglichen)
    # Gleichstand, damit die Ordnung total ist und die Ziehung reihenfolgeunabhängig bleibt.
    gereiht = sorted(drin, key=lambda k: (loswert(anker, k.schluessel), k.schluessel))

    gruppen, rang = [], 0
    for nummer, groesse in enumerate(groessen, start=1):
        plaetze = []
        for platz_nr in range(groesse):
            kandidat = gereiht[rang]
            plaetze.append(
                Platz(
                    schluessel=kandidat.schluessel,
                    gruppe=nummer,
                    loswert=loswert(anker, kandidat.schluessel),
                    rang=platz_nr + 1,
                )
            )
            rang += 1
        gruppen.append(tuple(plaetze))

    return Ziehung(
        anker=anker,
        gruppen=tuple(gruppen),
        lostopf=tuple(k.schluessel for k in gereiht),
        ausgeschlossen=tuple(draussen),
        version=VERSION,
    )
