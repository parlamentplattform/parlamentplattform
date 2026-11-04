"""Freiwilliger Gemeindezugang ohne Parteibeitritt (ADR-016)."""

import logging
from smtplib import SMTPException

from django import forms
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from mitglieder.auth_flows import EinmalToken
from mitglieder.botschutz import BotschutzMixin, drossel_zuviel
from mitglieder.mail import send_mail
from mitglieder.models import Gemeinde, Gemeindezugang, Mitglied, Wohnsitzart
from mitglieder.wohnsitz import WohnsitzFormularMixin, wohnsitz_anwenden, wohnsitz_auswahl
from plattform_core.gemeindezugang import mindestens_sechzehn

log = logging.getLogger(__name__)


class OrtsFormular(WohnsitzFormularMixin, forms.Form):
    wohnsitz_pflicht = True
    wohnsitz_art = wohnsitz_auswahl(registrierung=True)
    gemeinde = forms.CharField(
        label=gettext_lazy("Hauptwohnsitz-Gemeinde"), required=False, max_length=140,
        widget=forms.TextInput(attrs={"list": "gemeinden", "autocomplete": "off"}),
    )
    meldung = forms.BooleanField(label=gettext_lazy(
        "Die Angaben entsprechen meinem tatsächlich gemeldeten Hauptwohnsitz."
    ))


class ZugangsFormular(OrtsFormular):
    geburtsdatum = forms.DateField(
        label=gettext_lazy("Geburtsdatum"), widget=forms.DateInput(attrs={"type": "date"}, format="%Y-%m-%d"),
        help_text=gettext_lazy("Nur zur Prüfung der Altersgrenze bei der Anmeldung; wird nicht gespeichert."),
    )
    datenschutz = forms.BooleanField(label=gettext_lazy(
        "Ich habe die Hinweise zum Gemeindekonto und zum Datenschutz gelesen."
    ))

    def clean_geburtsdatum(self):
        datum = self.cleaned_data["geburtsdatum"]
        if not mindestens_sechzehn(datum, timezone.localdate()):
            raise forms.ValidationError(_("Der Gemeindezugang ist ab dem vollendeten 16. Lebensjahr möglich."))
        return datum

    def clean(self):
        daten = super().clean()
        if daten.get("wohnsitz_art") != Wohnsitzart.OESTERREICH or self.gemeinde_objekt is None:
            self.add_error("gemeinde", _("Für die Gemeindeanmeldung ist ein tatsächlich gemeldeter Hauptwohnsitz in einer österreichischen Gemeinde erforderlich."))
        return daten


class AnmeldeFormular(BotschutzMixin, ZugangsFormular):
    field_order = ["email", "anzeigename", "wohnsitz_art", "gemeinde", "geburtsdatum",
                   "meldung", "datenschutz", "rechenfrage", "website", "pruefung"]
    email = forms.EmailField(label=gettext_lazy("E-Mail-Adresse"), max_length=150)
    anzeigename = forms.CharField(label=gettext_lazy("Anzeigename"), max_length=120)

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if Mitglied.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(_("Für diese Adresse existiert bereits ein Konto — nutzen Sie den Login per E-Mail-Link."))
        return email


def bestaetigungslink_senden(request, konto):
    token = EinmalToken.ausstellen(konto, EinmalToken.Zweck.GEMEINDE)
    link = request.build_absolute_uri(reverse("gemeinde:bestaetigen", args=[token]))
    if send_mail(
        _("Gemeindekonto: E-Mail-Adresse bestätigen"),
        _("Guten Tag,\n\nmit diesem Link bestätigen Sie Ihren Gemeindezugang (gültig 48 Stunden):\n\n%(link)s\n\nSie treten dadurch keiner Partei bei. Es entstehen kein Mitgliedsbeitrag und keine Parteirechte. Die Bestätigung ist kein Identitäts- oder Meldenachweis.\n\nWenn Sie diese Anmeldung nicht veranlasst haben, ignorieren Sie diese Nachricht.") % {"link": link},
        None, [konto.email],
    ) != 1:
        raise OSError("Bestätigungsnachricht nicht angenommen")


def _gemeinden():
    return [g.anzeige for g in Gemeinde.objects.order_by("name", "kennziffer")]


@require_GET
def start(request):
    return render(request, "mitglieder/gemeinde_start.html")


@require_http_methods(["GET", "POST"])
@never_cache
def anmelden(request):
    if request.user.is_authenticated:
        return redirect("gemeinde:konto")
    form = AnmeldeFormular(request.POST if request.method == "POST" else None, request=request)
    if request.method == "POST":
        if drossel_zuviel(request, "registrierung", limit=5):
            form.add_error(None, _("Zu viele Versuche von dieser Verbindung — bitte in einer Stunde erneut."))
        elif form.is_valid():
            try:
                with transaction.atomic():
                    # username ist bereits datenbankweit eindeutig, auch bei paralleler Anmeldung.
                    d = form.cleaned_data
                    konto = Mitglied(
                        username=d["email"], email=d["email"], parteikonto=False,
                        is_active=False, klarname_oeffentlich=False,
                        pseudonym_oeffentlich=d["anzeigename"],
                    )
                    wohnsitz_anwenden(konto, form)
                    konto.set_unusable_password()
                    konto.save()
                    jetzt = timezone.now()
                    Gemeindezugang.objects.create(konto=konto, angemeldet_am=jetzt, alter_erklaert_am=jetzt)
                    bestaetigungslink_senden(request, konto)
            except IntegrityError:
                form.add_error("email", _("Für diese Adresse existiert bereits ein Konto — nutzen Sie den Login per E-Mail-Link."))
            except (SMTPException, OSError):
                log.warning("Gemeindeanmeldung wegen gestörtem Bestätigungsversand zurückgerollt.")
                form.add_error(None, _("Die Anmeldung wurde nicht gespeichert. Bitte versuchen Sie den E-Mail-Versand später erneut."))
            else:
                return render(request, "mitglieder/mail_gesendet.html", {"zweck": _("Bestätigung"), "email": d["email"]})
    return render(request, "mitglieder/gemeinde_formular.html", {"form": form, "gemeinden": _gemeinden(), "anmeldung": True})


@require_GET
@never_cache
@transaction.atomic
def bestaetigen(request, token):
    konto = EinmalToken.einloesen(token, EinmalToken.Zweck.GEMEINDE)
    if konto is None or konto.parteikonto:
        return render(request, "mitglieder/token_ungueltig.html", status=400)
    konto = Mitglied.objects.select_for_update().get(pk=konto.pk)
    zugang = get_object_or_404(Gemeindezugang, konto=konto)
    if zugang.bestaetigt_am is not None:
        return render(request, "mitglieder/token_ungueltig.html", status=400)
    konto.is_active = True
    konto.save(update_fields=["is_active"])
    zugang.bestaetigt_am = timezone.now()
    zugang.save(update_fields=["bestaetigt_am"])
    login(request, konto)
    messages.success(request, _("Ihr Gemeindekonto ist bestätigt. Sie sind keiner Partei beigetreten."))
    return redirect("gemeinde:konto")


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def konto(request):
    zugang = Gemeindezugang.objects.filter(konto=request.user, bestaetigt_am__isnull=False).first()
    formular = OrtsFormular if zugang else ZugangsFormular
    form = formular(request.POST if request.method == "POST" else None, initial={
        "wohnsitz_art": request.user.wohnsitz_art_aktuell,
        "gemeinde": request.user.wohnsitz.anzeige if request.user.wohnsitz_id else "",
    })
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            aktuell = Mitglied.objects.select_for_update().get(pk=request.user.pk)
            if aktuell.testkonto:
                return render(request, "mitglieder/token_ungueltig.html", status=403)
            geaendert = wohnsitz_anwenden(aktuell, form)
            aktuell.save(update_fields=["wohnsitz_art", "wohnsitz", "gemeinde", "bundesland"])
            if aktuell.parteikonto and geaendert:
                from verfahren.models import AuditEintrag

                AuditEintrag.anhaengen({"typ": "profil", "aktion": "stammdaten", "mitglied": aktuell.pk, "felder": geaendert})
            jetzt = timezone.now()
            Gemeindezugang.objects.get_or_create(konto=aktuell, defaults={
                "angemeldet_am": jetzt, "alter_erklaert_am": jetzt, "bestaetigt_am": jetzt,
            })
        messages.success(request, _("Gemeindeangaben gespeichert. Festgehaltene Verfahrenskreise bleiben unverändert."))
        return redirect("gemeinde:konto")
    return render(request, "mitglieder/gemeinde_konto.html", {"form": form, "zugang": zugang, "gemeinden": _gemeinden()})


@login_required
@never_cache
@require_GET
def export(request):
    m = request.user
    zugang = Gemeindezugang.objects.filter(konto=m).values(
        "angemeldet_am", "alter_erklaert_am", "bestaetigt_am"
    ).first()
    antwort = JsonResponse({
        "konto": {"email": m.email, "anzeigename": m.pseudonym_oeffentlich, "parteikonto": m.parteikonto},
        "hauptwohnsitz": {"art": m.wohnsitz_art_aktuell, "gemeinde": m.wohnsitz.kennziffer if m.wohnsitz_id else None},
        "gemeindezugang": zugang,
    }, json_dumps_params={"ensure_ascii": False})
    antwort["Content-Disposition"] = 'attachment; filename="gemeindekonto.json"'
    return antwort
