"""Lesende Ansichten. Grundsatz F-31: Sortierung ausschließlich nach Frist und
Phase — niemals nach Beliebtheit. Ergebnisseiten sind ohne Login lesbar (F-20)."""
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from plattform_core import Phase
from verfahren.models import Antrag


def index(request):
    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    gruppen = [
        ("Laufende Abstimmungen", antraege.filter(phase=Phase.ABSTIMMUNG.value).order_by("phase_beginn")),
        ("In Beratung", antraege.filter(phase=Phase.BERATUNG.value).order_by("phase_beginn")),
        ("Sammeln Unterstützung", antraege.filter(phase=Phase.UNTERSTUETZUNG.value).order_by("phase_beginn")),
        ("Abgeschlossen", antraege.filter(
            phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value, Phase.VERFALLEN.value]
        ).order_by("-phase_beginn")[:20]),
    ]
    return render(request, "verfahren/index.html", {"gruppen": gruppen})


def antrag_detail(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    ergebnis = None
    if antrag.phase in (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value):
        ergebnis = antrag.auszaehlen()
    return render(request, "verfahren/antrag.html", {
        "antrag": antrag,
        "fassung": antrag.aktueller_text(),
        "ergebnis": ergebnis,
        "unterstuetzungen": antrag.unterstuetzungen.count(),
    })


def gesund(request):
    return JsonResponse({"status": "ok"})
