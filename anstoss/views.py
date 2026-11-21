"""Anstoß-Ansichten (F-69): entgegennehmen, sichten, exportieren.

Grundsätze: ohne JavaScript voll funktionsfähig (htmx nur als Zugabe),
Honigtopf, Sendeabstand und Verbindungsdrossel statt Captcha, keine
Anmeldepflicht. Die Verwaltungsansicht ist wie jede andere Seite übersetzbar
(seit 0.40.0)."""

import csv

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.html import format_html
from django.utils.http import url_has_allowed_host_and_scheme
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from anstoss.models import Anstoss, AnstossStatus
from mitglieder.botschutz import drossel_zuviel
from mitglieder.verwaltung import nur_admins
from parameter.models import zahl
from verfahren.models import AuditEintrag

# Zielwerte — gelesen wird das Register (anstoss-mindestabstand-sekunden, anstoss-tagesgrenze).
MIN_ABSTAND_SEKUNDEN = 60
TAGESGRENZE = 20


def _drossel_text() -> str:
    """Derselbe Satz wie im Widget (anstoss/_widget.html), für die htmx-Antwort."""
    return _("Über diese Verbindung kamen in der letzten Stunde schon viele Anstöße — bitte später noch einmal versuchen.")


def _mit_param(seite: str, wert: str) -> str:
    """Hängt ?anstoss=<wert> an — vorhandene Anstoß-Parameter werden ersetzt."""
    from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

    teile = urlsplit(seite)
    q = [(k, v) for k, v in parse_qsl(teile.query) if k != "anstoss"]
    q.append(("anstoss", wert))
    return urlunsplit(("", "", teile.path or "/", urlencode(q), ""))


def _seite_zum_speichern(seite: str) -> str:
    """Was von der Herkunftsseite gespeichert wird (GP-131): der Pfad ohne Abfrage — Suchbegriffe
    gehören nicht in Liste und Ausfuhr —, bei Routen mit Kennung im Pfad nur der Routenname, damit
    weder Einspruchskennung noch Ausweiscode im Klartext liegen."""
    from urllib.parse import urlsplit

    from django.urls import Resolver404, resolve

    pfad = urlsplit(seite).path or "/"
    try:
        treffer = resolve(pfad)
    except Resolver404:
        return pfad
    return treffer.view_name if (treffer.kwargs or treffer.args) else pfad


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
    mindestabstand = zahl("anstoss-mindestabstand-sekunden", MIN_ABSTAND_SEKUNDEN)
    tagesgrenze = zahl("anstoss-tagesgrenze", TAGESGRENZE)

    ergebnis = "danke"
    if honig:
        pass  # Bots freundlich ins Leere laufen lassen — nichts speichern, nichts verraten
    elif not text:
        ergebnis = "leer"
    elif (zuletzt and jetzt.timestamp() - float(zuletzt) < mindestabstand) or anzahl >= tagesgrenze:
        ergebnis = "warte"
    elif drossel_zuviel(request, "anstoss", limit=tagesgrenze):
        # Die Sitzung gehört dem Client: Wer das Cookie weglässt, hat jedes Mal eine leere
        # (Befund #67). Darum zusätzlich je Verbindung und Stunde — und erst hier, damit
        # leere und Honigtopf-POSTs kein Budget verbrauchen. Eigene Meldung (GP-201): Wer hinter
        # einer gemeinsamen Adresse noch nichts gesendet hat, soll nicht „warten“ lesen.
        ergebnis = "drossel"
    else:
        Anstoss.objects.create(
            text=text[:4000],
            seite=_seite_zum_speichern(seite)[:300],
            nutzer=request.user if request.user.is_authenticated else None,
        )
        request.session["anstoss_zuletzt"] = jetzt.timestamp()
        request.session["anstoss_tag"] = heute
        request.session["anstoss_anzahl"] = anzahl + 1

    if request.headers.get("HX-Request"):
        # Rückmeldung als Ereignis (HX-Trigger), nicht als Inline-Script: Alpine schließt die
        # Karte und zeigt die Blase; ohne JavaScript greift die Umleitung mit ?anstoss=…
        if ergebnis == "drossel":
            antwort = HttpResponse(format_html('<p class="anstoss-echo">{}</p>', _drossel_text()))
        else:
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
    status = request.POST.get("status", "")
    if status in AnstossStatus.values:
        with transaction.atomic():
            anstoss = get_object_or_404(Anstoss.objects.select_for_update(), pk=pk)
            vorher, alter_vermerk = anstoss.status, anstoss.vermerk
            anstoss.status = status
            anstoss.vermerk = (request.POST.get("vermerk") or "").strip()[:300] or alter_vermerk
            if (anstoss.status, anstoss.vermerk) != (vorher, alter_vermerk):
                anstoss.save(update_fields=["status", "vermerk"])
                # GP-133: Status und Vermerk mit Spur, der Vermerktext selbst bleibt intern.
                AuditEintrag.anhaengen(
                    {
                        "typ": "anstoss_status",
                        "anstoss": anstoss.pk,
                        "vorher": vorher,
                        "status": anstoss.status,
                        "vermerk_geaendert": anstoss.vermerk != alter_vermerk,
                        "durch": request.user.pk,
                    }
                )
    else:
        get_object_or_404(Anstoss, pk=pk)
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
    zeilen = list(_zeilen())
    for zeile in zeilen:
        schreiber.writerow({k: _zelle(v) for k, v in zeile.items()})
    _ausfuhr_vermerken(request, "csv", len(zeilen))
    return antwort


def _ausfuhr_vermerken(request, format_: str, zeilen: int) -> None:
    """GP-133: Die Ausfuhr nennt Anzeigenamen — sie geschieht nicht ohne Spur. Der Eintrag ist die
    einzige Schreibhandlung; scheitert er, geht keine Datei hinaus."""
    AuditEintrag.anhaengen({"typ": "anstoss_ausfuhr", "format": format_, "zeilen": zeilen, "durch": request.user.pk})


#: Zeichen, mit denen eine Tabellenkalkulation eine Zelle als Formel liest (GP-132).
FORMELZEICHEN = ("=", "+", "-", "@", "\t", "\r")


def _zelle(wert):
    """Eine CSV-Zelle, die keine Formel werden kann: führendes Formelzeichen → Hochkomma davor."""
    if isinstance(wert, str) and wert.startswith(FORMELZEICHEN):
        return "'" + wert
    return wert


@nur_admins
def export_json(request):
    zeilen = list(_zeilen())
    antwort = JsonResponse(
        {"anstoesse": zeilen, "exportiert_am": timezone.now().isoformat()},
        json_dumps_params={"ensure_ascii": False, "indent": 1},
    )
    _ausfuhr_vermerken(request, "json", len(zeilen))
    antwort["Content-Disposition"] = 'attachment; filename="anstoesse.json"'
    return antwort
