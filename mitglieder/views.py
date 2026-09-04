"""Registrierung, Bestätigung, Login, Logout — bewusst schlicht und lesbar.

E-Mail-Versand läuft über Djangos Mail-Backend (Entwicklung: Konsole;
Produktion: EU-SMTP, siehe Betriebshandbuch). Die Texte sind höflich,
präzise und ohne Marketing — wie alles hier.
"""

from __future__ import annotations

import logging
from smtplib import SMTPException

from django import forms
from django.contrib import messages
from django.contrib.auth import login as dj_login
from django.contrib.auth import logout as dj_logout
from django.core.mail import send_mail
from django.db import transaction
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from mitglieder.auth_flows import EinmalToken, beitragsreferenz
from mitglieder.botschutz import BotschutzMixin, drossel_zuviel
from mitglieder.models import Gemeinde, Identitaetsstufe, Mitglied
from verfahren.models import AuditEintrag

log = logging.getLogger(__name__)

MAIL_STOERUNG = gettext_lazy(
    "Unser E-Mail-Versand ist im Moment gestört — bitte versuchen Sie es in einigen "
    "Minuten erneut. Bleibt das Problem bestehen, schreiben Sie uns an didide@ddoe.at."
)


class RegistrierungsFormular(BotschutzMixin, forms.Form):
    vorname = forms.CharField(label=gettext_lazy("Vorname"), max_length=80)
    nachname = forms.CharField(label=gettext_lazy("Nachname"), max_length=80)
    email = forms.EmailField(label=gettext_lazy("E-Mail-Adresse"))
    geburtsjahr = forms.IntegerField(label=gettext_lazy("Geburtsjahr"), min_value=1900, max_value=2100)
    gemeinde = forms.CharField(
        label=gettext_lazy("Wohnsitz-Gemeinde"),
        max_length=140,
        widget=forms.TextInput(
            attrs={
                "list": "gemeinden",
                "autocomplete": "off",
                "placeholder": gettext_lazy("Tippen und aus der Liste wählen …"),
            }
        ),
        help_text=gettext_lazy(
            "Bitte aus dem amtlichen Gemeindeverzeichnis wählen — Bezirk und Bundesland "
            "ordnen wir dann automatisch zu. Mit der ID Austria erfolgt das später amtlich."
        ),
    )

    def clean_gemeinde(self):
        eingabe = self.cleaned_data["gemeinde"]
        treffer, kandidaten = Gemeinde.finden(eingabe)
        if treffer:
            self.gemeinde_objekt = treffer
            return treffer.name
        if kandidaten:
            optionen = "; ".join(g.anzeige for g in kandidaten)
            raise forms.ValidationError(
                _("Diesen Gemeindenamen gibt es mehrmals — bitte präzisieren: %s.") % optionen
            )
        vorschlaege = list(
            Gemeinde.objects.filter(name__istartswith=eingabe.strip()[:10]).values_list("name", flat=True)[:5]
        )
        hinweis = (_(" Meinten Sie: %s?") % ", ".join(vorschlaege)) if vorschlaege else ""
        raise forms.ValidationError(
            _("„%(eingabe)s“ steht nicht im amtlichen Gemeindeverzeichnis — bitte aus der Liste wählen.")
            % {"eingabe": eingabe}
            + hinweis
        )

    grundsaetze = forms.BooleanField(
        label=gettext_lazy(
            "Ich bekenne mich zu den Grundsätzen des § 3 des Satzungsentwurfs "
            "(ein Mensch – eine Stimme, Menschenwürde, Rechtsstaat, Gewaltfreiheit)."
        )
    )

    def clean_geburtsjahr(self):
        jahr = self.cleaned_data["geburtsjahr"]
        if timezone.now().year - jahr < 16:
            raise forms.ValidationError(
                _("Mitglied kann werden, wer das 16. Lebensjahr vollendet hat (§ 4 Abs 1).")
            )
        return jahr

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if Mitglied.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                _("Für diese Adresse existiert bereits ein Konto — nutzen Sie den Login per E-Mail-Link.")
            )
        return email


class LoginFormular(BotschutzMixin, forms.Form):
    email = forms.EmailField(label=gettext_lazy("E-Mail-Adresse"))


def registrieren(request):
    if request.method == "POST":
        form = RegistrierungsFormular(request.POST)
        if drossel_zuviel(request, "registrierung", limit=5):
            form.add_error(None, _("Zu viele Versuche von dieser Verbindung — bitte in einer Stunde erneut."))
        elif form.is_valid():
            d = form.cleaned_data
            try:
                # Konto und Mailversand stehen und fallen gemeinsam: Scheitert der
                # Versand, wird alles zurückgerollt — die Adresse bleibt frei und
                # ein zweiter Versuch ist jederzeit möglich (kein „halbes“ Konto).
                with transaction.atomic():
                    mitglied = Mitglied.objects.create(
                        username=d["email"],
                        email=d["email"],
                        first_name=d["vorname"],
                        last_name=d["nachname"],
                        identitaetsstufe=Identitaetsstufe.UNGEPRUEFT,
                        is_active=False,  # aktiv erst nach E-Mail-Bestätigung
                    )
                    gemeinde = form.gemeinde_objekt  # geprüft in clean_gemeinde
                    mitglied.gemeinde = gemeinde.name
                    mitglied.bundesland = gemeinde.bundesland
                    mitglied.wohnsitz = gemeinde
                    mitglied.set_unusable_password()
                    mitglied.save()
                    token = EinmalToken.ausstellen(mitglied, EinmalToken.Zweck.BESTAETIGUNG)
                    link = request.build_absolute_uri(reverse("mitglieder:bestaetigen", args=[token]))
                    send_mail(
                        _("Bitte bestätigen Sie Ihre E-Mail-Adresse — ParlamentPlattform"),
                        _(
                            "Guten Tag %(vorname)s %(nachname)s,\n\n"
                            "mit diesem Link bestätigen Sie Ihre Adresse und aktivieren Ihren Zugang "
                            "(gültig 48 Stunden):\n\n%(link)s\n\n"
                            "Wenn Sie sich nicht registriert haben, ignorieren Sie diese Nachricht.\n\n"
                            "Direkte Demokratie Österreich — Wir sind das Werkzeug."
                        )
                        % {"vorname": d["vorname"], "nachname": d["nachname"], "link": link},
                        None,
                        [d["email"]],
                    )
            except (SMTPException, OSError):
                log.exception("Bestätigungs-Mail nicht versendbar — Registrierung zurückgerollt.")
                form.add_error(None, _("Ihre Registrierung wurde nicht gespeichert: %s") % MAIL_STOERUNG)
            else:
                AuditEintrag.anhaengen({"typ": "registrierung", "mitglied": mitglied.pk})
                return render(
                    request,
                    "mitglieder/mail_gesendet.html",
                    {"zweck": _("Bestätigung"), "email": d["email"]},
                )
    else:
        form = RegistrierungsFormular()
    gemeinden = [f"{name} ({bezirk})" for name, bezirk in Gemeinde.objects.values_list("name", "bezirk")]
    return render(request, "mitglieder/registrieren.html", {"form": form, "gemeinden": gemeinden})


def bestaetigen(request, token: str):
    mitglied = EinmalToken.einloesen(token, EinmalToken.Zweck.BESTAETIGUNG)
    if mitglied is None:
        return render(request, "mitglieder/token_ungueltig.html", status=400)
    mitglied.is_active = True
    if mitglied.beitritt is None:
        mitglied.beitritt = timezone.now().date()  # Beginn der Anwartschaft (§ 4 Abs 4)
    mitglied.save(update_fields=["is_active", "beitritt"])
    dj_login(request, mitglied)
    AuditEintrag.anhaengen({"typ": "email_bestaetigt", "mitglied": mitglied.pk})
    messages.success(request, _("E-Mail bestätigt — willkommen! Sie sind jetzt Anwärterin bzw. Anwärter."))
    # F-53: Neue Mitglieder landen in der Einführung (jederzeit überspringbar);
    # der Beitrags-QR (Willkommensseite) ist ihr Abschluss.
    return redirect("mitglieder:einfuehrung", schritt=1)


IBAN = "AT57 2033 0000 0006 9435"
BEITRAG_RICHTWERT = "30"


def _beitrags_qr(referenz: str) -> str:
    """EPC-QR-Code („Zahlen mit Code") für die Beitragsüberweisung (F-38).

    Standardformat des European Payments Council — jede österreichische
    Banking-App liest ihn. Die Überweisung läuft als (Echtzeit-)Überweisung
    direkt von Konto zu Konto: kein Zahlungsdienstleister, keine Prozente.
    Betrag ist in der App änderbar (Selbsteinschätzung, § 4 Abs 3).
    Der Empfängername steht mit Umlaut im Code: Die dritte Payload-Zeile
    („1") deklariert UTF-8, und seit der EU-Empfängerprüfung (Verification
    of Payee) zählt der exakte Kontowortlaut „Direkte Demokratie Österreich"."""
    import segno

    nutzlast = "\n".join(
        [
            "BCD",
            "002",
            "1",
            "SCT",
            "",  # BIC (im EWR optional)
            "Direkte Demokratie Österreich",
            IBAN.replace(" ", ""),
            f"EUR{BEITRAG_RICHTWERT}",
            "",  # Zweck-Code
            "",  # strukturierte Referenz
            f"{referenz} Mitgliedsbeitrag",
        ]
    )
    return segno.make(nutzlast, error="m").svg_inline(scale=3.2)


def willkommen(request):
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    referenz = beitragsreferenz(request.user)
    return render(
        request,
        "mitglieder/willkommen.html",
        {
            "referenz": referenz,
            "iban": IBAN,
            "richtwert": BEITRAG_RICHTWERT,
            "qr_svg": _beitrags_qr(referenz),
        },
    )


def login_anfordern(request):
    if request.method == "POST":
        form = LoginFormular(request.POST)
        if drossel_zuviel(request, "anmeldelink", limit=10):
            form.add_error(None, _("Zu viele Versuche von dieser Verbindung — bitte in einer Stunde erneut."))
        elif form.is_valid():
            email = form.cleaned_data["email"].lower()
            mitglied = Mitglied.objects.filter(email__iexact=email, is_active=True).first()
            if mitglied:
                token = EinmalToken.ausstellen(mitglied, EinmalToken.Zweck.LOGIN)
                link = request.build_absolute_uri(reverse("mitglieder:login_einloesen", args=[token]))
                try:
                    send_mail(
                        _("Ihr Anmeldelink — ParlamentPlattform"),
                        _(
                            "Guten Tag,\n\nmit diesem Link melden Sie sich an (gültig 30 Minuten):\n\n%(link)s\n\n"
                            "Wenn Sie keinen Login angefordert haben, ignorieren Sie diese Nachricht."
                        )
                        % {"link": link},
                        None,
                        [email],
                    )
                except (SMTPException, OSError):
                    # Eine Betriebsstörung wird offen gemeldet statt einer „unterwegs“-Seite
                    # ohne Mail. (Ob eine Adresse registriert ist, zeigt ohnehin schon das
                    # Registrierungsformular — hier entsteht kein neuer Auskunftskanal.)
                    log.exception("Anmeldelink nicht versendbar.")
                    form.add_error(None, MAIL_STOERUNG)
                    return render(request, "mitglieder/login.html", {"form": form})
            # Absichtlich identische Antwort, ob das Konto existiert oder nicht
            # (keine Adress-Enumeration).
            return render(request, "mitglieder/mail_gesendet.html", {"zweck": _("Anmeldung"), "email": email})
    else:
        form = LoginFormular()
    return render(request, "mitglieder/login.html", {"form": form})


def login_einloesen(request, token: str):
    mitglied = EinmalToken.einloesen(token, EinmalToken.Zweck.LOGIN)
    if mitglied is None:
        return render(request, "mitglieder/token_ungueltig.html", status=400)
    dj_login(request, mitglied)
    return redirect("verfahren:parlament")


@require_POST
def abmelden(request):
    dj_logout(request)
    messages.info(request, _("Sie sind abgemeldet."))
    return redirect("verfahren:index")


def mitgliedschaft(request):
    """Öffentliche Schaufenster-Seite der Mitgliedschaft: erst plakativ, was
    Mitglieder können, dann die Details (Anwartschaft, Beitrag, Identität)
    und der Weg vom Antrag zum Beschluss — ehrlich und ohne Kleingedrucktes."""
    return render(request, "mitglieder/mitgliedschaft.html")
