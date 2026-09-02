"""Anstoß-Ansichten (F-69): entgegennehmen, sichten, exportieren.

Grundsätze: ohne JavaScript voll funktionsfähig (htmx nur als Zugabe),
Honigtopf und Sendeabstand statt Captcha, keine Anmeldepflicht. Die
Verwaltungsansicht ist — wie die gesamte Verwaltung — bewusst nur deutsch."""

import csv

from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from anstoss.models import Anstoss, AnstossStatus
from mitglieder.verwaltung import nur_admins

MIN_ABSTAND_SEKUNDEN = 60
TAGESGRENZE = 20


def _mit_param(seite: str, wert: str) -> str:
    """Hängt ?anstoss=<wert> an — vorhandene Anstoß-Parameter werden ersetzt."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    teile = urlsplit(seite)
    q = [(k, v) for k, v in parse_qsl(teile.query) if k != "anstoss"]
    q.append(("anstoss", wert))
    return urlunsplit(("", "", teile.path or "/", urlencode(q), ""))


@require_POST
def senden(request):
    seite = (request.POST.get("seite") or "/")[:300]
    if not url_has_allowed_host_and_scheme(seite, allowed_hosts=None) or not seite.startswith("/"):
        seite = "/"
    text = (request.POST.get("text") or "").strip()
    honig = (request.POST.get("webseite") or "").strip()  # Honigtopf: Menschen lassen das Feld leer
    jetzt = timezone.now()
    heute = jetzt.date().isoformat()
    zuletzt = request.session.get("anstoss_zuletzt")
    anzahl = int(request.session.get("anstoss_anzahl", 0))
    if request.session.get("anstoss_tag") != heute:
        anzahl = 0

    ergebnis = "danke"
    if honig:
        pass  # Bots freundlich ins Leere laufen lassen — nichts speichern, nichts verraten
    elif not text:
        ergebnis = "leer"
    elif (zuletzt and jetzt.timestamp() - float(zuletzt) < MIN_ABSTAND_SEKUNDEN) or anzahl >= TAGESGRENZE:
        ergebnis = "warte"
    else:
        Anstoss.objects.create(
            text=text[:4000],
            seite=seite,
            nutzer=request.user if request.user.is_authenticated else None,
        )
        request.session["anstoss_zuletzt"] = jetzt.timestamp()
        request.session["anstoss_tag"] = heute
        request.session["anstoss_anzahl"] = anzahl + 1

    if request.headers.get("HX-Request"):
        # Rückmeldung als Ereignis (HX-Trigger), nicht als Inline-Script: Alpine schließt die
        # Karte und zeigt die Blase; ohne JavaScript greift die Umleitung mit ?anstoss=…
        antwort = render(request, "anstoss/_meldung.html", {"ergebnis": ergebnis})
        antwort["HX-Trigger"] = f"anstoss-{ergebnis}"
        return antwort
    return redirect(_mit_param(seite, ergebnis))


@nur_admins
def verwaltung_liste(request):
    gewaehlt = request.GET.get("status", "")
    anstoesse = Anstoss.objects.select_related("nutzer")
    if gewaehlt in AnstossStatus.values:
        anstoesse = anstoesse.filter(status=gewaehlt)
    else:
        gewaehlt = ""
    zaehlung = {wert: Anstoss.objects.filter(status=wert).count() for wert, _n in AnstossStatus.choices}
    return render(
        request,
        "anstoss/verwaltung.html",
        {
            "anstoesse": anstoesse[:300],
            "gewaehlt": gewaehlt,
            "zaehlung": zaehlung,
            "gesamt": Anstoss.objects.count(),
            "statuswahl": AnstossStatus.choices,
        },
    )


@nur_admins
@require_POST
def status_setzen(request, pk: int):
    anstoss = get_object_or_404(Anstoss, pk=pk)
    status = request.POST.get("status", "")
    if status in AnstossStatus.values:
        anstoss.status = status
        anstoss.vermerk = (request.POST.get("vermerk") or anstoss.vermerk)[:300]
        anstoss.save(update_fields=["status", "vermerk"])
    weiter = request.POST.get("weiter") or ""
    if not weiter.startswith("/") or not url_has_allowed_host_and_scheme(weiter, allowed_hosts=None):
        return redirect("anstoss:verwaltung")
    return redirect(weiter)


def _zeilen():
    for a in Anstoss.objects.select_related("nutzer"):
        yield {
            "nr": a.pk,
            "erstellt": a.erstellt.isoformat(),
            "seite": a.seite,
            "status": a.status,
            "mitglied": a.nutzer.anzeigename if a.nutzer else "",
            "vermerk": a.vermerk,
            "text": a.text,
        }


@nur_admins
def export_csv(request):
    antwort = HttpResponse(content_type="text/csv; charset=utf-8")
    antwort["Content-Disposition"] = 'attachment; filename="anstoesse.csv"'
    antwort.write("\ufeff")  # BOM, damit Excel Umlaute richtig liest
    schreiber = csv.DictWriter(
        antwort, fieldnames=["nr", "erstellt", "seite", "status", "mitglied", "vermerk", "text"]
    )
    schreiber.writeheader()
    for zeile in _zeilen():
        schreiber.writerow(zeile)
    return antwort


@nur_admins
def export_json(request):
    antwort = JsonResponse(
        {"anstoesse": list(_zeilen()), "exportiert_am": timezone.now().isoformat()},
        json_dumps_params={"ensure_ascii": False, "indent": 1},
    )
    antwort["Content-Disposition"] = 'attachment; filename="anstoesse.json"'
    return antwort
