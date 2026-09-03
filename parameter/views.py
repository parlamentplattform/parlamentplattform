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
    from plattform_core.weicherfilter import REGLER
    from verfahren.views import REGLER_MERKMALE, REGLER_NAMEN

    erstbestand_sicherstellen()
    return render(
        request,
        "parameter/liste.html",
        {
            "parameter": Parameter.objects.all(),
            # FB-B6: die offene Regel v2 des WeicherFilters, Regler für Regler nachlesbar
            "weicherfilter_regler": [
                (i + 1, REGLER_NAMEN[name], REGLER_MERKMALE[name]) for i, name in enumerate(REGLER)
            ],
        },
    )


def _offen(daten) -> JsonResponse:
    antwort = JsonResponse(daten, json_dumps_params={"ensure_ascii": False, "indent": 1})
    antwort["Access-Control-Allow-Origin"] = "*"
    return antwort


def export_json(request):
    """FB-M5 (§ 12 Abs 5): Stellgrößen und Verfahrensordnung im sprachneutralen Schema
    (docs/SCHEMA.md, ADR-009) — der Austausch zwischen den Landesinstanzen. Die bisherigen
    Felder bleiben, dazu kommen Kopf und Schema-Kennungen."""
    from django.conf import settings

    from plattform_core import __version__
    from plattform_core.schema import parameter_export
    from verfahren.models import Verfahrensordnung

    erstbestand_sicherstellen()
    parameter = [
        {
            "schluessel": p.schluessel,
            "schema_key": p.schema_key,
            "wert": p.wert,
            "einheit": p.einheit,
            "beschreibung": p.beschreibung,
            "quelle": p.quelle,
            "geaendert_am": p.geaendert_am.isoformat(),
        }
        for p in Parameter.objects.all()
    ]
    ordnungen = [
        {**(vo.regeln or {}), "id": vo.policy_id, "version": vo.version}
        for vo in Verfahrensordnung.objects.filter(aktiv=True).order_by("policy_id")
    ]
    return _offen(
        parameter_export(
            settings.DDOE_SYSTEM_ID, settings.DDOE_SYSTEM_NAME, __version__, parameter, ordnungen, timezone.now()
        )
    )


def kennzahlen_json(request):
    """FB-M5: der aggregierte Lernfortschritt dieser Instanz — Zählungen und Anteile über das
    Ganze, nie über einen Menschen (Art 9 DSGVO). Kennungen nach docs/SCHEMA.md."""
    from django.conf import settings
    from django.db.models import Count

    from mitglieder.models import Mitglied
    from plattform_core import Phase, __version__
    from plattform_core.schema import kennzahlen_export, turnout_mean
    from verfahren.models import Antrag, Kategorie, Vollzugsstatus
    from verfahren.views import _register_zeilen

    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    je_phase = dict.fromkeys(("unterstuetzung", "beratung", "abstimmung", "angenommen", "abgelehnt", "verfallen"), 0)
    for zeile in antraege.values("phase").annotate(n=Count("pk")):
        if zeile["phase"] in je_phase:
            je_phase[zeile["phase"]] = zeile["n"]
    entschieden = antraege.filter(
        phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value], stimmberechtigte_anzahl__gt=0
    )
    anteile = [a.stimmabgaben.count() / a.stimmberechtigte_anzahl for a in entschieden]
    register = _register_zeilen()
    je_status = {wert: sum(1 for z in register if z["status"] == wert) for wert, _name in Vollzugsstatus.choices}
    werte = {
        "members.active": Mitglied.objects.filter(is_active=True).count(),
        "motions.total": antraege.count(),
        "motions.by_phase": je_phase,
        "votes.completed": entschieden.count(),
        "votes.turnout_mean": turnout_mean(anteile),
        "implementation.by_status": je_status,
        "areas_of_life.active": Kategorie.objects.filter(aktiv=True).count(),
    }
    return _offen(
        kennzahlen_export(settings.DDOE_SYSTEM_ID, settings.DDOE_SYSTEM_NAME, __version__, werte, timezone.now())
    )


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
