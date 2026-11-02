"""Öffentliche Quellen-Nachlese; ausschließlich lesende GET-Ansichten."""

import json

from django.core.paginator import Paginator
from django.db.models import Count
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from faktenbasis.models import Norm, RisImport
from parameter.models import zahl


@require_safe
def index(request):
    seiten = Paginator(Norm.objects.select_related("importlauf"), max(1, min(100, zahl("faktenbasis-seitengroesse", 20))))
    return render(request, "faktenbasis/index.html", {
        "seite": seiten.get_page(request.GET.get("seite")),
        "umfang": Norm.objects.aggregate(schnappschuesse=Count("pk"), dokumente=Count("ris_id", distinct=True)),
        "letzter": RisImport.objects.first(),
        "erfolg": RisImport.objects.filter(erfolgreich=True).first(),
    })


@require_safe
def norm(request, pk):
    eintrag = get_object_or_404(Norm.objects.select_related("importlauf"), pk=pk)
    return render(request, "faktenbasis/norm.html", {
        "norm": eintrag,
        "fassungen": Norm.objects.filter(ris_id=eintrag.ris_id).order_by("-stand", "-pk"),
        "rohdaten": json.dumps(eintrag.rohdaten, ensure_ascii=False, indent=2),
    })


@require_safe
def importantwort(request, pk):
    lauf = get_object_or_404(RisImport, pk=pk, erfolgreich=True)
    antwort = JsonResponse(lauf.antwort, json_dumps_params={"ensure_ascii": False, "indent": 2})
    antwort["Content-Disposition"] = f'attachment; filename="ris-import-{lauf.pk}.json"'
    return antwort
