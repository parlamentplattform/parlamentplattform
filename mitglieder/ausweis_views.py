"""Der Mitgliedsausweis im Web (FB-K8): der eigene Ausweis zum Herunterladen und die öffentliche
Prüfseite, auf die der QR-Code der Karte führt.

Die Prüfseite nennt keinen Namen — sie bestätigt nur, dass zur Adresse eine bestehende
Mitgliedschaft mit geprüftem Nachweis gehört (oder eben nicht). Wer die Karte in der Hand hat,
vergleicht Nummer und Person selbst; wer die Adresse errät, erfährt nichts über einen Menschen.

Zwei Adressformen (GP-091): Neue Karten tragen allein einen Zufallsschlüssel; gedruckte Karten mit
Konto-ID und Prüfcode gelten weiter. Beide Routen heißen gleich — der Anstoß speichert zu Routen
mit Kennung nur den Routennamen.
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
    ausweis_moeglich,
    ausweis_pdf,
    ausweis_stand,
    code_passt,
    dateiname,
    mitglied_zum_schluessel,
)
from mitglieder.models import Mitglied

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
    """Die Prüfseite hinter dem QR-Code gedruckter Karten (alte Adressform mit Konto-ID und Code):
    gültig oder nicht — ohne Personenbezug."""
    mitglied = Mitglied.objects.filter(pk=nummer).first() if 0 < nummer < 2**63 else None
    return _pruefseite(request, mitglied if code_passt(mitglied, code) else None)


@never_cache
def ausweis_pruefen_schluessel(request, schluessel: str):
    """Die Prüfseite hinter dem QR-Code neuer Karten: Die Adresse trägt allein den Zufallsschlüssel."""
    return _pruefseite(request, mitglied_zum_schluessel(schluessel))


def _pruefseite(request, mitglied):
    """`mitglied`: das Konto, dessen Code oder Schlüssel gestimmt hat — sonst None. Datum und
    Nachweis in der Sprache der Seite."""
    stand = ausweis_stand(mitglied) if mitglied is not None else "ungueltig"
    gueltig, ausstaendig = stand == "gueltig", stand == "ausstaendig"
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
