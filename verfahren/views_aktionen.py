"""Handelnde Ansichten: einbringen, unterstützen, kommentieren, abstimmen, exportieren.

Berechtigungsstufen (aus Satzung § 4):
- Lesen: alle, ohne Login (F-20).
- Einbringen, unterstützen, kommentieren: bestätigte Mitglieder
  (Identitätsstufe mindestens „geprüft").
- Abstimmen: stimmberechtigte Mitglieder (Anwartschaft; im Aufbau gilt die
  Übergangsregel nach § 4 Abs 4 lit d, konfiguriert über DDOE_UEBERGANGSREGEL).
"""

from __future__ import annotations

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from mitglieder.models import Identitaetsstufe
from plattform_core import Gegenstand, Phase
from plattform_core.similarity import aehnlichste
from verfahren.models import (
    Antrag,
    Kommentar,
    StimmabgabeFehler,
    StimmRegister,
    Verfahrensordnung,
    antrag_einbringen,
    stimme_abgeben,
)

OFFENE_PHASEN = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]


def _ist_bestaetigt(user) -> bool:
    return user.is_authenticated and user.identitaetsstufe != Identitaetsstufe.UNGEPRUEFT


class AntragsFormular(forms.Form):
    titel = forms.CharField(label="Titel", max_length=200)
    wortlaut = forms.CharField(label="Wortlaut des Antrags", widget=forms.Textarea(attrs={"rows": 10}))
    begruendung = forms.CharField(
        label="Begründung", widget=forms.Textarea(attrs={"rows": 6}), required=False
    )


class KommentarFormular(forms.Form):
    text = forms.CharField(
        label="Beitrag zur Beratung", widget=forms.Textarea(attrs={"rows": 4}), max_length=4000
    )


@login_required
def einbringen(request):
    """F-10 + F-35: Einbringen mit Ähnlichkeitshinweis — der Hinweis schlägt vor,
    er blockiert nie. „Trotzdem einbringen" ist immer gleichwertig möglich."""
    if not _ist_bestaetigt(request.user):
        return render(request, "verfahren/nur_bestaetigte.html", status=403)
    ordnung = Verfahrensordnung.objects.filter(aktiv=True).order_by("-version").first()
    if ordnung is None:
        return render(request, "verfahren/keine_ordnung.html", status=503)

    aehnliche = []
    if request.method == "POST":
        form = AntragsFormular(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            if not request.POST.get("trotzdem"):
                offene = list(Antrag.objects.filter(phase__in=OFFENE_PHASEN).values_list("id", "titel"))
                texte = {a.pk: a for a in Antrag.objects.filter(id__in=[i for i, _ in offene])}
                kandidaten = []
                for aid, titel in offene:
                    fassung = texte[aid].aktueller_text()
                    kandidaten.append((aid, f"{titel} {fassung.wortlaut if fassung else ''}"))
                treffer = aehnlichste(f"{d['titel']} {d['wortlaut']}", kandidaten)
                if treffer:
                    aehnliche = [
                        {"antrag": texte[aid], "prozent": round(score * 100)} for aid, score in treffer
                    ]
                    return render(
                        request,
                        "verfahren/einbringen.html",
                        {
                            "form": form,
                            "aehnliche": aehnliche,
                            "ordnung": ordnung,
                        },
                    )
            antrag = antrag_einbringen(request.user, d["titel"], d["wortlaut"], d["begruendung"], ordnung)
            messages.success(request, "Ihr Antrag ist eingebracht und sammelt jetzt Unterstützung.")
            return redirect("verfahren:antrag", pk=antrag.pk)
    else:
        form = AntragsFormular()
    return render(
        request, "verfahren/einbringen.html", {"form": form, "aehnliche": aehnliche, "ordnung": ordnung}
    )


@login_required
@require_POST
def unterstuetzen(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    if not _ist_bestaetigt(request.user):
        return render(request, "verfahren/nur_bestaetigte.html", status=403)
    antrag.fortschreiben()
    if antrag.phase != Phase.UNTERSTUETZUNG.value:
        messages.error(request, "Die Unterstützungsphase dieses Antrags ist beendet.")
        return redirect("verfahren:antrag", pk=pk)
    _, neu = antrag.unterstuetzungen.get_or_create(mitglied=request.user)
    if neu:
        messages.success(request, "Danke — Ihre Unterstützung ist erfasst.")
        antrag.fortschreiben()  # Schwelle eventuell gerade erreicht
    else:
        antrag.unterstuetzungen.filter(mitglied=request.user).delete()
        messages.info(request, "Ihre Unterstützung wurde zurückgezogen.")
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def kommentieren(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    if not _ist_bestaetigt(request.user):
        return render(request, "verfahren/nur_bestaetigte.html", status=403)
    antrag.fortschreiben()
    if antrag.phase not in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value):
        messages.error(request, "Die Beratung dieses Antrags ist beendet.")
        return redirect("verfahren:antrag", pk=pk)
    form = KommentarFormular(request.POST)
    if form.is_valid():
        Kommentar.objects.create(antrag=antrag, mitglied=request.user, text=form.cleaned_data["text"])
        messages.success(request, "Ihr Beitrag ist veröffentlicht.")
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def abstimmen(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()
    stichtag = antrag.phase_beginn.date()
    if not request.user.ist_stimmberechtigt(
        Gegenstand.SACHFRAGE, stichtag, uebergang=settings.DDOE_UEBERGANGSREGEL
    ):
        return render(request, "verfahren/nicht_stimmberechtigt.html", status=403)
    wahl = request.POST.get("stimme", "")
    try:
        stimme_abgeben(antrag, request.user, wahl)
        messages.success(request, "Ihre Stimme ist erfasst — bis zum Fristende können Sie sie ändern.")
    except (StimmabgabeFehler, ValueError):
        messages.error(request, "Diese Stimme konnte nicht erfasst werden (läuft die Abstimmung noch?).")
    return redirect("verfahren:antrag", pk=pk)


def export_json(request, pk):
    """F-21/F-23: maschinenlesbarer Export zum unabhängigen Nachrechnen —
    kompatibel mit verify/nachrechnen.py. Erst nach Abstimmungsende verfügbar,
    damit kein Zwischenstand die laufende Abstimmung beeinflusst."""
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()
    if antrag.phase not in (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value):
        return JsonResponse({"fehler": "Export erst nach Abstimmungsende (§ 5 Abs 3 lit d)."}, status=409)
    daten = {
        "antrag": antrag.pk,
        "titel": antrag.titel,
        "policy": antrag.policy_snapshot,
        "stimmberechtigte": antrag.stimmberechtigte_anzahl,
        "stimmen": [
            {"pseudonym": s.pseudonym.hex, "stimme": s.stimme}
            for s in antrag.stimmabgaben.order_by("pseudonym")
        ],
        "exportiert_am": timezone.now().isoformat(),
    }
    antwort = JsonResponse(daten, json_dumps_params={"ensure_ascii": False, "indent": 1})
    antwort["Content-Disposition"] = f'attachment; filename="antrag-{antrag.pk}-export.json"'
    return antwort


def eigene_stimme(request, pk):
    """Zeigt dem eingeloggten Mitglied Pseudonym und Prüfcode der eigenen Stimme
    (F-21: 'meine Stimme steht korrekt in der Liste')."""
    antrag = get_object_or_404(Antrag, pk=pk)
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    eintrag = StimmRegister.objects.filter(antrag=antrag, mitglied=request.user).first()
    return render(request, "verfahren/eigene_stimme.html", {"antrag": antrag, "eintrag": eintrag})
