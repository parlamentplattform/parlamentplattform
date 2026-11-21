"""Ziel der Anmeldung (GP-100): Wer eine geschützte Seite öffnet, landet nach dem Anmeldelink dort.

Das Ziel kommt als `?next=` (so erzeugt es `login_required`) auf die Anmeldeseite, steht dort als
verborgenes Feld `ziel` im Formular und wird am Anmeldelink gemerkt (`EinmalToken.ziel`) — der Link
wird oft auf einem anderen Gerät geöffnet als dem, das ihn angefordert hat, eine Sitzung trüge ihn
nicht. Bei jedem Schritt wird es neu geprüft: nur ein Pfad dieser Seite, der auflösbar ist und GET
annimmt. Fremde Hosts, schreibende Adressen (`require_POST`) und die Anmeldewege selbst fallen weg.
"""

from __future__ import annotations

import inspect
from urllib.parse import urlencode, urlsplit

from django.http import HttpResponseRedirect
from django.urls import Resolver404, resolve, reverse

from verfahren.hinweise import sicherer_pfad

ZIEL_LAENGE = 500  # Spaltenbreite von EinmalToken.ziel

# Ziele, zu denen eine Anmeldung nie zurückführt: die Anmeldewege selbst.
OHNE_RUECKKEHR = {
    "mitglieder:login", "mitglieder:login_einloesen", "mitglieder:abmelden",
    "mitglieder:bestaetigen", "mitglieder:registrieren", "gemeinde:anmelden",
}


def _nimmt_get_an(ansicht) -> bool:
    """Nimmt die Ansicht GET an? Liest `require_http_methods`/`require_POST` entlang der Hülle
    (`__wrapped__`) und `http_method_names` klassenbasierter Ansichten."""
    klasse = getattr(ansicht, "view_class", None)
    if klasse is not None and "get" not in getattr(klasse, "http_method_names", ["get"]):
        return False
    schicht, gesehen = ansicht, 0
    while schicht is not None and gesehen < 20:
        try:
            erlaubt = inspect.getclosurevars(schicht).nonlocals.get("request_method_list")
        except (TypeError, ValueError):
            erlaubt = None
        if erlaubt is not None and "GET" not in erlaubt:
            return False
        schicht, gesehen = getattr(schicht, "__wrapped__", None), gesehen + 1
    return True


def ziel_pruefen(ziel: str | None) -> str:
    """Das Ziel, wenn es eine eigene, lesende Adresse ist — sonst ein leerer Text."""
    if not ziel or len(ziel) > ZIEL_LAENGE or not sicherer_pfad(ziel):
        return ""
    try:
        treffer = resolve(urlsplit(ziel).path)
    except Resolver404:
        return ""
    if treffer.view_name in OHNE_RUECKKEHR or not _nimmt_get_an(treffer.func):
        return ""
    return ziel


def ist_gemeindeweg(ziel: str) -> bool:
    """Gehört das (geprüfte) Ziel zum Gemeindezugang? Nur dorthin führt ein Gemeindekonto zurück:
    Parteiseiten sähe es ohnehin nur als Gast, eine geschützte schickte es erneut zur Anmeldung."""
    try:
        return resolve(urlsplit(ziel).path).view_name.startswith("gemeinde:")
    except Resolver404:
        return False


def zur_anmeldung(request) -> HttpResponseRedirect:
    """Umleitung auf die Anmeldeseite, bei einem Lesezugriff mit der aufgerufenen Seite als Ziel."""
    anmeldung = reverse("mitglieder:login")
    if request.method in ("GET", "HEAD"):
        ziel = ziel_pruefen(request.get_full_path())
        if ziel:
            return HttpResponseRedirect(f"{anmeldung}?{urlencode({'next': ziel})}")
    return HttpResponseRedirect(anmeldung)
