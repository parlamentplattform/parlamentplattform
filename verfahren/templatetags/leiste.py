"""Template-Tags der App-Leiste (FB-A1, FB-N8): aktiver Hauptpunkt, Initiale für den Konto-Avatar."""

from django import template

register = template.Library()

# Welche Seite welchen Hauptpunkt markiert — nach Präfix statt exaktem Pfad, damit auch
# Antragsseiten, Mandatar-Details oder Gremien-Bereiche ihren Bereich zeigen.
BEREICHE = {
    ("verfahren", "parlament"): "parlament",
    ("verfahren", "antrag"): "parlament",
    ("verfahren", "eigene_stimme"): "parlament",
    ("verfahren", "einbringen"): "parlament",
    ("verfahren", "kategorien"): "parlament",
    ("verfahren", "kategorie"): "parlament",
    ("verfahren", "umsetzung"): "umsetzung",
    ("verfahren", "umsetzung_json"): "umsetzung",
    ("verfahren", "zukunftswerkstatt"): "zukunftswerkstatt",
}
APPS = {"mandatare": "mandatare", "uebersicht": "uebersicht", "gremien": "gremien"}
VERWALTUNG = {("gremien", "rollen"), ("gremien", "rollen_aktion"), ("mandatare", "verwaltung"), ("mandatare", "verwaltung_aktion")}


@register.simple_tag(takes_context=True)
def nav_aktiv(context) -> str:
    request = context.get("request")
    treffer = getattr(request, "resolver_match", None)
    if treffer is None:
        return ""
    schluessel = (treffer.app_name, treffer.url_name)
    if schluessel in VERWALTUNG:
        return ""
    return BEREICHE.get(schluessel) or APPS.get(treffer.app_name, "")


@register.filter
def initiale(name) -> str:
    """Erster Buchstabe des Anzeigenamens für den Avatar-Kreis (Spec 3.1)."""
    return (str(name or "").strip()[:1] or "?").upper()
