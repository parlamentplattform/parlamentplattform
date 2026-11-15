"""Öffentliche DDÖ-Ratsinitiativen und bewusst veröffentlichte Verlaufsmeldungen."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_safe

from mandatare.gemeindequellen import quellen_url_feld
from mandatare.gemeinderechte import darf_bearbeiten, eigenes_gemeindemandat
from mandatare.models import Ratsinitiative, Ratsmeldung
from mitglieder.models import Gemeinde
from parameter.models import zahl
from plattform_core.gemeindeansicht import RATSINITIATIVENREIHUNG
from verfahren.models import AuditEintrag


def oeffentliche_initiativen(gemeinde):
    return (Ratsinitiative.objects.filter(gemeinde=gemeinde).select_related("mandat__mitglied")
            .defer("mandat__foto").order_by(*RATSINITIATIVENREIHUNG))


def _seite(request, initiative_qs):
    return Paginator(initiative_qs, max(1, zahl("suche-treffer-hoechstzahl", 24))).get_page(request.GET.get("seite"))


def _ziel(initiative):
    return redirect("gemeinde:ratsinitiative", kennziffer=initiative.gemeinde.kennziffer, pk=initiative.pk)


class InitiativeFormular(forms.ModelForm):
    class Meta:
        model = Ratsinitiative
        fields = ["art", "titel", "text"]
        labels = {"art": gettext_lazy("Art der Ratsinitiative"), "titel": gettext_lazy("Titel"),
                  "text": gettext_lazy("Öffentliche Beschreibung")}
        widgets = {"text": forms.Textarea(attrs={"rows": 6})}


class MeldungFormular(forms.ModelForm):
    quellen_url = quellen_url_feld()
    quelle_bestaetigt = forms.BooleanField(
        label=gettext_lazy("Dieser Beleg ist öffentlich zugänglich und gehört zu diesem Verlaufsvermerk."),
        required=False,
    )

    class Meta:
        model = Ratsmeldung
        fields = ["art", "datum", "text", "quellen_url", "quelle_bestaetigt"]
        labels = {"art": gettext_lazy("Art des Eintrags"), "datum": gettext_lazy("Datum des Vorgangs"),
                  "text": gettext_lazy("Öffentliche Beschreibung")}
        widgets = {"datum": forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
                   "text": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, initiative, **kwargs):
        super().__init__(*args, **kwargs)
        self.einbringung = initiative.meldungen.filter(art=Ratsmeldung.Art.EINGEBRACHT).first()
        arten = (
            Ratsmeldung.Art.ANTWORT if self.einbringung else Ratsmeldung.Art.EINGEBRACHT,
            Ratsmeldung.Art.NACHTRAG,
        )
        self.fields["art"].choices = [(art.value, art.label) for art in arten]

    def clean_datum(self):
        datum = self.cleaned_data["datum"]
        if datum > timezone.localdate():
            raise forms.ValidationError(_("Ein dokumentierter Vorgang darf nicht in der Zukunft liegen."))
        if self.cleaned_data.get("art") == Ratsmeldung.Art.ANTWORT and datum < self.einbringung.datum:
            raise forms.ValidationError(_("Die Antwort kann nicht vor der Einbringung liegen."))
        return datum

    def clean(self):
        daten = super().clean()
        if daten.get("quellen_url") and not daten.get("quelle_bestaetigt"):
            self.add_error("quelle_bestaetigt", _("Bestätigen Sie die öffentliche Zugänglichkeit und die Zuordnung."))
        return daten


@require_safe
def liste(request, kennziffer):
    gemeinde = get_object_or_404(Gemeinde, kennziffer=kennziffer)
    return render(request, "mandatare/ratsinitiativen_liste.html", {
        "gemeinde": gemeinde, "seite": _seite(request, oeffentliche_initiativen(gemeinde)),
    })


@require_safe
def detail(request, kennziffer, pk):
    gemeinde = get_object_or_404(Gemeinde, kennziffer=kennziffer)
    initiative = get_object_or_404(oeffentliche_initiativen(gemeinde), pk=pk)
    darf_schreiben = (
        request.user.is_authenticated and request.user.pk == initiative.mandat.mitglied_id
        and initiative.mandat.aktiv and initiative.mandat.gemeinde_id == gemeinde.pk and darf_bearbeiten(request.user)
    )
    meldungen = _seite(request, initiative.meldungen.all())
    return render(request, "mandatare/ratsinitiative.html", {
        "initiative": initiative, "gemeinde": gemeinde, "meldungen": meldungen,
        "darf_schreiben": darf_schreiben,
    })


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def anlegen(request, pk):
    if not darf_bearbeiten(request.user):
        return render(request, "mandatare/kein_zugang.html", status=403)
    jetzt = timezone.now()
    mandat = eigenes_gemeindemandat(request.user, pk, jetzt, sperren=request.method == "POST")
    form = InitiativeFormular(request.POST if request.method == "POST" else None)
    if request.method == "POST" and form.is_valid():
        initiative = form.save(commit=False)
        initiative.mandat = mandat
        initiative.gemeinde = mandat.gemeinde
        initiative.veroeffentlicht_am = jetzt
        initiative.save()
        AuditEintrag.anhaengen({"typ": "ratsinitiative_veroeffentlicht", "mandat": mandat.pk,
                                "initiative": initiative.pk, "gemeinde": mandat.gemeinde.kennziffer})
        messages.success(request, _("Die Ratsinitiative ist veröffentlicht."))
        return _ziel(initiative)
    return render(request, "mandatare/ratsinitiative_formular.html", {"form": form, "mandat": mandat})


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
@transaction.atomic
def melden(request, pk, initiative_pk):
    if not darf_bearbeiten(request.user):
        return render(request, "mandatare/kein_zugang.html", status=403)
    jetzt = timezone.now()
    mandat = eigenes_gemeindemandat(request.user, pk, jetzt, sperren=request.method == "POST")
    initiative = get_object_or_404(mandat.ratsinitiativen, pk=initiative_pk, gemeinde_id=mandat.gemeinde_id)
    form = MeldungFormular(request.POST if request.method == "POST" else None, initiative=initiative)
    if request.method == "POST" and form.is_valid():
        meldung = form.save(commit=False)
        meldung.initiative = initiative
        meldung.eingetragen_am = jetzt
        meldung.save()
        AuditEintrag.anhaengen({"typ": "ratsinitiative_verlauf", "initiative": initiative.pk,
                                "meldung": meldung.pk, "art": meldung.art})
        messages.success(request, _("Der öffentliche Verlauf wurde ergänzt."))
        seite = _seite(request, initiative.meldungen.all()).paginator.num_pages
        url = reverse("gemeinde:ratsinitiative", args=[initiative.gemeinde.kennziffer, initiative.pk])
        return redirect(f"{url}?seite={seite}#vermerk-{meldung.pk}")
    return render(request, "mandatare/ratsinitiative_formular.html", {"form": form, "mandat": mandat, "initiative": initiative})
