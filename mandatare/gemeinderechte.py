"""Berechtigung zur Bearbeitung ausdrücklich zugeordneter DDÖ-Gemeindemandate."""

from django.shortcuts import get_object_or_404
from django.utils import timezone

from mandatare.models import Mandat
from verfahren.hinweise import mitwirkungssperre
from verfahren.models import Ebene


def aktive_gemeindemandate(jetzt):
    return Mandat.objects.filter(
        ebene=Ebene.GEMEINDE, gemeinde__isnull=False, angetreten__lte=timezone.localdate(jetzt),
        beendet__isnull=True, vertretung_beendet_am__isnull=True,
        mitglied__parteikonto=True, mitglied__is_active=True, mitglied__testkonto=False,
    )


def darf_bearbeiten(mitglied):
    return mitglied.darf_mitwirken and not mitwirkungssperre(mitglied)


def eigenes_gemeindemandat(mitglied, pk, jetzt, *, sperren=False):
    mandate = aktive_gemeindemandate(jetzt).filter(mitglied_id=mitglied.pk)
    if sperren:
        mandate = mandate.select_for_update(of=("self",))
    return get_object_or_404(mandate, pk=pk)
