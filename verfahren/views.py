"""Lesende Ansichten. Grundsatz F-31: Sortierung ausschließlich nach Frist und
Phase — niemals nach Beliebtheit. Ergebnisseiten sind ohne Login lesbar (F-20)."""

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render

from plattform_core import Phase
from verfahren.models import Antrag, Kategorie

LAUFEND = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]


def index(request):
    """Das Hauptfenster in vier Bereichen (§ 5 Abs 10, F-40) — Reihung immer nur
    nach Phase und Frist, nie nach Beliebtheit oder verdeckter Gewichtung (F-31)."""
    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    laufend = antraege.filter(phase__in=LAUFEND)

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
        ("Laufende Abstimmungen", antraege.filter(phase=Phase.ABSTIMMUNG.value).order_by("phase_beginn")),
        ("In Beratung", antraege.filter(phase=Phase.BERATUNG.value).order_by("phase_beginn")),
        ("Sammeln Unterstützung", antraege.filter(phase=Phase.UNTERSTUETZUNG.value).order_by("phase_beginn")),
        (
            "Abgeschlossen",
            antraege.filter(
                phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value, Phase.VERFALLEN.value]
            ).order_by("-phase_beginn")[:20],
        ),
    ]
    return render(
        request,
        "verfahren/index.html",
        {
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
    return render(
        request,
        "verfahren/antrag.html",
        {
            "antrag": antrag,
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


def gesund(request):
    return JsonResponse({"status": "ok"})
