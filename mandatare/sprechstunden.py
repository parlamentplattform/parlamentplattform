"""Öffentliche Veröffentlichung und Absage für ausdrücklich zugeordnete Gemeindemandate."""

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import F, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from mandatare.gemeinderechte import aktive_gemeindemandate, darf_bearbeiten, eigenes_gemeindemandat
from mandatare.models import SPRECHSTUNDE_ORT_MAX, Sprechstunde
from plattform_core.gemeindeansicht import SPRECHSTUNDENREIHUNG
from verfahren.models import AuditEintrag


def kommende_in(gemeinde, jetzt):
    """Die kommenden Termine am Ort: die eines aktiven, hier zugeordneten Mandats — und jeder abgesagte bis
    zu seinem Ende, auch wenn das Mandat inzwischen geendet hat oder umgeordnet ist: Wer den Termin gesehen
    hat, liest die Absage statt einer leeren Liste (GP-116)."""
    gueltig = Q(mandat__in=aktive_gemeindemandate(jetzt), mandat__gemeinde=F("gemeinde"))
    # Abgesagte nur von Parteikonten ohne Testkennzeichen — wie die Sitzungen der Ortsseite; Testkonten erscheinen nie
    abgesagt = Q(abgesagt_am__isnull=False, mandat__mitglied__parteikonto=True, mandat__mitglied__testkonto=False)
    return (
        Sprechstunde.objects.filter(gemeinde=gemeinde, ende__gt=jetzt)
        .filter(gueltig | abgesagt)
        .select_related("mandat__mitglied").defer("mandat__foto").order_by(*SPRECHSTUNDENREIHUNG)
    )


def termine_absagen(mandat, anlass: str, jetzt=None, *, ausser_gemeinde_id=None) -> list[int]:
    """Die kommenden, nicht abgesagten Sprechstunden eines Mandats mit Stempel und Audit-Eintrag (Anlass)
    absagen — bei Mandatsende, Ende der Vertretung, geänderter Zuordnung oder Kontosperre (GP-116).
    `ausser_gemeinde_id`: Termine an diesem Ort bleiben (die neue Zuordnung). Rückgabe: die Termine."""
    jetzt = jetzt or timezone.now()
    termine = Sprechstunde.objects.select_for_update().filter(mandat=mandat, ende__gt=jetzt, abgesagt_am__isnull=True)
    if ausser_gemeinde_id is not None:
        termine = termine.exclude(gemeinde_id=ausser_gemeinde_id)
    abgesagt = []
    with transaction.atomic():
        for termin in termine.select_related("gemeinde"):
            termin.abgesagt_am = jetzt
            termin.save(update_fields=["abgesagt_am"])
            AuditEintrag.anhaengen({"typ": "sprechstunde_abgesagt", "mandat": mandat.pk, "termin": termin.pk,
                                    "gemeinde": termin.gemeinde.kennziffer, "anlass": anlass})
            abgesagt.append(termin.pk)
    return abgesagt


class SprechstundenFormular(forms.Form):
    beginn = forms.DateTimeField(
        label=gettext_lazy("Beginn (Wiener Zeit)"),
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )
    ende = forms.DateTimeField(
        label=gettext_lazy("Ende (Wiener Zeit)"),
        widget=forms.DateTimeInput(format="%Y-%m-%dT%H:%M", attrs={"type": "datetime-local"}),
    )
    treffpunkt = forms.CharField(label=gettext_lazy("Öffentlicher Treffpunkt"), max_length=SPRECHSTUNDE_ORT_MAX)

    def clean(self):
        daten = super().clean()
        beginn, ende = daten.get("beginn"), daten.get("ende")
        for feld in ("beginn", "ende"):
            roh = parse_datetime(self.data.get(feld, "")) if daten.get(feld) else None
            if roh is not None and timezone.is_aware(roh):
                self.add_error(feld, _("Bitte geben Sie die Wiener Ortszeit ohne Zeitzonenzusatz ein."))
        if beginn and beginn <= timezone.now():
            self.add_error("beginn", _("Der Beginn muss in der Zukunft liegen."))
        if beginn and ende and ende <= beginn:
            self.add_error("ende", _("Das Ende muss nach dem Beginn liegen."))
        return daten


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def verwalten(request, pk):
    if not darf_bearbeiten(request.user):
        return render(request, "mandatare/kein_zugang.html", status=403)
    jetzt = timezone.now()
    form = SprechstundenFormular(request.POST if request.method == "POST" else None)
    if request.method == "POST":
        with transaction.atomic():
            mandat = eigenes_gemeindemandat(request.user, pk, jetzt, sperren=True)
            if form.is_valid():
                existiert = mandat.sprechstunden.filter(
                    abgesagt_am__isnull=True, beginn__lt=form.cleaned_data["ende"], ende__gt=form.cleaned_data["beginn"],
                ).exists()
                if existiert:
                    form.add_error("beginn", _("Dieser Zeitraum überschneidet sich mit einer veröffentlichten Sprechstunde."))
                else:
                    termin = mandat.sprechstunden.create(
                        gemeinde_id=mandat.gemeinde_id, veroeffentlicht_am=timezone.now(), **form.cleaned_data,
                    )
                    AuditEintrag.anhaengen({"typ": "sprechstunde_veroeffentlicht", "mandat": mandat.pk,
                                            "termin": termin.pk, "gemeinde": mandat.gemeinde.kennziffer})
                    messages.success(request, _("Die Sprechstunde ist veröffentlicht."))
                    return redirect("mandatare:sprechstunden", pk=mandat.pk)
    else:
        mandat = eigenes_gemeindemandat(request.user, pk, jetzt)
    termine = (mandat.sprechstunden.filter(ende__gt=jetzt).select_related("gemeinde", "mandat__mitglied")
               .defer("mandat__foto").order_by(*SPRECHSTUNDENREIHUNG))
    return render(request, "mandatare/sprechstunden.html", {"mandat": mandat, "form": form, "termine": termine})


@login_required
@never_cache
@require_POST
@transaction.atomic
def absagen(request, pk, termin_pk):
    if not darf_bearbeiten(request.user):
        return render(request, "mandatare/kein_zugang.html", status=403)
    jetzt = timezone.now()
    mandat = eigenes_gemeindemandat(request.user, pk, jetzt, sperren=True)
    termin = get_object_or_404(mandat.sprechstunden, pk=termin_pk, ende__gt=jetzt)
    if termin.abgesagt_am is None:
        termin.abgesagt_am = jetzt
        termin.save(update_fields=["abgesagt_am"])
        AuditEintrag.anhaengen({"typ": "sprechstunde_abgesagt", "mandat": mandat.pk,
                                "termin": termin.pk, "gemeinde": termin.gemeinde.kennziffer})
        messages.success(request, _("Die Sprechstunde ist als abgesagt gekennzeichnet."))
    return redirect("mandatare:sprechstunden", pk=mandat.pk)
