"""Öffentlicher lesender Nachweis, mit ausdrücklicher Bindung beim Herunterladen."""

from django.http import JsonResponse
from django.shortcuts import render
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from faktenbasis.bestandsnachweis import bestandsnachweis
from plattform_core.faktenbestand import HASH_MUSTER, BestandsFehler


def _fehler(exc):
    if str(exc) == "umfang":
        return _("Der gespeicherte Bestand überschreitet die eingestellte Nachweisgrenze. Es wird kein Teilnachweis ausgegeben.")
    if str(exc) == "grenze":
        return _("Der Bestandsnachweis ist derzeit nicht verfügbar: Die Nachweisgrenze ist deaktiviert oder ungültig eingestellt.")
    return _("Der Bestandsnachweis ist derzeit nicht verfügbar: Eine gespeicherte Zuordnung ist ungültig. Es wird kein Teilnachweis ausgegeben.")


@never_cache
@require_safe
def bestand(request):
    try:
        stand = bestandsnachweis()
    except BestandsFehler as exc:
        return render(request, "faktenbasis/bestand.html", {"fehler": _fehler(exc)}, status=503)
    return render(request, "faktenbasis/bestand.html", {"stand": stand, "zeit": parse_datetime(stand["erstellt_am"])})


@never_cache
@require_safe
def bestand_json(request):
    pin = request.GET.get("sha256")
    if pin is not None and not HASH_MUSTER.fullmatch(pin):
        return JsonResponse({"fehler": "pruefsumme", "meldung": _("Die angegebene Prüfsumme ist ungültig.")}, status=400)
    try:
        stand = bestandsnachweis()
    except BestandsFehler as exc:
        return JsonResponse({"fehler": str(exc), "meldung": _fehler(exc)}, status=503)
    if pin is not None and pin != stand["sha256"]:
        return JsonResponse({"fehler": "geaendert", "meldung": _("Der gespeicherte Bestand hat sich seit der Anzeige geändert. Bitte laden Sie die Nachweisseite neu.")}, status=409)
    antwort = JsonResponse(stand, json_dumps_params={"ensure_ascii": False, "indent": 2})
    antwort["Content-Disposition"] = f'attachment; filename="faktenbestand-{stand["sha256"]}.json"'
    antwort["X-Content-Type-Options"] = "nosniff"
    return antwort
