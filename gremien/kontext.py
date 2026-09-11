"""Das Rollenband (FB-I1): Wer eine Rolle **hatte**, liest den Bereich weiter — mit Band.

`nur_gremium` setzt `request.abgelaufene_rolle`, wenn der Zugang nur aus einer abgelaufenen oder
beendeten Rolle folgt; die Vorlage `gremien/_rollenband.html` zeigt es an. Schreiben prüft jede
Handlung selbst; das Band öffnet nichts.
"""

from __future__ import annotations


def rollenband(request) -> dict:
    return {"abgelaufene_rolle": getattr(request, "abgelaufene_rolle", None)}
