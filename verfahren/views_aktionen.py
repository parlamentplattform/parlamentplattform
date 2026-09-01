"""Handelnde Ansichten: einbringen, unterstützen, kommentieren, abstimmen, exportieren.

Berechtigungsstufen (aus Satzung § 4):
- Lesen: alle, ohne Login (F-20).
- Einbringen, unterstützen, kommentieren: bestätigte Mitglieder
  (Identitätsstufe mindestens „geprüft").
- Abstimmen: stimmberechtigte Mitglieder (Anwartschaft; im Aufbau gilt die
  Übergangsregel nach § 4 Abs 4 lit d, konfiguriert über DDOE_UEBERGANGSREGEL).
"""

from __future__ import annotations

from django import forms
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from mitglieder.models import Identitaetsstufe, Mitgliedsstatus
from plattform_core import Gegenstand, Phase
from plattform_core.similarity import aehnlichste
from verfahren.models import (
    Antrag,
    Antragsart,
    Bewerbung,
    BewerbungsFehler,
    BewerbungsZustimmung,
    Ebene,
    Favorit,
    Kategorie,
    KategorieAbo,
    Kommentar,
    StimmabgabeFehler,
    StimmRegister,
    Verfahrensordnung,
    antrag_einbringen,
    bewerbung_einreichen,
    bewerbung_zustimmen,
    kategorien_zuordnen,
    stimme_abgeben,
    vollzug_fortschreiben,
)

OFFENE_PHASEN = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]


def _mitwirkung_gesperrt(request):
    """403-Antwort, wenn Mitwirkungsrechte fehlen — sonst None.

    Zwei Gründe: unbestätigte Identität (§ 4) oder ruhender Status (F-51:
    pausiert bis zum Beitragseingang bzw. ausgeschlossen nach § 4 Abs 6)."""
    if request.user.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
        return render(request, "verfahren/nur_bestaetigte.html", status=403)
    if request.user.status != Mitgliedsstatus.AKTIV:
        return render(
            request,
            "verfahren/mitwirkung_ruht.html",
            {"pausiert": request.user.status == Mitgliedsstatus.PAUSIERT},
            status=403,
        )
    return None


class AntragsFormular(forms.Form):
    """Titel, Wortlaut, Begründung — und die Ebene, gebunden an den eigenen Wohnsitz:
    Regionale Anträge sind nur in der ansässigen Region möglich (F-43); das Gebiet
    kommt aus dem Mitgliedsprofil, nie aus freier Eingabe. Lebensbereiche wählt
    niemand von Hand — die ordnet die Plattform automatisch zu (F-47)."""

    art = forms.ChoiceField(
        label=gettext_lazy("Art des Antrags"),
        widget=forms.RadioSelect,
        required=False,
        initial=Antragsart.SACHE.value,
        choices=[
            (
                Antragsart.SACHE.value,
                gettext_lazy("Sachantrag — ein Beschluss in der Sache"),
            ),
            (
                Antragsart.MANDAT.value,
                gettext_lazy(
                    "Mandats-Kandidatur — eine Personenwahl (§ 7 Abs 1): Mitglieder bewerben sich "
                    "am Antrag, die meiste Zustimmung gewinnt, die Reihenfolge ergibt die Liste"
                ),
            ),
        ],
    )
    titel = forms.CharField(
        label=gettext_lazy("Titel"),
        max_length=200,
        help_text=gettext_lazy("Bei einer Mandats-Kandidatur: das Mandat, z. B. „Listenreihung Gemeinderat …“."),
    )
    wortlaut = forms.CharField(
        label=gettext_lazy("Wortlaut des Antrags"),
        widget=forms.Textarea(attrs={"rows": 10}),
        help_text=gettext_lazy(
            "Bei einer Mandats-Kandidatur: Beschreibung des Mandats — Aufgabe, Zeitraum, Zuständigkeit."
        ),
    )
    begruendung = forms.CharField(
        label=gettext_lazy("Begründung"), widget=forms.Textarea(attrs={"rows": 6}), required=False
    )
    ebene = forms.ChoiceField(label=gettext_lazy("Gilt für"), widget=forms.RadioSelect, required=False)

    def __init__(self, *args, mitglied=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.mitglied = mitglied
        wahlen = [(Ebene.BUND.value, _("Ganz Österreich"))]
        if mitglied is not None and mitglied.bundesland:
            wahlen.append((Ebene.LAND.value, _("Mein Bundesland (%s)") % mitglied.get_bundesland_display()))
        if mitglied is not None and mitglied.wohnsitz_id and mitglied.wohnsitz.bezirk:
            wahlen.append((Ebene.BEZIRK.value, _("Mein Bezirk (%s)") % mitglied.wohnsitz.bezirk))
        if mitglied is not None and mitglied.gemeinde:
            wahlen.append((Ebene.GEMEINDE.value, _("Meine Gemeinde (%s)") % mitglied.gemeinde))
        self.fields["ebene"].choices = wahlen
        self.fields["ebene"].initial = Ebene.BUND.value

    def clean_ebene(self):
        return self.cleaned_data.get("ebene") or Ebene.BUND.value

    def clean_art(self):
        wert = self.cleaned_data.get("art") or Antragsart.SACHE.value
        return wert if wert in Antragsart.values else Antragsart.SACHE.value

    def gebiet(self) -> str:
        """Das Gebiet folgt zwingend dem Wohnsitz (F-43) — keine freie Eingabe."""
        ebene = self.cleaned_data["ebene"]
        if ebene == Ebene.GEMEINDE.value:
            return self.mitglied.gemeinde
        if ebene == Ebene.BEZIRK.value:
            return self.mitglied.wohnsitz.bezirk if self.mitglied.wohnsitz_id else ""
        if ebene == Ebene.LAND.value:
            return self.mitglied.get_bundesland_display()
        return ""


class KommentarFormular(forms.Form):
    text = forms.CharField(
        label=gettext_lazy("Beitrag zur Beratung"), widget=forms.Textarea(attrs={"rows": 4}), max_length=4000
    )


@login_required
def einbringen(request):
    """F-10 + F-35: Einbringen mit Ähnlichkeitshinweis — der Hinweis schlägt vor,
    er blockiert nie. „Trotzdem einbringen" ist immer gleichwertig möglich."""
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    ordnung = Verfahrensordnung.objects.filter(aktiv=True).order_by("-version").first()
    if ordnung is None:
        return render(request, "verfahren/keine_ordnung.html", status=503)

    aehnliche = []
    if request.method == "POST":
        form = AntragsFormular(request.POST, mitglied=request.user)
        if form.is_valid():
            d = form.cleaned_data
            # Ähnlichkeitshinweis nur für Sachanträge — Kandidaturen für dasselbe
            # Mandat sollen sich am BESTEHENDEN Antrag beteiligen (§ 7 Abs 1);
            # darauf weist die Antragsseite selbst hin.
            if not request.POST.get("trotzdem") and d["art"] == Antragsart.SACHE.value:
                offene = list(Antrag.objects.filter(phase__in=OFFENE_PHASEN).values_list("id", "titel"))
                texte = {a.pk: a for a in Antrag.objects.filter(id__in=[i for i, _ in offene])}
                kandidaten = []
                for aid, titel in offene:
                    fassung = texte[aid].aktueller_text()
                    kandidaten.append((aid, f"{titel} {fassung.wortlaut if fassung else ''}"))
                treffer = aehnlichste(f"{d['titel']} {d['wortlaut']}", kandidaten)
                if treffer:
                    # § 5 Abs 10 lit d: Übersicht ähnlicher Anträge SAMT Beteiligung —
                    # damit sichtbar ist, wo Unterstützung am meisten bewegt.
                    aehnliche = [
                        {
                            "antrag": texte[aid],
                            "prozent": round(score * 100),
                            "beteiligung": texte[aid].unterstuetzungen.count(),
                        }
                        for aid, score in treffer
                    ]
                    return render(
                        request,
                        "verfahren/einbringen.html",
                        {
                            "form": form,
                            "aehnliche": aehnliche,
                            "ordnung": ordnung,
                        },
                    )
            antrag = antrag_einbringen(
                request.user,
                d["titel"],
                d["wortlaut"],
                d["begruendung"],
                ordnung,
                ebene=d["ebene"],
                gebiet=form.gebiet(),
                art=d["art"],
            )
            zugeordnet = kategorien_zuordnen(antrag)  # F-47: die Plattform ordnet zu, nicht der Mensch
            if zugeordnet:
                namen = ", ".join(k.pfad_kurz for k in zugeordnet)
                messages.success(
                    request,
                    _(
                        "Ihr Antrag ist eingebracht und sammelt jetzt Unterstützung. Automatisch zugeordnet: %s."
                    )
                    % namen,
                )
            else:
                messages.success(request, _("Ihr Antrag ist eingebracht und sammelt jetzt Unterstützung."))
            return redirect("verfahren:antrag", pk=antrag.pk)
    else:
        form = AntragsFormular(mitglied=request.user)
    return render(
        request, "verfahren/einbringen.html", {"form": form, "aehnliche": aehnliche, "ordnung": ordnung}
    )


@login_required
@require_POST
def unterstuetzen(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    antrag.fortschreiben()
    if antrag.phase != Phase.UNTERSTUETZUNG.value:
        messages.error(request, _("Die Unterstützungsphase dieses Antrags ist beendet."))
        return redirect("verfahren:antrag", pk=pk)
    _egal, neu = antrag.unterstuetzungen.get_or_create(mitglied=request.user)
    if neu:
        messages.success(request, _("Danke — Ihre Unterstützung ist erfasst."))
        antrag.fortschreiben()  # Schwelle eventuell gerade erreicht
    else:
        antrag.unterstuetzungen.filter(mitglied=request.user).delete()
        messages.info(request, _("Ihre Unterstützung wurde zurückgezogen."))
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def kommentieren(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    antrag.fortschreiben()
    if antrag.phase not in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value):
        messages.error(request, _("Die Beratung dieses Antrags ist beendet."))
        return redirect("verfahren:antrag", pk=pk)
    form = KommentarFormular(request.POST)
    if form.is_valid():
        Kommentar.objects.create(antrag=antrag, mitglied=request.user, text=form.cleaned_data["text"])
        messages.success(request, _("Ihr Beitrag ist veröffentlicht."))
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def abstimmen(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()
    if antrag.art == Antragsart.MANDAT:
        messages.error(
            request, _("Bei einer Mandats-Kandidatur stimmen Sie den einzelnen Bewerbungen zu.")
        )
        return redirect("verfahren:antrag", pk=pk)
    stichtag = antrag.phase_beginn.date()
    if not request.user.ist_stimmberechtigt(
        Gegenstand.SACHFRAGE, stichtag, uebergang=settings.DDOE_UEBERGANGSREGEL
    ):
        return render(request, "verfahren/nicht_stimmberechtigt.html", status=403)
    wahl = request.POST.get("stimme", "")
    try:
        stimme_abgeben(antrag, request.user, wahl)
        messages.success(request, _("Ihre Stimme ist erfasst — bis zum Fristende können Sie sie ändern."))
    except (StimmabgabeFehler, ValueError):
        messages.error(request, _("Diese Stimme konnte nicht erfasst werden (läuft die Abstimmung noch?)."))
    # P4: Direktabstimmung aus der Regions-Kachel kehrt aufs Parlament zurück.
    weiter = request.POST.get("weiter", "")
    if weiter.startswith("/") and not weiter.startswith("//"):
        return redirect(weiter)
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def bewerben(request, pk):
    """§ 7 Abs 1 (F-70): sich am Kandidatur-Antrag beteiligen — man wird im
    Antragsfenster als wählbar geführt. Möglich bis zum Abstimmungsbeginn."""
    antrag = get_object_or_404(Antrag, pk=pk)
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    if not request.user.ist_stimmberechtigt(
        Gegenstand.PERSONENWAHL, timezone.now().date(), uebergang=settings.DDOE_UEBERGANGSREGEL
    ):
        return render(request, "verfahren/nicht_stimmberechtigt.html", status=403)
    if not request.POST.get("waehlbar"):
        messages.error(
            request,
            _("Bitte bestätigen Sie, dass Sie die gesetzlichen Voraussetzungen der Wählbarkeit erfüllen."),
        )
        return redirect("verfahren:antrag", pk=pk)
    try:
        bewerbung_einreichen(antrag, request.user, request.POST.get("vorstellung", ""))
        messages.success(
            request, _("Ihre Bewerbung ist erfasst — Sie werden im Antragsfenster als wählbar geführt.")
        )
    except BewerbungsFehler:
        messages.error(request, _("Bewerben ist nur bis zum Beginn der Abstimmung möglich (§ 7 Abs 1)."))
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def bewerbung_zurueckziehen(request, pk):
    """Der Rückzug bleibt dokumentiert; die Bewerbung zählt nicht mehr."""
    antrag = get_object_or_404(Antrag, pk=pk)
    bewerbung = antrag.bewerbungen.filter(mitglied=request.user, zurueckgezogen=False).first()
    if bewerbung:
        bewerbung.zurueckgezogen = True
        bewerbung.save(update_fields=["zurueckgezogen"])
        from verfahren.models import AuditEintrag

        AuditEintrag.anhaengen(
            {"typ": "bewerbung_zurueckgezogen", "antrag": antrag.pk, "bewerbung": bewerbung.pk}
        )
        messages.info(request, _("Ihre Bewerbung ist zurückgezogen — das bleibt öffentlich dokumentiert."))
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def kandidatur_zustimmen(request, pk, bewerbung_pk):
    """Zustimmungswahl (§ 7 Abs 1): Zustimmung geben oder zurücknehmen —
    geheim über das Stimmregister, änderbar bis zum Fristende."""
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()
    stichtag = antrag.phase_beginn.date()
    if not request.user.ist_stimmberechtigt(
        Gegenstand.PERSONENWAHL, stichtag, uebergang=settings.DDOE_UEBERGANGSREGEL
    ):
        return render(request, "verfahren/nicht_stimmberechtigt.html", status=403)
    bewerbung = get_object_or_404(Bewerbung, pk=bewerbung_pk, antrag=antrag)
    try:
        dazu = bewerbung_zustimmen(antrag, request.user, bewerbung)
        if dazu:
            messages.success(request, _("Zustimmung erfasst — bis zum Fristende können Sie sie zurücknehmen."))
        else:
            messages.info(request, _("Zustimmung zurückgenommen."))
    except StimmabgabeFehler:
        messages.error(
            request, _("Diese Zustimmung konnte nicht erfasst werden (läuft die Abstimmung noch?).")
        )
    return redirect("verfahren:antrag", pk=pk)


def export_json(request, pk):
    """F-21/F-23: maschinenlesbarer Export zum unabhängigen Nachrechnen —
    kompatibel mit verify/nachrechnen.py. Erst nach Abstimmungsende verfügbar,
    damit kein Zwischenstand die laufende Abstimmung beeinflusst."""
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()
    if antrag.phase not in (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value):
        return JsonResponse({"fehler": "Export erst nach Abstimmungsende (§ 5 Abs 3 lit d)."}, status=409)
    daten = {
        "antrag": antrag.pk,
        "titel": antrag.titel,
        "art": antrag.art,
        "policy": antrag.policy_snapshot,
        "stimmberechtigte": antrag.stimmberechtigte_anzahl,
        "stimmen": [
            {"pseudonym": s.pseudonym.hex, "stimme": s.stimme}
            for s in antrag.stimmabgaben.order_by("pseudonym")
        ],
        "exportiert_am": timezone.now().isoformat(),
    }
    if antrag.art == Antragsart.MANDAT:
        # Personenwahl (§ 7 Abs 1): Bewerbungen in Einreichungsreihenfolge und alle
        # Zustimmungen (Pseudonym → Bewerbung) — jede Person kann das Ergebnis
        # damit unabhängig nachrechnen; die eigene Stimme findet man per Prüfcode.
        daten["bewerbungen"] = [
            {
                "bewerbung": b.pk,
                "name": b.mitglied.anzeigename,
                "eingereicht_am": b.erstellt_am.isoformat(),
                "zurueckgezogen": b.zurueckgezogen,
            }
            for b in antrag.bewerbungen.all()
        ]
        daten["zustimmungen"] = [
            {"pseudonym": z.pseudonym.hex, "bewerbung": z.bewerbung_id}
            for z in BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag).order_by(
                "pseudonym", "bewerbung_id"
            )
        ]
    antwort = JsonResponse(daten, json_dumps_params={"ensure_ascii": False, "indent": 1})
    antwort["Content-Disposition"] = f'attachment; filename="antrag-{antrag.pk}-export.json"'
    return antwort


def eigene_stimme(request, pk):
    """Zeigt dem eingeloggten Mitglied Pseudonym und Prüfcode der eigenen Stimme
    (F-21: 'meine Stimme steht korrekt in der Liste')."""
    antrag = get_object_or_404(Antrag, pk=pk)
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    eintrag = StimmRegister.objects.filter(antrag=antrag, mitglied=request.user).first()
    return render(request, "verfahren/eigene_stimme.html", {"antrag": antrag, "eintrag": eintrag})


@login_required
@require_POST
def favorisieren(request, pk):
    """Bereich a (§ 5 Abs 10 lit a, F-41): Favorit setzen bzw. entfernen.
    Favoriten sind rein persönlich und wirken nie auf Reihung oder Ergebnis."""
    antrag = get_object_or_404(Antrag, pk=pk)
    _egal, neu = Favorit.objects.get_or_create(antrag=antrag, mitglied=request.user)
    if neu:
        messages.success(
            request,
            _("Als Favorit gemerkt — Sie finden das Thema jetzt in Ihrem Bereich auf der Startseite."),
        )
    else:
        Favorit.objects.filter(antrag=antrag, mitglied=request.user).delete()
        messages.info(request, _("Favorit entfernt."))
    weiter = request.POST.get("weiter", "")
    if request.headers.get("HX-Request"):
        # App-Verhalten (P1): Der Stern tauscht sich selbst aus, ohne Neuladen —
        # ohne JavaScript läuft derselbe POST als gewöhnlicher Redirect weiter.
        return render(
            request,
            "verfahren/_stern.html",
            {"antrag": antrag, "ist_favorit": neu, "weiter": weiter or "/"},
        )
    if weiter.startswith("/") and not weiter.startswith("//"):
        return redirect(weiter)
    return redirect("verfahren:antrag", pk=pk)


@login_required
@require_POST
def vollzug_eintragen(request, pk):
    """F-55, § 6 Abs 10: den Umsetzungsstand fortschreiben. Bis das Rollensystem
    (F-05) den Integrations- und Berichtswesenrat abbildet, schreiben Admins fort —
    jeder Eintrag ist öffentlich, dauerhaft und auditiert."""
    antrag = get_object_or_404(Antrag, pk=pk)
    if not request.user.hat_adminrechte:
        return render(request, "mitglieder/verwaltung_kein_zugang.html", status=403)
    try:
        vollzug_fortschreiben(
            antrag, request.user, request.POST.get("status", ""), request.POST.get("vermerk", "")
        )
        messages.success(request, _("Umsetzungsstand fortgeschrieben — öffentlich im Register sichtbar."))
    except ValueError:
        messages.error(request, _("Das Umsetzungsregister führt nur angenommene Anträge."))
    return redirect("verfahren:antrag", pk=pk)


def _laufend_je_ast() -> dict[int, int]:
    """Laufende Anträge je Knoten EINSCHLIESSLICH aller Unterkategorien —
    mit zwei Datenbankabfragen statt einer je Knoten."""
    from django.db.models import Count

    direkt: dict[int, int] = {
        zeile["kategorien"]: zeile["n"]
        for zeile in Antrag.objects.filter(phase__in=OFFENE_PHASEN, kategorien__isnull=False)
        .values("kategorien")
        .annotate(n=Count("id", distinct=True))
    }
    kinder: dict[int | None, list[int]] = {}
    for kid, eid in Kategorie.objects.filter(aktiv=True).values_list("id", "eltern_id"):
        kinder.setdefault(eid, []).append(kid)
    summen: dict[int, int] = {}

    def summe(kid: int) -> int:
        if kid not in summen:
            summen[kid] = direkt.get(kid, 0) + sum(summe(c) for c in kinder.get(kid, []))
        return summen[kid]

    for geschwister in kinder.values():
        for kid in geschwister:
            summe(kid)
    return summen


def kategorie_fokus(request, slug=None):
    """F-45: die Fokus-Ansicht des Kategorienbaums — von der einen Wurzel
    („Das gesellschaftliche Zusammenleben“) über Säulen und Bereiche bis in die
    Detailkategorie. Oben der Stamm als Brotkrume, in der Mitte der aktuelle
    Bereich, darunter die Unterbereiche zum Weiterklicken; jede Ebene ist
    favorisierbar (F-46, Ast-Wirkung), die Suche findet Namen und Schlagworte.
    Alles ohne JavaScript: jeder Klick ist eine Seite."""
    if slug:
        knoten = get_object_or_404(Kategorie, slug=slug, aktiv=True)
    else:
        knoten = Kategorie.objects.filter(aktiv=True, eltern=None).order_by("reihenfolge").first()
        if knoten is None:
            return render(request, "verfahren/keine_ordnung.html", status=503)

    abonniert: set[int] = set()
    if request.user.is_authenticated:
        abonniert = set(request.user.kategorie_abos.values_list("kategorie_id", flat=True))
    laufend = _laufend_je_ast()

    suchtext = request.GET.get("q", "").strip()
    treffer = []
    if suchtext:
        norm = suchtext.casefold()
        for k in Kategorie.objects.filter(aktiv=True):
            if (
                norm in k.name.casefold()
                or norm in k.beschreibung.casefold()
                or any(norm in wort.casefold() for wort in k.schlagworte)
            ):
                treffer.append({"k": k, "laufend": laufend.get(k.pk, 0), "abonniert": k.pk in abonniert})
        treffer.sort(key=lambda t: (t["k"].tiefe, t["k"].name))
        treffer = treffer[:40]

    kinder = [
        {
            "k": kind,
            "laufend": laufend.get(kind.pk, 0),
            "abonniert": kind.pk in abonniert,
            "anzahl_unter": kind.kinder.filter(aktiv=True).count(),
        }
        for kind in knoten.kinder.filter(aktiv=True).order_by("reihenfolge")
    ]
    ast_antraege = (
        Antrag.objects.filter(phase__in=OFFENE_PHASEN, kategorien__in=knoten.nachfahren_ids())
        .distinct()
        .order_by("phase_beginn")[:6]
    )
    return render(
        request,
        "verfahren/kategorie_fokus.html",
        {
            "knoten": knoten,
            "stamm": knoten.vorfahren(),
            "kinder": kinder,
            "abonniert": knoten.pk in abonniert,
            "laufend_gesamt": laufend.get(knoten.pk, 0),
            "ast_antraege": ast_antraege,
            "suchtext": suchtext,
            "treffer": treffer,
            "ist_wurzel": knoten.eltern_id is None,
        },
    )


@login_required
@require_POST
def kategorie_abonnieren(request, slug):
    """Abo umschalten — rein persönlich, wirkt nie auf Reihung oder Ergebnis."""
    kategorie = get_object_or_404(Kategorie, slug=slug, aktiv=True)
    _egal, neu = KategorieAbo.objects.get_or_create(kategorie=kategorie, mitglied=request.user)
    if neu:
        messages.success(
            request,
            _("„%s“ ist jetzt Favorit — Neues daraus erscheint in Ihrem Hauptfenster.") % kategorie.name,
        )
    else:
        KategorieAbo.objects.filter(kategorie=kategorie, mitglied=request.user).delete()
        messages.info(request, _("Favorit „%s“ entfernt.") % kategorie.name)
    weiter = request.POST.get("weiter", "")
    if weiter.startswith("/") and not weiter.startswith("//"):
        return redirect(weiter)
    return redirect("verfahren:kategorien")
