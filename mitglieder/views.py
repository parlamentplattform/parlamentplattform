"""Registrierung, Bestätigung, Login, Logout — bewusst schlicht und lesbar.

E-Mail-Versand läuft über Djangos Mail-Backend (Entwicklung: Konsole;
Produktion: EU-SMTP, siehe Betriebshandbuch). Die Texte sind höflich,
präzise und ohne Marketing — wie alles hier.
"""

from __future__ import annotations

from django import forms
from django.contrib import messages
from django.contrib.auth import login as dj_login
from django.contrib.auth import logout as dj_logout
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from mitglieder.auth_flows import EinmalToken, beitragsreferenz
from mitglieder.models import Bundesland, Identitaetsstufe, Mitglied
from verfahren.models import AuditEintrag


class RegistrierungsFormular(forms.Form):
    vorname = forms.CharField(label="Vorname", max_length=80)
    nachname = forms.CharField(label="Nachname", max_length=80)
    email = forms.EmailField(label="E-Mail-Adresse")
    geburtsjahr = forms.IntegerField(label="Geburtsjahr", min_value=1900, max_value=2100)
    gemeinde = forms.CharField(label="Wohnsitz-Gemeinde", max_length=120)
    bundesland = forms.ChoiceField(
        label="Bundesland",
        choices=Bundesland.choices,
        help_text="Wohnsitz bestimmt, für welche Region Sie regionale Anträge einbringen können (F-43).",
    )
    grundsaetze = forms.BooleanField(
        label="Ich bekenne mich zu den Grundsätzen des § 3 des Satzungsentwurfs "
        "(ein Mensch – eine Stimme, Menschenwürde, Rechtsstaat, Gewaltfreiheit)."
    )

    def clean_geburtsjahr(self):
        jahr = self.cleaned_data["geburtsjahr"]
        if timezone.now().year - jahr < 16:
            raise forms.ValidationError(
                "Mitglied kann werden, wer das 16. Lebensjahr vollendet hat (§ 4 Abs 1)."
            )
        return jahr

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if Mitglied.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError(
                "Für diese Adresse existiert bereits ein Konto — nutzen Sie den Login per E-Mail-Link."
            )
        return email


class LoginFormular(forms.Form):
    email = forms.EmailField(label="E-Mail-Adresse")


def registrieren(request):
    if request.method == "POST":
        form = RegistrierungsFormular(request.POST)
        if form.is_valid():
            d = form.cleaned_data
            mitglied = Mitglied.objects.create(
                username=d["email"],
                email=d["email"],
                first_name=d["vorname"],
                last_name=d["nachname"],
                identitaetsstufe=Identitaetsstufe.UNGEPRUEFT,
                is_active=False,  # aktiv erst nach E-Mail-Bestätigung
            )
            mitglied.gemeinde = d["gemeinde"]
            mitglied.bundesland = d["bundesland"]
            mitglied.set_unusable_password()
            mitglied.save()
            token = EinmalToken.ausstellen(mitglied, EinmalToken.Zweck.BESTAETIGUNG)
            link = request.build_absolute_uri(reverse("mitglieder:bestaetigen", args=[token]))
            send_mail(
                "Bitte bestätigen Sie Ihre E-Mail-Adresse — ParlamentPlattform",
                f"Guten Tag {d['vorname']} {d['nachname']},\n\n"
                f"mit diesem Link bestätigen Sie Ihre Adresse und aktivieren Ihren Zugang "
                f"(gültig 48 Stunden):\n\n{link}\n\n"
                f"Wenn Sie sich nicht registriert haben, ignorieren Sie diese Nachricht.\n\n"
                f"Direkte Demokratie Österreich — Wir sind das Werkzeug.",
                None,
                [d["email"]],
            )
            AuditEintrag.anhaengen({"typ": "registrierung", "mitglied": mitglied.pk})
            return render(
                request, "mitglieder/mail_gesendet.html", {"zweck": "Bestätigung", "email": d["email"]}
            )
    else:
        form = RegistrierungsFormular()
    return render(request, "mitglieder/registrieren.html", {"form": form})


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
    messages.success(request, "E-Mail bestätigt — willkommen! Sie sind jetzt Anwärterin bzw. Anwärter.")
    return redirect("mitglieder:willkommen")


def willkommen(request):
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    return render(
        request,
        "mitglieder/willkommen.html",
        {
            "referenz": beitragsreferenz(request.user),
            "iban": "AT57 2033 0000 0006 9435",
        },
    )


def login_anfordern(request):
    if request.method == "POST":
        form = LoginFormular(request.POST)
        if form.is_valid():
            email = form.cleaned_data["email"].lower()
            mitglied = Mitglied.objects.filter(email__iexact=email, is_active=True).first()
            if mitglied:
                token = EinmalToken.ausstellen(mitglied, EinmalToken.Zweck.LOGIN)
                link = request.build_absolute_uri(reverse("mitglieder:login_einloesen", args=[token]))
                send_mail(
                    "Ihr Anmeldelink — ParlamentPlattform",
                    f"Guten Tag,\n\nmit diesem Link melden Sie sich an (gültig 30 Minuten):\n\n{link}\n\n"
                    f"Wenn Sie keinen Login angefordert haben, ignorieren Sie diese Nachricht.",
                    None,
                    [email],
                )
            # Absichtlich identische Antwort, ob das Konto existiert oder nicht
            # (keine Adress-Enumeration).
            return render(request, "mitglieder/mail_gesendet.html", {"zweck": "Anmeldung", "email": email})
    else:
        form = LoginFormular()
    return render(request, "mitglieder/login.html", {"form": form})


def login_einloesen(request, token: str):
    mitglied = EinmalToken.einloesen(token, EinmalToken.Zweck.LOGIN)
    if mitglied is None:
        return render(request, "mitglieder/token_ungueltig.html", status=400)
    dj_login(request, mitglied)
    return redirect("verfahren:index")


@require_POST
def abmelden(request):
    dj_logout(request)
    messages.info(request, "Sie sind abgemeldet.")
    return redirect("verfahren:index")
