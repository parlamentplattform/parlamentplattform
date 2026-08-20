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
}


@register.filter
def phase_name(wert: str) -> str:
    return str(NAMEN.get(wert, wert))
