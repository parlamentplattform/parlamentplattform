"""Gemeindelogin ist auf Parteiseiten ausschließlich der öffentliche Gastzugang.

Die Grenze gilt auch für neue, künftig ergänzte Parteiseiten. Auf Gemeinde- und
Anmeldewegen bleibt dieselbe authentifizierte Identität verfügbar (ADR-016).
"""

from urllib.parse import urlsplit

from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.shortcuts import render, resolve_url
from django.utils.deprecation import MiddlewareMixin


class GemeindezugangBegrenzen(MiddlewareMixin):
    def process_view(self, request, view_func, view_args, view_kwargs):
        user = request.user
        request.gemeindekonto = user if user.is_authenticated and not user.parteikonto else None
        if request.gemeindekonto is None:
            return None
        name = request.resolver_match.view_name or ""
        if name.startswith("gemeinde:") or name in {
            "mitglieder:login", "mitglieder:login_einloesen", "mitglieder:abmelden", "set_language",
        }:
            return None
        # Alle vorhandenen Fachbereiche prüfen wie bisher ihre Gast-/Parteirechte.
        # Keine globale Kontoanmeldung allein darf ein Parteischreibrecht erzeugen.
        request.user = AnonymousUser()
        request._cached_user = request.user
        request._acached_user = request.user
        if name == "anstoss:senden":
            return None  # dieselbe öffentliche Rückmeldung wie ohne Konto
        if request.method not in {"GET", "HEAD", "OPTIONS"}:
            # GP-095: eine ganze Seite mit Grund und Weg zurück zum Gemeindekonto statt eines nackten Satzes
            return render(request, "mitglieder/gemeinde_gesperrt.html", status=403)
        return None

    def process_response(self, request, response):
        # GP-078: Eine geschützte Parteiseite schickte das angemeldete Gemeindekonto zur Anmeldung —
        # ein Kreis ohne Ausgang. Statt der Umleitung kommt dieselbe Auskunft wie bei Schreibwegen.
        if (
            getattr(request, "gemeindekonto", None) is not None
            and response.status_code == 302
            and urlsplit(response.get("Location", "")).path == resolve_url(settings.LOGIN_URL)
        ):
            return render(request, "mitglieder/gemeinde_gesperrt.html", status=403)
        return response
