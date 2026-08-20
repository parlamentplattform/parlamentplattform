"""Menschliche, übersetzbare Namen für die technischen Phasenwerte (F-33).

Die Datenbank führt Phasen als stabile Slugs (`unterstuetzung`, `abstimmung` …);
angezeigt wird immer die übersetzte Form.
"""

from django import template
from django.utils.translation import gettext_lazy as _

register = template.Library()

NAMEN = {
    "unterstuetzung": _("Unterstützung"),
    "beratung": _("Beratung"),
    "abstimmung": _("Abstimmung"),
    "angenommen": _("angenommen"),
    "abgelehnt": _("abgelehnt"),
    "verfallen": _("verfallen"),
    "zurueckgewiesen": _("zurückgewiesen"),
    # Stimmwerte (für „Ihre aktuelle Stimme“)
    "ja": _("Ja"),
    "nein": _("Nein"),
    "enthaltung": _("Enthaltung"),
    # Vollzugsstatus des Umsetzungsregisters (F-55)
    "offen": _("offen"),
    "in_umsetzung": _("in Umsetzung"),
    "blockiert": _("blockiert"),
    "umgesetzt": _("umgesetzt"),
    "zurueckgestellt": _("zurückgestellt"),
}


@register.filter
def phase_name(wert: str) -> str:
    return str(NAMEN.get(wert, wert))


# Ampelfarben des Umsetzungsregisters (F-55) — identisch mit den Meldungsfarben der Plattform.
FARBEN = {
    "umgesetzt": "background:#EFF6F1;color:#1E4736",
    "in_umsetzung": "background:#EDF3F5;color:#0E4C5C",
    "blockiert": "background:#F9EFEE;color:#6E2222",
    "zurueckgestellt": "background:#FBF6EA;color:#7A5A16",
    "offen": "background:#F6F3EC;color:#4a5b66",
}


@register.filter
def vollzug_stil(wert: str) -> str:
    return FARBEN.get(wert, "")
