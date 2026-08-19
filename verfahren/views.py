"""Lesende Ansichten. Grundsatz F-31: Sortierung ausschließlich nach Frist und
Phase — niemals nach Beliebtheit. Ergebnisseiten sind ohne Login lesbar (F-20)."""

import json

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
        (
            "Abgeschlossen",
            antraege.filter(
                phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value, Phase.VERFALLEN.value]
            ).order_by("-phase_beginn")[:20],
        ),
    ]
    return render(request, "verfahren/index.html", {"gruppen": gruppen})


def antrag_detail(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()  # fällige Übergänge lazy anwenden (idempotent; Produktion: zusätzlich Cron)
    ergebnis = None
    if antrag.phase in (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value):
        ergebnis = antrag.auszaehlen()
    from plattform_core.phases import (
        abstimmung_frist_ende,
        beratung_frist_ende,
        unterstuetzung_frist_ende,
    )

    policy = antrag.policy()
    frist = None
    if antrag.phase == Phase.UNTERSTUETZUNG.value:
        frist = unterstuetzung_frist_ende(antrag.phase_beginn, policy)
    elif antrag.phase == Phase.BERATUNG.value:
        frist = beratung_frist_ende(antrag.phase_beginn, policy)
    elif antrag.phase == Phase.ABSTIMMUNG.value:
        frist = abstimmung_frist_ende(antrag.phase_beginn, policy)
    unterstuetzt_von_mir = (
        request.user.is_authenticated and antrag.unterstuetzungen.filter(mitglied=request.user).exists()
    )
    meine_stimme = None
    if request.user.is_authenticated:
        reg = antrag.stimmregister.filter(mitglied=request.user).first()
        if reg:
            ab = antrag.stimmabgaben.filter(pseudonym=reg.pseudonym).first()
            meine_stimme = ab.stimme if ab else None
    return render(
        request,
        "verfahren/antrag.html",
        {
            "antrag": antrag,
            "policy_json": json.dumps(antrag.policy_snapshot, indent=1, ensure_ascii=False),
            "fassung": antrag.aktueller_text(),
            "ergebnis": ergebnis,
            "unterstuetzungen": antrag.unterstuetzungen.count(),
            "kommentare": antrag.kommentare.select_related("mitglied"),
            "frist": frist,
            "unterstuetzt_von_mir": unterstuetzt_von_mir,
            "meine_stimme": meine_stimme,
            "phase_offen": antrag.phase in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value),
            "abstimmung_laeuft": antrag.phase == Phase.ABSTIMMUNG.value,
        },
    )


def gesund(request):
    return JsonResponse({"status": "ok"})
