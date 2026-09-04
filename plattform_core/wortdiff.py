"""Wort-Diff zweier Texte (FB-G6, FB-ER1): Was hat der Expertenrat am Antrag geändert?

Wer über einen Vorschlag abstimmt, muss sehen können, was daran neu ist. Der Vergleich
arbeitet auf Wörtern statt auf Zeilen — ein umformulierter Satz zeigt so die drei
geänderten Wörter und nicht den ganzen Absatz als ausgetauscht.

Rückgabe ist eine Folge von `(art, text)` mit `art` in `gleich`, `ein`, `aus`; die
Anzeige entscheidet über Farbe und Durchstreichung. Der Kern bleibt framework-frei,
damit die Darstellung geprüft werden kann, ohne HTML zu erzeugen.
"""

from __future__ import annotations

import difflib
import re

VERSION = 1

#: Wörter samt anhängender Leerzeichen — so bleibt der Textfluss beim Zusammensetzen erhalten.
_WORTE = re.compile(r"\S+\s*")


def zerlegen(text: str) -> list[str]:
    return _WORTE.findall(text or "")


def vergleichen(alt: str, neu: str) -> list[tuple[str, str]]:
    """Die Abschnitte von `alt` nach `neu` — benachbarte gleicher Art zusammengefasst."""
    a, b = zerlegen(alt), zerlegen(neu)
    # Verglichen wird ohne die anhängenden Leerzeichen — sonst gälte „Satz." als etwas anderes
    # als „Satz. ". Ausgegeben werden die ursprünglichen Stücke samt Abstand.
    a_schluessel = [w.strip() for w in a]
    b_schluessel = [w.strip() for w in b]
    teile: list[tuple[str, str]] = []

    def anfuegen(art: str, worte: list[str]) -> None:
        if not worte:
            return
        if teile and teile[-1][0] == art:
            teile[-1] = (art, teile[-1][1] + "".join(worte))
        else:
            teile.append((art, "".join(worte)))

    for art, a1, a2, b1, b2 in difflib.SequenceMatcher(None, a_schluessel, b_schluessel, autojunk=False).get_opcodes():
        if art == "equal":
            anfuegen("gleich", a[a1:a2])
        elif art == "delete":
            anfuegen("aus", a[a1:a2])
        elif art == "insert":
            anfuegen("ein", b[b1:b2])
        else:  # replace: erst weg, dann hin — so liest es sich wie eine Korrektur
            anfuegen("aus", a[a1:a2])
            anfuegen("ein", b[b1:b2])
    return teile


def zusammenfassung(teile) -> dict:
    """Wie viele Wörter kamen dazu, wie viele fielen weg — für die Zeile über dem Diff."""
    ein = sum(len(zerlegen(text)) for art, text in teile if art == "ein")
    aus = sum(len(zerlegen(text)) for art, text in teile if art == "aus")
    return {"ein": ein, "aus": aus, "unveraendert": ein == 0 and aus == 0}


def absaetze(text: str) -> list[str]:
    """Die Absätze eines Wortlauts — die Bezugsstellen der Kritik (FB-G6), ab 1 gezählt."""
    return [teil.strip() for teil in re.split(r"\n\s*\n", text or "") if teil.strip()]
