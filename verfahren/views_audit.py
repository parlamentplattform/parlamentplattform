"""Das öffentliche Audit-Log `/audit/` und `/audit.json` (Bestandsaufnahme A7, Schritt 2 · 0.52.0).

Mehrere Seiten versprechen ein öffentliches Audit-Log (Parameterregister, Verwaltung); bis 0.51 gab es
nur die Spur je Antrag. Hier steht die ganze Kette, neueste zuerst, filterbar nach Antrag und Art, mit
dem Ergebnis der letzten Prüfung. Mitgliedskennungen und Personengründe erscheinen als „•“ (Entscheidung
des Gründers 29.9.2026, F2 a; `verfahren/audit_oeffentlich.py`)."""

from __future__ import annotations

from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.fields.json import KeyTextTransform
from django.http import JsonResponse
from django.shortcuts import render

from verfahren.audit_oeffentlich import eintrag_oeffentlich
from verfahren.audit_pruefung import gemerkter_stand
from verfahren.models import AuditEintrag

#: Rückfallwert; der gültige steht im Register unter „audit-seite-eintraege“ (FB-J2).
SEITE_EINTRAEGE = 50

#: Was eine Zeile neben Art und Zeit zeigt — alles außer diesen Schlüsseln.
NICHT_ANZEIGEN = ("typ", "zeit")


def seite_eintraege() -> int:
    from parameter.models import zahl

    return max(10, min(500, zahl("audit-seite-eintraege", SEITE_EINTRAEGE)))


def _filter(request) -> tuple[dict, Q]:
    """Die Filter aus der Adresse — nur, was sich lesen lässt; alles andere wird still übergangen."""
    gewaehlt, bedingung = {"antrag": "", "art": ""}, Q()
    antrag = (request.GET.get("antrag") or "").strip().lstrip("#")
    if antrag.isdigit():
        gewaehlt["antrag"] = antrag
        bedingung &= Q(ereignis__antrag=int(antrag))
    art = (request.GET.get("art") or "").strip()
    if art and art in arten():
        gewaehlt["art"] = art
        # Zwei ältere Ereignisse tragen ihre Art unter `art` statt `typ` (bis 0.51)
        bedingung &= Q(ereignis__typ=art) | (Q(ereignis__art=art) & ~Q(ereignis__has_key="typ"))
    return gewaehlt, bedingung


def arten() -> list[str]:
    """Alle Arten, die in der Kette vorkommen, alphabetisch."""
    typen = AuditEintrag.objects.annotate(t=KeyTextTransform("typ", "ereignis")).values_list("t", flat=True)
    alt = (
        AuditEintrag.objects.exclude(ereignis__has_key="typ")
        .annotate(a=KeyTextTransform("art", "ereignis"))
        .values_list("a", flat=True)
    )
    return sorted({t for t in [*typen.distinct(), *alt.distinct()] if t})


def _zeile(eintrag) -> dict:
    daten = eintrag_oeffentlich(eintrag)
    daten["felder"] = [(k, v) for k, v in daten["ereignis"].items() if k not in NICHT_ANZEIGEN]
    daten["antrag"] = eintrag.ereignis.get("antrag") if isinstance(eintrag.ereignis.get("antrag"), int) else None
    return daten


def audit(request):
    gewaehlt, bedingung = _filter(request)
    eintraege = AuditEintrag.objects.filter(bedingung).order_by("-lfd")
    seite = Paginator(eintraege, seite_eintraege()).get_page(request.GET.get("seite"))
    abfrage = "&".join(f"{k}={v}" for k, v in gewaehlt.items() if v)
    return render(
        request,
        "verfahren/audit.html",
        {
            "seite": seite,
            "zeilen": [_zeile(e) for e in seite.object_list],
            "gewaehlt": gewaehlt,
            "arten": arten(),
            "abfrage": abfrage,
            "pruefung": gemerkter_stand(),
        },
    )


def audit_json(request):
    """Maschinenlesbar, aufsteigend ab `?ab=<laufende Nummer>` (ausschließlich), seitenweise. `weiter` ist
    die Adresse der nächsten Seite oder null. Gekürzte Einträge tragen "gekuerzt": true."""
    gewaehlt, bedingung = _filter(request)
    ab = request.GET.get("ab", "")
    eintraege = AuditEintrag.objects.filter(bedingung).order_by("lfd")
    if ab.isdigit():
        eintraege = eintraege.filter(lfd__gt=int(ab))
    groesse = seite_eintraege()
    liste = list(eintraege[: groesse + 1])
    mehr = len(liste) > groesse
    liste = liste[:groesse]
    weiter = None
    if mehr:
        parameter = "&".join([f"ab={liste[-1].lfd}", *(f"{k}={v}" for k, v in gewaehlt.items() if v)])
        weiter = request.build_absolute_uri(f"{request.path}?{parameter}")
    stand = gemerkter_stand()
    return JsonResponse(
        {
            "pruefung": {
                "intakt": stand.get("intakt"),
                "geprueft_am": stand.get("geprueft_am"),
                "eintraege": stand.get("eintraege"),
                "kopf": stand.get("kopf"),
            }
            if stand
            else None,
            "eintraege": [eintrag_oeffentlich(e) for e in liste],
            "weiter": weiter,
        },
        json_dumps_params={"ensure_ascii": False, "indent": 1},
    )
