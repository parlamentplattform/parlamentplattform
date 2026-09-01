"""Gremien-Werkstatt, Ring 0a (F-66/F-67): Ansichten.

Öffentlich: die Besetzung aller Gremien samt Ausschreibungshinweis (§ 6 Abs 8).
Rolleninhaber: der Arbeitsbereich des Expertenrats (Gruppe 1) mit dem
Entwurfsfenster je Antrag in der Beratung — Fassungen append-only, Beiträge
und die interne Einreich-Abstimmung dokumentiert (§ 6 Abs 9).
Unterstützer: das offene Votum der Entwurfsschleife (§ 5 Abs 12) — der
Endpoint wohnt hier, das Formular auf der Antragsseite.
Verwaltung: Rollenzuweisung auf Zeit, auditiert (bewusst nur deutsch)."""

from functools import wraps

from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from gremien.models import (
    EinreichStimme,
    Entwurf,
    EntwurfsBeitrag,
    EntwurfsFassung,
    EntwurfsStatus,
    Gremium,
    Pruefung,
    Rolle,
    UnterstuetzerVotum,
    standard_ende,
)
from ki.anbieter import SteckplatzStumm, anbieter_waehlen
from ki.models import Zweck, lauf_ausfuehren
from mitglieder.models import Mitglied, Mitgliedsstatus
from mitglieder.verwaltung import nur_admins
from plattform_core import Phase
from verfahren.models import Antrag, Antragsart, AuditEintrag

# Der Auftrag an den Modell-Steckplatz (F-60) für die Werkstatt-Einschätzung —
# bewusst öffentlich im Quellcode: Auch der Auftrag ist Teil der Rechenschaft.
EINSCHAETZUNGS_AUFTRAG = (
    "Du bist Fach-Assistent des Expertenrats der ParlamentPlattform (Direkte Demokratie "
    "Österreich). Prüfe den folgenden Antragsentwurf: Fasse ihn in drei bis fünf Sätzen "
    "zusammen, benenne Unklarheiten im Wortlaut, offene Vollzugs- oder Kostenfragen und "
    "mache konkrete Formulierungsvorschläge. Liegen Wünsche der Unterstützer bei, prüfe, "
    "ob die Fassung sie aufgreift. Du machst Vorschläge — jede Entscheidung treffen "
    "Menschen. Antworte auf Deutsch, nüchtern und knapp, in Fließtext ohne Listen."
)


def nur_gremium(*gremien: str):
    """Zugang für aktive Rolleninhaber; Admins dürfen zuschauen (Aufsicht),
    schreiben aber nur mit echter Rolle — das prüfen die Handlungen selbst."""

    def deko(ansicht):
        @wraps(ansicht)
        def innen(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("mitglieder:login")
            if not (Rolle.hat(request.user, *gremien) or request.user.hat_adminrechte):
                return render(request, "gremien/kein_zugang.html", status=403)
            return ansicht(request, *args, **kwargs)

        return innen

    return deko


# ── Öffentlich ────────────────────────────────────────────────────────────────


def uebersicht(request):
    """Die Besetzung aller Gremien — Rollen auf Zeit, öffentlich (§ 6 Abs 8)."""
    heute = timezone.localdate()
    bloecke = []
    for wert, name in Gremium.choices:
        rollen = list(
            Rolle.objects.filter(gremium=wert, beendet_grund="", endet_am__gte=heute)
            .select_related("mitglied")
            .order_by("berufen_am")
        )
        bloecke.append({"wert": wert, "name": name, "rollen": rollen})
    beendete = Rolle.objects.exclude(beendet_grund="").count()
    return render(request, "gremien/uebersicht.html", {"bloecke": bloecke, "beendete": beendete})


def mein(request):
    """Der kurze Weg: bringt Rolleninhaber in ihren Arbeitsbereich."""
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    if Rolle.hat(request.user, Gremium.EXPERTENRAT_1):
        return redirect("gremien:expertenrat")
    if Rolle.hat(request.user, Gremium.EXPERTENRAT_2):
        return redirect("gremien:pruefung")
    if Rolle.hat(request.user, Gremium.KOORDINATIONSRAT):
        return redirect("gremien:koordination")
    return redirect("gremien:uebersicht")


# ── Arbeitsbereich Expertenrat, Gruppe 1 ─────────────────────────────────────


@nur_gremium(Gremium.EXPERTENRAT_1)
def expertenrat(request):
    """Alle Sachanträge in der Beratung — mit oder ohne offenes Entwurfsfenster."""
    antraege = list(
        Antrag.objects.filter(phase=Phase.BERATUNG.value, art=Antragsart.SACHE)
        .select_related("entwurf")
        .order_by("phase_beginn")
    )
    zeilen = [{"antrag": a, "entwurf": getattr(a, "entwurf", None)} for a in antraege]
    zurueckliegend = list(
        Entwurf.objects.exclude(antrag__phase=Phase.BERATUNG.value)
        .select_related("antrag")
        .order_by("-erstellt_am")[:10]
    )
    return render(
        request,
        "gremien/expertenrat.html",
        {
            "zeilen": zeilen,
            "zurueckliegend": zurueckliegend,
            "darf_schreiben": Rolle.hat(request.user, Gremium.EXPERTENRAT_1),
        },
    )


@nur_gremium(Gremium.EXPERTENRAT_1)
def fenster(request, antrag_id: int):
    """Das Entwurfsfenster: Antragstext daneben, Fassungen append-only,
    interne Beiträge, die Einreich-Abstimmung mit offenem Stand."""
    antrag = get_object_or_404(Antrag, pk=antrag_id, art=Antragsart.SACHE)
    entwurf = getattr(antrag, "entwurf", None)
    stand = entwurf.einreich_stand() if entwurf else None
    meine_stimme = None
    if entwurf and request.user.is_authenticated:
        meine_stimme = entwurf.einreich_stimmen.filter(
            mitglied=request.user, runde=entwurf.runde
        ).first()
    return render(
        request,
        "gremien/fenster.html",
        {
            "antrag": antrag,
            "text": antrag.aktueller_text(),
            "entwurf": entwurf,
            "fassungen": list(entwurf.fassungen.select_related("verfasst_von")) if entwurf else [],
            "beitraege": list(entwurf.beitraege.select_related("mitglied")) if entwurf else [],
            "stand": stand,
            "meine_stimme": meine_stimme,
            "voten": list(entwurf.unterstuetzer_voten.filter(runde=entwurf.runde)) if entwurf else [],
            "darf_schreiben": Rolle.hat(request.user, Gremium.EXPERTENRAT_1),
            "in_beratung": antrag.phase == Phase.BERATUNG.value,
            "steckplatz_bereit": anbieter_waehlen() is not None,
        },
    )


@nur_gremium(Gremium.EXPERTENRAT_1)
@require_POST
def fenster_aktion(request, antrag_id: int):
    """Eine Werkstatt, kleine Handlungen — jede Übergabe auditiert (F-66)."""
    antrag = get_object_or_404(Antrag, pk=antrag_id, art=Antragsart.SACHE)
    if not Rolle.hat(request.user, Gremium.EXPERTENRAT_1):
        messages.error(request, _("Schreiben kann hier nur, wer eine aktive Rolle in Gruppe 1 hat."))
        return redirect("gremien:fenster", antrag_id=antrag.pk)
    aktion = request.POST.get("aktion", "")
    entwurf = getattr(antrag, "entwurf", None)

    if aktion == "oeffnen":
        if antrag.phase != Phase.BERATUNG.value:
            messages.error(request, _("Ein Entwurfsfenster öffnet nur während der Beratung."))
            return redirect("gremien:fenster", antrag_id=antrag.pk)
        if entwurf is None:
            entwurf = Entwurf.objects.create(antrag=antrag)
            grundlage = antrag.aktueller_text()
            EntwurfsFassung.objects.create(
                entwurf=entwurf,
                nummer=1,
                wortlaut=grundlage.wortlaut if grundlage else "",
                begruendung="Arbeitsgrundlage: übernommener Antragswortlaut.",
                verfasst_von=request.user,
            )
            AuditEintrag.anhaengen({"typ": "entwurfsfenster_geoeffnet", "antrag": antrag.pk})
            messages.success(request, _("Entwurfsfenster geöffnet — der Antragswortlaut ist die Arbeitsgrundlage."))
        return redirect("gremien:fenster", antrag_id=antrag.pk)

    if entwurf is None:
        raise Http404("Kein Entwurfsfenster.")
    if entwurf.status != EntwurfsStatus.IN_ARBEIT:
        messages.error(request, _("Der Vorschlag ist eingereicht — die Werkstatt ruht, bis er zurückkommt."))
        return redirect("gremien:fenster", antrag_id=antrag.pk)

    if aktion == "fassung":
        wortlaut = (request.POST.get("wortlaut") or "").strip()
        if not wortlaut:
            messages.error(request, _("Eine Fassung braucht einen Wortlaut."))
        else:
            letzte = entwurf.aktuelle_fassung()
            EntwurfsFassung.objects.create(
                entwurf=entwurf,
                nummer=(letzte.nummer if letzte else 0) + 1,
                wortlaut=wortlaut,
                begruendung=(request.POST.get("begruendung") or "").strip()[:4000],
                verfasst_von=request.user,
            )
            messages.success(request, _("Neue Fassung angehängt — alle früheren bleiben stehen."))

    elif aktion == "beitrag":
        text = (request.POST.get("text") or "").strip()
        if text:
            EntwurfsBeitrag.objects.create(entwurf=entwurf, mitglied=request.user, text=text[:4000])
            messages.success(request, _("Beitrag festgehalten."))

    elif aktion == "ki_einschaetzung":
        fassung = entwurf.aktuelle_fassung()
        eingabe = f"Titel: {antrag.titel}\n\nEntwurfsfassung {fassung.nummer} (Runde {entwurf.runde}):\n{fassung.wortlaut}"
        if fassung.begruendung:
            eingabe += f"\n\nBegründung der Fassung:\n{fassung.begruendung}"
        wuensche = [
            v.wunsch
            for v in entwurf.unterstuetzer_voten.filter(runde=entwurf.runde - 1).exclude(wunsch="")
        ]
        if wuensche:
            eingabe += "\n\nWünsche der Unterstützer aus der Vorrunde:\n- " + "\n- ".join(wuensche)
        try:
            lauf = lauf_ausfuehren(
                Zweck.EINSCHAETZUNG, EINSCHAETZUNGS_AUFTRAG, eingabe, request.user, antrag=antrag
            )
        except SteckplatzStumm as grund:
            messages.info(request, str(grund))
        else:
            EntwurfsBeitrag.objects.create(
                entwurf=entwurf, mitglied=request.user, text=lauf.antwort[:4000], ki_lauf=lauf
            )
            messages.success(
                request,
                _("KI-Einschätzung festgehalten — deutlich gekennzeichnet: Sie schlägt vor, entschieden wird hier."),
            )

    elif aktion == "vollzugsbezug":
        entwurf.vollzugsbezug = request.POST.get("vollzugsbezug") == "ja"
        entwurf.save(update_fields=["vollzugsbezug"])
        messages.success(
            request,
            _("Vollzugs-/Beschaffungsbezug: %(wert)s.")
            % {"wert": _("ja — Gruppe 2 prüft") if entwurf.vollzugsbezug else _("nein")},
        )

    elif aktion == "stimme":
        einverstanden = request.POST.get("einverstanden") == "ja"
        EinreichStimme.objects.update_or_create(
            entwurf=entwurf,
            mitglied=request.user,
            runde=entwurf.runde,
            defaults={"einverstanden": einverstanden, "abgegeben_am": timezone.now()},
        )
        messages.success(request, _("Deine Stimme zur Einreichung ist festgehalten — offen, wie alles hier."))

    elif aktion == "einreichen":
        stand = entwurf.einreich_stand()
        if not stand["einreichbar"]:
            messages.error(
                request,
                _("Noch nicht einreichbar: %(ja)s Ja bei %(noetig)s nötigen Stimmen (aktive Rollen: %(aktive)s).")
                % stand,
            )
        else:
            entwurf.einreichen()
            if entwurf.vollzugsbezug:
                messages.success(request, _("Eingereicht — der Vorschlag geht zuerst an Gruppe 2 (§ 6 Abs 7)."))
            else:
                messages.success(request, _("Eingereicht — der Vorschlag liegt jetzt den Unterstützern vor (§ 5 Abs 12)."))

    return redirect("gremien:fenster", antrag_id=antrag.pk)


# ── Entwurfsschleife: das offene Votum der Unterstützer (§ 5 Abs 12) ─────────


@require_POST
def votum(request, entwurf_id: int):
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    entwurf = get_object_or_404(Entwurf.objects.select_related("antrag"), pk=entwurf_id)
    antrag = entwurf.antrag
    if entwurf.status != EntwurfsStatus.UNTERSTUETZER:
        messages.error(request, _("Der Vorschlag liegt gerade nicht zum Votum vor."))
        return redirect("verfahren:antrag", pk=antrag.pk)
    if not antrag.unterstuetzungen.filter(mitglied=request.user).exists():
        messages.error(request, _("Das Votum steht den Unterstützern dieses Antrags zu (§ 5 Abs 12)."))
        return redirect("verfahren:antrag", pk=antrag.pk)
    annehmen = request.POST.get("votum") == "annehmen"
    wunsch = (request.POST.get("wunsch") or "").strip()[:2000]
    if not annehmen and not wunsch:
        messages.error(request, _("Eine Rückgabe braucht einen konkreten Wunsch — sonst weiß die Werkstatt nicht, wohin."))
        return redirect("verfahren:antrag", pk=antrag.pk)
    UnterstuetzerVotum.objects.update_or_create(
        entwurf=entwurf,
        mitglied=request.user,
        runde=entwurf.runde,
        defaults={"annehmen": annehmen, "wunsch": wunsch, "abgegeben_am": timezone.now()},
    )
    messages.success(
        request,
        _("Angenommen — danke.") if annehmen else _("Zurückgegeben — dein Wunsch geht offen an die Werkstatt."),
    )
    # Haben alle Unterstützer gestimmt, wertet die Schleife sofort aus.
    antrag.fortschreiben()
    return redirect("verfahren:antrag", pk=antrag.pk)


# ── Verwaltung: Rollen auf Zeit (bewusst nur deutsch) ────────────────────────


class RollenFormular(forms.Form):
    mitglied = forms.ModelChoiceField(
        queryset=Mitglied.objects.filter(is_active=True, status=Mitgliedsstatus.AKTIV).order_by(
            "last_name", "first_name", "username"
        ),
        label="Mitglied",
    )
    gremium = forms.ChoiceField(label="Gremium", choices=Gremium.choices)
    endet_am = forms.DateField(label="Endet am", initial=standard_ende)
    bestaetigt = forms.BooleanField(
        label="Von der Mitgliederversammlung bestätigt (§ 6 Abs 8)", required=False
    )


@nur_admins
def rollen(request):
    heute = timezone.localdate()
    alle = list(Rolle.objects.select_related("mitglied").order_by("gremium", "berufen_am"))
    return render(
        request,
        "gremien/verwaltung_rollen.html",
        {"form": RollenFormular(), "rollen": alle, "heute": heute},
    )


@nur_admins
@require_POST
def rollen_aktion(request):
    aktion = request.POST.get("aktion", "")

    if aktion == "berufen":
        form = RollenFormular(request.POST)
        if not form.is_valid():
            messages.error(request, "Bitte alle Pflichtfelder prüfen.")
            return redirect("gremien:rollen")
        d = form.cleaned_data
        rolle = Rolle.objects.create(
            mitglied=d["mitglied"],
            gremium=d["gremium"],
            endet_am=d["endet_am"],
            bestaetigt=d["bestaetigt"],
        )
        AuditEintrag.anhaengen(
            {
                "typ": "rolle_berufen",
                "rolle": rolle.pk,
                "gremium": rolle.gremium,
                "endet_am": rolle.endet_am.isoformat(),
                "bestaetigt": rolle.bestaetigt,
            }
        )
        messages.success(
            request,
            f"Rolle berufen: {rolle.get_gremium_display()} bis {rolle.endet_am:%d.%m.%Y} — öffentlich sichtbar.",
        )

    elif aktion == "bestaetigen":
        rolle = get_object_or_404(Rolle, pk=request.POST.get("rolle"))
        rolle.bestaetigt = True
        rolle.save(update_fields=["bestaetigt"])
        AuditEintrag.anhaengen({"typ": "rolle_bestaetigt", "rolle": rolle.pk})
        messages.success(request, "Bestätigung der Mitgliederversammlung vermerkt.")

    elif aktion == "beenden":
        rolle = get_object_or_404(Rolle, pk=request.POST.get("rolle"))
        grund = (request.POST.get("grund") or "").strip()
        if not grund:
            messages.error(request, "Eine vorzeitige Beendigung braucht einen Grund — er bleibt dokumentiert.")
            return redirect("gremien:rollen")
        rolle.beendet_grund = grund[:200]
        rolle.save(update_fields=["beendet_grund"])
        AuditEintrag.anhaengen({"typ": "rolle_beendet", "rolle": rolle.pk, "grund": rolle.beendet_grund})
        messages.info(request, "Rolle beendet — Grund im Audit-Log festgehalten.")

    return redirect("gremien:rollen")


# ── Arbeitsbereich Expertenrat, Gruppe 2 (§ 6 Abs 7) ─────────────────────────


@nur_gremium(Gremium.EXPERTENRAT_2)
def pruefung(request):
    """Korruptions-Redundanz: Vorschläge mit Vollzugs- oder Beschaffungsbezug —
    validieren, begründet zurückgeben oder den Austausch beim KoRat beantragen."""
    offene = list(
        Entwurf.objects.filter(status=EntwurfsStatus.PRUEFUNG).select_related("antrag")
    )
    zeilen = [
        {
            "entwurf": e,
            "fassung": e.aktuelle_fassung(),
            "austausch_offen": e.pruefungen.filter(
                ergebnis=Pruefung.Ergebnis.AUSTAUSCH, korat_entscheid=""
            ).exists(),
        }
        for e in offene
    ]
    erledigte = list(
        Pruefung.objects.exclude(entwurf__status=EntwurfsStatus.PRUEFUNG)
        .select_related("entwurf__antrag", "durch")
        .order_by("-erstellt_am")[:10]
    )
    return render(
        request,
        "gremien/pruefung.html",
        {
            "zeilen": zeilen,
            "erledigte": erledigte,
            "darf_schreiben": Rolle.hat(request.user, Gremium.EXPERTENRAT_2),
        },
    )


@nur_gremium(Gremium.EXPERTENRAT_2)
@require_POST
def pruefung_aktion(request, entwurf_id: int):
    entwurf = get_object_or_404(Entwurf.objects.select_related("antrag"), pk=entwurf_id)
    if not Rolle.hat(request.user, Gremium.EXPERTENRAT_2):
        messages.error(request, _("Prüfen kann hier nur, wer eine aktive Rolle in Gruppe 2 hat."))
        return redirect("gremien:pruefung")
    if entwurf.status != EntwurfsStatus.PRUEFUNG:
        messages.error(request, _("Dieser Vorschlag liegt nicht (mehr) zur Prüfung vor."))
        return redirect("gremien:pruefung")
    ergebnis = request.POST.get("ergebnis", "")
    begruendung = (request.POST.get("begruendung") or "").strip()
    if ergebnis not in Pruefung.Ergebnis.values or not begruendung:
        messages.error(request, _("Bitte Ergebnis wählen und begründen — die Begründung wird veröffentlicht."))
        return redirect("gremien:pruefung")
    Pruefung.objects.create(
        entwurf=entwurf, runde=entwurf.runde, ergebnis=ergebnis, begruendung=begruendung[:4000],
        durch=request.user,
    )
    AuditEintrag.anhaengen(
        {"typ": "vorschlag_geprueft", "antrag": entwurf.antrag_id, "runde": entwurf.runde, "ergebnis": ergebnis}
    )
    if ergebnis == Pruefung.Ergebnis.VALIDIERT:
        entwurf.zu_den_unterstuetzern()
        messages.success(request, _("Validiert — der Vorschlag liegt jetzt den Unterstützern vor (§ 5 Abs 12)."))
    elif ergebnis == Pruefung.Ergebnis.ZURUECK:
        entwurf.zurueck_an_gruppe_1(f"Gruppe 2: {begruendung[:160]}", frist_erneuern=True)
        messages.success(request, _("Mit Begründung zurückgegeben — die Werkstatt ist wieder am Zug."))
    else:
        messages.success(
            request, _("Austausch beantragt — der Koordinationsrat entscheidet; die Begründung ist öffentlich.")
        )
    return redirect("gremien:pruefung")


# ── Koordinationsrat: Austauschanträge und Rollenübersicht (§ 6 Abs 8) ───────


@nur_gremium(Gremium.KOORDINATIONSRAT)
def koordination(request):
    offene = list(
        Pruefung.objects.filter(ergebnis=Pruefung.Ergebnis.AUSTAUSCH, korat_entscheid="")
        .select_related("entwurf__antrag", "durch")
        .order_by("erstellt_am")
    )
    entschiedene = list(
        Pruefung.objects.filter(ergebnis=Pruefung.Ergebnis.AUSTAUSCH)
        .exclude(korat_entscheid="")
        .select_related("entwurf__antrag")
        .order_by("-erstellt_am")[:10]
    )
    heute = timezone.localdate()
    rollen = list(
        Rolle.objects.filter(beendet_grund="", endet_am__gte=heute)
        .select_related("mitglied")
        .order_by("gremium", "berufen_am")
    )
    return render(
        request,
        "gremien/koordination.html",
        {
            "offene": offene,
            "entschiedene": entschiedene,
            "rollen": rollen,
            "darf_schreiben": Rolle.hat(request.user, Gremium.KOORDINATIONSRAT),
        },
    )


@nur_gremium(Gremium.KOORDINATIONSRAT)
@require_POST
def koordination_aktion(request, pruefung_id: int):
    antrag_der_g2 = get_object_or_404(
        Pruefung.objects.select_related("entwurf__antrag"),
        pk=pruefung_id,
        ergebnis=Pruefung.Ergebnis.AUSTAUSCH,
        korat_entscheid="",
    )
    if not Rolle.hat(request.user, Gremium.KOORDINATIONSRAT):
        messages.error(request, _("Entscheiden kann hier nur, wer eine aktive Rolle im Koordinationsrat hat."))
        return redirect("gremien:koordination")
    entscheid = request.POST.get("entscheid", "")
    begruendung = (request.POST.get("begruendung") or "").strip()
    if entscheid not in ("stattgegeben", "abgelehnt") or not begruendung:
        messages.error(request, _("Bitte entscheiden und begründen — die Entscheidung wird veröffentlicht."))
        return redirect("gremien:koordination")
    antrag_der_g2.korat_entscheid = entscheid
    antrag_der_g2.korat_begruendung = begruendung[:2000]
    antrag_der_g2.save(update_fields=["korat_entscheid", "korat_begruendung"])
    entwurf = antrag_der_g2.entwurf
    if entscheid == "stattgegeben":
        betroffen = list(Rolle.aktive(Gremium.EXPERTENRAT_1))
        for rolle in betroffen:
            rolle.beendet_grund = "Austausch durch den Koordinationsrat (§ 6 Abs 7)"
            rolle.save(update_fields=["beendet_grund"])
        entwurf.zurueck_an_gruppe_1(
            "Austausch der Gruppe 1 durch den Koordinationsrat (§ 6 Abs 7).", frist_erneuern=True
        )
        messages.success(
            request,
            _("Stattgegeben — %(n)s Rollen der Gruppe 1 beendet (dokumentiert); die neue Gruppe übernimmt den Entwurf.")
            % {"n": len(betroffen)},
        )
    else:
        messages.success(request, _("Abgelehnt — der Vorschlag bleibt bei Gruppe 2 zur Prüfung."))
    AuditEintrag.anhaengen(
        {
            "typ": "austausch_entschieden",
            "antrag": entwurf.antrag_id,
            "entscheid": entscheid,
            "pruefung": antrag_der_g2.pk,
        }
    )
    return redirect("gremien:koordination")
