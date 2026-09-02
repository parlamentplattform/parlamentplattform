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


RING_UMFANG = 50.3  # 2·π·8 — der Kreis mit r = 8 im 20-px-Fristring (FB-D2)


@register.filter
def rest_ring(prozent) -> str:
    """stroke-dashoffset für den Fristring: 0 % verstrichen = voller Versatz, 100 % = 0."""
    try:
        anteil = min(100, max(0, float(prozent))) / 100
    except (TypeError, ValueError):
        anteil = 0
    return f"{RING_UMFANG * (1 - anteil):.1f}"
