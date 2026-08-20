"""Zähl-Middleware für die Übersichtsseite (F-50/F-52).

Gezählt werden nur erfolgreiche HTML-Seitenabrufe echter Browser. Werkzeuge,
Suchmaschinen und Monitoring (erkennbar an der Browserkennung) bleiben außen
vor, ebenso statische Dateien, der Gesundheitscheck und die Verwaltung.
Ein Fehler beim Zählen darf nie eine Seite kaputt machen — deshalb ist alles
in ein stilles Sicherheitsnetz gewickelt.
"""

from __future__ import annotations

import logging
import re

from uebersicht.models import aufruf_zaehlen

log = logging.getLogger(__name__)

MASCHINEN = re.compile(
    r"bot|crawl|spider|slurp|monitor|preview|scan|probe|fetch|curl|wget|python-requests|go-http-client|headless",
    re.IGNORECASE,
)
NICHT_ZAEHLEN = ("/static/", "/gesund/", "/verwaltung/", "/favicon")


class Besuchszaehlung:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._zaehlen(request, response)
        except Exception:  # pragma: no cover — Zählen ist Beiwerk, nie Blocker
            log.exception("Besuchszählung übersprungen.")
        return response

    def _zaehlen(self, request, response) -> None:
        if request.method != "GET" or response.status_code != 200:
            return
        if not response.get("Content-Type", "").startswith("text/html"):
            return
        if request.path.startswith(NICHT_ZAEHLEN):
            return
        browser = request.META.get("HTTP_USER_AGENT", "")
        if not browser or MASCHINEN.search(browser):
            return
        antrag_id = None
        treffer = getattr(request, "resolver_match", None)
        if treffer and treffer.view_name == "verfahren:antrag":
            antrag_id = int(treffer.kwargs["pk"])
        # IP nur flüchtig für die Tageskennung — gespeichert wird sie nie.
        from mitglieder.botschutz import klienten_ip

        aufruf_zaehlen(klienten_ip(request), browser, antrag_id)
