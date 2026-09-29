"""Audit-Log als Hash-Kette: Manipulationserkennung ohne Blockchain-Theater.

Verfahrensrelevante Ereignisse werden als Einträge protokolliert (Phasenwechsel,
Stimmen, Rollen, Beschlüsse, Registeränderungen; Unterstützungen und ihr Rückzug
bisher nicht — siehe Befund #27/#57). Der Hash eines Eintrags versiegelt den Hash
des Vorgängers plus den kanonisch serialisierten Ereignisinhalt, seit 0.45 samt
Zeitstempel. Wer irgendeinen alten Eintrag verändert, verändert damit
zwangsläufig alle nachfolgenden Hashes.

Was die Kette heute leistet — und was nicht: Sie erkennt jede Änderung, die nicht
bis zum Kopf nachgerechnet wurde. Ein extern veröffentlichter Kettenkopf, gegen
den man einen vollständig neu gerechneten Kopf vergleichen könnte, ist geplant
(F-22, ADR-005), aber noch nicht gebaut; bis dahin schützt die Kette vor stillen
Änderungen, nicht vor jemandem mit Schreibzugriff, der alles neu rechnet.

Das Verfahren ist absichtlich in ~60 Zeilen erklärbar: "Jeder Eintrag
versiegelt alle vorherigen." Mehr Kryptografie braucht es für diesen Zweck
nicht (ADR-005).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

GENESIS = "0" * 64


def _kanonisch(ereignis: dict[str, Any]) -> bytes:
    """Kanonische JSON-Serialisierung: sortierte Schlüssel, keine Leerzeichen,
    UTF-8 unverändert. Zwei inhaltsgleiche Ereignisse ergeben byte-identische
    Serialisierungen — die Grundvoraussetzung reproduzierbarer Hashes."""
    return json.dumps(ereignis, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def ereignis_hash(vorgaenger_hash: str, ereignis: dict[str, Any]) -> str:
    """SHA-256 über Vorgänger-Hash und kanonisches Ereignis."""
    h = hashlib.sha256()
    h.update(vorgaenger_hash.encode("ascii"))
    h.update(_kanonisch(ereignis))
    return h.hexdigest()


class KettenFehler(ValueError):
    """Die vorhandene Kette lässt sich nicht als lückenlose Folge lesen."""


def vorgaenger_zuordnen(hashes: Iterable[str], start_hash: str = GENESIS) -> list[str]:
    """Zu einer Folge gespeicherter Hashes (in Kettenreihenfolge) der Vorgänger jedes Eintrags.

    Der erste Eintrag hängt am Startwert, jeder weitere am Hash seines Vorgängers. Das Ergebnis
    ist die Spalte `vorgaenger`, die den Vorgänger zur Datenbank-Tatsache macht: Mit einer
    Eindeutigkeitsbedingung darauf können zwei Einträge nie mehr am selben Kopf hängen — eine
    Gabel ist dann physisch unmöglich, nicht nur unwahrscheinlich.

    Kommt ein Hash zweimal vor, hingen zwei Einträge am selben Vorgänger; eine solche Kette ist
    schon gegabelt und lässt sich nicht eindeutig zuordnen — das wird gemeldet, nicht kaschiert."""
    zuordnung: list[str] = []
    vergeben: set[str] = set()
    aktuell = start_hash
    for index, gespeichert in enumerate(hashes):
        if aktuell in vergeben:
            raise KettenFehler(
                f"Eintrag {index} hängt am selben Vorgänger wie ein früherer — die Kette ist gegabelt."
            )
        zuordnung.append(aktuell)
        vergeben.add(aktuell)
        aktuell = gespeichert
    return zuordnung


def kette_pruefen(
    eintraege: Iterable[tuple[dict[str, Any], str]],
    start_hash: str = GENESIS,
) -> tuple[bool, int | None]:
    """Prüft eine Kette aus (ereignis, gespeicherter_hash)-Paaren.

    Rückgabe: (True, None) wenn alles stimmt, sonst (False, index) mit dem
    Index des ersten Eintrags, dessen Hash nicht zum Inhalt passt.
    """
    aktuell = start_hash
    for index, (ereignis, gespeichert) in enumerate(eintraege):
        erwartet = ereignis_hash(aktuell, ereignis)
        if erwartet != gespeichert:
            return False, index
        aktuell = gespeichert
    return True, None


@dataclass(frozen=True)
class Befund:
    """Ergebnis von `kette_nachrechnen` — was geprüft wurde und, falls etwas nicht stimmt, wo."""

    intakt: bool
    geprueft: int  # Zahl der nachgerechneten Einträge
    kopf: str  # Hash des letzten geprüften Eintrags (bei einem Bruch: des letzten stimmigen)
    letzte_nummer: int | None  # laufende Nummer des letzten stimmigen Eintrags
    bruch: int | None = None  # laufende Nummer des ersten Eintrags, der nicht stimmt
    grund: str | None = None  # „vorgaenger“: hängt nicht am Vorgänger · „hash“: Inhalt passt nicht zum Hash


def kette_nachrechnen(
    eintraege: Iterable[tuple[int, dict[str, Any], str, str]],
    start_hash: str = GENESIS,
    start_nummer: int | None = None,
) -> Befund:
    """Rechnet eine Kette aus (laufende Nummer, ereignis, gespeicherter Vorgänger, gespeicherter Hash) nach.

    Anders als `kette_pruefen` prüft sie auch die gespeicherte Spalte `vorgaenger` und nennt die laufende
    Nummer der Bruchstelle, nicht nur ihre Position — so lässt sich die Prüfung stückweise fortsetzen: Wer
    den Kopf und die Nummer eines geprüften Stands kennt, rechnet mit `start_hash` ab dort weiter. Zwei
    Gründe gibt es: Ein Eintrag hängt nicht am Hash seines Vorgängers („vorgaenger“ — ein Eintrag wurde
    entfernt, eingeschoben oder umgehängt), oder sein Inhalt ergibt nicht seinen Hash („hash“ — er wurde
    verändert)."""
    kopf, letzte, geprueft = start_hash, start_nummer, 0
    for nummer, ereignis, vorgaenger, gespeichert in eintraege:
        if vorgaenger != kopf:
            return Befund(False, geprueft, kopf, letzte, nummer, "vorgaenger")
        if ereignis_hash(vorgaenger, ereignis) != gespeichert:
            return Befund(False, geprueft, kopf, letzte, nummer, "hash")
        kopf, letzte, geprueft = gespeichert, nummer, geprueft + 1
    return Befund(True, geprueft, kopf, letzte)


def bruchstellen(
    eintraege: Iterable[tuple[int, dict[str, Any], str, str]],
    start_hash: str = GENESIS,
    hoechstens: int = 20,
) -> list[tuple[int, str]]:
    """Alle Bruchstellen einer Kette, nicht nur die erste: (laufende Nummer, Grund) je Eintrag, der nicht
    stimmt — höchstens `hoechstens`. Nach einem Bruch rechnet sie mit dem gespeicherten Hash weiter, so
    bleiben die Einträge dahinter geprüft, statt nach dem ersten Fehler für immer ungeprüft zu sein."""
    gefunden: list[tuple[int, str]] = []
    kopf = start_hash
    for nummer, ereignis, vorgaenger, gespeichert in eintraege:
        if vorgaenger != kopf:
            gefunden.append((nummer, "vorgaenger"))
        elif ereignis_hash(vorgaenger, ereignis) != gespeichert:
            gefunden.append((nummer, "hash"))
        if len(gefunden) >= hoechstens:
            break
        kopf = gespeichert
    return gefunden
