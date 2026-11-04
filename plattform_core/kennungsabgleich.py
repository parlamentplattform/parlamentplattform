"""Exakte Dokumentkennung mit damaligen Quellen vergleichen, kein Rechtsurteil."""

import copy
from collections import defaultdict
from datetime import date

from plattform_core.quellenumfang import dokumentart

VERSION = 2


def abgleichen(normen, quellen):
    """Ein Eintrag je Modellnorm, gleiche Reihenfolge. Keine Titelsuche oder URL-Auflösung.

    Quellenrahmen und Antwortform müssen vom Aufrufer vorab geprüft werden.
    Auch eine passende Kennung bestätigt weder den Modelltitel noch Betroffenheit,
    Geltung oder Änderungsbedarf. Mehrdeutige damalige Stände bleiben unzugeordnet.
    """
    if not isinstance(normen, list) or len(normen) > 8 or not isinstance(quellen, list) or len(quellen) > 20:
        raise ValueError("Abgleichsgrenze")
    index = defaultdict(list)
    for q in quellen:
        if (not isinstance(q, dict) or not isinstance(q.get("ris_id"), str)
                or type(q.get("norm_id")) is not int or q["norm_id"] < 1
                or not isinstance(q.get("kurztitel"), str) or not 0 < len(q["kurztitel"]) <= 1000
                or not isinstance(q.get("abschnitt"), str) or len(q["abschnitt"]) > 100
                or not isinstance(q.get("stand"), str) or date.fromisoformat(q["stand"]).isoformat() != q["stand"]):
            raise ValueError("Quellenform")
        if ("ebene" in q) != ("bundesland" in q):
            raise ValueError("Unvollständige Quellenherkunft")
        ebene, land = q.get("ebene", "Bund"), q.get("bundesland", "")
        dokumentart(ebene, land, q["ris_id"])
        quelle = {k: q[k] for k in ("norm_id", "ris_id", "kurztitel", "abschnitt", "stand")}
        if "ebene" in q:
            quelle.update(ebene=ebene, bundesland=land)
        index[(ebene, q["ris_id"])].append(quelle)
    ergebnis = []
    for position, n in enumerate(normen):
        if not isinstance(n, dict):
            raise ValueError("Modellnormform")
        kennung = n.get("kennung")
        treffer = []
        if (n.get("ebene") in ("Bund", "Land") and n.get("aenderung") in ("aendern", "aufheben", "beruehrt", "unklar")
                and isinstance(kennung, str)):
            treffer = index[(n["ebene"], kennung)]
        ergebnis.append({"position": position, "kennung": kennung, "rechtlich_verifiziert": False,
            "zustand": "gleich" if len(treffer) == 1 else "mehrdeutig" if treffer else "keine",
            "quelle": copy.deepcopy(treffer[0]) if len(treffer) == 1 else None})
    return ergebnis
