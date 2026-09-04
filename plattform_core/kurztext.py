"""Die Kurzfassungen der Partner-Einladung lesen (FB-M9).

Die Dateien unter `docs/partner/kurz/` sind bewusst schlicht gehalten: eine Überschrift, ein
paar Absätze, ein kursiver Schlusssatz — und hinter einem waagrechten Strich das Arbeitsmaterial
(Glossar, offene Punkte für Muttersprachler), das niemand auf der Seite sehen soll.

Diese Datei liest genau diese Form. Sie ist **kein** Markdown-Übersetzer: Für die drei Formen,
die vorkommen, braucht es keine Abhängigkeit, und was hier nicht vorkommt, soll auch nicht
unbemerkt durchrutschen. Wer die Dateien um Tabellen oder Listen erweitert, muss diesen Leser
erweitern — und merkt es, weil der Text sonst unverändert als Absatz erscheint.

Der Rückgabewert ist bewusst schlicht: Überschrift, Absätze, Schlusssatz. Das Auszeichnen
übernimmt die Vorlage, damit hier nie HTML entsteht, das jemand escapen müsste.
"""

from __future__ import annotations

VERSION = 1

#: Ab hier steht Arbeitsmaterial, kein Seiteninhalt.
TRENNER = "---"


def lesen(inhalt: str) -> dict:
    """Zerlegt eine Kurzfassung in Überschrift, Absätze und Schlusssatz.

    `absaetze` enthält die gewöhnlichen Absätze, `schluss` den kursiv ausgezeichneten
    Schlusssatz (ohne die Sternchen) — er wird auf der Seite leiser gesetzt als der Rest.
    Fehlt etwas, bleibt das Feld leer; diese Datei wirft nicht, weil eine fehlende
    Übersetzung keine halbe Seite zerstören soll."""
    vorne = inhalt.split(f"\n{TRENNER}\n", 1)[0]
    ueberschrift, absaetze, schluss = "", [], ""

    for block in (b.strip() for b in vorne.split("\n\n")):
        if not block:
            continue
        if block.startswith("# ") and not ueberschrift:
            ueberschrift = block[2:].strip()
            continue
        # Zeilenumbrüche innerhalb eines Absatzes sind Satzumbrüche der Quelldatei, kein Absatz
        text = " ".join(zeile.strip() for zeile in block.splitlines())
        if text.startswith("*") and text.endswith("*") and not text.startswith("**"):
            schluss = text[1:-1].strip()
        else:
            absaetze.append(text)

    return {"ueberschrift": ueberschrift, "absaetze": absaetze, "schluss": schluss}


def ist_vollstaendig(gelesen: dict) -> bool:
    """Taugt die Fassung zum Anzeigen? Eine Überschrift und mindestens ein Absatz müssen da sein."""
    return bool(gelesen.get("ueberschrift")) and bool(gelesen.get("absaetze"))
