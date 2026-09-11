"""Mitgliederverwaltung (F-51) — das Backend für Admins.

Grundsätze:
- Zugang haben nur Admins. Der fixe Admin (DDOE_FIX_ADMIN, satzungsgebender
  Erstzugang) ist immer Admin; weitere ernennen und entziehen Admins einander.
- Der fixe Admin kann weder pausiert noch ausgeschlossen noch entmachtet werden;
  niemand kann sich selbst pausieren, ausschließen oder die Rechte entziehen.
  Auch seine Anmeldeadresse ändert hier niemand, und kein anderes Konto
  bekommt sie — sonst wäre die Garantie über ein Formular aufgehoben.
- Die Anmeldeadresse eines Mitglieds wird nie sofort geändert: Der Login läuft
  passwortlos über genau diese Adresse, eine Änderung wäre eine Kontoübernahme
  samt Blick auf das Stimmregister-Pseudonym (§ 5 Abs 3). Darum Nachricht mit
  Einspruchslink an die bisherige Adresse, Wartefrist und ein zweiter Admin
  (`Adresswechsel`).
- Jede Handlung landet im öffentlichen Audit-Log (F-22) — mit Aktion, Mitglieds-
  nummer und Begründung, aber ohne personenbezogene Werte.
- Statusfolgen: „pausiert“ lässt Anmelden und Lesen zu, Mitwirkungsrechte ruhen
  (§ 4 Abs 3); „ausgeschlossen“ deaktiviert das Konto (§ 4 Abs 6 — der Knopf
  vollzieht den satzungsmäßigen Beschluss, er ersetzt ihn nicht). Jeder Wechsel
  trägt sein Datum (`status_seit`), damit die Stimmberechtigung am Stichtag
  geprüft werden kann (§ 4 Abs 4 lit a).
"""

from __future__ import annotations

import logging
from functools import wraps
from smtplib import SMTPException

from django import forms
from django.conf import settings
from django.contrib import messages
from django.core.mail import send_mail
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import formats, timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from mitglieder.models import Adresswechsel, Gemeinde, Identitaetsstufe, Mitglied, Mitgliedsstatus
from verfahren.models import AuditEintrag

log = logging.getLogger(__name__)


def nur_admins(ansicht):
    @wraps(ansicht)
    def innen(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("mitglieder:login")
        if not request.user.hat_adminrechte:
            return render(request, "mitglieder/verwaltung_kein_zugang.html", status=403)
        return ansicht(request, *args, **kwargs)

    return innen


def _auditieren(request, aktion: str, mitglied: Mitglied, **extra) -> None:
    AuditEintrag.anhaengen(
        {"typ": "verwaltung", "aktion": aktion, "mitglied": mitglied.pk, "durch": request.user.pk, **extra}
    )


class StammdatenFormular(forms.Form):
    """Falsche Angaben korrigieren — mehr nicht. Felder, die die Plattform selbst
    herleitet (Bundesland, Bezirk), folgen weiterhin dem Gemeindeverzeichnis."""

    vorname = forms.CharField(label=gettext_lazy("Vorname"), max_length=80, required=False)
    nachname = forms.CharField(label=gettext_lazy("Nachname"), max_length=80, required=False)
    email = forms.EmailField(label=gettext_lazy("E-Mail-Adresse"))
    anzeigename = forms.CharField(
        label=gettext_lazy("Öffentlicher Anzeigename (leer = Klarname)"), max_length=50, required=False
    )
    gemeinde = forms.CharField(
        label=gettext_lazy("Wohnsitz-Gemeinde (leer = keine Angabe)"),
        max_length=140,
        required=False,
        widget=forms.TextInput(attrs={"list": "gemeinden", "autocomplete": "off"}),
    )
    identitaetsstufe = forms.ChoiceField(label=gettext_lazy("Identitätsstufe"), choices=Identitaetsstufe.choices)
    beitrag_zuletzt_am = forms.DateField(
        label=gettext_lazy("Letzter Beitragseingang"),
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, mitglied: Mitglied, **kwargs):
        super().__init__(*args, **kwargs)
        self.mitglied = mitglied
        self.gemeinde_objekt = None

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if email == (self.mitglied.email or "").lower():
            return email
        # F-51: Der satzungsgebende Erstzugang hängt an seiner Adresse (DDOE_FIX_ADMIN).
        # Wer sie ihm nähme, entmachtete ihn; wer sie sich gäbe, würde selbst unantastbar.
        if self.mitglied.ist_fixer_admin:
            raise forms.ValidationError(
                _("Die Adresse des satzungsgebenden Erstzugangs wird hier nicht geändert (F-51).")
            )
        if email == getattr(settings, "DDOE_FIX_ADMIN", "").lower():
            raise forms.ValidationError(
                _("Diese Adresse ist dem satzungsgebenden Erstzugang vorbehalten (F-51).")
            )
        if Mitglied.objects.filter(email__iexact=email).exclude(pk=self.mitglied.pk).exists():
            raise forms.ValidationError(_("Diese Adresse gehört bereits zu einem anderen Konto."))
        if Adresswechsel.offener(self.mitglied) is not None:
            raise forms.ValidationError(
                _("Für dieses Konto läuft bereits eine Adressänderung — zuerst abbrechen oder abwarten.")
            )
        return email

    def clean_gemeinde(self):
        eingabe = self.cleaned_data["gemeinde"].strip()
        if not eingabe:
            return ""
        treffer, kandidaten = Gemeinde.finden(eingabe)
        if treffer:
            self.gemeinde_objekt = treffer
            return treffer.name
        if kandidaten:
            optionen = "; ".join(g.anzeige for g in kandidaten)
            raise forms.ValidationError(_("Mehrdeutig — bitte präzisieren: %(optionen)s.") % {"optionen": optionen})
        raise forms.ValidationError(_("Steht nicht im amtlichen Gemeindeverzeichnis."))


@nur_admins
def liste(request):
    Adresswechsel.faellige_anwenden()
    mitglieder = Mitglied.objects.order_by("-date_joined")
    suche = request.GET.get("q", "").strip()
    if suche:
        mitglieder = mitglieder.filter(
            Q(first_name__icontains=suche)
            | Q(last_name__icontains=suche)
            | Q(email__icontains=suche)
            | Q(gemeinde__icontains=suche)
            | Q(pseudonym_oeffentlich__icontains=suche)
        )
    status = request.GET.get("status", "")
    if status in Mitgliedsstatus.values:
        mitglieder = mitglieder.filter(status=status)
    zahlen = {
        "gesamt": Mitglied.objects.count(),
        "aktiv": Mitglied.objects.filter(status=Mitgliedsstatus.AKTIV, is_active=True).count(),
        "pausiert": Mitglied.objects.filter(status=Mitgliedsstatus.PAUSIERT).count(),
        "ausgeschlossen": Mitglied.objects.filter(status=Mitgliedsstatus.AUSGESCHLOSSEN).count(),
        "unbestaetigt": Mitglied.objects.filter(is_active=False)
        .exclude(status=Mitgliedsstatus.AUSGESCHLOSSEN)
        .count(),
    }
    return render(
        request,
        "mitglieder/verwaltung_liste.html",
        {
            "mitglieder": mitglieder[:200],
            "suche": suche,
            "status": status,
            "zahlen": zahlen,
            "statuswahl": Mitgliedsstatus.choices,
        },
    )


def _adresswechsel_beantragen(request, mitglied: Mitglied, neue_email: str) -> bool:
    """Antrag anlegen und die BISHERIGE Adresse benachrichtigen — beides oder nichts.
    Scheitert der Versand, gibt es keinen Antrag: Ohne Einspruchsmöglichkeit des
    Inhabers wäre die Frist wertlos."""
    try:
        with transaction.atomic():
            wechsel, klar = Adresswechsel.beantragen(mitglied, neue_email, request.user)
            link = request.build_absolute_uri(reverse("mitglieder:adresswechsel_einspruch", args=[klar]))
            frist = formats.date_format(timezone.localtime(wechsel.frist_bis), "SHORT_DATETIME_FORMAT")
            send_mail(
                _("Ihre Anmeldeadresse soll geändert werden — ParlamentPlattform"),
                _(
                    "Guten Tag,\n\n"
                    "die Verwaltung hat beantragt, die Anmeldeadresse Ihres Kontos auf eine andere "
                    "E-Mail-Adresse zu ändern. Wirksam wird das frühestens am %(frist)s und nur, wenn "
                    "ein zweiter Admin die Änderung bestätigt.\n\n"
                    "Wenn Sie das NICHT veranlasst haben, widersprechen Sie bitte mit diesem Link — "
                    "die Änderung wird dann verworfen:\n\n%(link)s\n\n"
                    "Bis dahin bleibt diese Adresse Ihre Anmeldeadresse.\n\n"
                    "Direkte Demokratie Österreich — Wir sind das Werkzeug."
                )
                % {"frist": frist, "link": link},
                None,
                [mitglied.email],
            )
    except (SMTPException, OSError):
        log.exception("Adresswechsel-Nachricht nicht versendbar — Antrag verworfen.")
        messages.error(
            request,
            _("Die Adressänderung wurde nicht vorgemerkt: Die Nachricht an die bisherige Adresse ließ sich nicht versenden."),
        )
        return False
    _auditieren(request, "email_geaendert_beantragt", mitglied)
    messages.success(
        request,
        _(
            "Adressänderung vorgemerkt: Die bisherige Adresse wurde benachrichtigt; wirksam wird sie "
            "frühestens am %(frist)s, sobald ein zweiter Admin bestätigt hat."
        )
        % {"frist": frist},
    )
    return True


def _stammdaten_anwenden(request, mitglied: Mitglied, form: StammdatenFormular) -> None:
    d = form.cleaned_data
    geaendert = []
    zuordnung = {
        "first_name": d["vorname"],
        "last_name": d["nachname"],
        "pseudonym_oeffentlich": d["anzeigename"],
        "beitrag_zuletzt_am": d["beitrag_zuletzt_am"],
    }
    for feld, neu in zuordnung.items():
        if getattr(mitglied, feld) != neu:
            setattr(mitglied, feld, neu)
            geaendert.append(feld)
    geaendert += mitglied.identitaetsstufe_setzen(d["identitaetsstufe"])
    if d["gemeinde"]:
        g = form.gemeinde_objekt
        if mitglied.wohnsitz_id != g.pk:
            mitglied.gemeinde, mitglied.bundesland, mitglied.wohnsitz = g.name, g.bundesland, g
            geaendert.append("wohnsitz")
    elif mitglied.gemeinde:
        mitglied.gemeinde, mitglied.bundesland, mitglied.wohnsitz = "", "", None
        geaendert.append("wohnsitz")
    if geaendert:
        mitglied.save()
        _auditieren(request, "stammdaten_geaendert", mitglied, felder=sorted(set(geaendert)))
        messages.success(request, _("Stammdaten gespeichert."))
    adresse_neu = d["email"] != (mitglied.email or "").lower()
    if adresse_neu:
        # Nie sofort (F-51, § 5 Abs 3): Einspruchsfrist für die bisherige Adresse, zweiter Admin.
        _adresswechsel_beantragen(request, mitglied, d["email"])
    elif not geaendert:
        messages.info(request, _("Keine Änderungen."))


def _adresswechsel_aktion(request, mitglied: Mitglied, aktion: str) -> None:
    wechsel = Adresswechsel.offener(mitglied)
    if wechsel is None:
        messages.error(request, _("Für dieses Konto läuft keine Adressänderung."))
        return
    if aktion == "adresswechsel_bestaetigen":
        if wechsel.bestaetigen(request.user):
            messages.success(
                request,
                _("Bestätigt. Nach Ablauf der Frist wird die neue Adresse zur Anmeldeadresse — sofern kein Einspruch kommt."),
            )
        else:
            messages.error(
                request, _("Die Bestätigung braucht einen zweiten Admin — nicht den, der die Änderung beantragt hat.")
            )
    elif aktion == "adresswechsel_abbrechen":
        wechsel.widerrufen("abbruch", durch=request.user)
        messages.success(request, _("Adressänderung abgebrochen — die bisherige Adresse bleibt."))


def _status_aktion(request, mitglied: Mitglied, aktion: str) -> None:
    grund = request.POST.get("grund", "").strip()
    selbst = mitglied.pk == request.user.pk
    if aktion in ("pausieren", "ausschliessen", "admin_nehmen"):
        if mitglied.ist_fixer_admin:
            messages.error(request, _("Der satzungsgebende Erstzugang ist unantastbar (F-51)."))
            return
        if selbst:
            messages.error(request, _("Diese Aktion können nur andere Admins auf Ihr Konto anwenden."))
            return
    if aktion in ("pausieren", "ausschliessen") and not grund:
        messages.error(request, _("Bitte eine Begründung angeben — sie wird im Audit-Log veröffentlicht."))
        return

    if aktion == "pausieren":
        mitglied.save(update_fields=mitglied.status_setzen(Mitgliedsstatus.PAUSIERT, grund))
        messages.success(
            request, _("Mitgliedschaft pausiert — Mitwirkungsrechte ruhen bis zum Beitragseingang.")
        )
    elif aktion == "ausschliessen":
        felder = mitglied.status_setzen(Mitgliedsstatus.AUSGESCHLOSSEN, grund)
        mitglied.is_active = False
        mitglied.save(update_fields=[*felder, "is_active"])
        messages.success(request, _("Mitglied ausgeschlossen und Konto deaktiviert."))
    elif aktion == "reaktivieren":
        felder = mitglied.status_setzen(Mitgliedsstatus.AKTIV, "")
        mitglied.is_active = True
        felder.append("is_active")
        if mitglied.beitritt is None:
            # Unbestätigtes Konto von Hand freigeschaltet: Ohne Beitritt bliebe es für immer
            # ohne Anwartschaft (§ 4 Abs 4) — der Rettungsweg wäre wirkungslos.
            mitglied.beitritt = timezone.localdate()
            felder.append("beitritt")
        mitglied.save(update_fields=felder)
        messages.success(request, _("Mitgliedschaft ist wieder aktiv."))
    elif aktion == "beitrag":
        mitglied.beitrag_zuletzt_am = timezone.localdate()
        felder = ["beitrag_zuletzt_am"]
        if mitglied.status == Mitgliedsstatus.PAUSIERT:
            felder += mitglied.status_setzen(Mitgliedsstatus.AKTIV, "")
            messages.success(request, _("Beitragseingang vermerkt — die Pause ist damit aufgehoben."))
        else:
            messages.success(request, _("Beitragseingang vermerkt."))
        mitglied.save(update_fields=felder)
    elif aktion == "admin_geben":
        mitglied.ist_admin = True
        mitglied.save(update_fields=["ist_admin"])
        messages.success(
            request, _("%(name)s hat jetzt Zugang zur Verwaltung.") % {"name": mitglied.anzeigename}
        )
    elif aktion == "admin_nehmen":
        mitglied.ist_admin = False
        mitglied.save(update_fields=["ist_admin"])
        messages.success(request, _("Adminrechte entzogen."))
    else:
        messages.error(request, _("Unbekannte Aktion."))
        return
    _auditieren(request, aktion, mitglied, **({"grund": grund} if grund else {}))


@nur_admins
def mitglied(request, pk: int):
    Adresswechsel.faellige_anwenden()
    person = get_object_or_404(Mitglied, pk=pk)
    if request.method == "POST" and request.POST.get("aktion") == "stammdaten":
        form = StammdatenFormular(request.POST, mitglied=person)
        if form.is_valid():
            _stammdaten_anwenden(request, person, form)
            return redirect("mitglieder:verwaltung_mitglied", pk=pk)
    elif request.method == "POST" and request.POST.get("aktion", "").startswith("adresswechsel_"):
        _adresswechsel_aktion(request, person, request.POST.get("aktion", ""))
        return redirect("mitglieder:verwaltung_mitglied", pk=pk)
    elif request.method == "POST":
        _status_aktion(request, person, request.POST.get("aktion", ""))
        return redirect("mitglieder:verwaltung_mitglied", pk=pk)
    else:
        form = StammdatenFormular(
            mitglied=person,
            initial={
                "vorname": person.first_name,
                "nachname": person.last_name,
                "email": person.email,
                "anzeigename": person.pseudonym_oeffentlich,
                "gemeinde": person.gemeinde,
                "identitaetsstufe": person.identitaetsstufe,
                "beitrag_zuletzt_am": person.beitrag_zuletzt_am,
            },
        )
    gemeinden = [f"{name} ({bezirk})" for name, bezirk in Gemeinde.objects.values_list("name", "bezirk")]
    return render(
        request,
        "mitglieder/verwaltung_mitglied.html",
        {
            "person": person,
            "form": form,
            "gemeinden": gemeinden,
            "adresswechsel": Adresswechsel.offener(person),
        },
    )


def adresswechsel_einspruch(request, token: str):
    """Der Einspruchslink aus der Nachricht an die bisherige Adresse — öffentlich
    erreichbar (der Inhaber ist womöglich nicht angemeldet), Wirkung nur per POST."""
    wechsel = Adresswechsel.per_einspruch(token)
    if wechsel is None:
        return render(request, "mitglieder/token_ungueltig.html", status=400)
    if request.method == "POST" and wechsel.status == Adresswechsel.Status.OFFEN:
        wechsel.widerrufen("einspruch")
        return render(request, "mitglieder/adresswechsel_einspruch.html", {"zustand": "widerrufen"})
    zustand = "offen" if wechsel.status == Adresswechsel.Status.OFFEN else wechsel.status
    return render(request, "mitglieder/adresswechsel_einspruch.html", {"zustand": zustand})
