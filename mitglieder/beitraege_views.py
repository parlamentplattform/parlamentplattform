"""Beitragsseite und Beitragsverwaltung (F-59, § 4 Abs 3).

Bereich Mitglied: /beitrag/ — jederzeit erreichbarer QR-Kasten samt
„Ich habe überwiesen": Das ist der Moment, in dem sich ein Kontoabruf lohnt,
also passiert er genau dann (Kontingent vorausgesetzt) — und bei Treffer ist
das Konto sofort freigeschaltet.

Bereich Verwaltung: /verwaltung/beitraege/ — Kopplungsstand, Prüfhinweise
(Absendername wich ab) und die Erinnerungsliste: alle, deren letzter Eingang
länger als zwölf Monate zurückliegt, mit Haken je Zeile oder gesamt —
versendet wird erst auf Knopfdruck, entschieden von Menschen.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db.models import Q
from django.shortcuts import redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from mitglieder import bank
from mitglieder.auth_flows import beitragsreferenz
from mitglieder.models import Bankkopplung, Beitragseingang, Mitglied, Mitgliedsstatus
from mitglieder.verwaltung import nur_admins
from mitglieder.views import BEITRAG_RICHTWERT, IBAN, _beitrags_qr

ABGLEICH_MINDESTABSTAND = 180  # Sekunden zwischen zwei mitglieder-ausgelösten Abrufen
VERWALTUNG_NACHHOLFRIST = 6 * 3600  # Verwaltungsbesuch holt einen Abgleich nach, wenn älter


def _beitrags_kontext(nutzer) -> dict:
    referenz = beitragsreferenz(nutzer)
    return {
        "referenz": referenz,
        "iban": IBAN,
        "richtwert": BEITRAG_RICHTWERT,
        "qr_svg": _beitrags_qr(referenz),
    }


def beitrag(request):
    """Die dauerhafte Bezahlseite — aus dem Hauptmenü jederzeit erreichbar."""
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    kopplung = Bankkopplung.aktuelle() if bank.eingerichtet() else None
    return render(
        request,
        "mitglieder/beitrag.html",
        {
            **_beitrags_kontext(request.user),
            "eingaenge": request.user.beitraege.all()[:10],
            "abgleich_aktiv": kopplung is not None,
        },
    )


def _abstand_gewahrt(kopplung: Bankkopplung | None, sekunden: int) -> bool:
    if kopplung is None or kopplung.zuletzt_abgerufen is None:
        return True
    return (timezone.now() - kopplung.zuletzt_abgerufen).total_seconds() >= sekunden


@require_POST
def beitrag_gemeldet(request):
    """„Ich habe überwiesen" — der gezielte Abgleich im richtigen Moment."""
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    kopplung = Bankkopplung.aktuelle()
    if not bank.eingerichtet() or kopplung is None:
        messages.info(
            request,
            _("Danke für die Meldung! Der automatische Abgleich ist noch nicht eingerichtet — Eingänge werden derzeit von der Verwaltung geprüft."),
        )
        return redirect("mitglieder:beitrag")
    if not _abstand_gewahrt(kopplung, ABGLEICH_MINDESTABSTAND):
        messages.info(request, _("Der letzte Abgleich ist keine drei Minuten her — bitte gleich noch einmal versuchen."))
        return redirect("mitglieder:beitrag")

    vorher = set(request.user.beitraege.values_list("pk", flat=True))
    _neu, meldung = bank.abgleich_ausfuehren()
    if request.user.beitraege.exclude(pk__in=vorher).exists():
        messages.success(
            request,
            _("Ihre Zahlung ist angekommen und verbucht — Ihre Mitwirkungsrechte sind aktiv. Danke!"),
        )
    elif meldung == "kontingent_erschoepft":
        messages.info(
            request,
            _("Die Bank erlaubt nur wenige Abrufe pro Tag und das heutige Kontingent ist verbraucht — Ihr Eingang wird beim nächsten Abgleich automatisch erkannt."),
        )
    elif meldung.startswith("abruf_gescheitert"):
        messages.info(
            request,
            _("Die Bank war gerade nicht erreichbar — wir gleichen automatisch wieder ab, Ihr Eingang geht nicht verloren."),
        )
    else:
        messages.info(
            request,
            _("Noch kein Eingang mit Ihrer Referenz sichtbar — je nach Bank dauert eine Überweisung Sekunden (Echtzeit) bis einen Bankarbeitstag. Wir prüfen automatisch weiter."),
        )
    return redirect("mitglieder:beitrag")


@nur_admins
def verwaltung_beitraege(request):
    kopplung = Bankkopplung.aktuelle()

    # Nachholender Abgleich: Wer die Beitragsverwaltung öffnet, will aktuelle Zahlen.
    if kopplung and _abstand_gewahrt(kopplung, VERWALTUNG_NACHHOLFRIST) and kopplung.abruf_erlaubt():
        bank.abgleich_ausfuehren()
        kopplung.refresh_from_db()

    grenze = timezone.localdate() - timezone.timedelta(days=365)
    faellige = (
        Mitglied.objects.filter(is_active=True)
        .exclude(status=Mitgliedsstatus.AUSGESCHLOSSEN)
        .filter(Q(beitrag_zuletzt_am__lt=grenze) | Q(beitrag_zuletzt_am=None))
        .order_by("beitrag_zuletzt_am", "date_joined")
    )
    institutionen, institutionen_fehler = [], False
    if bank.eingerichtet() and kopplung is None:
        try:
            institutionen = bank.institutionen()
        except Exception:  # noqa: BLE001 — Auswahl ist Komfort; das Textfeld bleibt
            institutionen_fehler = True
    return render(
        request,
        "mitglieder/verwaltung_beitraege.html",
        {
            "kopplung": kopplung,
            "eingerichtet": bank.eingerichtet(),
            "institutionen": institutionen,
            "institutionen_fehler": institutionen_fehler,
            "faellige": faellige,
            "grenze": grenze,
            "hinweise": Beitragseingang.objects.filter(namens_hinweis=True).select_related("mitglied")[:20],
            "letzte": Beitragseingang.objects.select_related("mitglied")[:15],
        },
    )


@nur_admins
@require_POST
def beitrag_erinnern(request):
    """Erinnerungsmail an ausgewählte oder alle fälligen Mitglieder — auf Knopfdruck."""
    grenze = timezone.localdate() - timezone.timedelta(days=365)
    faellige = (
        Mitglied.objects.filter(is_active=True)
        .exclude(status=Mitgliedsstatus.AUSGESCHLOSSEN)
        .filter(Q(beitrag_zuletzt_am__lt=grenze) | Q(beitrag_zuletzt_am=None))
    )
    if not request.POST.get("alle"):
        ids = request.POST.getlist("mitglied")
        faellige = faellige.filter(pk__in=ids)

    versendet, gescheitert = 0, 0
    for m in faellige:
        try:
            send_mail(
                "Erinnerung: Ihr Mitgliedsbeitrag bei der DDÖ",
                f"Guten Tag {m.first_name or m.anzeigename}!\n\n"
                "Ihr letzter Mitgliedsbeitrag liegt länger als zwölf Monate zurück "
                "(oder es ist noch keiner eingegangen). Die Höhe bleibt Ihre "
                "Selbsteinschätzung — niemand wird aus finanziellen Gründen "
                "ausgeschlossen (§ 4 Abs 3).\n\n"
                "Am schnellsten geht es mit dem QR-Code auf Ihrer Beitragsseite:\n"
                f"{settings.DDOE_BASIS_URL}/beitrag/\n\n"
                f"Ihre persönliche Referenz: {beitragsreferenz(m)}\n\n"
                "Danke, dass Sie das Werkzeug mittragen!\n"
                "Direkte Demokratie Österreich",
                settings.DEFAULT_FROM_EMAIL,
                [m.email],
            )
            versendet += 1
        except OSError:
            gescheitert += 1
    if versendet:
        from mitglieder.verwaltung import _auditieren

        _auditieren(request, "beitrag_erinnerung", request.user, anzahl=versendet)
        messages.success(request, _("%d Erinnerung(en) versendet.") % versendet)
    if gescheitert:
        messages.error(request, _("%d Erinnerung(en) konnten nicht versendet werden (Mailserver).") % gescheitert)
    if not versendet and not gescheitert:
        messages.info(request, _("Niemand ausgewählt."))
    return redirect("mitglieder:verwaltung_beitraege")


@nur_admins
@require_POST
def auszug_hochladen(request):
    """Kontoauszug-Upload (camt.053 oder CSV aus dem Online-Banking) — der Weg
    ohne Drittanbieter: gleiche Zuordnung, gleiche Verbuchung, gleiche Hinweise.
    Die Datei wird nur gelesen, nie gespeichert."""
    datei = request.FILES.get("auszug")
    if datei is None:
        messages.error(request, _("Keine Datei ausgewählt."))
        return redirect("mitglieder:verwaltung_beitraege")
    if datei.size > 5 * 1024 * 1024:
        messages.error(request, _("Die Datei ist größer als 5 MB — bitte einen kürzeren Zeitraum exportieren."))
        return redirect("mitglieder:verwaltung_beitraege")
    roh = datei.read()
    try:
        inhalt = roh.decode("utf-8-sig")
    except UnicodeDecodeError:
        inhalt = roh.decode("latin-1")

    from plattform_core.bankauszug import auszug_lesen

    umsaetze = auszug_lesen(inhalt)
    if not umsaetze:
        messages.error(request, _("Aus der Datei ließ sich kein Umsatz lesen — erwartet wird ein camt.053-XML oder ein Umsatz-CSV mit Kopfzeile."))
        return redirect("mitglieder:verwaltung_beitraege")
    neu, gesamt = bank.verbuchen_aus_umsaetzen(umsaetze)
    from mitglieder.verwaltung import _auditieren

    _auditieren(request, "auszug_abgleich", request.user, umsaetze=len(umsaetze), verbucht=neu)
    messages.success(
        request,
        _("Auszug gelesen: %(umsaetze)d Umsätze, %(gesamt)d mit Beitragsreferenz, %(neu)d neu verbucht.")
        % {"umsaetze": len(umsaetze), "gesamt": gesamt, "neu": neu},
    )
    return redirect("mitglieder:verwaltung_beitraege")


@nur_admins
@require_POST
def bank_koppeln(request):
    institution = request.POST.get("institution_id", "").strip()
    if not bank.eingerichtet():
        messages.error(request, _("Die Dienst-Schlüssel (DDOE_BANK_SECRET_ID/KEY) sind noch nicht gesetzt."))
        return redirect("mitglieder:verwaltung_beitraege")
    if not institution:
        messages.error(request, _("Bitte eine Bank auswählen."))
        return redirect("mitglieder:verwaltung_beitraege")
    try:
        link = bank.kopplung_starten(institution)
    except Exception:  # noqa: BLE001 — Netz-/Dienststörung ehrlich melden
        messages.error(request, _("Der Kontoinformationsdienst war nicht erreichbar — bitte später erneut versuchen."))
        return redirect("mitglieder:verwaltung_beitraege")
    return redirect(link)


@nur_admins
def bank_rueckkehr(request):
    try:
        kopplung = bank.kopplung_abschliessen()
    except Exception:  # noqa: BLE001
        kopplung = None
    if kopplung:
        messages.success(
            request,
            _("Bankkonto gekoppelt — Zustimmung gültig bis %s. Der Abgleich läuft ab jetzt automatisch.")
            % kopplung.consent_bis.strftime("%d.%m.%Y"),
        )
    else:
        messages.error(request, _("Die Kopplung wurde nicht abgeschlossen — bitte erneut starten."))
    return redirect("mitglieder:verwaltung_beitraege")


@nur_admins
@require_POST
def verwaltung_abgleichen(request):
    neu, meldung = bank.abgleich_ausfuehren(erzwungen=True)
    if meldung == "ok":
        messages.success(request, _("Abgleich ausgeführt — %d neue(r) Eingang/Eingänge verbucht.") % neu)
    elif meldung == "kontingent_erschoepft":
        messages.info(request, _("Das heutige Abruf-Kontingent der Bank (4) ist verbraucht — morgen geht es weiter."))
    elif meldung == "keine_kopplung":
        messages.info(request, _("Noch kein Bankkonto gekoppelt."))
    else:
        messages.error(request, _("Abruf gescheitert — die Bank oder der Dienst war nicht erreichbar."))
    return redirect("mitglieder:verwaltung_beitraege")
