"""Der Mitgliedsausweis im Web (FB-K8): der eigene Ausweis zum Herunterladen und die öffentliche
Prüfseite, auf die der QR-Code der Karte führt.

Die Prüfseite nennt keinen Namen — sie bestätigt nur, dass zu Nummer und Code eine bestehende
Mitgliedschaft mit geprüftem Nachweis gehört (oder eben nicht). Wer die Karte in der Hand hat,
vergleicht Nummer und Person selbst; wer die Adresse errät, erfährt nichts über einen Menschen.
"""

from __future__ import annotations

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.utils import formats, timezone
from django.utils.translation import gettext as _
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from mitglieder.ausweis import (
    STUFE_KURZ,
    ausweis_erstellbar,
    ausweis_gueltig,
    ausweis_moeglich,
    ausweis_pdf,
    dateiname,
)
from mitglieder.models import Identitaetsstufe, Mitglied

log = logging.getLogger(__name__)


@login_required
@never_cache
def ausweis_pdf_view(request):
    """Der eigene Ausweis als PDF — nur für das angemeldete Konto, nur mit geprüftem Nachweis und
    einem Namen auf der Karte. Scheitert die Zeichnung, sagt es das Profil — kein Fehlerbild."""
    mitglied = request.user
    if not ausweis_erstellbar(mitglied):
        if ausweis_moeglich(mitglied):
            messages.info(
                request,
                _("Für den Mitgliedsausweis braucht es einen Namen auf der Karte — ergänzen Sie Vor- und Nachname in den Stammdaten."),
            )
        else:
            messages.info(request, _("Ihren Mitgliedsausweis gibt es mit der Freischaltung — sobald Ihre Identität geprüft ist."))
        return redirect("mitglieder:profil")
    try:
        pdf = ausweis_pdf(mitglied)
    except (OSError, ValueError):
        log.exception("Mitgliedsausweis für Mitglied %s nicht erzeugbar.", mitglied.pk)
        messages.error(
            request,
            _("Der Mitgliedsausweis lässt sich gerade nicht erzeugen; die Störung ist protokolliert. Versuchen Sie es später noch einmal."),
        )
        return redirect("mitglieder:profil")
    antwort = HttpResponse(pdf, content_type="application/pdf")
    antwort["Content-Disposition"] = f'attachment; filename="{dateiname(mitglied)}"'
    return antwort


@never_cache
def ausweis_pruefen(request, nummer: int, code: str):
    """Die Prüfseite hinter dem QR-Code: gültig oder nicht — ohne Personenbezug. Datum und Nachweis
    in der Sprache der Seite."""
    mitglied = Mitglied.objects.filter(pk=nummer).first() if 0 < nummer < 2**63 else None
    gueltig = ausweis_gueltig(mitglied, code)
    import secrets
    ausstaendig = bool(mitglied and ausweis_moeglich(mitglied)
        and mitglied.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT
        and mitglied.ausweis_code and code.isascii()
        and secrets.compare_digest(mitglied.ausweis_code.encode(), code.encode()))
    angaben = None
    if gueltig:
        beitritt = mitglied.beitritt or timezone.localdate(mitglied.ausweis_ausgestellt_am)
        stufe = STUFE_KURZ.get(mitglied.identitaetsstufe)
        angaben = {"seit": formats.date_format(beitritt, "F Y"), "stufe": _(stufe) if stufe else _("geprüft")}
    return render(
        request,
        "mitglieder/ausweis_pruefen.html",
        {
            "nummer": mitglied.mitgliedsnummer_text if (gueltig or ausstaendig) else "—",
            "gueltig": gueltig,
            "ausstaendig": ausstaendig,
            "angaben": angaben,
            "heute": formats.date_format(timezone.localdate(), "SHORT_DATE_FORMAT"),
        },
    )


@login_required
@never_cache
@require_POST
def ausweis_probe(request):
    """Eigene Mailvorschau; keine Empfängerparameter und keine fremden Konten."""
    from mitglieder.postausgang import AUSWEIS_VORSCHAU, beauftragen

    if not ausweis_erstellbar(request.user):
        messages.error(request, _("Für den Probeversand muss Ihr eigener Ausweis im Profil verfügbar sein."))
    elif beauftragen(request.user, AUSWEIS_VORSCHAU):
        messages.success(request, _("Die Ausweis-Vorschau ist zum Versand an Ihre hinterlegte E-Mail-Adresse vorgemerkt."))
    else:
        messages.info(request, _("Die Ausweis-Vorschau wurde bereits angefordert."))
    return redirect("mitglieder:profil")
