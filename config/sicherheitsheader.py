"""Browserquellen für HTML begrenzen, ohne zusätzliche Berichte zu sammeln.

Die eingecheckte Alpine-Fassung benötigt Stringauswertung, bestehende Ansichten
verwenden Inline-Styles. Die Ausnahmen sind bewusst benannt (ADR-015); dies ist
kein Ersatz für Escaping und sichere Inhaltstypen und keine vollständig strikte CSP.
"""

RICHTLINIE = "; ".join((
    "default-src 'none'",
    "script-src 'self' 'unsafe-eval'",
    "script-src-attr 'none'",
    "style-src 'self' 'unsafe-inline'",
    "img-src 'self' data:",
    "font-src 'self'",
    "connect-src 'self'",
    "manifest-src 'self'",
    "base-uri 'none'",
    "form-action 'self'",
    "frame-ancestors 'none'",
    "object-src 'none'",
    "frame-src 'none'",
    "worker-src 'none'",
    "media-src 'none'",
))


class BrowserQuellenBegrenzen:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        antwort = self.get_response(request)
        typ = antwort.get("Content-Type", "").split(";", 1)[0].strip().lower()
        if typ in {"text/html", "application/xhtml+xml"}:
            antwort.setdefault("Content-Security-Policy", RICHTLINIE)
        return antwort


class PersoenlichesNichtSpeichern:
    """Antworten an ein angemeldetes Konto landen in keinem Zwischenspeicher (GP-154): Profil, Postfach
    und Verwaltungslisten tragen Personenbezug, ein geteilter Rechner oder Proxy hielte sie sonst fest.
    Legt die Ansicht selbst `Cache-Control` fest, bleibt es dabei; Gastantworten bleiben unverändert."""

    WERT = "no-store, private"

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        antwort = self.get_response(request)
        nutzer = getattr(request, "user", None)
        if nutzer is not None and nutzer.is_authenticated and not antwort.has_header("Cache-Control"):
            antwort["Cache-Control"] = self.WERT
        return antwort
