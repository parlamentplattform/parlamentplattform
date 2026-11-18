"""Gemeinsame Einstiege und eigene öffentliche Arbeitsstände eines Gemeindemandats."""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_safe

from mandatare.gemeindehaushalt import haushaltsquellen_in
from mandatare.gemeindeprojekte import projektstaende_in
from mandatare.gemeinderechte import darf_bearbeiten, eigenes_gemeindemandat
from mandatare.models import Gemeindeprojektstand
from mandatare.ratsinitiativen import oeffentliche_initiativen
from mandatare.sprechstunden import kommende_in


@login_required
@never_cache
@require_safe
def arbeitsplatz(request, pk):
    jetzt = timezone.now()
    mandat = eigenes_gemeindemandat(request.user, pk, jetzt)
    gemeinde = mandat.gemeinde
    return render(request, "mandatare/gemeindearbeitsplatz.html", {
        "mandat": mandat,
        "gemeinde": gemeinde,
        "darf_schreiben": darf_bearbeiten(request.user),
        "naechster_termin": kommende_in(gemeinde, jetzt).filter(
            mandat=mandat, beginn__gte=jetzt, abgesagt_am__isnull=True,
        ).first(),
        "initiative": oeffentliche_initiativen(gemeinde).filter(mandat=mandat).first(),
        "projektstand": projektstaende_in(gemeinde).filter(projekt__mandat=mandat).exclude(
            lage=Gemeindeprojektstand.Lage.ZURUECKGEZOGEN,
        ).first(),
        "haushaltsquelle": haushaltsquellen_in(gemeinde).filter(mandat=mandat).exclude(url="").first(),
    })
