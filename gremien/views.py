"""Gremien-Werkstatt, Ring 0a (F-66/F-67): Ansichten.

Öffentlich: die Besetzung aller Gremien samt Ausschreibungshinweis (§ 6 Abs 8).
Rolleninhaber: der Arbeitsbereich des Expertenrats (Gruppe 1) mit dem
Entwurfsfenster je Antrag in der Beratung — Fassungen append-only, Beiträge
und die interne Einreich-Abstimmung dokumentiert (§ 6 Abs 9).
Unterstützer: das offene Votum der Entwurfsschleife (§ 5 Abs 12) — der
Endpoint wohnt hier, das Formular auf der Antragsseite.
Verwaltung: Rollenzuweisung auf Zeit, auditiert."""

from datetime import date, timedelta
from functools import wraps

from django import forms
from django.contrib import messages
from django.http import Http404, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from gremien.models import (
    JA_NEIN,
    PRUEFPUNKTE,
    SATZUNG_MIN_INTEGRITAETSRAT,
    Anlass,
    Auslosung,
    Aussetzung,
    BeschlussStatus,
    Entwurf,
    EntwurfsBeitrag,
    EntwurfsFassung,
    EntwurfsStatus,
    Fachliste,
    GremienBeschluss,
    GremienStimme,
    Gremium,
    Hinweis,
    HinweisStatus,
    Interessenbindung,
    Pruefung,
    Regelpruefung,
    Rolle,
    Ueberlastungsmeldung,
    WunschVermerk,
    aussetzungen_fortschreiben,
    aussetzungs_gegenstand,
    beschluss_frist,
    gruppe_2_nachziehen,
    parametertests_fortschreiben,
    standard_ende,
    unvereinbar,
)
from ki.anbieter import SteckplatzStumm, anbieter_waehlen
from ki.models import Zweck, lauf_ausfuehren
from mitglieder.models import Mitglied, Mitgliedsstatus
from mitglieder.verwaltung import nur_admins
from parameter.models import Parameter, ParameterTest, Status, TestStatus
from plattform_core import Phase, wortdiff
from plattform_core.losziehung import SATZUNG_MIN_RATSGROESSE
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


PARAMETERVORSCHLAG_AUFTRAG = (
    "Du bist Assistent der Zukunftswerkstatt der ParlamentPlattform (Direkte Demokratie "
    "Österreich). Ein befristeter Test eines Verfahrensparameters ist ausgewertet. Lies "
    "Hypothese, Messgröße und die Zahlen vorher und während des Tests. Sag in vier bis sechs "
    "Sätzen, ob die Zahlen die Hypothese stützen, was sie nicht zeigen können, und welcher "
    "der drei Wege dir plausibel erscheint: einführen, verwerfen oder verlängern. Du machst "
    "einen Vorschlag — entschieden wird vom Koordinationsrat. Antworte auf Deutsch, nüchtern, "
    "in Fließtext ohne Listen."
)


def nur_gremium(*gremien: str):
    """Zugang für aktive Rolleninhaber; Admins dürfen zuschauen (Aufsicht),
    schreiben aber nur mit echter Rolle — das prüfen die Handlungen selbst.

    Wer eine Rolle **hatte**, liest weiter — mit Band (FB-I1): Das eigene Wirken soll man
    nachlesen können, auch wenn die zwei Jahre um sind. Schreiben prüft jede Handlung
    selbst über `Rolle.hat` / `Rolle.hat_fuer`; der Lesezugang öffnet nichts davon."""

    def deko(ansicht):
        @wraps(ansicht)
        def innen(request, *args, **kwargs):
            if not request.user.is_authenticated:
                return redirect("mitglieder:login")
            request.abgelaufene_rolle = None
            if not (Rolle.hat(request.user, *gremien) or request.user.hat_adminrechte):
                fruehere = Rolle.letzte(request.user, *gremien)
                if fruehere is None:
                    return render(request, "gremien/kein_zugang.html", status=403)
                request.abgelaufene_rolle = fruehere
            return ansicht(request, *args, **kwargs)

        return innen

    return deko


#: Die Räte, die einen gemeinsamen Bereich ohne eigene Werkstatt haben (FB-I1).
RAT_BEREICHE = {
    Gremium.BERICHTSWESENRAT.value: {
        "satzung": "§ 6 Abs 5 · § 6 Abs 10: führt das öffentliche Umsetzungsregister und nimmt Vollzugsberichte entgegen.",
        "verweise": lambda: [
            {"url": reverse("verfahren:umsetzung"), "titel": "Das Umsetzungsregister", "text": "Stand der Umsetzung zu jedem angenommenen Antrag, mit Historie."},
            {"url": reverse("verfahren:umsetzung_json"), "titel": "Umsetzungsregister als JSON", "text": "Maschinenlesbar, mit voller Historie."},
        ],
    },
    Gremium.ENTWICKLUNGSRAT.value: {
        "satzung": "§ 6 Abs 4: verantwortet Erstellung, Betrieb und Optimierung von ParlamentPlattform und Zukunftswerkstatt.",
        "verweise": lambda: [
            {"url": reverse("parameter:regeln"), "titel": "Das Regelverzeichnis", "text": "Jede automatisierte Regel mit Fassung, Datum und Begründung (§ 2 Abs 6)."},
            {"url": reverse("parameter:liste"), "titel": "Das Parameterregister", "text": "Die Stellgrößen mit Herkunft und Änderungsgeschichte."},
            {"url": reverse("verfahren:zukunftswerkstatt"), "titel": "Die Zukunftswerkstatt", "text": "Stand des Modell-Steckplatzes, Budget, Läufe."},
        ],
    },
}


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


def _bereich_url(gremium: str) -> str:
    """Wo der Arbeitsbereich eines Gremiums liegt."""
    feste = {
        Gremium.EXPERTENRAT_1: "gremien:expertenrat",
        Gremium.EXPERTENRAT_2: "gremien:pruefung",
        Gremium.KOORDINATIONSRAT: "gremien:koordination",
        Gremium.INTEGRITAETSRAT: "gremien:integritaet",
    }
    if gremium in feste:
        return reverse(feste[gremium])
    if gremium in RAT_BEREICHE:
        return reverse("gremien:rat", args=[gremium])
    return reverse("gremien:uebersicht")


def mein(request):
    """Der kurze Weg: bringt Rolleninhaber in ihren Arbeitsbereich.

    Eine Rolle — direkt hinein. Mehrere — eine Auswahlseite (FB-I1): Wer in Gruppe 1 für
    einen Antrag gelost ist und zugleich im Koordinationsrat sitzt, soll nicht raten müssen,
    wohin der Knopf führt."""
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    heute = timezone.localdate()
    rollen = list(
        Rolle.objects.filter(mitglied=request.user, beendet_grund="", endet_am__gte=heute)
        .select_related("antrag")
        .order_by("gremium", "berufen_am")
    )
    if not rollen:
        return redirect("gremien:uebersicht")
    bereiche = []
    gesehen = set()
    for rolle in rollen:
        if rolle.gremium in gesehen:
            continue
        gesehen.add(rolle.gremium)
        bereiche.append(
            {
                "name": rolle.get_gremium_display(),
                "url": _bereich_url(rolle.gremium),
                "antrag": rolle.antrag,
                "endet_am": rolle.endet_am,
            }
        )
    if len(bereiche) == 1:
        return redirect(bereiche[0]["url"])
    return render(request, "gremien/mein.html", {"bereiche": bereiche})


# ── Arbeitsbereich Expertenrat, Gruppe 1 ─────────────────────────────────────



def fachliste(request):
    """Die öffentlich geführte Liste der Fachleute (§ 6 Abs 7).

    Öffentlich ohne Anmeldung: Aus dieser Liste wird der Expertenrat je Antrag ausgelost, und
    wer das Ergebnis nachrechnen will, muss den Lostopf kennen. Interessenbindungen und Honorare
    stehen dabei — die Satzung nennt beides ausdrücklich; ohne diese Angabe wäre die Auslosung
    eine Auswahl unter Unbekannten."""
    eintraege = (
        Fachliste.objects.select_related("mitglied")
        .prefetch_related("fachgebiete")
        .order_by("gestrichen_am", "schluessel")
    )
    zeilen = [
        {
            "eintrag": e,
            "unvereinbar": unvereinbar(e.mitglied) if e.gefuehrt else "",
            "fachgebiete": list(e.fachgebiete.all()),
        }
        for e in eintraege
    ]
    return render(
        request,
        "gremien/fachliste.html",
        {
            "zeilen": zeilen,
            "gefuehrt": sum(1 for z in zeilen if z["eintrag"].gefuehrt and not z["unvereinbar"]),
            "mindestgroesse": SATZUNG_MIN_RATSGROESSE,
        },
    )


def auslosung(request, antrag_id: int):
    """Eine vollzogene Auslosung, offen zum Nachrechnen (§ 6 Abs 7, § 2 Abs 6).

    Öffentlich ohne Anmeldung: Wer prüfen will, ob die Fachleute wirklich gelost und nicht
    ausgesucht wurden, braucht den Anker, den Lostopf und die Loswerte — sonst ist
    „Zufallsverfahren" eine Behauptung."""
    antrag = get_object_or_404(Antrag, pk=antrag_id)
    ziehungen = list(
        Auslosung.objects.filter(antrag=antrag).prefetch_related("rollen__mitglied").order_by("runde")
    )
    namen = dict(
        Fachliste.objects.select_related("mitglied").values_list("schluessel", "mitglied__username")
    )
    for eintrag in Fachliste.objects.select_related("mitglied"):
        namen[eintrag.schluessel] = eintrag.anzeigename
    zeilen = [
        {
            "auslosung": a,
            "gruppen": [
                {
                    "nummer": nummer,
                    "plaetze": [
                        {**p, "name": namen.get(p["schluessel"], p["schluessel"])}
                        for p in a.plaetze
                        if p["gruppe"] == nummer
                    ],
                }
                for nummer in sorted({p["gruppe"] for p in a.plaetze})
            ],
        }
        for a in ziehungen
    ]
    return render(
        request,
        "gremien/auslosung.html",
        {"antrag": antrag, "zeilen": zeilen, "namen": namen},
    )

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
            "ratsmitglieder": [r.mitglied for r in Rolle.aktive(Gremium.EXPERTENRAT_1).select_related("mitglied")],
            "jahr": timezone.localdate().year,
        },
    )



def _beratungsfrist(antrag) -> dict | None:
    """Wann die Beratung endet — und damit die Frist für den Erstvorschlag (FB-J1).

    Die Dauer steht in der Ordnung, die beim Einbringen an den Antrag geheftet wurde
    (§ 5 Abs 5), nicht im Register: Wer die Frist im Register verkürzt, darf einem laufenden
    Verfahren nicht die Zeit nehmen. Läuft die Frist ab, ohne dass ein Vorschlag vorliegt,
    geht der Antrag ohne Vorschlag weiter — Untätigkeit hemmt nie."""
    if antrag.phase != Phase.BERATUNG.value:
        return None
    ende = antrag.wirksamer_phase_beginn() + timedelta(days=antrag.policy().beratung_tage)
    rest = (ende - timezone.now()).days
    return {"ende": ende, "resttage": max(rest, 0), "abgelaufen": rest < 0}

@nur_gremium(Gremium.EXPERTENRAT_1)
def fenster(request, antrag_id: int):
    """Das Entwurfsfenster: Antragstext daneben, Fassungen append-only,
    interne Beiträge, die Einreich-Abstimmung mit offenem Stand."""
    from verfahren.views import _einschaetzung

    antrag = get_object_or_404(Antrag, pk=antrag_id, art=Antragsart.SACHE)
    entwurf = getattr(antrag, "entwurf", None)
    text = antrag.aktueller_text()
    fassungen = list(entwurf.fassungen.select_related("verfasst_von")) if entwurf else []
    letzte = fassungen[-1] if fassungen else None
    vorige = fassungen[-2] if len(fassungen) > 1 else None
    diff_an = bool(request.GET.get("diff")) and vorige is not None
    einreichung = None
    if entwurf:
        offener = entwurf.einreichungsbeschluss()
        if offener is not None:
            offener_stimmen = list(offener.stimmen.select_related("mitglied"))
            einreichung = {
                "beschluss": offener,
                "auswertung": offener.auswertung(),
                "stimmen": offener_stimmen,
                "meine_stimme": next((s for s in offener_stimmen if s.mitglied_id == request.user.pk), None),
            }
    wuensche = _kritik_der_runde(antrag, entwurf.runde - 1) if entwurf and entwurf.runde > 1 else []
    vermerke = (
        {v.kommentar_id: v for v in entwurf.wunschvermerke.select_related("durch")} if entwurf else {}
    )
    for wunsch in wuensche:
        wunsch["vermerk"] = vermerke.get(wunsch["id"])
    return render(
        request,
        "gremien/fenster.html",
        {
            "antrag": antrag,
            "text": text,
            "absaetze_antrag": wortdiff.absaetze(text.wortlaut) if text else [],
            "entwurf": entwurf,
            "fassungen": fassungen,
            "letzte": letzte,
            "vorige": vorige,
            "absaetze_fassung": wortdiff.absaetze(letzte.wortlaut) if letzte else [],
            "diff_an": diff_an,
            "diff": wortdiff.vergleichen(vorige.wortlaut, letzte.wortlaut) if diff_an else [],
            "diff_stand": wortdiff.zusammenfassung(wortdiff.vergleichen(vorige.wortlaut, letzte.wortlaut))
            if vorige is not None and letzte is not None
            else None,
            "beitraege": list(entwurf.beitraege.select_related("mitglied", "ki_lauf")) if entwurf else [],
            "einreichung": einreichung,
            "interessenbindungen": list(
                antrag.interessenbindungen.select_related("mitglied").order_by("-runde", "erklaert_am")
            ),
            "einschaetzung": _einschaetzung(antrag),
            "abstimmung": _abstimmung_stand(antrag, entwurf) if entwurf else None,
            "wuensche_vorrunde": wuensche,
            "darf_schreiben": Rolle.hat_fuer(request.user, Gremium.EXPERTENRAT_1, antrag),
            "auslosung": Auslosung.objects.filter(antrag=antrag).order_by("-runde").first(),
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
    if not Rolle.hat_fuer(request.user, Gremium.EXPERTENRAT_1, antrag):
        # § 6 Abs 7: Der Expertenrat wird „für die Beratung zu einzelnen Anträgen" gelost.
        # Ohne diese Bindung schriebe eine für Antrag A geloste Fachkraft an Antrag B mit —
        # und die Auslosung wäre eine Anzeige statt einer Zuständigkeit.
        messages.error(
            request,
            _("Schreiben kann hier nur, wer für diesen Antrag in Gruppe 1 gelost oder berufen ist."),
        )
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
        elif entwurf.einreichungsbeschluss() is not None:
            # Sonst stimmte die Gruppe über einen Text ab, der sich unter der Hand ändert.
            messages.error(request, _("Solange über die Einreichung abgestimmt wird, ruht die Fassung."))
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
        absatz = _absatz(request.POST.get("absatz"), entwurf)
        if text:
            EntwurfsBeitrag.objects.create(
                entwurf=entwurf, mitglied=request.user, text=text[:4000], absatz=absatz
            )
            messages.success(request, _("Beitrag festgehalten."))

    elif aktion == "wunsch":
        # Ein Wunsch der Unterstützer, als berücksichtigt vermerkt — eine Auskunft der Gruppe,
        # kein Urteil; deshalb umschaltbar und ohne Audit.
        from verfahren.models import Kommentar

        kommentar = get_object_or_404(Kommentar, pk=request.POST.get("kommentar"), antrag=antrag, ist_kritik=True)
        vorhanden = WunschVermerk.objects.filter(entwurf=entwurf, kommentar=kommentar).first()
        if vorhanden is not None:
            vorhanden.delete()
            messages.info(request, _("Vermerk zurückgenommen."))
        else:
            fassung = entwurf.aktuelle_fassung()
            WunschVermerk.objects.create(
                entwurf=entwurf, kommentar=kommentar, fassung=fassung.nummer if fassung else 0, durch=request.user
            )
            messages.success(request, _("Als berücksichtigt vermerkt — die Unterstützer prüfen das in der nächsten Runde."))

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
        if entwurf.vollzugsbezug:
            # § 6 Abs 7: „zwei unabhängig voneinander besetzte Gruppen“ — Gruppe 2 wird gelost,
            # sobald feststeht, dass sie gebraucht wird (Befund #14/#37). Einmal je Antrag.
            if gruppe_2_nachziehen(antrag) is not None:
                messages.info(request, _("Gruppe 2 wurde für diesen Antrag aus der Fachliste gelost."))

    elif aktion == "einreichung":
        if antrag.phase != Phase.BERATUNG.value:
            messages.error(request, _("Der Antrag ist nicht (mehr) in der Beratung."))
        elif entwurf.einreichungsbeschluss() is not None:
            messages.info(request, _("Über die Einreichung wird bereits abgestimmt."))
        else:
            beschluss = entwurf.einreichungsbeschluss_anlegen(request.user)
            if beschluss is None:
                messages.error(request, _("Ohne Fassung gibt es nichts einzureichen."))
            else:
                messages.success(
                    request,
                    _("Beschluss %(nummer)s angelegt — die Gruppe stimmt über die Einreichung ab; die Fassung ruht solange.")
                    % {"nummer": beschluss.nummer},
                )

    return redirect("gremien:fenster", antrag_id=antrag.pk)


def _absatz(roh, entwurf) -> int | None:
    """Die Absatznummer eines Beitrags — nur, wenn es den Absatz in der aktuellen Fassung gibt."""
    try:
        nummer = int(roh or 0)
    except (TypeError, ValueError):
        return None
    fassung = entwurf.aktuelle_fassung()
    if nummer < 1 or fassung is None or nummer > len(wortdiff.absaetze(fassung.wortlaut)):
        return None
    return nummer


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


def _unvereinbarkeit(mitglied, gremium: str) -> str:
    """Warum diese Rolle nicht vergeben werden darf — oder leer (§ 6 Abs 3 lit a).

    Mitglieder des Integritätsrats dürfen keinem anderen Rat angehören und kein Mandat
    ausüben; umgekehrt darf niemand in den Integritätsrat, der in einem anderen Rat sitzt."""
    if gremium == Gremium.INTEGRITAETSRAT:
        andere = Rolle.objects.filter(
            mitglied=mitglied, beendet_grund="", endet_am__gte=timezone.localdate()
        ).exclude(gremium=Gremium.INTEGRITAETSRAT)
        if andere.exists():
            return "Mitglied eines anderen Rates (§ 6 Abs 3 lit a)"
        grund = unvereinbar(mitglied)
        if grund and "Mandat" in grund:
            return grund
        return ""
    if Rolle.hat(mitglied, Gremium.INTEGRITAETSRAT):
        return "Mitglied des Integritätsrats — kein anderer Rat (§ 6 Abs 3 lit a)"
    return ""


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
        grund = _unvereinbarkeit(d["mitglied"], d["gremium"])
        if grund:
            # § 6 Abs 3 lit a — geprüft bei der Vergabe, nicht erst beim Losen: Eine Rolle,
            # die es nicht geben darf, soll gar nicht erst entstehen.
            messages.error(request, f"Nicht berufen — {grund}.")
            return redirect("gremien:rollen")
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
            "beschluesse": beschluesse_fuer(Gremium.EXPERTENRAT_2, request.user),
            "darf_stimmen": Rolle.hat(request.user, Gremium.EXPERTENRAT_2),
            "ratsmitglieder": [r.mitglied for r in Rolle.aktive(Gremium.EXPERTENRAT_2).select_related("mitglied")],
            "jahr": timezone.localdate().year,
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
    if not Rolle.hat_fuer(request.user, beschluss.gremium, beschluss.antrag):
        # Bei einem Beschluss zu einem Antrag zählt die Rolle FÜR DIESEN Antrag — sonst
        # stimmten Gelose fremder Verfahren mit, und das Quorum wäre eine andere Frage.
        messages.error(
            request,
            _("Abstimmen kann nur, wer für diese Sache eine aktive Rolle in diesem Gremium hat."),
        )
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
    if beschluss.anlass == Anlass.EINREICHUNG:
        # § 6 Abs 7: Interessenbindungen zu DIESEM Antrag — Pflichtfeld; „keine" ist eine Antwort.
        bindung = (request.POST.get("interessenbindung") or "").strip()
        if not bindung:
            messages.error(
                request,
                _("Bitte die Interessenbindungen zu diesem Antrag angeben — „keine“ ist eine Antwort (§ 6 Abs 7)."),
            )
            return redirect(zurueck)
        Interessenbindung.objects.update_or_create(
            antrag=beschluss.antrag,
            mitglied=request.user,
            runde=beschluss.entwurf.runde if beschluss.entwurf_id else 1,
            defaults={"text": bindung[:1000], "erklaert_am": timezone.now()},
        )
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
    if beschluss.anlass == Anlass.EINREICHUNG and beschluss.antrag_id:
        return reverse("gremien:fenster", args=[beschluss.antrag_id])
    return _bereich_url(beschluss.gremium)


@require_POST
def beschluss_umsetzung(request, beschluss_id: int):
    """Der Umsetzungsvermerk zu einem entschiedenen Beschluss (FB-I5): was wie umgesetzt wird,
    wer es übernimmt, bis wann. Schreiben darf, wer im Rat eine aktive Rolle hat; der
    Vermerk steht öffentlich beim Beschluss (§ 6 Abs 9)."""
    beschluss = get_object_or_404(GremienBeschluss, pk=beschluss_id)
    zurueck = _beschluss_zurueck(beschluss)
    if not Rolle.hat_fuer(request.user, beschluss.gremium, beschluss.antrag):
        messages.error(request, _("Den Umsetzungsvermerk schreibt nur, wer in diesem Rat eine aktive Rolle hat."))
        return redirect(zurueck)
    if beschluss.status != BeschlussStatus.ENTSCHIEDEN:
        messages.error(request, _("Ein Umsetzungsvermerk gehört zu einem entschiedenen Beschluss."))
        return redirect(zurueck)
    vermerk = (request.POST.get("umsetzungsvermerk") or "").strip()
    if not vermerk:
        messages.error(request, _("Bitte sagen, was wie umgesetzt wird."))
        return redirect(zurueck)
    beschluss.umsetzungsvermerk = vermerk[:2000]
    beschluss.umsetzung_durch = None
    wer = request.POST.get("umsetzung_durch")
    if wer:
        rolle = Rolle.aktive(beschluss.gremium).filter(mitglied_id=wer).select_related("mitglied").first()
        if rolle is None:
            messages.error(request, _("Zugewiesen werden kann nur ein Mitglied dieses Rates."))
            return redirect(zurueck)
        beschluss.umsetzung_durch = rolle.mitglied
    beschluss.umsetzung_frist = None
    frist = (request.POST.get("umsetzung_frist") or "").strip()
    if frist:
        try:
            beschluss.umsetzung_frist = date.fromisoformat(frist)
        except ValueError:
            messages.error(request, _("Die Frist braucht ein Datum."))
            return redirect(zurueck)
    beschluss.save(update_fields=["umsetzungsvermerk", "umsetzung_durch", "umsetzung_frist"])
    AuditEintrag.anhaengen(
        {
            "typ": "umsetzungsvermerk",
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
            "zugewiesen": beschluss.umsetzung_durch_id is not None,
            "frist": beschluss.umsetzung_frist.isoformat() if beschluss.umsetzung_frist else None,
        }
    )
    messages.success(request, _("Umsetzungsvermerk festgehalten — er steht öffentlich beim Beschluss."))
    return redirect(zurueck)


def protokoll(request, gremium: str, jahr: int):
    """Das Sitzungsprotokoll eines Rates für ein Jahr (FB-I4, § 6 Abs 9) — als JSON.

    Ein Rat, der auf der Plattform arbeitet, hat kein Protokollbuch: Die Beschlüsse mit
    Stimmen, Begründungen und Umsetzungsvermerken **sind** das Protokoll. Öffentlich, weil die
    Satzung es so will; maschinenlesbar, damit es niemand abtippen muss."""
    if gremium not in Gremium.values:
        raise Http404("Kein solches Gremium.")
    GremienBeschluss.faellige_abschliessen()
    beschluesse = (
        GremienBeschluss.objects.filter(gremium=gremium, angelegt_am__year=jahr)
        .prefetch_related("stimmen__mitglied")
        .select_related("antrag", "umsetzung_durch")
        .order_by("angelegt_am")
    )
    eintraege = []
    for b in beschluesse:
        auswertung = b.auswertung()
        eintraege.append(
            {
                "nummer": b.nummer,
                "anlass": b.anlass,
                "gegenstand": b.gegenstand,
                "beschreibung": b.beschreibung,
                "antrag": b.antrag_id,
                "angelegt_am": b.angelegt_am.isoformat(),
                "frist": b.frist.isoformat() if b.frist else None,
                "status": b.status,
                "ergebnis": b.ergebnis,
                "entschieden_am": b.entschieden_am.isoformat() if b.entschieden_am else None,
                "regel_version": b.regel_version,
                "abgegeben": auswertung.abgegeben,
                "noetig": auswertung.noetig,
                "stimmen": [
                    {
                        "mitglied": s.mitglied.anzeigename,
                        "option": s.option,
                        "begruendung": s.begruendung,
                        "abgegeben_am": s.abgegeben_am.isoformat(),
                        "geaendert": s.geaendert_am is not None,
                    }
                    for s in b.stimmen.all()
                ],
                "umsetzungsvermerk": b.umsetzungsvermerk,
                "umsetzung_durch": b.umsetzung_durch.anzeigename if b.umsetzung_durch else None,
                "umsetzung_frist": b.umsetzung_frist.isoformat() if b.umsetzung_frist else None,
            }
        )
    antwort = JsonResponse(
        {
            "gremium": gremium,
            "name": Gremium(gremium).label,
            "jahr": jahr,
            "beschluesse": eintraege,
            "exportiert_am": timezone.now().isoformat(),
        },
        json_dumps_params={"ensure_ascii": False, "indent": 1},
    )
    antwort["Content-Disposition"] = f'attachment; filename="protokoll-{gremium}-{jahr}.json"'
    return antwort



# ── Arbeitsbereich Integritätsrat (§ 6 Abs 3) ────────────────────────────────


#: Was der Integritätsrat beschließen kann, und worauf es sich bezieht. Ein Anlass steht hier
#: erst, wenn seine Wirkung gebaut ist — ein Knopf, der schweigend nichts tut, wäre schlimmer
#: als ein fehlender.
IR_ANLAESSE = [
    (Anlass.HERVORHEBUNG, "Antrag hervorheben", "§ 5 Abs 10 lit b"),
    (Anlass.HERVORHEBUNG_AUFHEBEN, "Hervorhebung aufheben", "§ 5 Abs 10 lit b"),
    (Anlass.ZURUECKWEISUNG, "Antrag zurückweisen", "§ 5 Abs 2"),
    (Anlass.ZURUECKWEISUNG_AUFHEBEN, "Zurückweisung aufheben", "§ 5 Abs 2"),
    (Anlass.AUSSETZUNG, "Aussetzen", "§ 6 Abs 3 lit d"),
    (Anlass.AUSSETZUNG_AUFHEBEN, "Aussetzung aufheben", "§ 6 Abs 3 lit d"),
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
            "ratsmitglieder": [r.mitglied for r in Rolle.aktive(Gremium.INTEGRITAETSRAT).select_related("mitglied")],
            "anlaesse": IR_ANLAESSE,
            "aktive": aktive,
            "mindestbesetzung": SATZUNG_MIN_INTEGRITAETSRAT,
            "besetzt": aktive >= SATZUNG_MIN_INTEGRITAETSRAT,
            "hervorgehoben": hervorgehoben,
            "zurueckgewiesen": zurueckgewiesen,
            "aussetzungen": _aussetzungen_lage(),
            "regelpruefungen": Regelpruefung.objects.select_related("beschluss")[:5],
            "regelpruefung_offen": Regelpruefung.objects.filter(geprueft_am__isnull=True).exists(),
            "jahr": timezone.localdate().year,
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
    if anlass == Anlass.AUSSETZUNG:
        # § 6 Abs 3 lit d nennt nur „den Vollzug eines Beschlusses oder eine laufende Abstimmung“
        # — geprüft schon beim Anlegen, damit der Rat nicht über etwas abstimmt, das ohne
        # Wirkung bliebe (Befund #31). Die Phase vorher fortschreiben, sonst gälte ein alter Stand.
        antrag.fortschreiben()
        if aussetzungs_gegenstand(antrag) is None:
            messages.error(
                request,
                _("Aussetzen lässt sich nur eine laufende Abstimmung oder der Vollzug eines Beschlusses (§ 6 Abs 3 lit d)."),
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


def _aussetzungen_lage() -> list[dict]:
    """Laufende zuerst, danach die beendeten — mit dem Grund, warum sie endeten."""
    aussetzungen_fortschreiben()
    jetzt = timezone.now()
    zeilen = [
        {"aussetzung": a, "laeuft": a.laeuft(jetzt), "stand": a.stand(jetzt)}
        for a in Aussetzung.objects.select_related("antrag", "beschluss")[:20]
    ]
    return sorted(zeilen, key=lambda z: (not z["laeuft"],))


@nur_gremium(Gremium.INTEGRITAETSRAT)
@require_POST
def integritaet_schiedsgericht(request, aussetzung_id: int):
    """Vermerkt den Antrag an das Parteischiedsgericht (§ 6 Abs 3 lit d).

    Ohne diesen Vermerk endet die Aussetzung binnen sieben Tagen von selbst — die Satzung sagt
    das ausdrücklich, und die Plattform tut es auch, ohne dass jemand daran denken muss."""
    if not Rolle.hat(request.user, Gremium.INTEGRITAETSRAT):
        messages.error(request, _("Das kann nur, wer eine aktive Rolle im Integritätsrat hat."))
        return redirect("gremien:integritaet")
    aussetzung = get_object_or_404(Aussetzung, pk=aussetzung_id)
    kennung = (request.POST.get("kennung") or "").strip()
    if not kennung:
        messages.error(request, _("Bitte die Kennung des Antrags beim Parteischiedsgericht angeben."))
        return redirect("gremien:integritaet")
    if not aussetzung.laeuft():
        messages.error(request, _("Diese Aussetzung wirkt nicht mehr."))
        return redirect("gremien:integritaet")
    aussetzung.schiedsgericht_am = timezone.now()
    aussetzung.schiedsgericht_kennung = kennung[:60]
    aussetzung.save(update_fields=["schiedsgericht_am", "schiedsgericht_kennung"])
    AuditEintrag.anhaengen(
        {
            "typ": "aussetzung_beim_schiedsgericht",
            "antrag": aussetzung.antrag_id,
            "aussetzung": aussetzung.pk,
            "kennung": aussetzung.schiedsgericht_kennung,
        }
    )
    messages.success(request, _("Vermerkt — die Aussetzung endet jetzt nicht mehr mit der Frist."))
    return redirect("gremien:integritaet")


@nur_gremium(Gremium.INTEGRITAETSRAT)
@require_POST
def integritaet_regelpruefung(request):
    """Legt die jährliche Prüfung der automatisierten Regeln an (§ 2 Abs 6).

    Das Verzeichnis wird dabei eingefroren, wie es in diesem Augenblick steht: Der Vermerk
    „geprüft am …" wäre ohne die Liste, auf die er sich bezieht, wertlos."""
    from plattform_core.regelwerk import VERSION as VERZEICHNIS_VERSION
    from plattform_core.regelwerk import als_dict

    if not Rolle.hat(request.user, Gremium.INTEGRITAETSRAT):
        messages.error(request, _("Das kann nur, wer eine aktive Rolle im Integritätsrat hat."))
        return redirect("gremien:integritaet")
    jahr = timezone.localdate().year
    if Regelpruefung.objects.filter(jahr=jahr).exists():
        messages.info(request, _("Für dieses Jahr läuft die Prüfung bereits oder ist abgeschlossen."))
        return redirect("gremien:integritaet")
    stand = als_dict()
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.REGELPRUEFUNG,
        gegenstand=f"Jährliche Prüfung der automatisierten Regeln {jahr}",
        beschreibung=(
            f"{len(stand)} Regeln geprüft (Verzeichnis Fassung {VERZEICHNIS_VERSION}). "
            "Der geprüfte Stand ist an diesem Beschluss eingefroren."
        ),
        optionen=[
            {"wert": "geprueft", "name": "geprüft, keine Beanstandung"},
            {"wert": "beanstandet", "name": "beanstandet"},
        ],
        frist=beschluss_frist(),
        angelegt_von=request.user,
    )
    Regelpruefung.objects.create(
        jahr=jahr, beschluss=beschluss, stand=stand, verzeichnis_fassung=VERZEICHNIS_VERSION
    )
    AuditEintrag.anhaengen(
        {
            "typ": "regelpruefung_angelegt",
            "jahr": jahr,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
            "regeln": len(stand),
        }
    )
    messages.success(
        request,
        _("Prüfung %(nummer)s angelegt — %(n)s Regeln eingefroren.")
        % {"nummer": beschluss.nummer, "n": len(stand)},
    )
    return redirect("gremien:integritaet")

# ── Koordinationsrat: Austauschanträge und Rollenübersicht (§ 6 Abs 8) ───────


@nur_gremium(Gremium.KOORDINATIONSRAT)
def koordination(request):
    """Der Arbeitsbereich des Koordinationsrats (FB-I5, § 6 Abs 2): vier Karten.

    Aufgaben (Austauschanträge, Überlastungsmeldungen, Vollzugsberichte), der Posteingang der
    Zukunftswerkstatt, die Beschlüsse mit Umsetzungsvermerk, Parameter & Tests. Kein Knopf
    hier wirkt unmittelbar: Jeder legt einen Beschluss an oder vermerkt etwas — der Rat
    entscheidet als Rat (§ 6 Abs 2 lit e), nicht wer zuerst drückt."""
    from parameter.kennzahlen import werte
    from plattform_core.parametertest import messgroessen

    parametertests_fortschreiben()
    jetzt = timezone.now()
    offene = list(
        Pruefung.objects.filter(ergebnis=Pruefung.Ergebnis.AUSTAUSCH, korat_entscheid="")
        .select_related("entwurf__antrag", "durch", "korat_beschluss")
        .order_by("erstellt_am")
    )
    for pruefung_ in offene:
        pruefung_.beschluss_offen = (
            pruefung_.korat_beschluss if pruefung_.korat_beschluss and pruefung_.korat_beschluss.offen else None
        )
    entschiedene = list(
        Pruefung.objects.filter(ergebnis=Pruefung.Ergebnis.AUSTAUSCH)
        .exclude(korat_entscheid="")
        .select_related("entwurf__antrag")
        .order_by("-erstellt_am")[:10]
    )
    ueberlastungen = []
    for meldung in Ueberlastungsmeldung.objects.select_related("beschluss", "antrag_an_mv")[:20]:
        rest = (meldung.frist - jetzt).days
        ueberlastungen.append(
            {
                "meldung": meldung,
                "resttage": max(rest, 0),
                "ueberfaellig": rest < 0 and not meldung.erledigt_am,
                "beschluss_offen": meldung.beschluss if meldung.beschluss and meldung.beschluss.offen else None,
            }
        )
    from verfahren.models import Vollzugseintrag

    heute = timezone.localdate()
    tests = []
    for test in ParameterTest.objects.select_related("parameter", "beschluss", "ki_lauf")[:20]:
        offener = None
        if test.status == TestStatus.AUSGEWERTET:
            offener = GremienBeschluss.objects.filter(einfuehrungen=test, status=BeschlussStatus.OFFEN).first()
        tests.append(
            {
                "test": test,
                "gegenueberstellung": test.gegenueberstellung() if test.werte_nachher else None,
                "einfuehrung_offen": offener,
            }
        )
    return render(
        request,
        "gremien/koordination.html",
        {
            "beschluesse": beschluesse_fuer(Gremium.KOORDINATIONSRAT, request.user),
            "darf_stimmen": Rolle.hat(request.user, Gremium.KOORDINATIONSRAT),
            "darf_schreiben": Rolle.hat(request.user, Gremium.KOORDINATIONSRAT),
            "ratsmitglieder": [r.mitglied for r in Rolle.aktive(Gremium.KOORDINATIONSRAT).select_related("mitglied")],
            "aktive": Rolle.aktive(Gremium.KOORDINATIONSRAT).count(),
            "offene": offene,
            "entschiedene": entschiedene,
            "ueberlastungen": ueberlastungen,
            "vollzugsberichte": list(Vollzugseintrag.objects.select_related("antrag").order_by("-erstellt_am")[:10]),
            "laufende": list(
                Antrag.objects.exclude(phase__in=(Phase.ZURUECKGEWIESEN.value, Phase.VERFALLEN.value))
                .filter(hervorgehoben=False)
                .order_by("-phase_beginn")[:50]
            ),
            "hinweise": list(Hinweis.objects.select_related("parametertest__parameter")[:20]),
            "tests": tests,
            "parameter": list(Parameter.objects.exclude(status=Status.IM_TEST).order_by("gruppe", "schluessel")),
            "messgroessen": messgroessen(werte()),
            "jahr": heute.year,
            "rollen": list(
                Rolle.objects.filter(beendet_grund="", endet_am__gte=heute)
                .select_related("mitglied", "antrag")
                .order_by("gremium", "berufen_am")
            ),
        },
    )


#: Was der Koordinationsrat beschließen kann — und welche Wirkung daran hängt.
KR_ANLAESSE = {
    Anlass.INTERN.value: "innere Angelegenheit",
    Anlass.AUSTAUSCH.value: "Austausch der Gruppe 1",
    Anlass.UEBERLASTUNG.value: "Vorschlag zur Überlastungsmeldung",
    Anlass.HERVORHEBUNG_ANREGEN.value: "Hervorhebung beim Integritätsrat beantragen",
}


@nur_gremium(Gremium.KOORDINATIONSRAT)
@require_POST
def koordination_beschluss(request):
    """Legt einen Beschluss des Koordinationsrats an — abgestimmt wird danach (§ 6 Abs 2 lit e)."""
    if not Rolle.hat(request.user, Gremium.KOORDINATIONSRAT):
        messages.error(request, _("Beschlüsse anlegen kann nur, wer eine aktive Rolle im Koordinationsrat hat."))
        return redirect("gremien:koordination")
    anlass = request.POST.get("anlass", "")
    if anlass not in KR_ANLAESSE:
        messages.error(request, _("Für diesen Anlass gibt es keinen Beschlussweg."))
        return redirect("gremien:koordination")
    beschreibung = (request.POST.get("beschreibung") or "").strip()
    if not beschreibung:
        messages.error(request, _("Bitte sagen, worum es geht — der Text wird mit dem Beschluss veröffentlicht."))
        return redirect("gremien:koordination")
    felder = {"antrag": None, "gegenstand": ""}
    pruefung_ = meldung = None
    if anlass == Anlass.AUSTAUSCH:
        pruefung_ = get_object_or_404(
            Pruefung.objects.select_related("entwurf__antrag"),
            pk=request.POST.get("pruefung"),
            ergebnis=Pruefung.Ergebnis.AUSTAUSCH,
            korat_entscheid="",
        )
        if pruefung_.korat_beschluss and pruefung_.korat_beschluss.offen:
            messages.info(request, _("Über diesen Austauschantrag wird bereits abgestimmt."))
            return redirect("gremien:koordination")
        felder["antrag"] = pruefung_.entwurf.antrag
        felder["gegenstand"] = f"Austausch der Gruppe 1: {pruefung_.entwurf.antrag.titel}"
    elif anlass == Anlass.UEBERLASTUNG:
        meldung = get_object_or_404(Ueberlastungsmeldung, pk=request.POST.get("meldung"), erledigt_am__isnull=True)
        if meldung.beschluss and meldung.beschluss.offen:
            messages.info(request, _("Über diese Meldung wird bereits abgestimmt."))
            return redirect("gremien:koordination")
        felder["gegenstand"] = f"Vorschlag an die Mitgliederversammlung: Überlastung {meldung.stelle}"
    elif anlass == Anlass.HERVORHEBUNG_ANREGEN:
        antrag = get_object_or_404(Antrag, pk=request.POST.get("antrag"))
        if GremienBeschluss.objects.filter(
            gremium=Gremium.KOORDINATIONSRAT, anlass=anlass, antrag=antrag, status=BeschlussStatus.OFFEN
        ).exists():
            messages.info(request, _("Zu diesem Antrag läuft bereits ein solcher Beschluss."))
            return redirect("gremien:koordination")
        felder["antrag"] = antrag
        felder["gegenstand"] = f"Hervorhebung beantragen: {antrag.titel}"
    else:
        felder["gegenstand"] = (request.POST.get("gegenstand") or "").strip()
        if not felder["gegenstand"]:
            messages.error(request, _("Ein Beschluss braucht einen Gegenstand."))
            return redirect("gremien:koordination")
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.KOORDINATIONSRAT,
        anlass=anlass,
        gegenstand=felder["gegenstand"][:200],
        beschreibung=beschreibung[:4000],
        optionen=JA_NEIN,
        frist=beschluss_frist(),
        antrag=felder["antrag"],
        angelegt_von=request.user,
    )
    if pruefung_ is not None:
        pruefung_.korat_beschluss = beschluss
        pruefung_.save(update_fields=["korat_beschluss"])
    if meldung is not None:
        meldung.beschluss = beschluss
        meldung.save(update_fields=["beschluss"])
    AuditEintrag.anhaengen(
        {
            "typ": "gremienbeschluss_angelegt",
            "gremium": Gremium.KOORDINATIONSRAT.value,
            "anlass": anlass,
            "antrag": felder["antrag"].pk if felder["antrag"] else None,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
        }
    )
    messages.success(request, _("Beschluss %(nummer)s angelegt — jetzt stimmt der Rat ab.") % {"nummer": beschluss.nummer})
    return redirect("gremien:koordination")


@nur_gremium(Gremium.KOORDINATIONSRAT)
@require_POST
def koordination_hinweis(request, hinweis_id: int):
    """Ein Eintrag des Posteingangs wird erledigt: Beschluss, Kenntnis oder Verwerfen mit Grund."""
    if not Rolle.hat(request.user, Gremium.KOORDINATIONSRAT):
        messages.error(request, _("Den Posteingang bearbeitet nur, wer eine aktive Rolle im Koordinationsrat hat."))
        return redirect("gremien:koordination")
    hinweis = get_object_or_404(Hinweis, pk=hinweis_id, status=HinweisStatus.OFFEN)
    aktion = request.POST.get("aktion", "")
    jetzt = timezone.now()
    if aktion == "beschluss":
        if hinweis.parametertest is None or hinweis.parametertest.status != TestStatus.AUSGEWERTET:
            messages.error(request, _("Aus diesem Hinweis lässt sich kein Beschluss ableiten."))
            return redirect("gremien:koordination")
        beschluss = _einfuehrung_anlegen(hinweis.parametertest, request.user)
        if beschluss is None:
            messages.info(request, _("Über die Einführung wird bereits abgestimmt."))
            return redirect("gremien:koordination")
        hinweis.status = HinweisStatus.BESCHLUSS
        hinweis.grund = beschluss.nummer
    elif aktion == "kenntnis":
        hinweis.status = HinweisStatus.KENNTNIS
    elif aktion == "verwerfen":
        grund = (request.POST.get("grund") or "").strip()
        if not grund:
            messages.error(request, _("Verwerfen braucht einen Grund — er bleibt stehen."))
            return redirect("gremien:koordination")
        hinweis.status = HinweisStatus.VERWORFEN
        hinweis.grund = grund[:500]
        if hinweis.parametertest and hinweis.parametertest.status == TestStatus.AUSGEWERTET:
            test = hinweis.parametertest
            test.status = TestStatus.VERWORFEN
            test.auswertung = (test.auswertung + f"\\n\\nVerworfen: {grund}")[:4000]
            test.save(update_fields=["status", "auswertung"])
    else:
        messages.error(request, _("Unbekannte Handlung."))
        return redirect("gremien:koordination")
    hinweis.erledigt_von = request.user
    hinweis.erledigt_am = jetzt
    hinweis.save(update_fields=["status", "grund", "erledigt_von", "erledigt_am"])
    AuditEintrag.anhaengen({"typ": "hinweis_erledigt", "hinweis": hinweis.pk, "status": hinweis.status})
    messages.success(request, _("Erledigt: %(status)s.") % {"status": hinweis.get_status_display()})
    return redirect("gremien:koordination")


def _einfuehrung_anlegen(test, von):
    """Der Beschluss über die Einführung eines getesteten Werts (§ 6 Abs 11 lit c)."""
    if GremienBeschluss.objects.filter(einfuehrungen=test, status=BeschlussStatus.OFFEN).exists():
        return None
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.KOORDINATIONSRAT,
        anlass=Anlass.PARAMETER_EINFUEHRUNG,
        gegenstand=f"Einführung: {test.parameter.schluessel} = {test.testwert}"[:200],
        beschreibung=test.auswertung[:4000],
        optionen=JA_NEIN,
        frist=beschluss_frist(),
        angelegt_von=von,
    )
    test.einfuehrung_beschluss = beschluss
    test.save(update_fields=["einfuehrung_beschluss"])
    AuditEintrag.anhaengen(
        {
            "typ": "gremienbeschluss_angelegt",
            "gremium": Gremium.KOORDINATIONSRAT.value,
            "anlass": Anlass.PARAMETER_EINFUEHRUNG.value,
            "test": test.pk,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
        }
    )
    return beschluss


@nur_gremium(Gremium.KOORDINATIONSRAT)
@require_POST
def koordination_test(request, test_id: int):
    """Parametertests (FB-J3, § 6 Abs 11 lit c): anordnen, Einführung beschließen, verwerfen,
    die Zukunftswerkstatt fragen. Anordnen und Einführen laufen über einen Beschluss —
    die Satzung nennt beide Male den Rat, nicht ein Ratsmitglied."""
    if not Rolle.hat(request.user, Gremium.KOORDINATIONSRAT):
        messages.error(request, _("Tests ordnet nur an, wer eine aktive Rolle im Koordinationsrat hat."))
        return redirect("gremien:koordination")
    aktion = request.POST.get("aktion", "")
    if aktion == "anordnen":
        return _test_anordnen(request)
    test = get_object_or_404(ParameterTest.objects.select_related("parameter"), pk=test_id)
    if test.status != TestStatus.AUSGEWERTET:
        messages.error(request, _("Das geht nur bei einem ausgewerteten Test."))
        return redirect("gremien:koordination")
    if aktion == "einfuehrung":
        beschluss = _einfuehrung_anlegen(test, request.user)
        if beschluss is None:
            messages.info(request, _("Über die Einführung wird bereits abgestimmt."))
        else:
            messages.success(request, _("Beschluss %(nummer)s angelegt — jetzt stimmt der Rat ab.") % {"nummer": beschluss.nummer})
    elif aktion == "verwerfen":
        grund = (request.POST.get("grund") or "").strip()
        if not grund:
            messages.error(request, _("Verwerfen braucht einen Grund — er bleibt stehen."))
            return redirect("gremien:koordination")
        test.status = TestStatus.VERWORFEN
        test.auswertung = (test.auswertung + f"\\n\\nVerworfen: {grund}")[:4000]
        test.save(update_fields=["status", "auswertung"])
        Hinweis.objects.filter(parametertest=test, status=HinweisStatus.OFFEN).update(
            status=HinweisStatus.VERWORFEN, grund=grund[:500], erledigt_von=request.user, erledigt_am=timezone.now()
        )
        AuditEintrag.anhaengen({"typ": "parametertest_verworfen", "test": test.pk, "grund": grund[:500]})
        messages.success(request, _("Verworfen — der alte Wert gilt weiter, der Grund bleibt stehen."))
    elif aktion == "zukunftswerkstatt":
        g = test.gegenueberstellung()
        eingabe = (
            f"Parameter: {test.parameter.schluessel} ({test.parameter.beschreibung})\\n"
            f"Alter Wert: {test.alter_wert} — Testwert: {test.testwert}\\n"
            f"Hypothese: {test.hypothese}\\nMessgröße: {test.messgroesse}\\n"
            f"Vorher: {g.vorher} — während des Tests: {g.nachher} — Differenz: {g.differenz}"
            + (f" ({g.anteil} %)" if g.anteil is not None else "")
            + f"\\nTestzeitraum: {test.beginn} bis {test.ende}"
        )
        try:
            lauf = lauf_ausfuehren(Zweck.PARAMETERVORSCHLAG, PARAMETERVORSCHLAG_AUFTRAG, eingabe, request.user)
        except SteckplatzStumm as grund:
            messages.info(request, str(grund))
        else:
            test.ki_lauf = lauf
            test.save(update_fields=["ki_lauf"])
            messages.success(request, _("Einschätzung festgehalten — sie schlägt vor, entschieden wird hier."))
    else:
        messages.error(request, _("Unbekannte Handlung."))
    return redirect("gremien:koordination")


def _test_anordnen(request):
    from parameter.kennzahlen import werte
    from plattform_core.parametertest import messgroessen

    parameter = get_object_or_404(Parameter, pk=request.POST.get("parameter"))
    testwert = (request.POST.get("testwert") or "").strip()[:100]
    hypothese = (request.POST.get("hypothese") or "").strip()[:300]
    messgroesse = (request.POST.get("messgroesse") or "").strip()[:80]
    rueckweg = (request.POST.get("rueckweg") or "").strip()[:1000]
    try:
        ende = date.fromisoformat((request.POST.get("ende") or "").strip())
    except ValueError:
        ende = None
    if not (testwert and hypothese and messgroesse and rueckweg and ende):
        messages.error(request, _("Testwert, Hypothese, Messgröße, Ende und Rückweg sind Pflicht — der Test wird veröffentlicht."))
        return redirect("gremien:koordination")
    if ende <= timezone.localdate():
        messages.error(request, _("Das Ende des Tests muss in der Zukunft liegen."))
        return redirect("gremien:koordination")
    if messgroesse not in messgroessen(werte()):
        messages.error(request, _("Die Messgröße muss eine Kennzahl aus /kennzahlen.json sein."))
        return redirect("gremien:koordination")
    if testwert == parameter.wert:
        messages.info(request, _("Der Testwert ist der geltende Wert — nichts zu testen."))
        return redirect("gremien:koordination")
    if parameter.status == Status.IM_TEST or ParameterTest.objects.filter(
        parameter=parameter, status__in=(TestStatus.GEPLANT, TestStatus.LAEUFT)
    ).exists():
        messages.info(request, _("Auf diesem Parameter läuft schon ein Test oder ist einer geplant."))
        return redirect("gremien:koordination")
    test = ParameterTest.objects.create(
        parameter=parameter,
        testwert=testwert,
        hypothese=hypothese,
        messgroesse=messgroesse,
        ende=ende,
        rueckweg=rueckweg,
        angeordnet_von=request.user,
    )
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.KOORDINATIONSRAT,
        anlass=Anlass.PARAMETERTEST,
        gegenstand=f"Test: {parameter.schluessel} = {testwert} bis {ende:%d.%m.%Y}"[:200],
        beschreibung=f"Hypothese: {hypothese}\\nMessgröße: {messgroesse}\\nRückweg: {rueckweg}"[:4000],
        optionen=JA_NEIN,
        frist=beschluss_frist(),
        angelegt_von=request.user,
    )
    test.beschluss = beschluss
    test.save(update_fields=["beschluss"])
    AuditEintrag.anhaengen(
        {
            "typ": "gremienbeschluss_angelegt",
            "gremium": Gremium.KOORDINATIONSRAT.value,
            "anlass": Anlass.PARAMETERTEST.value,
            "schluessel": parameter.schluessel,
            "test": test.pk,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
        }
    )
    messages.success(request, _("Beschluss %(nummer)s angelegt — der Test beginnt, wenn der Rat zustimmt.") % {"nummer": beschluss.nummer})
    return redirect("gremien:koordination")


@require_POST
def ueberlastung_melden(request):
    """Eine Überlastungsmeldung (§ 6 Abs 10) — von der berichtspflichtigen Stelle.

    Heute melden die Admins der Plattform (sie führen das Umsetzungsregister, bis der
    Integrations- und Berichtswesenrat besetzt ist) und dessen Mitglieder. Die Meldung ist
    sofort öffentlich; die 30-Tage-Frist des Koordinationsrats läuft ab jetzt."""
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    if not (request.user.hat_adminrechte or Rolle.hat(request.user, Gremium.BERICHTSWESENRAT)):
        messages.error(request, _("Überlastung meldet nur eine berichtspflichtige Stelle (§ 6 Abs 10)."))
        return redirect("verfahren:umsetzung")
    stelle = (request.POST.get("stelle") or "").strip()[:120]
    begruendung = (request.POST.get("begruendung") or "").strip()
    if not stelle or not begruendung:
        messages.error(request, _("Stelle und Begründung sind Pflicht — die Meldung wird veröffentlicht."))
        return redirect("verfahren:umsetzung")
    meldung = Ueberlastungsmeldung.objects.create(
        stelle=stelle, begruendung=begruendung[:4000], gemeldet_von=request.user
    )
    AuditEintrag.anhaengen({"typ": "ueberlastung_gemeldet", "meldung": meldung.pk, "stelle": stelle})
    messages.success(
        request,
        _("Überlastungsmeldung veröffentlicht — der Koordinationsrat hat bis %(datum)s Zeit für einen Vorschlag.")
        % {"datum": timezone.localtime(meldung.frist).strftime("%d.%m.%Y")},
    )
    return redirect("verfahren:umsetzung")


# ── Die weiteren Räte (FB-I1): Berichtswesenrat, Entwicklungsrat ───────────────────────


def _rat_pruefen(gremium: str) -> None:
    if gremium not in RAT_BEREICHE:
        raise Http404("Dieser Rat hat keinen eigenen Bereich.")


def rat(request, gremium: str):
    """Der gemeinsame Bereich der Räte ohne eigene Werkstatt: Beschlüsse und Verweise."""
    _rat_pruefen(gremium)
    return nur_gremium(gremium)(_rat)(request, gremium)


def _rat(request, gremium: str):
    bereich = RAT_BEREICHE[gremium]
    heute = timezone.localdate()
    return render(
        request,
        "gremien/rat.html",
        {
            "gremium": gremium,
            "name": Gremium(gremium).label,
            "satzung": bereich["satzung"],
            "verweise": bereich["verweise"](),
            "beschluesse": beschluesse_fuer(gremium, request.user),
            "darf_stimmen": Rolle.hat(request.user, gremium),
            "darf_schreiben": Rolle.hat(request.user, gremium),
            "ratsmitglieder": [r.mitglied for r in Rolle.aktive(gremium).select_related("mitglied")],
            "ueberlastungen": list(Ueberlastungsmeldung.objects.all()[:10])
            if gremium == Gremium.BERICHTSWESENRAT
            else [],
            "jahr": heute.year,
            "rollen": list(Rolle.aktive(gremium).select_related("mitglied").order_by("berufen_am")),
        },
    )


@require_POST
def rat_beschluss(request, gremium: str):
    """Ein Beschluss in einer inneren Angelegenheit — für jeden Rat (FB-I4)."""
    if gremium not in Gremium.values:
        raise Http404("Kein solches Gremium.")
    zurueck = _bereich_url(gremium)
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    if not Rolle.hat(request.user, gremium):
        messages.error(request, _("Beschlüsse anlegen kann nur, wer in diesem Rat eine aktive Rolle hat."))
        return redirect(zurueck)
    gegenstand = (request.POST.get("gegenstand") or "").strip()
    beschreibung = (request.POST.get("beschreibung") or "").strip()
    if not gegenstand or not beschreibung:
        messages.error(request, _("Gegenstand und Beschreibung sind Pflicht — beides wird veröffentlicht."))
        return redirect(zurueck)
    beschluss = GremienBeschluss.objects.create(
        gremium=gremium,
        anlass=Anlass.INTERN,
        gegenstand=gegenstand[:200],
        beschreibung=beschreibung[:4000],
        optionen=JA_NEIN,
        frist=beschluss_frist(),
        angelegt_von=request.user,
    )
    AuditEintrag.anhaengen(
        {
            "typ": "gremienbeschluss_angelegt",
            "gremium": gremium,
            "anlass": Anlass.INTERN.value,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
        }
    )
    messages.success(request, _("Beschluss %(nummer)s angelegt — jetzt stimmt der Rat ab.") % {"nummer": beschluss.nummer})
    return redirect(zurueck)


# ── Der jährliche öffentliche Bericht des Integritätsrats (§ 6 Abs 3 lit c) ─────────────


def integritaet_bericht(request, jahr: int):
    """„Er berichtet mindestens jährlich öffentlich." — erzeugt aus dem, was der Rat im Jahr tat.

    Kein Freitext, den jemand kürzen könnte (§ 6 Abs 3 lit c: der Koordinationsrat darf die
    Berichte weder kürzen noch zurückhalten): Die Seite entsteht aus den Beschlüssen,
    Aussetzungen und der Regelprüfung des Jahres. Wer den Bericht liest, liest Daten."""
    GremienBeschluss.faellige_abschliessen()
    beschluesse = list(
        GremienBeschluss.objects.filter(gremium=Gremium.INTEGRITAETSRAT, angelegt_am__year=jahr)
        .select_related("antrag")
        .order_by("angelegt_am")
    )
    nach_anlass = {}
    for b in beschluesse:
        nach_anlass.setdefault(b.get_anlass_display(), []).append(b)
    aussetzungen = list(
        Aussetzung.objects.filter(beginn__year=jahr).select_related("antrag", "beschluss")
    )
    regelpruefungen = list(Regelpruefung.objects.filter(beschluss__angelegt_am__year=jahr).select_related("beschluss"))
    rollen = list(
        Rolle.objects.filter(gremium=Gremium.INTEGRITAETSRAT, berufen_am__year__lte=jahr, endet_am__year__gte=jahr)
        .select_related("mitglied")
        .order_by("berufen_am")
    )
    return render(
        request,
        "gremien/integritaet_bericht.html",
        {
            "jahr": jahr,
            "beschluesse": beschluesse,
            "nach_anlass": sorted(nach_anlass.items()),
            "entschieden": sum(1 for b in beschluesse if b.status == BeschlussStatus.ENTSCHIEDEN),
            "ohne_ergebnis": sum(1 for b in beschluesse if b.status == BeschlussStatus.OHNE_ERGEBNIS),
            "aussetzungen": aussetzungen,
            "regelpruefungen": regelpruefungen,
            "rollen": rollen,
            "hervorgehoben": Antrag.objects.filter(hervorgehoben=True).count(),
            "zurueckgewiesen": Antrag.objects.filter(phase=Phase.ZURUECKGEWIESEN.value, phase_beginn__year=jahr).count(),
            "mindestbesetzung": SATZUNG_MIN_INTEGRITAETSRAT,
            "jahre": sorted(
                {d.year for d in GremienBeschluss.objects.filter(gremium=Gremium.INTEGRITAETSRAT).values_list("angelegt_am", flat=True)}
                | {timezone.localdate().year}
            ),
        },
    )
