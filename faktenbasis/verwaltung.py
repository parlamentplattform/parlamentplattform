"""Ausdrücklich ausgelöste amtliche Einzelabrufe mit bestehenden Verwaltungsrechten."""

from functools import wraps

from django import forms
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_http_methods, require_POST

from faktenbasis import importieren, volltext
from faktenbasis.models import Norm
from faktenbasis.ris import RisFehler
from mitglieder.models import Identitaetsstufe
from mitglieder.verwaltung import nur_admins
from parameter.models import zahl
from verfahren.models import AuditEintrag


def darf_aktualisieren(mitglied):
    return (
        mitglied.is_authenticated and mitglied.hat_adminrechte and mitglied.darf_mitwirken
        and not mitglied.testkonto and mitglied.identitaetsstufe != Identitaetsstufe.UNGEPRUEFT
        and not mitglied.adresswechsel_offen
    )


def nur_quellenverwaltung(ansicht):
    @wraps(ansicht)
    @nur_admins
    def innen(request, *args, **kwargs):
        if not darf_aktualisieren(request.user):
            return render(request, "mitglieder/verwaltung_kein_zugang.html", status=403)
        return ansicht(request, *args, **kwargs)
    return innen


class QuellenFormular(forms.Form):
    gesetzesnummer = forms.RegexField(
        regex=r"\A[0-9]{8}\Z", max_length=8,
        label=gettext_lazy("Gesetzesnummer"),
        help_text=gettext_lazy("Die achtstellige Gesetzesnummer aus dem RIS, keine Dokumentnummer oder Internetadresse."),
        error_messages={"invalid": gettext_lazy("Bitte genau acht Ziffern eingeben.")},
        widget=forms.TextInput(attrs={"inputmode": "numeric", "pattern": "[0-9]{8}"}),
    )
    stand = forms.DateField(
        label=gettext_lazy("Stichtag"), input_formats=["%Y-%m-%d"],
        widget=forms.DateInput(format="%Y-%m-%d", attrs={"type": "date"}),
    )


def _audit(request, aktion, **daten):
    AuditEintrag.anhaengen({"typ": "verwaltung", "aktion": aktion, "durch": request.user.pk, **daten})


def _fehlermeldung(request, fehler):
    if fehler.code == "abruf_belegt":
        text = _("Ein Quellenabruf läuft noch oder ist gerade beendet worden. Bitte kurz warten.")
    elif fehler.code == "abruf_kontingent":
        text = _("Das gemeinsame Stundenkontingent für Quellenabrufe ist ausgeschöpft oder gesperrt.")
    else:
        text = _("Die Quelle konnte nicht übernommen werden. Bereits gespeicherte Angaben bleiben erhalten.")
    messages.warning(request, f"{text} ({fehler.code})")


@never_cache
@nur_quellenverwaltung
@require_http_methods(["GET", "POST"])
def metadaten(request):
    formular = QuellenFormular(request.POST if request.method == "POST" else None,
                              initial={"stand": timezone.localdate()})
    if request.method == "POST" and formular.is_valid():
        nummer, stand = formular.cleaned_data["gesetzesnummer"], formular.cleaned_data["stand"]
        daten = {"gesetzesnummer": nummer, "stand": stand.isoformat()}
        try:
            lauf = importieren.importieren(nummer, stand)
        except RisFehler as fehler:
            _audit(request, "faktenbasis_metadaten", **daten, erfolgreich=False, fehlercode=fehler.code)
            _fehlermeldung(request, fehler)
        else:
            _audit(request, "faktenbasis_metadaten", **daten, erfolgreich=True, importlauf=lauf.pk)
            messages.success(request, _("Metadaten übernommen: %(gelesen)s Dokumente gelesen, %(neu)s neue Schnappschüsse.")
                             % {"gelesen": lauf.gelesen, "neu": lauf.neu})
        return redirect("faktenbasis:index")
    return render(request, "faktenbasis/verwaltung.html", {
        "formular": formular, "stundenkontingent": max(0, zahl("faktenbasis-manuelle-abrufe-je-stunde", 10)),
    })


@never_cache
@nur_quellenverwaltung
@require_POST
def dokumenttext(request, pk):
    norm = get_object_or_404(Norm, pk=pk)
    try:
        lauf = volltext.importieren(norm)
    except RisFehler as fehler:
        _audit(request, "faktenbasis_dokumenttext", norm=norm.pk, erfolgreich=False, fehlercode=fehler.code)
        _fehlermeldung(request, fehler)
    else:
        _audit(request, "faktenbasis_dokumenttext", norm=norm.pk, abruf=lauf.pk, erfolgreich=True)
        messages.success(request, _("Der amtliche Dokumenttext wurde übernommen. Frühere Texte bleiben erhalten."))
    return redirect("faktenbasis:norm", pk=norm.pk)
