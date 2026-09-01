"""Lesende Ansichten. Grundsatz F-31: Sortierung ausschließlich nach Frist und
Phase — niemals nach Beliebtheit. Ergebnisseiten sind ohne Login lesbar (F-20)."""

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.translation import gettext as _

from plattform_core import Phase
from verfahren.models import Antrag, Kategorie, Vollzugsstatus

LAUFEND = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]


def index(request):
    """Das Hauptfenster in vier Bereichen (§ 5 Abs 10, F-40) — Reihung immer nur
    nach Phase und Frist, nie nach Beliebtheit oder verdeckter Gewichtung (F-31)."""
    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    laufend = antraege.filter(phase__in=LAUFEND)

    # Bühne für Gäste: drei öffentliche Kennzahlen (identisch mit der Übersichtsseite, F-50).
    buehne = None
    if not request.user.is_authenticated:
        from mitglieder.models import Mitglied

        buehne = {
            "mitglieder": Mitglied.objects.filter(is_active=True).count(),
            "laufend": laufend.count(),
            "beschluesse": Antrag.objects.filter(phase=Phase.ANGENOMMEN.value).count(),
        }

    # Bereich a — persönliche Favoriten und abonnierte Lebensbereiche (F-41, F-46)
    favoriten_abstimmung = favoriten_sonstige = themen_neu = None
    meine_favoriten: set[int] = set()
    if request.user.is_authenticated:
        meine_favoriten = set(request.user.favoriten.values_list("antrag_id", flat=True))
        eigene = laufend.filter(id__in=meine_favoriten)
        favoriten_abstimmung = eigene.filter(phase=Phase.ABSTIMMUNG.value).order_by("phase_beginn")
        favoriten_sonstige = eigene.exclude(phase=Phase.ABSTIMMUNG.value).order_by("phase_beginn")
        # Ein Abo gilt für den ganzen Ast: Unterkategorien der abonnierten Bereiche zählen mit.
        abo_ids = set(request.user.kategorie_abos.values_list("kategorie_id", flat=True))
        kinder: dict[int | None, list[int]] = {}
        for kid, eid in Kategorie.objects.filter(aktiv=True).values_list("id", "eltern_id"):
            kinder.setdefault(eid, []).append(kid)
        rand = list(abo_ids)
        while rand:
            neue = [k for e in rand for k in kinder.get(e, []) if k not in abo_ids]
            abo_ids.update(neue)
            rand = neue
        themen_neu = (
            laufend.filter(kategorien__in=abo_ids)
            .exclude(id__in=meine_favoriten)
            .distinct()
            .order_by("phase_beginn")[:6]
        )

    # Bereich b — vom Integritätsrat hervorgehobene Abstimmungen (F-42, nie algorithmisch)
    wichtige = laufend.filter(hervorgehoben=True).order_by("phase_beginn")

    # Bereich c — regionale Anträge (Gemeinde/Bezirk/Land, F-43)
    regionale = laufend.exclude(ebene="bund").order_by("phase_beginn")

    # Bereich d — alle Verfahren nach Phase und Frist
    gruppen = [
        (_("Laufende Abstimmungen"), antraege.filter(phase=Phase.ABSTIMMUNG.value).order_by("phase_beginn")),
        (_("In Beratung"), antraege.filter(phase=Phase.BERATUNG.value).order_by("phase_beginn")),
        (
            _("Sammeln Unterstützung"),
            antraege.filter(phase=Phase.UNTERSTUETZUNG.value).order_by("phase_beginn"),
        ),
        (
            _("Abgeschlossen"),
            antraege.filter(
                phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value, Phase.VERFALLEN.value]
            ).order_by("-phase_beginn")[:20],
        ),
    ]
    return render(
        request,
        "verfahren/index.html",
        {
            "buehne": buehne,
            "gruppen": gruppen,
            "favoriten_abstimmung": favoriten_abstimmung,
            "favoriten_sonstige": favoriten_sonstige,
            "themen_neu": themen_neu,
            "meine_favoriten": meine_favoriten,
            "wichtige": wichtige,
            "regionale": regionale,
        },
    )


def antrag_detail(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()  # fällige Übergänge lazy anwenden (idempotent; Produktion: zusätzlich Cron)
    ergebnis = None
    if antrag.phase in (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value):
        ergebnis = antrag.auszaehlen()
    from plattform_core.phases import (
        abstimmung_frist_ende,
        beratung_frist_ende,
        unterstuetzung_frist_ende,
    )

    policy = antrag.policy()
    frist = None
    if antrag.phase == Phase.UNTERSTUETZUNG.value:
        frist = unterstuetzung_frist_ende(antrag.phase_beginn, policy)
    elif antrag.phase == Phase.BERATUNG.value:
        frist = beratung_frist_ende(antrag.phase_beginn, policy)
    elif antrag.phase == Phase.ABSTIMMUNG.value:
        frist = abstimmung_frist_ende(antrag.phase_beginn, policy)
    unterstuetzt_von_mir = (
        request.user.is_authenticated and antrag.unterstuetzungen.filter(mitglied=request.user).exists()
    )
    meine_stimme = None
    if request.user.is_authenticated:
        reg = antrag.stimmregister.filter(mitglied=request.user).first()
        if reg:
            ab = antrag.stimmabgaben.filter(pseudonym=reg.pseudonym).first()
            meine_stimme = ab.stimme if ab else None
    ist_favorit = request.user.is_authenticated and antrag.favoriten.filter(mitglied=request.user).exists()
    vollzug = None
    if antrag.phase == Phase.ANGENOMMEN.value:
        vollzug = list(antrag.vollzug.select_related("durch"))
    return render(
        request,
        "verfahren/antrag.html",
        {
            "antrag": antrag,
            "vollzug": vollzug,
            "vollzug_statuswahl": Vollzugsstatus.choices,
            "darf_vollzug": antrag.phase == Phase.ANGENOMMEN.value
            and request.user.is_authenticated
            and request.user.hat_adminrechte,
            "ist_favorit": ist_favorit,
            "policy_json": json.dumps(antrag.policy_snapshot, indent=1, ensure_ascii=False),
            "fassung": antrag.aktueller_text(),
            "ergebnis": ergebnis,
            "unterstuetzungen": antrag.unterstuetzungen.count(),
            "kommentare": antrag.kommentare.select_related("mitglied"),
            "frist": frist,
            "unterstuetzt_von_mir": unterstuetzt_von_mir,
            "meine_stimme": meine_stimme,
            "phase_offen": antrag.phase in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value),
            "abstimmung_laeuft": antrag.phase == Phase.ABSTIMMUNG.value,
        },
    )


def _register_zeilen():
    """Alle angenommenen Anträge mit aktuellem Vollzugsstand (F-55) — ohne Eintrag gilt „offen"."""
    angenommene = (
        Antrag.objects.filter(phase=Phase.ANGENOMMEN.value)
        .order_by("-phase_beginn")
        .prefetch_related("vollzug__durch")
    )
    zeilen = []
    for a in angenommene:
        stand = a.vollzugsstand()
        zeilen.append({"antrag": a, "stand": stand, "status": stand.status if stand else "offen"})
    return zeilen


def umsetzung(request):
    """F-55, § 6 Abs 10: das öffentliche Umsetzungsregister. Ein Beschluss, den
    niemand umsetzt, entwertet das Verfahren (L6) — deshalb steht hier zu jedem
    angenommenen Antrag der Stand der Umsetzung, offen für alle, mit voller Historie."""
    zeilen = _register_zeilen()
    zaehlung = [(wert, sum(1 for z in zeilen if z["status"] == wert)) for wert, _n in Vollzugsstatus.choices]
    gewaehlt = request.GET.get("status", "")
    if gewaehlt in Vollzugsstatus.values:
        zeilen = [z for z in zeilen if z["status"] == gewaehlt]
    else:
        gewaehlt = ""
    return render(
        request,
        "verfahren/umsetzung.html",
        {
            "zeilen": zeilen,
            "zaehlung": zaehlung,
            "gewaehlt": gewaehlt,
            "statuswahl": Vollzugsstatus.choices,
        },
    )


def umsetzung_json(request):
    """F-23: das Umsetzungsregister maschinenlesbar — Stand und volle Historie."""
    daten = [
        {
            "antrag": z["antrag"].pk,
            "titel": z["antrag"].titel,
            "angenommen_am": z["antrag"].phase_beginn.isoformat(),
            "status": z["status"],
            "historie": [
                {
                    "status": v.status,
                    "vermerk": v.vermerk,
                    "am": v.erstellt_am.isoformat(),
                    "durch": v.durch.anzeigename,
                }
                for v in reversed(list(z["antrag"].vollzug.all()))
            ],
        }
        for z in _register_zeilen()
    ]
    antwort = JsonResponse(
        {"register": daten, "exportiert_am": timezone.now().isoformat()},
        json_dumps_params={"ensure_ascii": False, "indent": 1},
    )
    antwort["Content-Disposition"] = 'attachment; filename="umsetzungsregister.json"'
    return antwort


def gesund(request):
    return JsonResponse({"status": "ok"})


def staatssimulation(request):
    """Die öffentliche Seite zur StaatsSimulation — Aufklärung für alle und
    Einladung an die verwandten Bewegungen weltweit (§ 12). Reiner Inhalt,
    keine Datenbankabfragen; die Strategie dahinter liegt im Repository."""
    return render(request, "verfahren/staatssimulation.html")
