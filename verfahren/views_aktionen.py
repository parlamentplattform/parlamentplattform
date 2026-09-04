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
from django.urls import reverse
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
    FilterProfil,
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


def _chat_antwort(request, antrag, anker: str = ""):
    """Nach jeder Chat-Handlung: mit htmx nur die Zone tauschen, sonst zurück auf den Anker."""
    from verfahren.views import _chat_lage

    if request.headers.get("HX-Request"):
        return render(
            request,
            "verfahren/_chat.html",
            {"antrag": antrag, "chat": _chat_lage(antrag, request.user)},
        )
    ziel = reverse("verfahren:antrag", kwargs={"pk": antrag.pk})
    return redirect(f"{ziel}#{anker}" if anker else ziel)


@login_required
@require_POST
def kommentieren(request, pk):
    """Einen Beitrag in den Chat schreiben (FB-G1) — als eigener Faden oder als Antwort."""
    from verfahren.chat import ChatGesperrt, beitrag_schreiben

    antrag = get_object_or_404(Antrag, pk=pk)
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    antrag.fortschreiben()
    antwort_auf = None
    roh = request.POST.get("antwort_auf")
    if roh:
        antwort_auf = Kommentar.objects.filter(
            pk=roh, antrag=antrag, archiviert_am__isnull=True
        ).first()
        if antwort_auf is None:
            messages.error(request, _("Der Beitrag, auf den Sie antworten wollten, ist nicht mehr im laufenden Chat."))
            return _chat_antwort(request, antrag)
    form = KommentarFormular(request.POST)
    if not form.is_valid():
        messages.error(request, _("Bitte einen Text eingeben."))
        return _chat_antwort(request, antrag)
    try:
        beitrag = beitrag_schreiben(antrag, request.user, form.cleaned_data["text"], antwort_auf)
    except ChatGesperrt:
        messages.error(request, _("Die Beratung dieses Antrags ist beendet."))
        return _chat_antwort(request, antrag)
    return _chat_antwort(request, antrag, f"k-{beitrag.pk}")


def _eigener_beitrag(request, pk, beitrag_pk):
    """Beitrag samt Antrag holen und prüfen, dass er dem Mitglied gehört und änderbar ist."""
    antrag = get_object_or_404(Antrag, pk=pk)
    beitrag = get_object_or_404(Kommentar, pk=beitrag_pk, antrag=antrag)
    return antrag, beitrag


@login_required
@require_POST
def beitrag_bearbeiten(request, pk, beitrag_pk):
    """Den eigenen Beitrag ändern — nur binnen fünf Minuten, danach steht er (FB-G1)."""
    antrag, beitrag = _eigener_beitrag(request, pk, beitrag_pk)
    if not beitrag.darf_bearbeiten(request.user):
        messages.error(request, _("Ändern ist nur in den ersten fünf Minuten möglich."))
        return _chat_antwort(request, antrag, f"k-{beitrag.pk}")
    text = (request.POST.get("text") or "").strip()[:4000]
    if not text:
        messages.error(request, _("Bitte einen Text eingeben."))
        return _chat_antwort(request, antrag, f"k-{beitrag.pk}")
    beitrag.text = text
    beitrag.bearbeitet_am = timezone.now()
    beitrag.save(update_fields=["text", "bearbeitet_am"])
    return _chat_antwort(request, antrag, f"k-{beitrag.pk}")


@login_required
@require_POST
def beitrag_entfernen(request, pk, beitrag_pk):
    """Den eigenen Beitrag zurückziehen (FB-G1): Der Text weicht einem Vermerk, der Faden bleibt.
    Gelöscht wird nichts — Antworten darunter verlören sonst ihren Bezug (Grundregel 7)."""
    antrag, beitrag = _eigener_beitrag(request, pk, beitrag_pk)
    if beitrag.mitglied_id != request.user.pk or beitrag.archiviert_am:
        messages.error(request, _("Nur eigene Beiträge im laufenden Chat lassen sich zurückziehen."))
        return _chat_antwort(request, antrag, f"k-{beitrag.pk}")
    if not beitrag.geloescht:
        beitrag.geloescht = True
        beitrag.save(update_fields=["geloescht"])
    return _chat_antwort(request, antrag, f"k-{beitrag.pk}")


@login_required
@require_POST
def reagieren(request, pk, beitrag_pk):
    """Zustimmen oder die Zustimmung zurücknehmen (FB-G1, D-G1).

    Rein informativ: Die Reihung des Chats bleibt chronologisch (Grundregel 6). Die Wahl im
    Abstimmungs-Chat des Expertenrats-Vorschlags folgt mit S7."""
    from verfahren.chat import reaktion_umschalten

    antrag, beitrag = _eigener_beitrag(request, pk, beitrag_pk)
    sperre = _mitwirkung_gesperrt(request)
    if sperre:
        return sperre
    if beitrag.archiviert_am or beitrag.geloescht:
        messages.error(request, _("Auf diesen Beitrag lässt sich nicht mehr reagieren."))
        return _chat_antwort(request, antrag, f"k-{beitrag.pk}")
    reaktion_umschalten(beitrag, request.user)
    return _chat_antwort(request, antrag, f"k-{beitrag.pk}")


@login_required
@require_POST
def melden(request, pk, beitrag_pk):
    """Einen Beitrag melden (Art 16 DSA, § 5 Abs 2, FB-G1). Die Meldung geht an die Verwaltung
    und bleibt nachlesbar; entschieden wird dort mit öffentlichem Grund."""
    from verfahren.models import AuditEintrag, Meldung

    antrag, beitrag = _eigener_beitrag(request, pk, beitrag_pk)
    grund = request.POST.get("grund", "")
    if grund not in Meldung.Grund.values:
        messages.error(request, _("Bitte einen Grund wählen."))
        return _chat_antwort(request, antrag, f"k-{beitrag.pk}")
    meldung, neu = Meldung.objects.get_or_create(
        kommentar=beitrag,
        mitglied=request.user,
        defaults={"grund": grund, "erlaeuterung": (request.POST.get("erlaeuterung") or "").strip()[:500]},
    )
    if neu:
        AuditEintrag.anhaengen(
            {"art": "beitrag_gemeldet", "antrag": antrag.pk, "beitrag": beitrag.pk, "grund": grund}
        )
    messages.success(request, _("Danke — die Meldung liegt der Verwaltung vor."))
    return _chat_antwort(request, antrag, f"k-{beitrag.pk}")


@login_required
@require_POST
def chat_gelesen(request, pk):
    """Den Lesestand vorrücken (FB-G2) — schickt die Zone, damit die „neu"-Linie verschwindet."""
    from verfahren.chat import gelesen_merken

    antrag = get_object_or_404(Antrag, pk=pk)
    gelesen_merken(antrag, request.user)
    return _chat_antwort(request, antrag)


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


def _zurueck_zum_parlament(request):
    weiter = request.POST.get("weiter", "")
    if weiter.startswith("/") and not weiter.startswith("//"):
        return redirect(weiter)
    return redirect("verfahren:parlament")


def _regler_aus_post(request):
    from plattform_core.weicherfilter import REGLER, regler_bereinigen

    return regler_bereinigen({name: request.POST.get(f"r_{name}") for name in REGLER})


@login_required
@require_POST
def filter_anwenden(request):
    """P5: Regler anwenden — ins aktive Profil speichern oder als neues Profil
    anlegen (höchstens fünf). Wirkt nur auf die eigene Ansicht (§ 2 Abs 6)."""
    regler = _regler_aus_post(request)
    favoriten_zuerst = bool(request.POST.get("favoriten_zuerst"))
    profile = request.user.filterprofile
    name_neu = (request.POST.get("profilname") or "").strip()[:24]
    werte = {"regler": regler, "favoriten_zuerst": favoriten_zuerst}

    if request.POST.get("als_neues"):
        if not name_neu:
            messages.error(request, _("Bitte einen Namen für die neue Konfiguration angeben."))
            return _zurueck_zum_parlament(request)
        if profile.count() >= FilterProfil.HOECHSTZAHL and not profile.filter(name=name_neu).exists():
            messages.error(
                request, _("Höchstens fünf Konfigurationen — bitte zuerst eine löschen oder überschreiben.")
            )
            return _zurueck_zum_parlament(request)
        profil, _egal = FilterProfil.objects.update_or_create(mitglied=request.user, name=name_neu, defaults=werte)
    else:
        profil = profile.filter(aktiv=True).first()
        if profil is None:
            if profile.count() >= FilterProfil.HOECHSTZAHL:
                messages.error(
                    request, _("Höchstens fünf Konfigurationen — bitte zuerst eine löschen oder überschreiben.")
                )
                return _zurueck_zum_parlament(request)
            profil, _egal = FilterProfil.objects.get_or_create(
                mitglied=request.user, name=str(_("Eigenes")), defaults=werte
            )
        profil.regler = regler
        profil.favoriten_zuerst = favoriten_zuerst
    profil.aktiv = True
    profil.save()
    profile.exclude(pk=profil.pk).update(aktiv=False)
    messages.success(
        request,
        _("Ihr Filter „%s“ ist aktiv — die Reihung folgt jetzt Ihren offenen Reglern.") % profil.name,
    )
    return _zurueck_zum_parlament(request)


@login_required
@require_POST
def beanstanden(request, pk):
    """FB-F2 (§ 6 Abs 11 lit b): eine Einschätzung der Zukunftswerkstatt beanstanden.
    Der Vermerk ist öffentlich und bleibt stehen; er ist zugleich die Anforderung eines
    Korrekturlaufs. Die Modellrechnung schlägt vor — wer einen Fehler sieht, hält ihn fest."""
    from ki.models import KILauf
    from verfahren.models import AuditEintrag, Beanstandung

    antrag = get_object_or_404(Antrag, pk=pk)
    text = (request.POST.get("text") or "").strip()[:2000]
    if not text:
        messages.error(request, _("Bitte beschreiben Sie, was an der Einschätzung falsch ist."))
        return _zurueck_zum_antrag(request, antrag)
    lauf = KILauf.objects.filter(antrag=antrag, erfolgreich=True).order_by("-erstellt_am").first()
    beanstandung = Beanstandung.objects.create(antrag=antrag, lauf=lauf, mitglied=request.user, text=text)
    AuditEintrag.anhaengen(
        {
            "art": "einschaetzung_beanstandet",
            "antrag": antrag.pk,
            "beanstandung": beanstandung.pk,
            "lauf": lauf.pk if lauf else None,
        }
    )
    messages.success(
        request,
        _("Ihre Beanstandung ist öffentlich vermerkt — die Zukunftswerkstatt rechnet den Punkt nach."),
    )
    return _zurueck_zum_antrag(request, antrag)


def _zurueck_zum_antrag(request, antrag):
    weiter = request.POST.get("weiter", "")
    if weiter.startswith("/") and not weiter.startswith("//"):
        return redirect(weiter)
    return redirect("verfahren:antrag", pk=antrag.pk)


@login_required
@require_POST
def filter_vorschau(request):
    """FB-B2 Live-Vorschau: reiht mit den gerade gezogenen Reglern, speichert nichts —
    die Antwort ist nur die Liste (#filter-liste), htmx tauscht sie sanft aus."""
    from verfahren.models import Unterstuetzung
    from verfahren.views import LAUFEND, _abo_ids, _meine_stimmen, _weicherfilter_feed

    regler = _regler_aus_post(request)
    favoriten_zuerst = bool(request.POST.get("favoriten_zuerst"))
    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    laufend = antraege.filter(phase__in=LAUFEND)
    jetzt = timezone.now()
    feed = _weicherfilter_feed(
        request.user, antraege, laufend, jetzt, _abo_ids(request.user),
        _meine_stimmen(request.user, list(laufend)), regler, favoriten_zuerst,
    )
    return render(
        request,
        "verfahren/_filter_liste.html",
        {
            "feed": feed,
            "meine_unterstuetzungen": set(
                Unterstuetzung.objects.filter(mitglied=request.user).values_list("antrag_id", flat=True)
            ),
        },
    )


@login_required
@require_POST
def filter_favoriten(request):
    """FB-B1: Schalter „★ Favoriten zuerst“ umschalten — in der aktiven Konfiguration,
    sonst in der Voreinstellung des Mitglieds."""
    profil = request.user.filterprofile.filter(aktiv=True).first()
    if profil is not None:
        profil.favoriten_zuerst = not profil.favoriten_zuerst
        profil.save(update_fields=["favoriten_zuerst"])
    else:
        request.user.favoriten_zuerst = not request.user.favoriten_zuerst
        request.user.save(update_fields=["favoriten_zuerst"])
    return _zurueck_zum_parlament(request)


@login_required
@require_POST
def filter_umbenennen(request, pk):
    """FB-B3: Konfiguration umbenennen (≤ 24 Zeichen, je Mitglied eindeutig)."""
    profil = get_object_or_404(FilterProfil, pk=pk, mitglied=request.user)
    name = (request.POST.get("name") or "").strip()[:24]
    if not name:
        messages.error(request, _("Bitte einen Namen angeben."))
    elif request.user.filterprofile.exclude(pk=profil.pk).filter(name=name).exists():
        messages.error(request, _("Eine Konfiguration mit diesem Namen gibt es schon."))
    else:
        profil.name = name
        profil.save(update_fields=["name"])
    return _zurueck_zum_parlament(request)


@login_required
@require_POST
def filter_waehlen(request, pk):
    profil = get_object_or_404(FilterProfil, pk=pk, mitglied=request.user)
    request.user.filterprofile.update(aktiv=False)
    profil.aktiv = True
    profil.save(update_fields=["aktiv"])
    return _zurueck_zum_parlament(request)


@login_required
@require_POST
def filter_neutral(request):
    """Zurück zur strengen Voreinstellung: Phase und Frist, chronologisch."""
    request.user.filterprofile.update(aktiv=False)
    return _zurueck_zum_parlament(request)


@login_required
@require_POST
def filter_loeschen(request, pk):
    profil = get_object_or_404(FilterProfil, pk=pk, mitglied=request.user)
    profil.delete()
    messages.info(request, _("Profil „%s“ gelöscht.") % profil.name)
    return _zurueck_zum_parlament(request)


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


def kategorie_weiter(request, slug=None):
    """Die alte Lebensbereiche-Seite ist bewusst gefallen (Vorgabe 1.9. abends):
    Der Fächer wohnt direkt im Parlament, die Suche im Feldkopf. Alte Adressen
    und Lesezeichen landen sanft am richtigen Ort."""
    ziel = reverse("verfahren:parlament")
    if slug:
        return redirect(f"{ziel}?fach={slug}#feld-favoriten")
    return redirect(f"{ziel}#feld-favoriten")


@login_required
@require_POST
def kategorie_abonnieren(request, slug):
    """Abo umschalten — rein persönlich, wirkt nie auf Reihung oder Ergebnis."""
    kategorie = get_object_or_404(Kategorie, slug=slug, aktiv=True)
    _egal, neu = KategorieAbo.objects.get_or_create(kategorie=kategorie, mitglied=request.user)
    if not neu:
        KategorieAbo.objects.filter(kategorie=kategorie, mitglied=request.user).delete()
    weiter = request.POST.get("weiter", "")
    if not (weiter.startswith("/") and not weiter.startswith("//")):
        weiter = reverse("verfahren:parlament")
    if request.headers.get("HX-Request"):
        # FB-C4: mit htmx wechselt nur der Stern selbst — kein Feldtausch, keine Flash-Meldung
        return render(
            request,
            "verfahren/_kategorie_stern.html",
            {"slug": slug, "name": kategorie.name, "abonniert": neu, "weiter": weiter},
        )
    if neu:
        messages.success(
            request,
            _("„%s“ ist jetzt Favorit — Neues daraus erscheint in Ihrem Hauptfenster.") % kategorie.name,
        )
    else:
        messages.info(request, _("Favorit „%s“ entfernt.") % kategorie.name)
    return redirect(weiter)
