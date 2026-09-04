"""Was jede Seite braucht (FB-G3): der Zähler am Gesprächs-Griff.

Der Griff liegt auf jeder Seite der Plattform (D-G3) und trägt die Zahl der Gespräche mit
ungelesener Antwort. Für Gäste ist er nicht da, dann kostet der Prozessor auch nichts.
"""

from __future__ import annotations


def gespraeche(request) -> dict:
    nutzer = getattr(request, "user", None)
    if nutzer is None or not nutzer.is_authenticated:
        return {"gespraeche_ungelesen": 0}
    from verfahren.chat import ungelesene_gespraeche

    return {"gespraeche_ungelesen": ungelesene_gespraeche(nutzer)}
