"""Mandatare-Ansichten (M1, F-71): öffentliche Seite und Verwaltung.

Öffentlich: Liste und Detailseite je Mandatar — Foto, aktuelle Aufgaben und
Entscheidungsprozesse samt Fristen, verknüpfte Abstimmungen. Ohne Mandat
zeigt die Seite ehrlich den Stand: Die Wahl der Kandidaten läuft bereits
über das Parlament (F-70). Die Pflege übernimmt vorerst die Verwaltung
(deutsch, wie die gesamte Verwaltung); die Mandatar-Rolle folgt mit M2."""

from django import forms
from django.contrib import messages
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from mandatare.models import FOTO_HOECHSTGROESSE, Aufgabe, Aufgabenstatus, Mandat, foto_typ_erkennen
from mitglieder.models import Mitglied, Mitgliedsstatus
from mitglieder.verwaltung import nur_admins
from plattform_core import Phase
from verfahren.models import Antrag, Antragsart, AuditEintrag

LAUFEND = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]


def _aufgaben_sortiert(mandat):
    """Offene und laufende Aufgaben zuerst, innerhalb dessen die nächste Frist
    vorn (ohne Frist zuletzt); Erledigtes am Ende."""
    alle = list(mandat.aufgaben.select_related("antrag"))
    fern = timezone.localdate().replace(year=timezone.localdate().year + 100)
    return sorted(
        alle,
        key=lambda a: (a.status == Aufgabenstatus.ERLEDIGT, a.frist or fern, -a.pk),
    )


def liste(request):
    mandate = list(
        Mandat.objects.filter(beendet__isnull=True)
        .select_related("mitglied")
        .prefetch_related("aufgaben")
    )
    fuer_karten = [
        {
            "mandat": m,
            "aufgaben": [a for a in _aufgaben_sortiert(m) if a.status != Aufgabenstatus.ERLEDIGT][:2],
        }
        for m in mandate
    ]
    kandidaturen = (
        Antrag.objects.filter(art=Antragsart.MANDAT, phase__in=LAUFEND).order_by("phase_beginn")[:6]
    )
    return render(
        request,
        "mandatare/liste.html",
        {
            "karten": fuer_karten,
            "ehemalige": Mandat.objects.filter(beendet__isnull=False).count(),
            "kandidaturen": kandidaturen,
        },
    )


def detail(request, pk: int):
    mandat = get_object_or_404(Mandat.objects.select_related("mitglied"), pk=pk)
    return render(
        request,
        "mandatare/detail.html",
        {"mandat": mandat, "aufgaben": _aufgaben_sortiert(mandat)},
    )


def foto(request, pk: int):
    mandat = get_object_or_404(Mandat, pk=pk)
    if not mandat.foto:
        raise Http404("Kein Foto hinterlegt.")
    antwort = HttpResponse(bytes(mandat.foto), content_type=mandat.foto_typ or "image/jpeg")
    antwort["Cache-Control"] = "public, max-age=3600"
    return antwort


# --- Verwaltung (bewusst nur deutsch, wie die gesamte Verwaltung) -----------------


class MandatFormular(forms.Form):
    mitglied = forms.ModelChoiceField(
        queryset=Mitglied.objects.filter(is_active=True, status=Mitgliedsstatus.AKTIV).order_by(
            "last_name", "first_name", "username"
        ),
        label="Mitglied",
    )
    bezeichnung = forms.CharField(label="Mandat", max_length=120)
    ebene = forms.ChoiceField(label="Ebene", choices=[])
    gebiet = forms.CharField(label="Gebiet", max_length=120, required=False)
    angetreten = forms.DateField(label="Angetreten am", initial=timezone.localdate)
    vorstellung = forms.CharField(
        label="Vorstellung (öffentlich)", widget=forms.Textarea(attrs={"rows": 3}), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from verfahren.models import Ebene

        self.fields["ebene"].choices = Ebene.choices


@nur_admins
def verwaltung(request):
    form = MandatFormular()
    mandate = Mandat.objects.select_related("mitglied").prefetch_related("aufgaben")
    return render(request, "mandatare/verwaltung.html", {"form": form, "mandate": mandate})


@nur_admins
@require_POST
def verwaltung_aktion(request):
    """Eine Verwaltungsseite, mehrere kleine Handlungen — jede auditiert."""
    aktion = request.POST.get("aktion", "")

    if aktion == "anlegen":
        form = MandatFormular(request.POST)
        if not form.is_valid():
            messages.error(request, "Bitte alle Pflichtfelder prüfen.")
            return redirect("mandatare:verwaltung")
        d = form.cleaned_data
        mandat = Mandat.objects.create(
            mitglied=d["mitglied"],
            bezeichnung=d["bezeichnung"],
            ebene=d["ebene"],
            gebiet=d["gebiet"],
            angetreten=d["angetreten"],
            vorstellung=d["vorstellung"],
        )
        AuditEintrag.anhaengen(
            {"typ": "mandat_angelegt", "mandat": mandat.pk, "bezeichnung": mandat.bezeichnung}
        )
        messages.success(request, f"Mandat „{mandat.bezeichnung}“ angelegt — öffentlich sichtbar.")

    elif aktion == "beenden":
        mandat = get_object_or_404(Mandat, pk=request.POST.get("mandat"))
        mandat.beendet = timezone.localdate()
        mandat.save(update_fields=["beendet"])
        AuditEintrag.anhaengen({"typ": "mandat_beendet", "mandat": mandat.pk})
        messages.info(request, f"Mandat „{mandat.bezeichnung}“ als beendet vermerkt — bleibt dokumentiert.")

    elif aktion == "foto":
        mandat = get_object_or_404(Mandat, pk=request.POST.get("mandat"))
        datei = request.FILES.get("foto")
        if datei is None or datei.size > FOTO_HOECHSTGROESSE:
            messages.error(request, "Bitte ein Bild bis 800 kB wählen (JPEG, PNG oder WebP).")
            return redirect("mandatare:verwaltung")
        daten = datei.read()
        typ = foto_typ_erkennen(daten)
        if typ is None:
            messages.error(request, "Dateityp nicht erkannt — erlaubt sind JPEG, PNG und WebP.")
            return redirect("mandatare:verwaltung")
        mandat.foto = daten
        mandat.foto_typ = typ
        mandat.save(update_fields=["foto", "foto_typ"])
        messages.success(request, "Foto gespeichert.")

    elif aktion == "aufgabe":
        mandat = get_object_or_404(Mandat, pk=request.POST.get("mandat"))
        titel = (request.POST.get("titel") or "").strip()
        if not titel:
            messages.error(request, "Die Aufgabe braucht einen Titel.")
            return redirect("mandatare:verwaltung")
        antrag = None
        antrag_pk = (request.POST.get("antrag") or "").strip()
        if antrag_pk.isdigit():
            antrag = Antrag.objects.filter(pk=int(antrag_pk)).first()
        frist = None
        if request.POST.get("frist"):
            frist = forms.DateField().clean(request.POST["frist"])
        aufgabe = Aufgabe.objects.create(
            mandat=mandat,
            titel=titel[:200],
            beschreibung=(request.POST.get("beschreibung") or "")[:4000],
            frist=frist,
            antrag=antrag,
        )
        AuditEintrag.anhaengen({"typ": "mandats_aufgabe", "mandat": mandat.pk, "aufgabe": aufgabe.pk})
        messages.success(request, f"Aufgabe „{aufgabe.titel}“ veröffentlicht.")

    elif aktion == "aufgabe_status":
        aufgabe = get_object_or_404(Aufgabe, pk=request.POST.get("aufgabe"))
        status = request.POST.get("status", "")
        if status in Aufgabenstatus.values:
            aufgabe.status = status
            aufgabe.save(update_fields=["status", "aktualisiert_am"])
            messages.success(request, f"Aufgabe „{aufgabe.titel}“: {aufgabe.get_status_display()}.")

    return redirect("mandatare:verwaltung")
