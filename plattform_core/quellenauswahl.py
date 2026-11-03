"""Offene Wortanfangsauswahl von Kontextkandidaten, keine juristische Prüfung.

Es zählt kein Relevanzwert. Der übergebene, nach amtlicher Kennung geordnete
Bestand wird vollständig bis zu seiner offengelegten Grenze geprüft. Eine
Übereinstimmung eines Wortanfangs reicht; gleich lange Treffer sind gleichwertig.
"""

import hashlib
import re
import unicodedata

VERSION = 1
TECHNISCHE_TEXTGRENZE = 100_000
TECHNISCHE_BESTANDSGRENZE = 2000
METADATENZEICHEN = 2000
# Mit der Regel versioniert; keine Themen, Parteien oder Rechtsgebiete bevorzugen.
STOPPWOERTER = frozenset("""
aber alle allen aller alles also auch auf aus bei bis das dass dem den der des
die dies diese diesem diesen dieser dieses doch durch ein eine einem einen einer
eines einerseits erst etwas fuer für gegen haben hier hinter ihre ihren ihrer
ist kann kein keine mit nach nicht noch nur oder ohne sein seine sich sie sind
soll sollen sowie ueber über und unter vom von vor war was weder weil welche
welchem welchen welcher welches wenn werden wie wird wir zum zur zwischen
antrag antrags begruendung begründung wortlaut vorschlag gesetz gesetze
gesetzes gesetzlich gesetzliche gesetzlicher bundesgesetz bundesgesetze
""".split())
_WORT = re.compile(r"[^\W_]+", re.UNICODE)


def woerter(text, mindestlaenge):
    if type(mindestlaenge) is not int or not 2 <= mindestlaenge <= 12:
        raise ValueError("Wortlängengrenze")
    if not isinstance(text, str) or len(text) > TECHNISCHE_TEXTGRENZE:
        raise ValueError("Auswahltextgrenze")
    return sorted({w for w in _WORT.findall(unicodedata.normalize("NFKC", text).casefold())
                   if mindestlaenge <= len(w) <= 80 and w not in STOPPWOERTER and not w.isdecimal()})


def _baum(woerter):
    wurzel = {}
    for wort in woerter:
        ast = wurzel
        for zeichen in wort:
            ast = ast.setdefault(zeichen, {})
        ast[""] = True
    return wurzel


def _passt(wort, baum):
    ast = baum
    for zeichen in wort:
        if "" in ast:
            return True
        ast = ast.get(zeichen)
        if ast is None:
            return False
    return bool(ast)  # der Quellenwortlaut ist selbst Anfang eines Suchworts


def auswaehlen(text, bestand, *, hoechstzahl, mindestlaenge):
    """Bestand aus (Norm-ID, RIS-ID, Metadatentext); Ergebnis enthält alle Treffer-IDs.

    Zeichenweise Unicode-Normalisierung, Wörter aus Buchstaben/Ziffern,
    Stoppwörter und Mindestlänge, beidseitiger Wortanfang. Kein Volltextindex,
    kein semantisches Modell. Ausschließlich diese vorliegende Teilmenge.
    """
    if type(hoechstzahl) is not int or not 0 <= hoechstzahl <= 20:
        raise ValueError("Quellenhöchstzahl")
    if not isinstance(bestand, (list, tuple)) or len(bestand) > TECHNISCHE_BESTANDSGRENZE:
        raise ValueError("Bestandsgrenze")
    suchwoerter = woerter(text, mindestlaenge)
    baum = _baum(suchwoerter)
    geordnet = sorted(bestand, key=lambda q: (q[1], q[0]))
    if len({q[0] for q in geordnet}) != len(geordnet):
        raise ValueError("Doppelte Quelle")
    treffer = [pk for pk, _kennung, meta in geordnet
               if any(_passt(w, baum) for w in woerter(meta, mindestlaenge))]
    return {
        "regel_fassung": VERSION, "mindestwortlaenge": mindestlaenge,
        "unicode_fassung": unicodedata.unidata_version,
        "suchwoerter_anzahl": len(suchwoerter),
        "suchwoerter_sha256": hashlib.sha256("\n".join(suchwoerter).encode()).hexdigest(),
        "treffer_ids": treffer, "ausgewaehlt": treffer[:hoechstzahl],
        "treffer_begrenzt": len(treffer) > hoechstzahl,
    }
