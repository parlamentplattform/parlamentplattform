"""Mitgliederverwaltung (F-51) — das Backend für Admins.

Grundsätze:
- Zugang haben nur Admins. Der fixe Admin (DDOE_FIX_ADMIN, satzungsgebender
  Erstzugang) ist immer Admin; weitere ernennen und entziehen Admins einander.
- Der fixe Admin kann weder pausiert noch ausgeschlossen noch entmachtet werden;
  niemand kann sich selbst pausieren, ausschließen oder die Rechte entziehen.
- Jede Handlung landet im öffentlichen Audit-Log (F-22) — mit Aktion, Mitglieds-
  nummer und Begründung, aber ohne personenbezogene Werte.
- Statusfolgen: „pausiert“ lässt Anmelden und Lesen zu, Mitwirkungsrechte ruhen
  (§ 4 Abs 3); „ausgeschlossen“ deaktiviert das Konto (§ 4 Abs 6 — der Knopf
  vollzieht den satzungsmäßigen Beschluss, er ersetzt ihn nicht).
"""

from __future__ import annotations

from functools import wraps

from django import forms
from django.contrib import messages
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from mitglieder.models import Gemeinde, Identitaetsstufe, Mitglied, Mitgliedsstatus
from verfahren.models import AuditEintrag


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

    vorname = forms.CharField(label="Vorname", max_length=80, required=False)
    nachname = forms.CharField(label="Nachname", max_length=80, required=False)
    email = forms.EmailField(label="E-Mail-Adresse")
    anzeigename = forms.CharField(
        label="Öffentlicher Anzeigename (leer = Klarname)", max_length=50, required=False
    )
    gemeinde = forms.CharField(
        label="Wohnsitz-Gemeinde (leer = keine Angabe)",
        max_length=140,
        required=False,
        widget=forms.TextInput(attrs={"list": "gemeinden", "autocomplete": "off"}),
    )
    identitaetsstufe = forms.ChoiceField(label="Identitätsstufe", choices=Identitaetsstufe.choices)
    beitrag_zuletzt_am = forms.DateField(
        label="Letzter Beitragseingang",
        required=False,
        widget=forms.DateInput(attrs={"type": "date"}),
    )

    def __init__(self, *args, mitglied: Mitglied, **kwargs):
        super().__init__(*args, **kwargs)
        self.mitglied = mitglied
        self.gemeinde_objekt = None

    def clean_email(self):
        email = self.cleaned_data["email"].lower()
        if Mitglied.objects.filter(email__iexact=email).exclude(pk=self.mitglied.pk).exists():
            raise forms.ValidationError("Diese Adresse gehört bereits zu einem anderen Konto.")
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
            raise forms.ValidationError(f"Mehrdeutig — bitte präzisieren: {optionen}.")
        raise forms.ValidationError("Steht nicht im amtlichen Gemeindeverzeichnis.")


@nur_admins
def liste(request):
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


def _stammdaten_anwenden(request, mitglied: Mitglied, form: StammdatenFormular) -> None:
    d = form.cleaned_data
    geaendert = []
    zuordnung = {
        "first_name": d["vorname"],
        "last_name": d["nachname"],
        "pseudonym_oeffentlich": d["anzeigename"],
        "identitaetsstufe": d["identitaetsstufe"],
        "beitrag_zuletzt_am": d["beitrag_zuletzt_am"],
    }
    for feld, neu in zuordnung.items():
        if getattr(mitglied, feld) != neu:
            setattr(mitglied, feld, neu)
            geaendert.append(feld)
    if d["email"] != mitglied.email.lower():
        if mitglied.username == mitglied.email:
            mitglied.username = d["email"]  # Registrierte führen die Adresse als Anmeldenamen
            geaendert.append("username")
        mitglied.email = d["email"]
        geaendert.append("email")
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
        messages.success(request, "Stammdaten gespeichert.")
    else:
        messages.info(request, "Keine Änderungen.")


def _status_aktion(request, mitglied: Mitglied, aktion: str) -> None:
    grund = request.POST.get("grund", "").strip()
    selbst = mitglied.pk == request.user.pk
    if aktion in ("pausieren", "ausschliessen", "admin_nehmen"):
        if mitglied.ist_fixer_admin:
            messages.error(request, "Der satzungsgebende Erstzugang ist unantastbar (F-51).")
            return
        if selbst:
            messages.error(request, "Diese Aktion können nur andere Admins auf Ihr Konto anwenden.")
            return
    if aktion in ("pausieren", "ausschliessen") and not grund:
        messages.error(request, "Bitte eine Begründung angeben — sie wird im Audit-Log veröffentlicht.")
        return

    if aktion == "pausieren":
        mitglied.status, mitglied.status_grund = Mitgliedsstatus.PAUSIERT, grund
        mitglied.save(update_fields=["status", "status_grund"])
        messages.success(
            request, "Mitgliedschaft pausiert — Mitwirkungsrechte ruhen bis zum Beitragseingang."
        )
    elif aktion == "ausschliessen":
        mitglied.status, mitglied.status_grund, mitglied.is_active = (
            Mitgliedsstatus.AUSGESCHLOSSEN,
            grund,
            False,
        )
        mitglied.save(update_fields=["status", "status_grund", "is_active"])
        messages.success(request, "Mitglied ausgeschlossen und Konto deaktiviert.")
    elif aktion == "reaktivieren":
        mitglied.status, mitglied.status_grund, mitglied.is_active = Mitgliedsstatus.AKTIV, "", True
        mitglied.save(update_fields=["status", "status_grund", "is_active"])
        messages.success(request, "Mitgliedschaft ist wieder aktiv.")
    elif aktion == "beitrag":
        mitglied.beitrag_zuletzt_am = timezone.localdate()
        felder = ["beitrag_zuletzt_am"]
        if mitglied.status == Mitgliedsstatus.PAUSIERT:
            mitglied.status, mitglied.status_grund = Mitgliedsstatus.AKTIV, ""
            felder += ["status", "status_grund"]
            messages.success(request, "Beitragseingang vermerkt — die Pause ist damit aufgehoben.")
        else:
            messages.success(request, "Beitragseingang vermerkt.")
        mitglied.save(update_fields=felder)
    elif aktion == "admin_geben":
        mitglied.ist_admin = True
        mitglied.save(update_fields=["ist_admin"])
        messages.success(request, f"{mitglied.anzeigename} hat jetzt Zugang zur Verwaltung.")
    elif aktion == "admin_nehmen":
        mitglied.ist_admin = False
        mitglied.save(update_fields=["ist_admin"])
        messages.success(request, "Adminrechte entzogen.")
    else:
        messages.error(request, "Unbekannte Aktion.")
        return
    _auditieren(request, aktion, mitglied, **({"grund": grund} if grund else {}))


@nur_admins
def mitglied(request, pk: int):
    person = get_object_or_404(Mitglied, pk=pk)
    if request.method == "POST" and request.POST.get("aktion") == "stammdaten":
        form = StammdatenFormular(request.POST, mitglied=person)
        if form.is_valid():
            _stammdaten_anwenden(request, person, form)
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
        {"person": person, "form": form, "gemeinden": gemeinden},
    )
