"""Öffentlich verlinkte Sitzungsunterlagen, getrennt vom DDÖ-Bericht und vom Ticker."""

from urllib.parse import urlsplit

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.validators import URLValidator
from django.db import transaction
from django.db.models import OuterRef, Subquery
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from mandatare.gemeinderechte import darf_bearbeiten, eigenes_gemeindemandat
from mandatare.models import Gemeindesitzungsquelle
from mitglieder.models import Gemeinde
from parameter.models import zahl
from plattform_core.gemeindeansicht import SITZUNGSQUELLENREIHUNG
from verfahren.models import AuditEintrag


class Quellenformular(forms.Form):
    art = forms.ChoiceField(label=gettext_lazy("Unterlage"), choices=Gemeindesitzungsquelle.Art.choices)
    url = forms.CharField(
        label=gettext_lazy("Öffentlicher HTTPS-Link"),
        required=False,
        max_length=Gemeindesitzungsquelle._meta.get_field("url").max_length,
        validators=[URLValidator(schemes=["https"])],
        widget=forms.URLInput,
    )
    bestaetigt = forms.BooleanField(
        label=gettext_lazy("Diese Unterlage ist öffentlich und gehört zu dieser Gemeinderatssitzung."),
        required=False,
    )

    def clean_url(self):
        url = self.cleaned_data["url"]
        if url:
            teile = urlsplit(url)
            if teile.username is not None or teile.password is not None or "\\" in url:
                raise forms.ValidationError(_("Der Link darf keine Zugangsdaten oder Rückstriche enthalten."))
        return url


@require_safe
def liste(request, kennziffer):
    gemeinde = get_object_or_404(Gemeinde, kennziffer=kennziffer)
    letzte = Gemeindesitzungsquelle.objects.filter(
        aufgabe_id=OuterRef("aufgabe_id"), art=OuterRef("art")
    ).order_by("-pk").values("pk")[:1]
    quellen = (
        Gemeindesitzungsquelle.objects.filter(gemeinde=gemeinde, pk=Subquery(letzte))
        .select_related("aufgabe__mandat__mitglied").defer("aufgabe__mandat__foto").order_by(*SITZUNGSQUELLENREIHUNG)
    )
    seite = Paginator(quellen, max(1, zahl("suche-treffer-hoechstzahl", 24))).get_page(request.GET.get("seite"))
    return render(request, "mandatare/gemeindesitzungsquellen.html", {"gemeinde": gemeinde, "seite": seite})


def _quelle_erfassen(form, aufgabe, mandat, erste, jetzt, aktion):
    art, url = form.cleaned_data["art"], form.cleaned_data["url"]
    sitzung_am = erste.sitzung_am if erste else aufgabe.sitzungstag_datum
    vorher = aufgabe.gemeindesitzungsquellen.filter(art=art).order_by("-pk").first()
    if aktion == "zurueckziehen":
        if vorher is None or not vorher.url:
            form.add_error("art", _("Zu dieser Unterlage gibt es keinen veröffentlichten Link."))
            return False
        url = ""
    elif aktion == "veroeffentlichen":
        if not url:
            form.add_error("url", _("Geben Sie den öffentlichen Link zur Unterlage ein."))
            return False
        if not form.cleaned_data["bestaetigt"]:
            form.add_error("bestaetigt", _("Bestätigen Sie die öffentliche Zugänglichkeit und die Zuordnung."))
            return False
        if art == Gemeindesitzungsquelle.Art.NIEDERSCHRIFT and sitzung_am > timezone.localdate(jetzt):
            form.add_error("art", _("Die Niederschrift kann erst ab dem Sitzungstag verlinkt werden."))
            return False
    else:
        form.add_error(None, _("Unbekannte Aktion."))
        return False

    if vorher is None or vorher.url != url:
        quelle = aufgabe.gemeindesitzungsquellen.create(
            gemeinde_id=mandat.gemeinde_id, sitzung_am=sitzung_am, art=art, url=url, erfasst_am=jetzt,
        )
        AuditEintrag.anhaengen({
            "typ": "gemeindesitzungsquelle", "mandat": mandat.pk, "aufgabe": aufgabe.pk, "quelle": quelle.pk,
            "art": art, "zurueckgezogen": not url,
        })
    return True


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def verwalten(request, pk, aufgabe_pk):
    if not darf_bearbeiten(request.user):
        return render(request, "mandatare/kein_zugang.html", status=403)
    jetzt = timezone.now()
    mandat = eigenes_gemeindemandat(request.user, pk, jetzt, sperren=request.method == "POST")
    aufgabe = get_object_or_404(mandat.aufgaben, pk=aufgabe_pk, sitzungstag=True, frist__isnull=False)
    erste = aufgabe.gemeindesitzungsquellen.order_by("pk").first()
    if erste and erste.gemeinde_id != mandat.gemeinde_id:
        return render(request, "mandatare/kein_zugang.html", status=403)
    form = Quellenformular(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        if _quelle_erfassen(form, aufgabe, mandat, erste, jetzt, request.POST.get("aktion")):
            messages.success(request, _("Der öffentliche Quellenstand wurde gespeichert."))
            return redirect("gemeinde:sitzungsquellen", kennziffer=mandat.gemeinde.kennziffer)
    return render(request, "mandatare/gemeindesitzungsquelle_formular.html", {
        "form": form, "mandat": mandat, "aufgabe": aufgabe,
        "sitzung_am": erste.sitzung_am if erste else aufgabe.sitzungstag_datum,
    })
