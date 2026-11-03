"""Exakte Dokumentkennung mit damaligen Quellen vergleichen, kein Rechtsurteil."""

import copy
import re
from collections import defaultdict
from datetime import date

VERSION = 1
_NOR = re.compile(r"NOR[0-9]{8}\Z", re.ASCII)


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
        if (not isinstance(q, dict) or not isinstance(q.get("ris_id"), str) or not _NOR.fullmatch(q["ris_id"])
                or type(q.get("norm_id")) is not int or q["norm_id"] < 1
                or not isinstance(q.get("kurztitel"), str) or not 0 < len(q["kurztitel"]) <= 1000
                or not isinstance(q.get("abschnitt"), str) or len(q["abschnitt"]) > 100
                or not isinstance(q.get("stand"), str) or date.fromisoformat(q["stand"]).isoformat() != q["stand"]):
            raise ValueError("Quellenform")
        index[q["ris_id"]].append({k: q[k] for k in ("norm_id", "ris_id", "kurztitel", "abschnitt", "stand")})
    ergebnis = []
    for position, n in enumerate(normen):
        if not isinstance(n, dict):
            raise ValueError("Modellnormform")
        kennung = n.get("kennung")
        treffer = []
        if (n.get("ebene") == "Bund" and n.get("aenderung") in {"aendern", "aufheben", "beruehrt", "unklar"}
                and isinstance(kennung, str) and _NOR.fullmatch(kennung)):
            treffer = index[kennung]
        ergebnis.append({"position": position, "kennung": kennung, "rechtlich_verifiziert": False,
            "zustand": "gleich" if len(treffer) == 1 else "mehrdeutig" if treffer else "keine",
            "quelle": copy.deepcopy(treffer[0]) if len(treffer) == 1 else None})
    return ergebnis
