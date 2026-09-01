"""Parameterregister-Ansichten (F-68): öffentliche Liste, JSON-Export,
Verwaltung mit Pflicht-Grund — jede Änderung im Audit-Log."""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from mitglieder.verwaltung import nur_admins
from parameter.models import Parameter, erstbestand_sicherstellen
from verfahren.models import AuditEintrag


def liste(request):
    erstbestand_sicherstellen()
    return render(request, "parameter/liste.html", {"parameter": Parameter.objects.all()})


def export_json(request):
    erstbestand_sicherstellen()
    daten = [
        {
            "schluessel": p.schluessel,
            "wert": p.wert,
            "einheit": p.einheit,
            "beschreibung": p.beschreibung,
            "quelle": p.quelle,
            "geaendert_am": p.geaendert_am.isoformat(),
        }
        for p in Parameter.objects.all()
    ]
    antwort = JsonResponse({"parameter": daten}, json_dumps_params={"ensure_ascii": False, "indent": 1})
    antwort["Access-Control-Allow-Origin"] = "*"
    return antwort


@nur_admins
def verwaltung(request):
    erstbestand_sicherstellen()
    return render(request, "parameter/verwaltung.html", {"parameter": Parameter.objects.all()})


@nur_admins
@require_POST
def verwaltung_aktion(request):
    eintrag = get_object_or_404(Parameter, pk=request.POST.get("parameter"))
    neuer_wert = (request.POST.get("wert") or "").strip()[:100]
    grund = (request.POST.get("grund") or "").strip()
    if not neuer_wert or not grund:
        messages.error(request, "Neuer Wert und Grund sind Pflicht — der Grund wird veröffentlicht.")
        return redirect("parameter:verwaltung")
    if neuer_wert == eintrag.wert:
        messages.info(request, "Der Wert ist unverändert — nichts zu tun.")
        return redirect("parameter:verwaltung")
    alt = eintrag.wert
    eintrag.wert = neuer_wert
    eintrag.geaendert_am = timezone.now()
    eintrag.save(update_fields=["wert", "geaendert_am"])
    AuditEintrag.anhaengen(
        {
            "typ": "parameter_geaendert",
            "schluessel": eintrag.schluessel,
            "alt": alt,
            "neu": neuer_wert,
            "grund": grund[:500],
        }
    )
    messages.success(
        request,
        f"„{eintrag.schluessel}“: {alt} → {neuer_wert}. Grund steht im öffentlichen Audit-Log.",
    )
    return redirect("parameter:verwaltung")
