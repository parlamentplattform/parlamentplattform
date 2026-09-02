"""Template-Tags des Anstoß-Widgets."""

from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django import template

register = template.Library()


@register.simple_tag(takes_context=True)
def pfad_ohne_anstoss(context) -> str:
    """Aktueller Pfad samt Abfrage, aber ohne den Parameter `anstoss`.

    Ziel der Schließ-Links ohne JavaScript: Die Seite wird ohne Meldungszustand neu
    geladen, behält aber z. B. `?fach=` oder `?suche=` im Parlament.
    """
    request = context.get("request")
    if request is None:
        return "/"
    teile = urlsplit(request.get_full_path())
    rest = [(k, v) for k, v in parse_qsl(teile.query, keep_blank_values=True) if k != "anstoss"]
    return urlunsplit(("", "", teile.path or "/", urlencode(rest), ""))
