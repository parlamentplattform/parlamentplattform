"""Anzeigehilfen für den Chat (FB-G1, G3): Initialen, relative Zeit, Bearbeitungsfenster.

Die Regeln selbst stehen im Modell; hier steht nur, wie sie im Template lesbar werden.
"""

import json
from datetime import datetime

from django import template
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import ngettext

register = template.Library()


@register.filter
def initiale(name: str) -> str:
    """Erster Buchstabe des Anzeigenamens für den Avatar-Kreis."""
    name = (name or "").strip()
    return name[0].upper() if name else "?"


@register.filter
def zeit_her(wann) -> str:
    """„vor 2 Std." statt eines Zeitstempels — die genaue Zeit steht im Titel (FB-G1).
    Ab sieben Tagen wird das Datum genannt, weil „vor 43 Tagen" niemandem hilft."""
    if not wann:
        return ""
    sekunden = int((timezone.now() - wann).total_seconds())
    if sekunden < 60:
        return _("gerade eben")
    minuten = sekunden // 60
    if minuten < 60:
        return ngettext("vor %d Minute", "vor %d Minuten", minuten) % minuten
    stunden = minuten // 60
    if stunden < 24:
        return ngettext("vor %d Stunde", "vor %d Stunden", stunden) % stunden
    tage = stunden // 24
    if tage < 7:
        return ngettext("vor %d Tag", "vor %d Tagen", tage) % tage
    return timezone.localtime(wann).strftime("%d.%m.%Y")


@register.filter
def ortszeit(iso) -> str:
    """Ein Zeitstempel aus dem Archiv (ISO, UTC) in Ortszeit: „29.09.2026 11:26"."""
    if not iso:
        return ""
    try:
        wann = datetime.fromisoformat(str(iso))
    except ValueError:
        return str(iso)[:16]
    if timezone.is_naive(wann):
        return wann.strftime("%d.%m.%Y %H:%M")
    return timezone.localtime(wann).strftime("%d.%m.%Y %H:%M")


@register.filter
def kompakt(wert) -> str:
    """Ein Wert eines Audit-Ereignisses lesbar: Text wie er ist, alles andere als kompaktes JSON."""
    if isinstance(wert, str):
        return wert
    return json.dumps(wert, ensure_ascii=False, separators=(", ", ": "))


@register.filter
def darf_bearbeiten(kommentar, mitglied) -> bool:
    """Ob das Bearbeitungsfenster (Register `chat-bearbeitungsfenster-minuten`) noch offen ist (FB-G1)."""
    return kommentar.darf_bearbeiten(mitglied)
