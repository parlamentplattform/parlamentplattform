"""Gremien-Werkstatt, Ring 0a (F-66/F-67): Ansichten.

Öffentlich: die Besetzung aller Gremien samt Ausschreibungshinweis (§ 6 Abs 8).
Rolleninhaber: der Arbeitsbereich des Expertenrats (Gruppe 1) mit dem
Entwurfsfenster je Antrag in der Beratung — Fassungen append-only, Beiträge
und die interne Einreich-Abstimmung dokumentiert (§ 6 Abs 9).
Unterstützer: das offene Votum der Entwurfsschleife (§ 5 Abs 12) — der
Endpoint wohnt hier, das Formular auf der Antragsseite.
Verwaltung: Rollenzuweisung auf Zeit, auditiert."""

from functools import wraps

from django import forms
from django.contrib import messages
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from gremien.models import (
    JA_NEIN,
    PRUEFPUNKTE,
    SATZUNG_MIN_INTEGRITAETSRAT,
    Anlass,
    BeschlussStatus,
    EinreichStimme,
    Entwurf,
    EntwurfsBeitrag,
    EntwurfsFassung,
    EntwurfsStatus,
    GremienBeschluss,
    GremienStimme,
    Gremium,
    Pruefung,
    Rolle,
    beschluss_frist,
    standard_ende,
)
from ki.anbieter import SteckplatzStumm, anbieter_waehlen
from ki.models import Zweck, lauf_ausfuehren
from mitglieder.models import Mitglied, Mitgliedsstatus
from mitglieder.verwaltung import nur_admins
from plattform_core import Phase
from verfahren.chat import abstimmung_stand as _abstimmung_stand
from verfahren.chat import kritik_der_runde as _kritik_der_runde
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
    if Rolle.hat(request.user, Gremium.INTEGRITAETSRAT):
        return redirect("gremien:integritaet")
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
            "beschluesse": beschluesse_fuer(Gremium.EXPERTENRAT_1, request.user),
            "darf_stimmen": Rolle.hat(request.user, Gremium.EXPERTENRAT_1),
        },
    )



def _beratungsfrist(antrag) -> dict | None:
    """Wann die Beratung endet — und damit die Frist für den Erstvorschlag (FB-J1).

    Die Dauer steht in der Ordnung, die beim Einbringen an den Antrag geheftet wurde
    (§ 5 Abs 5), nicht im Register: Wer die Frist im Register verkürzt, darf einem laufenden
    Verfahren nicht die Zeit nehmen. Läuft die Frist ab, ohne dass ein Vorschlag vorliegt,
    geht der Antrag ohne Vorschlag weiter — Untätigkeit hemmt nie."""
    from datetime import timedelta

    if antrag.phase != Phase.BERATUNG.value:
        return None
    ende = antrag.phase_beginn + timedelta(days=antrag.policy().beratung_tage)
    rest = (ende - timezone.now()).days
    return {"ende": ende, "resttage": max(rest, 0), "abgelaufen": rest < 0}

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
            "abstimmung": _abstimmung_stand(antrag, entwurf) if entwurf else None,
            "wuensche_vorrunde": _kritik_der_runde(antrag, entwurf.runde - 1)
            if entwurf and entwurf.runde > 1
            else [],
            "darf_schreiben": Rolle.hat(request.user, Gremium.EXPERTENRAT_1),
            "in_beratung": antrag.phase == Phase.BERATUNG.value,
            "beratungsfrist": _beratungsfrist(antrag),
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
            f"Absatz {k['absatz']}: {k['text']}" if k["absatz"] else k["text"]
            for k in _kritik_der_runde(antrag, entwurf.runde - 1)
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


# ── Verwaltung: Rollen auf Zeit ──────────────────────────────────────────────


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
    """Korruptions-Redundanz der Gruppe 2 (§ 6 Abs 7) — als Beschluss des Gremiums.

    Bis 0.41 entschied, wer zuerst auf einen der drei Knöpfe drückte. Eine Redundanz aus einer
    Person ist keine; jetzt stimmt die Gruppe ab, mit Frist und veröffentlichter Begründung."""
    GremienBeschluss.faellige_abschliessen()
    offene = list(
        Entwurf.objects.filter(status=EntwurfsStatus.PRUEFUNG).select_related("antrag")
    )
    zeilen = []
    for entwurf in offene:
        entwurf.fortschreiben(entwurf.antrag)  # legt eine fehlende Abstimmung an, wertet fällige aus
        beschluss = entwurf.beschluesse.filter(
            gremium=Gremium.EXPERTENRAT_2, status=BeschlussStatus.OFFEN
        ).first()
        zeilen.append(
            {
                "entwurf": entwurf,
                "fassung": entwurf.aktuelle_fassung(),
                "beschluss": beschluss,
                "auswertung": beschluss.auswertung() if beschluss else None,
                "stimmen": list(beschluss.stimmen.select_related("mitglied")) if beschluss else [],
                "meine_stimme": (
                    beschluss.stimmen.filter(mitglied=request.user).first()
                    if beschluss and request.user.is_authenticated
                    else None
                ),
                "austausch_offen": entwurf.pruefungen.filter(
                    ergebnis=Pruefung.Ergebnis.AUSTAUSCH, korat_entscheid=""
                ).exists(),
            }
        )
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
            "pruefpunkte": PRUEFPUNKTE,
            "darf_schreiben": Rolle.hat(request.user, Gremium.EXPERTENRAT_2),
        },
    )



def beschluesse_fuer(gremium: str, nutzer, grenze: int = 12) -> list[dict]:
    """Die Beschlüsse eines Rates für seinen Bereich (FB-I4).

    Offene zuerst, danach die zuletzt entschiedenen — wer den Bereich öffnet, soll sehen, was
    von ihm erwartet wird, und dann, was zuletzt galt. Erledigte verschwinden nie (Grundregel 7),
    sie rücken nur nach hinten."""
    GremienBeschluss.faellige_abschliessen()
    offene = list(
        GremienBeschluss.objects.filter(gremium=gremium, status=BeschlussStatus.OFFEN)
        .prefetch_related("stimmen__mitglied")
        .order_by("frist", "angelegt_am")
    )
    erledigte = list(
        GremienBeschluss.objects.filter(gremium=gremium)
        .exclude(status=BeschlussStatus.OFFEN)
        .prefetch_related("stimmen__mitglied")
        .order_by("-entschieden_am")[:grenze]
    )
    zeilen = []
    for beschluss in offene + erledigte:
        stimmen = list(beschluss.stimmen.all())
        zeilen.append(
            {
                "beschluss": beschluss,
                "auswertung": beschluss.auswertung(),
                "stimmen": stimmen,
                "meine_stimme": next(
                    (s for s in stimmen if s.mitglied_id == getattr(nutzer, "pk", None)), None
                ),
            }
        )
    return zeilen


def beschluesse_oeffentlich(request):
    """Alle Beschlüsse aller Räte, für jeden lesbar (§ 6 Abs 9).

    Ohne Anmeldung: Wer in einem Rat sitzt, entscheidet über andere — das geschieht sichtbar,
    auch für Menschen, die (noch) nicht Mitglied sind. Gefiltert wird nach Gremium, gereiht nach
    Zeit; eine andere Reihung gibt es nicht und soll es nicht geben (Grundregel 6)."""
    GremienBeschluss.faellige_abschliessen()
    gewaehlt = request.GET.get("gremium", "")
    beschluesse = GremienBeschluss.objects.prefetch_related("stimmen__mitglied").order_by(
        "-angelegt_am"
    )
    if gewaehlt in Gremium.values:
        beschluesse = beschluesse.filter(gremium=gewaehlt)
    zeilen = [
        {
            "beschluss": b,
            "auswertung": b.auswertung(),
            "stimmen": list(b.stimmen.all()),
            "meine_stimme": None,
        }
        for b in beschluesse[: _register("gremien-beschluesse-seite", 50)]
    ]
    return render(
        request,
        "gremien/beschluesse.html",
        {
            "beschluesse": zeilen,
            "darf_stimmen": False,
            "gremien": Gremium.choices,
            "gewaehlt": gewaehlt,
        },
    )


def beschluss_oeffentlich(request, nummer: str):
    """Ein einzelner Beschluss unter seiner zitierfähigen Nummer (§ 5 Abs 10 lit b).

    Damit eine Begründung, die sich auf „IR-2026-04" beruft, auch irgendwohin führt."""
    beschluss = get_object_or_404(
        GremienBeschluss.objects.prefetch_related("stimmen__mitglied"), nummer=nummer
    )
    beschluss.abschliessen()
    beschluss.refresh_from_db()
    return render(
        request,
        "gremien/beschluss.html",
        {
            "eintrag": {
                "beschluss": beschluss,
                "auswertung": beschluss.auswertung(),
                "stimmen": list(beschluss.stimmen.all()),
                "meine_stimme": None,
            },
            "darf_stimmen": False,
        },
    )


def _register(schluessel: str, standard: int) -> int:
    from parameter.models import zahl

    return zahl(schluessel, standard)

@require_POST
def beschluss_stimme(request, beschluss_id: int):
    """Eine Stimme in einer internen Abstimmung (FB-I4, § 6 Abs 9: öffentlich mit Namen).

    Stimmberechtigt ist nur, wer im betreffenden Gremium eine **aktive** Rolle hat — geprüft
    wird beim Abgeben, nicht erst beim Zählen: Eine Stimme, die später stillschweigend verfällt,
    wäre schlimmer als eine, die gar nicht erst angenommen wird."""
    beschluss = get_object_or_404(GremienBeschluss, pk=beschluss_id)
    zurueck = _beschluss_zurueck(beschluss)
    if not Rolle.hat(request.user, beschluss.gremium):
        messages.error(request, _("Abstimmen kann nur, wer in diesem Gremium eine aktive Rolle hat."))
        return redirect(zurueck)
    if not beschluss.offen:
        messages.error(request, _("Dieser Beschluss ist bereits ausgewertet."))
        return redirect(zurueck)
    option = request.POST.get("option", "")
    if option not in beschluss.optionswerte():
        messages.error(request, _("Bitte eine der vorgesehenen Optionen wählen."))
        return redirect(zurueck)
    begruendung = (request.POST.get("begruendung") or "").strip()
    if not begruendung:
        messages.error(request, _("Bitte begründen — die Begründung wird veröffentlicht (§ 6 Abs 9)."))
        return redirect(zurueck)
    haken = [name for schluessel, name in PRUEFPUNKTE if request.POST.get(f"punkt_{schluessel}")]
    if haken:
        # Abgehakte Prüfpunkte gehören in die Begründung, nicht in eine Datenspalte: Sie sind
        # Teil dessen, was das Gremium öffentlich behauptet zu haben (§ 6 Abs 7).
        begruendung = begruendung + "\n\nGeprüft: " + "; ".join(haken) + "."
    stimme, neu = GremienStimme.objects.update_or_create(
        beschluss=beschluss,
        mitglied=request.user,
        defaults={"option": option, "begruendung": begruendung[:4000]},
    )
    if not neu:
        stimme.geaendert_am = timezone.now()
        stimme.save(update_fields=["geaendert_am"])
    AuditEintrag.anhaengen(
        {
            "typ": "gremienstimme_abgegeben",
            "gremium": beschluss.gremium,
            "beschluss": beschluss.pk,
            "option": option,
            "geaendert": not neu,
        }
    )
    if beschluss.abschliessen():
        beschluss.refresh_from_db()
        if beschluss.ergebnis:
            messages.success(
                request,
                _("Beschlossen: %(ergebnis)s — alle aktiven Rollen haben abgestimmt.")
                % {"ergebnis": beschluss.name_von(beschluss.ergebnis)},
            )
        else:
            messages.info(request, _("Abgestimmt haben alle, ein Ergebnis kam nicht zustande."))
    else:
        messages.success(request, _("Stimme abgegeben — sie steht mit Ihrem Namen öffentlich."))
    return redirect(zurueck)


def _beschluss_zurueck(beschluss) -> str:
    """Wohin nach einer Stimme — in den Bereich, aus dem der Beschluss stammt."""
    return {
        Gremium.EXPERTENRAT_1: "gremien:expertenrat",
        Gremium.EXPERTENRAT_2: "gremien:pruefung",
        Gremium.KOORDINATIONSRAT: "gremien:koordination",
        Gremium.INTEGRITAETSRAT: "gremien:integritaet",
    }.get(beschluss.gremium, "gremien:uebersicht")



# ── Arbeitsbereich Integritätsrat (§ 6 Abs 3) ────────────────────────────────


#: Was der Integritätsrat beschließen kann, und worauf es sich bezieht. Ein Anlass steht hier
#: erst, wenn seine Wirkung gebaut ist — ein Knopf, der schweigend nichts tut, wäre schlimmer
#: als ein fehlender.
IR_ANLAESSE = [
    (Anlass.HERVORHEBUNG, "Antrag hervorheben", "§ 5 Abs 10 lit b"),
    (Anlass.HERVORHEBUNG_AUFHEBEN, "Hervorhebung aufheben", "§ 5 Abs 10 lit b"),
    (Anlass.ZURUECKWEISUNG, "Antrag zurückweisen", "§ 5 Abs 2"),
    (Anlass.ZURUECKWEISUNG_AUFHEBEN, "Zurückweisung aufheben", "§ 5 Abs 2"),
]


@nur_gremium(Gremium.INTEGRITAETSRAT)
def integritaet(request):
    """Der Arbeitsbereich des Aufsichtsorgans (§ 6 Abs 3).

    Er überwacht die Einhaltung der Satzung, entscheidet über die Hervorhebung eines Antrags
    (§ 5 Abs 10 lit b) und über seine Zurückweisung (§ 5 Abs 2). Beides geschieht ausschließlich
    durch veröffentlichten, begründeten Beschluss — deshalb hat dieser Bereich keine Knöpfe, die
    unmittelbar wirken, sondern nur solche, die einen Beschluss anlegen."""
    aktive = Rolle.aktive(Gremium.INTEGRITAETSRAT).count()
    hervorgehoben = list(
        Antrag.objects.filter(hervorgehoben=True).order_by("-phase_beginn")[:20]
    )
    zurueckgewiesen = list(
        Antrag.objects.filter(phase=Phase.ZURUECKGEWIESEN.value).order_by("-phase_beginn")[:20]
    )
    return render(
        request,
        "gremien/integritaet.html",
        {
            "beschluesse": beschluesse_fuer(Gremium.INTEGRITAETSRAT, request.user),
            "darf_stimmen": Rolle.hat(request.user, Gremium.INTEGRITAETSRAT),
            "anlaesse": IR_ANLAESSE,
            "aktive": aktive,
            "mindestbesetzung": SATZUNG_MIN_INTEGRITAETSRAT,
            "besetzt": aktive >= SATZUNG_MIN_INTEGRITAETSRAT,
            "hervorgehoben": hervorgehoben,
            "zurueckgewiesen": zurueckgewiesen,
            "offene_antraege": Antrag.objects.exclude(
                phase__in=(Phase.ZURUECKGEWIESEN.value, Phase.VERFALLEN.value)
            ).order_by("-phase_beginn")[:50],
        },
    )


@nur_gremium(Gremium.INTEGRITAETSRAT)
@require_POST
def integritaet_beschluss(request):
    """Legt einen Beschluss des Integritätsrats an — abgestimmt wird danach (§ 6 Abs 2 lit e).

    Der Rat entscheidet nie mit einem Klick: Wer hier drückt, stellt die Frage; beantwortet wird
    sie von der Gruppe, mit Frist und veröffentlichter Begründung."""
    if not Rolle.hat(request.user, Gremium.INTEGRITAETSRAT):
        messages.error(request, _("Beschlüsse anlegen kann nur, wer eine aktive Rolle im Integritätsrat hat."))
        return redirect("gremien:integritaet")
    anlass = request.POST.get("anlass", "")
    erlaubt = {wert for wert, _name, _satzung in IR_ANLAESSE}
    if anlass not in erlaubt:
        messages.error(request, _("Für diesen Anlass gibt es keinen Beschlussweg."))
        return redirect("gremien:integritaet")
    antrag = get_object_or_404(Antrag, pk=request.POST.get("antrag"))
    begruendung = (request.POST.get("beschreibung") or "").strip()
    if not begruendung:
        messages.error(
            request,
            _("Bitte begründen — die Begründung erscheint mit dem Beschluss am Antrag (§ 5 Abs 10 lit b)."),
        )
        return redirect("gremien:integritaet")
    if GremienBeschluss.objects.filter(
        gremium=Gremium.INTEGRITAETSRAT, anlass=anlass, antrag=antrag, status=BeschlussStatus.OFFEN
    ).exists():
        messages.info(request, _("Zu diesem Antrag läuft bereits ein solcher Beschluss."))
        return redirect("gremien:integritaet")
    name = next(n for wert, n, _s in IR_ANLAESSE if wert == anlass)
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=anlass,
        gegenstand=f"{name}: {antrag.titel}"[:200],
        beschreibung=begruendung[:4000],
        optionen=JA_NEIN,
        frist=beschluss_frist(),
        antrag=antrag,
        angelegt_von=request.user,
    )
    AuditEintrag.anhaengen(
        {
            "typ": "gremienbeschluss_angelegt",
            "gremium": Gremium.INTEGRITAETSRAT.value,
            "anlass": anlass,
            "antrag": antrag.pk,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
        }
    )
    messages.success(
        request,
        _("Beschluss %(nummer)s angelegt — jetzt stimmt der Rat ab.") % {"nummer": beschluss.nummer},
    )
    return redirect("gremien:integritaet")

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
            "beschluesse": beschluesse_fuer(Gremium.KOORDINATIONSRAT, request.user),
            "darf_stimmen": Rolle.hat(request.user, Gremium.KOORDINATIONSRAT),
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
