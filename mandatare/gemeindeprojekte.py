"""Öffentliche Projektstände, jeweils ausdrücklich einem DDÖ-Gemeindemandat zugeordnet."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from mandatare.gemeindequellen import quellen_url_feld
from mandatare.gemeinderechte import darf_bearbeiten, eigenes_gemeindemandat
from mandatare.models import Gemeindeprojekt, Gemeindeprojektstand
from mitglieder.models import Gemeinde
from parameter.models import zahl
from plattform_core.gemeindeansicht import PROJEKTREIHUNG, PROJEKTVERLAUFSREIHUNG
from verfahren.models import AuditEintrag

LAGE = Gemeindeprojektstand.Lage


class Projektformular(forms.ModelForm):
    quelle = quellen_url_feld()
    bestaetigt = forms.BooleanField(label=gettext_lazy("Diese Quelle und diese Angaben sind öffentlich."))

    class Meta:
        model = Gemeindeprojektstand
        fields = ["titel", "lage", "stand_am", "quelle", "vermerk"]
        labels = {"titel": gettext_lazy("Projekttitel"), "lage": gettext_lazy("Belegter Projektstand"),
                  "stand_am": gettext_lazy("Datum des belegten Stands"), "vermerk": gettext_lazy("Öffentlicher Vermerk")}
        widgets = {"stand_am": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
                   "vermerk": forms.Textarea(attrs={"rows": 5})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["titel"].required = True
        self.fields["quelle"].required = True
        self.fields["lage"].choices = [(key, name) for key, name in LAGE.choices if key != LAGE.ZURUECKGEZOGEN]

    def clean_stand_am(self):
        stand_am = self.cleaned_data["stand_am"]
        if stand_am > timezone.localdate():
            raise forms.ValidationError(_("Ein dokumentierter Vorgang darf nicht in der Zukunft liegen."))
        return stand_am


def _seite(request, queryset):
    return Paginator(queryset, max(1, zahl("suche-treffer-hoechstzahl", 24))).get_page(request.GET.get("seite"))


def _aktueller_stand(staende):
    stand = staende.order_by(*PROJEKTVERLAUFSREIHUNG).first()
    if stand is None:
        raise Http404
    return stand


def projektstaende_in(gemeinde):
    letzte = Gemeindeprojektstand.objects.filter(projekt_id=OuterRef("projekt_id")).order_by(
        *PROJEKTVERLAUFSREIHUNG,
    ).values("pk")[:1]
    return (Gemeindeprojektstand.objects.filter(projekt__gemeinde=gemeinde, pk=Subquery(letzte))
            .select_related("projekt__mandat__mitglied").defer("projekt__mandat__foto", "vermerk")
            .order_by(*PROJEKTREIHUNG))


@require_safe
def liste(request, kennziffer):
    gemeinde = get_object_or_404(Gemeinde, kennziffer=kennziffer)
    staende = projektstaende_in(gemeinde)
    return render(request, "mandatare/gemeindeprojekte.html", {"gemeinde": gemeinde, "seite": _seite(request, staende)})


@require_safe
def detail(request, kennziffer, pk):
    projekt = get_object_or_404(
        Gemeindeprojekt.objects.select_related("gemeinde", "mandat__mitglied").defer("mandat__foto"),
        pk=pk, gemeinde__kennziffer=kennziffer,
    )
    stand = _aktueller_stand(projekt.staende)
    darf_schreiben = (
        request.user.is_authenticated and request.user.pk == projekt.mandat.mitglied_id
        and projekt.mandat.aktiv and projekt.mandat.gemeinde_id == projekt.gemeinde_id
        and darf_bearbeiten(request.user)
    )
    verlauf = projekt.staende.exclude(pk=stand.pk).only("pk", "lage", "erfasst_am").order_by(*PROJEKTVERLAUFSREIHUNG)
    return render(request, "mandatare/gemeindeprojekt.html", {
        "projekt": projekt, "aktuell": stand, "darf_schreiben": darf_schreiben, "seite": _seite(request, verlauf),
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def verwalten(request, pk, projekt_pk=None):
    if not darf_bearbeiten(request.user):
        return render(request, "mandatare/kein_zugang.html", status=403)
    jetzt = timezone.now()
    post = request.method == "POST"
    mandat = eigenes_gemeindemandat(request.user, pk, jetzt, sperren=post)
    projekt = None
    vorher = None
    if projekt_pk is not None:
        projekt = get_object_or_404(mandat.gemeindeprojekte, pk=projekt_pk, gemeinde_id=mandat.gemeinde_id)
        vorher = _aktueller_stand(projekt.staende)
    aktion = request.POST.get("aktion") if post else None
    ausgang_aktuell = vorher is None or request.POST.get("ausgang") == str(vorher.pk)
    if projekt and aktion == "zurueckziehen":
        if vorher.lage == LAGE.ZURUECKGEZOGEN:
            return redirect("gemeinde:projekt", kennziffer=projekt.gemeinde.kennziffer, pk=projekt.pk)
        if ausgang_aktuell:
            stand = projekt.staende.create(lage=LAGE.ZURUECKGEZOGEN, stand_am=timezone.localdate(jetzt), erfasst_am=jetzt)
            return _veroeffentlicht(request, stand, projekt)

    initial = {}
    if vorher and vorher.lage != LAGE.ZURUECKGEZOGEN:
        initial = {"titel": vorher.titel, "lage": vorher.lage, "stand_am": vorher.stand_am,
                   "quelle": vorher.quelle, "vermerk": vorher.vermerk}
    form = Projektformular(request.POST if aktion == "veroeffentlichen" else None, initial=initial)
    if aktion == "veroeffentlichen" and form.is_valid():
        if vorher and vorher.lage != LAGE.ZURUECKGEZOGEN and not (set(form.changed_data) - {"bestaetigt"}):
            return redirect("gemeinde:projekt", kennziffer=projekt.gemeinde.kennziffer, pk=projekt.pk)
        if ausgang_aktuell:
            if projekt is None:
                projekt = mandat.gemeindeprojekte.create(gemeinde_id=mandat.gemeinde_id, veroeffentlicht_am=jetzt)
            stand = form.save(commit=False)
            stand.projekt = projekt
            stand.erfasst_am = jetzt
            stand.save()
            return _veroeffentlicht(request, stand, projekt)
    return render(request, "mandatare/gemeindeprojekt_formular.html", {
        "mandat": mandat, "projekt": projekt, "form": form,
        "darf_zurueckziehen": vorher is not None and vorher.lage != LAGE.ZURUECKGEZOGEN,
        "ausgang": vorher.pk if vorher else None,
        "zwischenzeitlich_geaendert": post and not ausgang_aktuell,
    })


def _veroeffentlicht(request, stand, projekt):
    AuditEintrag.anhaengen({
        "typ": "gemeindeprojektstand", "projekt": projekt.pk, "stand": stand.pk, "mandat": projekt.mandat_id,
        "gemeinde": projekt.gemeinde.kennziffer, "lage": stand.lage,
    })
    messages.success(request, _("Der öffentliche Projektstand wurde gespeichert."))
    return redirect("gemeinde:projekt", kennziffer=projekt.gemeinde.kennziffer, pk=projekt.pk)
