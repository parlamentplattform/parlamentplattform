"""Lesbare Links zum Gemeindehaushalt mit nachvollziehbaren Berichtigungen."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from mandatare.gemeindequellen import quellen_url_feld
from mandatare.gemeinderechte import darf_bearbeiten, eigenes_gemeindemandat
from mandatare.models import Gemeindehaushaltsquelle
from mitglieder.models import Gemeinde
from parameter.models import zahl
from plattform_core.gemeindeansicht import HAUSHALTSQUELLENREIHUNG
from verfahren.models import AuditEintrag

ART = Gemeindehaushaltsquelle.Art


class Haushaltsquellenformular(forms.Form):
    art = forms.ChoiceField(label=gettext_lazy("Unterlage"), choices=ART.choices)
    jahr = forms.IntegerField(
        min_value=1, max_value=9999, label=gettext_lazy("Haushaltsjahr oder erstes Planjahr"),
    )
    bis_jahr = forms.IntegerField(
        min_value=1, max_value=9999, required=False, label=gettext_lazy("Letztes Planjahr (nur beim Finanzplan)"),
    )
    url = quellen_url_feld()
    bestaetigt = forms.BooleanField(
        label=gettext_lazy("Diese Unterlage ist öffentlich und gehört zu dieser Gemeinde und diesem Zeitraum."),
        required=False,
    )

    def clean(self):
        daten = super().clean()
        aktion = self.data.get("aktion")
        if aktion == "zurueckziehen":
            return daten
        if aktion != "veroeffentlichen":
            self.add_error(None, _("Unbekannte Aktion."))
            return daten
        if "url" in daten and not daten["url"]:
            self.add_error("url", _("Geben Sie den öffentlichen Link zur Unterlage ein."))
        if not daten.get("bestaetigt"):
            self.add_error("bestaetigt", _("Bestätigen Sie die öffentliche Zugänglichkeit und die Zuordnung."))
        art, jahr, bis = daten.get("art"), daten.get("jahr"), daten.get("bis_jahr")
        if art == ART.FINANZPLAN and jahr and "bis_jahr" in daten and (bis is None or bis < jahr):
            self.add_error("bis_jahr", _("Geben Sie das letzte Planjahr an. Es darf nicht vor dem ersten liegen."))
        elif art and art != ART.FINANZPLAN and bis is not None:
            self.add_error("bis_jahr", _("Ein letztes Planjahr gehört nur zum Finanzplan."))
        return daten


@require_safe
def liste(request, kennziffer):
    gemeinde = get_object_or_404(Gemeinde, kennziffer=kennziffer)
    letzte = Gemeindehaushaltsquelle.objects.filter(
        gemeinde_id=OuterRef("gemeinde_id"), mandat_id=OuterRef("mandat_id"),
        jahr=OuterRef("jahr"), art=OuterRef("art"),
    ).order_by("-pk").values("pk")[:1]
    quellen = (
        Gemeindehaushaltsquelle.objects.filter(gemeinde=gemeinde, pk=Subquery(letzte))
        .select_related("mandat__mitglied").defer("mandat__foto").order_by(*HAUSHALTSQUELLENREIHUNG)
    )
    seite = Paginator(quellen, max(1, zahl("suche-treffer-hoechstzahl", 24))).get_page(request.GET.get("seite"))
    return render(request, "mandatare/gemeindehaushalt.html", {"gemeinde": gemeinde, "seite": seite})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def verwalten(request, pk):
    if not darf_bearbeiten(request.user):
        return render(request, "mandatare/kein_zugang.html", status=403)
    jetzt = timezone.now()
    post = request.method == "POST"
    mandat = eigenes_gemeindemandat(request.user, pk, jetzt, sperren=post)
    form = Haushaltsquellenformular(request.POST if post else None)
    if post and form.is_valid() and _quelle_erfassen(form, mandat, jetzt):
        messages.success(request, _("Der öffentliche Quellenstand wurde gespeichert."))
        return redirect("gemeinde:haushalt", kennziffer=mandat.gemeinde.kennziffer)
    return render(request, "mandatare/gemeindehaushalt_formular.html", {"form": form, "mandat": mandat})


def _quelle_erfassen(form, mandat, jetzt):
    daten = form.cleaned_data
    gruppe = mandat.haushaltsquellen.filter(gemeinde_id=mandat.gemeinde_id, jahr=daten["jahr"], art=daten["art"])
    vorher = gruppe.order_by("-pk").first()
    bis, url = daten["bis_jahr"], daten["url"]
    if form.data.get("aktion") == "zurueckziehen":
        if vorher is None or not vorher.url:
            form.add_error("art", _("Zu dieser Unterlage gibt es keinen veröffentlichten Link."))
            return False
        bis, url = vorher.bis_jahr, ""
    if vorher is None or (vorher.bis_jahr, vorher.url) != (bis, url):
        quelle = mandat.haushaltsquellen.create(
            gemeinde_id=mandat.gemeinde_id, jahr=daten["jahr"], art=daten["art"],
            bis_jahr=bis, url=url, erfasst_am=jetzt,
        )
        AuditEintrag.anhaengen({
            "typ": "gemeindehaushaltsquelle", "mandat": mandat.pk, "gemeinde": mandat.gemeinde.kennziffer,
            "quelle": quelle.pk, "art": quelle.art, "zurueckgezogen": not url,
        })
    return True
