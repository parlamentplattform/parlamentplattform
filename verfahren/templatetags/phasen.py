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


# Ampelfarben des Umsetzungsregisters (F-55) als Token-Klassen aus base.html —
# dieselben Farben wie die Meldungen, in hell und dunkel (FB-P3).
KLASSEN = {
    "umgesetzt": "badge-ok",
    "in_umsetzung": "badge-info",
    "blockiert": "badge-warn",
    "zurueckgestellt": "badge-hinweis",
    "offen": "badge-still",
}


@register.filter
def vollzug_klasse(wert: str) -> str:
    return KLASSEN.get(wert, "badge-still")
