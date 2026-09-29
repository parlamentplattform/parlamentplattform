"""htmx-Anfragen ohne Sitzung wechseln die ganze Seite zur Anmeldung (Befund B1).

Läuft eine Direkt-Handlung aus Kachel, Feed-Zeile oder Stern ohne gültige Sitzung (abgelaufen,
abgemeldet, Konto stillgelegt), antwortet `login_required` mit einem 302 auf die Anmeldung. htmx
folgt ihm unsichtbar, findet in der Anmeldeseite das Feld nicht und tauscht es gegen nichts — das
Feld verschwände. Bei einer htmx-Anfrage wird dieser Redirect darum zu einer leeren Antwort mit
dem Kopf `HX-Redirect`: htmx wechselt die ganze Seite. `next` zeigt auf den sicheren `weiter`-Pfad
der Handlung (sonst das Parlament), nie auf die POST-Adresse selbst. Ohne htmx bleibt der 302.
"""

from __future__ import annotations

from urllib.parse import urlencode, urlsplit

from django.conf import settings
from django.http import HttpResponse
from django.shortcuts import resolve_url
from django.urls import reverse

from verfahren.hinweise import sicherer_pfad


class AnmeldungFuerHtmx:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        antwort = self.get_response(request)
        if antwort.status_code != 302 or request.headers.get("HX-Request") != "true":
            return antwort
        anmeldung = resolve_url(settings.LOGIN_URL)
        if urlsplit(antwort.get("Location", "")).path != anmeldung:
            return antwort
        weiter = request.POST.get("weiter", "") if request.method == "POST" else ""
        if not sicherer_pfad(weiter):
            weiter = reverse("verfahren:parlament")
        return HttpResponse(headers={"HX-Redirect": f"{anmeldung}?{urlencode({'next': weiter})}"})
