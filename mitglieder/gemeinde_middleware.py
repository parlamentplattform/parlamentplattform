"""Gemeindelogin ist auf Parteiseiten ausschließlich der öffentliche Gastzugang.

Die Grenze gilt auch für neue, künftig ergänzte Parteiseiten. Auf Gemeinde- und
Anmeldewegen bleibt dieselbe authentifizierte Identität verfügbar (ADR-016).
"""

from django.contrib.auth.models import AnonymousUser
from django.http import HttpResponseForbidden
from django.utils.deprecation import MiddlewareMixin
from django.utils.translation import gettext as _


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
            return HttpResponseForbidden(_("Dieser Vorgang gehört zur Parteimitgliedschaft."))
        return None
