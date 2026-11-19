"""Eigene Gemeindearbeit für den persönlichen JSON-Export."""

from django.db.models import Prefetch

from mandatare.models import (
    Gemeindehaushaltsquelle,
    Gemeindeprojekt,
    Gemeindesitzungsquelle,
    Ratsinitiative,
    Sprechstunde,
)


def mandate_fuer_export(mitglied):
    return mitglied.mandate.select_related("gemeinde").prefetch_related(
        Prefetch("sprechstunden", queryset=Sprechstunde.objects.select_related("gemeinde").order_by("pk")),
        Prefetch("ratsinitiativen", queryset=Ratsinitiative.objects.select_related("gemeinde").order_by("pk")),
        "ratsinitiativen__meldungen",
        Prefetch(
            "aufgaben__gemeindesitzungsquellen",
            queryset=Gemeindesitzungsquelle.objects.select_related("gemeinde").order_by("pk"),
        ),
        Prefetch("haushaltsquellen", queryset=Gemeindehaushaltsquelle.objects.select_related("gemeinde").order_by("pk")),
        Prefetch("gemeindeprojekte", queryset=Gemeindeprojekt.objects.select_related("gemeinde").order_by("pk")),
        "gemeindeprojekte__staende",
    )


def gemeindearbeit_exportieren(mandat):
    """Zuordnung und Verlauf einschließlich früherer Stände des eigenen Mandats."""
    return {
        "gemeindekennziffer": mandat.gemeinde.kennziffer if mandat.gemeinde_id else None,
        "sprechstunden": [
            {
                "sprechstunde": s.pk, "gemeindekennziffer": s.gemeinde.kennziffer,
                "beginn": s.beginn, "ende": s.ende, "treffpunkt": s.treffpunkt,
                "veroeffentlicht_am": s.veroeffentlicht_am, "abgesagt_am": s.abgesagt_am,
            }
            for s in mandat.sprechstunden.all()
        ],
        "ratsinitiativen": [
            {
                "initiative": i.pk, "gemeindekennziffer": i.gemeinde.kennziffer,
                "art": i.art, "titel": i.titel, "text": i.text, "veroeffentlicht_am": i.veroeffentlicht_am,
                "meldungen": [
                    {
                        "meldung": m.pk, "art": m.art, "datum": m.datum, "text": m.text,
                        "quellen_url": m.quellen_url, "eingetragen_am": m.eingetragen_am,
                    }
                    for m in i.meldungen.all()
                ],
            }
            for i in mandat.ratsinitiativen.all()
        ],
        "sitzungsquellen": [
            {
                "quelle": q.pk, "aufgabe": a.pk, "gemeindekennziffer": q.gemeinde.kennziffer,
                "sitzung_am": q.sitzung_am, "art": q.art, "url": q.url, "erfasst_am": q.erfasst_am,
            }
            for a in mandat.aufgaben.all()
            for q in a.gemeindesitzungsquellen.all()
        ],
        "haushaltsquellen": [
            {
                "quelle": q.pk, "gemeindekennziffer": q.gemeinde.kennziffer,
                "jahr": q.jahr, "bis_jahr": q.bis_jahr, "art": q.art, "url": q.url, "erfasst_am": q.erfasst_am,
            }
            for q in mandat.haushaltsquellen.all()
        ],
        "projekte": [
            {
                "projekt": p.pk, "gemeindekennziffer": p.gemeinde.kennziffer, "veroeffentlicht_am": p.veroeffentlicht_am,
                "staende": [
                    {
                        "stand": s.pk, "lage": s.lage, "titel": s.titel, "vermerk": s.vermerk,
                        "quelle": s.quelle, "stand_am": s.stand_am, "erfasst_am": s.erfasst_am,
                    }
                    for s in p.staende.all()
                ],
            }
            for p in mandat.gemeindeprojekte.all()
        ],
    }
