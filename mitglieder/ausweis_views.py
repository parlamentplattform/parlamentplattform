"""Der Mitgliedsausweis im Web (FB-K8): der eigene Ausweis zum Herunterladen und die öffentliche
Prüfseite, auf die der QR-Code der Karte führt.

Die Prüfseite nennt keinen Namen — sie bestätigt nur, dass zu Nummer und Code eine bestehende
Mitgliedschaft mit geprüfter Identität gehört (oder eben nicht). Wer die Karte in der Hand hat,
vergleicht Nummer und Person selbst; wer die Adresse errät, erfährt nichts über einen Menschen.
"""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import formats, timezone, translation
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache

from mitglieder.ausweis import STUFE_KURZ, ausweis_gueltig, ausweis_moeglich, ausweis_pdf, dateiname
from mitglieder.models import Mitglied


@login_required
@never_cache
def ausweis_pdf_view(request):
    """Der eigene Ausweis als PDF — nur für das angemeldete Konto, nur mit geprüfter Identität."""
    mitglied = request.user
    if not ausweis_moeglich(mitglied):
        messages.info(request, _("Ihren Mitgliedsausweis gibt es mit der Freischaltung — sobald Ihre Identität geprüft ist."))
        return redirect("mitglieder:profil")
    antwort = HttpResponse(ausweis_pdf(mitglied), content_type="application/pdf")
    antwort["Content-Disposition"] = f'attachment; filename="{dateiname(mitglied)}"'
    return antwort


@never_cache
def ausweis_pruefen(request, nummer: int, code: str):
    """Die Prüfseite hinter dem QR-Code: gültig oder nicht — ohne Personenbezug."""
    mitglied = Mitglied.objects.filter(pk=nummer).first()
    gueltig = ausweis_gueltig(mitglied, code)
    angaben = None
    if gueltig:
        with translation.override(None):
            beitritt = mitglied.beitritt or timezone.localdate(mitglied.ausweis_ausgestellt_am)
        angaben = {
            "seit": formats.date_format(beitritt, "F Y"),
            "stufe": STUFE_KURZ.get(mitglied.identitaetsstufe, _("geprüft")),
        }
    return render(
        request,
        "mitglieder/ausweis_pruefen.html",
        {"nummer": f"{nummer:06d}", "gueltig": gueltig, "angaben": angaben, "heute": timezone.localdate()},
    )
