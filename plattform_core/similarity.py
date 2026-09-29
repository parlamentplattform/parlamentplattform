"""Ähnlichkeit zwischen Anträgen — Stufe 1b (Wörter) und die Rechenhilfen für Stufe 2 (Bedeutung).

Fassung 1 verglich Dreizeichenfolgen (Trigramme) mit dem Jaccard-Koeffizienten. Das zählte die
Floskeln mit, die fast jeder Antrag trägt — „Die Bundesregierung wird aufgefordert, dem
Nationalrat einen Gesetzesentwurf vorzulegen …“ —, und zwei Anträge ohne jede inhaltliche
Nähe erreichten 29 Prozent (Anweisung des Gründers 28.9.2026: „Diese Funktion muss besser
werden“).

Fassung 2 rechnet auf Wort-Ebene und bleibt trotzdem mit Papier und Bleistift nachrechenbar:

1. Normalisieren (Kleinschreibung, Satzzeichen weg), in Wörter zerlegen.
2. Stoppwörter streichen (Funktionswörter und Antragsfloskeln, Liste unten) und Wörter unter
   drei Zeichen.
3. Stammform: ab fünf Zeichen eine Endung -en/-er/-es/-e/-n/-s kappen („Protokolle“ →
   „protokoll“, „veröffentlichen“ → „veröffentlich“).
4. Gewichten: Jedes Wort aus dem Titel zählt doppelt.
5. Wortanteil = gewichteter Jaccard über die Wortmengen (Summe der kleineren Gewichte geteilt
   durch die Summe der größeren); Paaranteil = Jaccard über die Paare aufeinanderfolgender
   Wörter (die Reihenfolge). Ähnlichkeit = ⅔ Wortanteil + ⅓ Paaranteil.

Stufe 2 (Bedeutung) rechnet der Anbieter des Modell-Steckplatzes in Vektoren; hier steht nur
der Kosinus, mit dem zwei Vektoren verglichen werden, und die Vereinigung beider Stufen. Kein
Wert hier entscheidet: Der Hinweis schlägt vor, einbringen kann man immer (§ 2 Abs 6).
"""

from __future__ import annotations

import math
import re
import unicodedata
from collections.abc import Sequence

#: Fassung der Ähnlichkeitsregel (§ 2 Abs 6). Sie schlägt beim Einbringen bestehende Anträge
#: vor und blockiert nie; die Schwellen stehen als Stellgrößen im Register
#: (aehnlichkeit-schwelle-prozent, aehnlichkeit-bedeutung-schwelle-prozent), das Verfahren hier.
VERSION = 2

#: Ein Text ist ein Wortlaut — oder ein Paar (Titel, Wortlaut), dann zählen die Titelwörter doppelt.
Text = str | tuple[str, str]

#: Gewicht eines Titelworts gegenüber einem Wort des Wortlauts.
TITELGEWICHT = 2.0
#: Anteile von Wortmenge und Wortfolge an der Ähnlichkeit.
WORTANTEIL, PAARANTEIL = 2 / 3, 1 / 3
#: Ab dieser Länge wird eine Endung gekappt; kürzere Wörter bleiben, wie sie sind.
STAMM_AB = 5
MINDESTLAENGE = 3
ENDUNGEN = ("en", "er", "es", "e", "n", "s")

#: Funktionswörter und Antragsfloskeln, die nichts über den Gegenstand eines Antrags sagen.
STOPPWOERTER = frozenset(
    """
    der die das den dem des ein eine einer eines einem einen und oder aber als auf aus bei bis
    durch für gegen in im ins mit nach ohne über um unter von vom vor zu zum zur zwischen an am ab
    seit während wegen trotz laut gemäß bezüglich hinsichtlich seitens mittels anhand
    ist sind war waren hat haben hatte hatten hätte hätten wäre wären werden wird wurde wurden
    werde würde würden worden sein seine seiner seinen seinem seines kann können könnte könnten
    soll sollen sollte sollten muss müssen müsste müssten darf dürfen möge mögen
    dass damit wenn weil ob wie wo was wer welche welcher welches welchem welchen
    nicht kein keine keiner keinen keinem keines sondern sowohl entweder weder noch
    sich ihre ihrer ihren ihrem ihres ihr ihm ihn es er sie wir uns unser unsere unserer unseren
    unserem man dies diese dieser dieses diesem diesen jene jener jenes alle allen aller alles
    jede jeder jedes jedem jeden auch bereits immer nur sehr mehr weniger hier dort dann denn
    doch etwa fast ganz gar je nun oft schon so viel viele vielen vieler wieder zwar zudem dabei
    dafür dazu hierzu daher deshalb somit jedoch allerdings sowie beziehungsweise bzw usw etc
    binnen innerhalb außerhalb spätestens mindestens höchstens sofort künftig zukünftig derzeit
    bisher bislang
    gegebenenfalls insbesondere jeweils jeweilige jeweiligen entsprechend entsprechende
    entsprechenden folgende folgenden folgendes bereich bereiche rahmen ziel ziele
    bundesregierung regierung bundesminister bundesministerin bundesministerium ministerium
    nationalrat bundesrat landtag gemeinderat parlament aufgefordert auffordern ersucht
    gesetzesentwurf gesetzentwurf gesetz gesetze gesetzes gesetzlich gesetzliche gesetzlichen
    regelung regelungen vorzulegen vorlegen vorgelegt umgehend rasch ehestmöglich möglichst
    umsetzen umzusetzen umsetzung einführen einzuführen einführung schaffen geschaffen prüfen
    geprüft prüfung sicherstellen sicherzustellen gewährleisten erforderlich erforderlichen
    notwendig notwendigen maßnahme maßnahmen antrag anträge antrages antragsteller beantragt
    beschließen beschluss beschlossen mitglieder mitgliederversammlung plattform partei ddö
    österreich österreichs österreichisch österreichische österreichischen bund bundes land
    landes länder ebene
    """.split()
)


def normalisieren(text: str) -> str:
    """Kleinschreibung, Unicode-Normalform, alles außer Buchstaben/Ziffern wird Leerraum."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = re.sub(r"[^\w\s]", " ", text, flags=re.UNICODE)
    return re.sub(r"\s+", " ", text).strip()


def stammform(wort: str) -> str:
    """Eine Endung kappen — nur ab STAMM_AB Zeichen und nur, wenn genug Stamm übrig bleibt."""
    if len(wort) < STAMM_AB:
        return wort
    for endung in ENDUNGEN:
        if wort.endswith(endung) and len(wort) - len(endung) >= MINDESTLAENGE:
            return wort[: -len(endung)]
    return wort


def woerter(text: str) -> list[str]:
    """Die tragenden Wörter eines Texts in ihrer Reihenfolge: ohne Stoppwörter, ohne Kurzwörter,
    in Stammform."""
    return [
        stammform(w)
        for w in normalisieren(text).split(" ")
        if len(w) >= MINDESTLAENGE and w not in STOPPWOERTER
    ]


def _teile(text: Text) -> tuple[str, str]:
    if isinstance(text, tuple):
        return text
    return "", text


def merkmale(text: Text) -> tuple[dict[str, float], set[str]]:
    """Gewichtete Wortmenge und Menge der Wortpaare eines Texts (oder eines Paars Titel, Wortlaut)."""
    titel, wortlaut = _teile(text)
    gewichte: dict[str, float] = {}
    paare: set[str] = set()
    for teil, gewicht in ((titel, TITELGEWICHT), (wortlaut, 1.0)):
        liste = woerter(teil)
        for w in liste:
            gewichte[w] = gewichte.get(w, 0.0) + gewicht
        paare.update(f"{a} {b}" for a, b in zip(liste, liste[1:], strict=False))
    return gewichte, paare


def _gewichteter_jaccard(a: dict[str, float], b: dict[str, float]) -> float:
    if not a or not b:
        return 0.0
    schluessel = set(a) | set(b)
    zaehler = sum(min(a.get(k, 0.0), b.get(k, 0.0)) for k in schluessel)
    nenner = sum(max(a.get(k, 0.0), b.get(k, 0.0)) for k in schluessel)
    return zaehler / nenner if nenner else 0.0


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _wert(ga: dict[str, float], pa: set[str], gb: dict[str, float], pb: set[str]) -> float:
    """⅔ Wortanteil + ⅓ Paaranteil. Hat keiner der beiden Texte ein Wortpaar (je ein tragendes Wort),
    gibt es keine Reihenfolge zu vergleichen — dann zählt allein der Wortanteil."""
    if not ga or not gb:
        return 0.0
    wortanteil = _gewichteter_jaccard(ga, gb)
    if not pa and not pb:
        return wortanteil
    return WORTANTEIL * wortanteil + PAARANTEIL * _jaccard(pa, pb)


def aehnlichkeit(a: Text, b: Text) -> float:
    """Ähnlichkeit zweier Texte, 0.0 bis 1.0: ⅔ Wortanteil (gewichteter Jaccard) plus ⅓ Paaranteil
    (Jaccard der Wortpaare). Symmetrisch, deterministisch, ohne Modell."""
    ga, pa = merkmale(a)
    gb, pb = merkmale(b)
    return _wert(ga, pa, gb, pb)


def aehnlichste(
    neuer_text: Text,
    kandidaten: list[tuple[int, Text]],
    schwelle: float = 0.30,
    limit: int = 3,
) -> list[tuple[int, float]]:
    """Die `limit` ähnlichsten Kandidaten oberhalb der Schwelle, absteigend
    nach Score; bei Gleichstand entscheidet die kleinere ID (Determinismus).

    `kandidaten` ist eine Liste (id, text). `schwelle` und `limit` sind die
    Stellgrößen „aehnlichkeit-schwelle-prozent“ (÷ 100) und „aehnlichkeit-treffer“
    des Parameterregisters — der Aufrufer reicht sie durch, denn dieses Paket
    bleibt Django-frei. Die Vorgaben hier sind nur die eingebauten Zielwerte,
    auf die das Register zurückfällt, wenn ein Eintrag fehlt.
    """
    gneu, pneu = merkmale(neuer_text)
    if not gneu:
        return []
    treffer: list[tuple[int, float]] = []
    for kid, text in kandidaten:
        g, p = merkmale(text)
        if not g:
            continue
        score = _wert(gneu, pneu, g, p)
        if score >= schwelle:
            treffer.append((kid, score))
    treffer.sort(key=lambda x: (-x[1], x[0]))
    return treffer[:limit]


# ── Stufe 2: Bedeutung (Vektoren vom Modell-Steckplatz) ───────────────────────────────────────


def kosinus(a: Sequence[float], b: Sequence[float]) -> float:
    """Kosinus-Ähnlichkeit zweier Vektoren, auf 0.0 bis 1.0 geklemmt. Ungleich lange oder leere
    Vektoren (anderes Modell, kaputter Datensatz) ergeben ehrlich 0.0 statt einer Ausnahme."""
    if not a or not b or len(a) != len(b):
        return 0.0
    skalar = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    if norm == 0.0:
        return 0.0
    return min(1.0, max(0.0, skalar / norm))


def vereinigen(
    wortwerte: dict[int, float],
    bedeutungswerte: dict[int, float],
    wort_schwelle: float,
    bedeutung_schwelle: float,
    limit: int = 3,
) -> list[tuple[int, float, float | None]]:
    """Treffer beider Stufen zusammenführen: Ein Kandidat zählt, sobald eine Stufe ihre Schwelle
    erreicht. Jede Zeile trägt (id, Wortvergleich, Bedeutung oder None, wenn kein Vektor vorlag);
    sortiert nach dem höheren der beiden Werte, bei Gleichstand nach der kleineren ID."""
    zeilen: list[tuple[int, float, float | None]] = []
    for kid in set(wortwerte) | set(bedeutungswerte):
        wort = wortwerte.get(kid, 0.0)
        bedeutung = bedeutungswerte.get(kid)
        if wort >= wort_schwelle or (bedeutung is not None and bedeutung >= bedeutung_schwelle):
            zeilen.append((kid, wort, bedeutung))
    zeilen.sort(key=lambda z: (-max(z[1], z[2] or 0.0), z[0]))
    return zeilen[:limit]
