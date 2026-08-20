"""Die öffentliche Übersichtsseite (F-50): was sich auf der Plattform tut.

Alles hier ist ohne Anmeldung sichtbar — Transparenz ist Bedingung (§ 2 Abs 5).
Abstimmungsverhalten erscheint ausschließlich als Summen je Abstimmung:
Einzelne Stimmen sind pseudonym (§ 5 Abs 3) und bleiben es auch hier.
"""

from __future__ import annotations

from bisect import bisect_right
from datetime import timedelta

from django.db.models import Count, Sum
from django.shortcuts import render
from django.utils import timezone

from mitglieder.models import Mitglied
from plattform_core import Phase
from plattform_core.diagramme import BLAU, GOLD, ROT, anteils_balken, balken_diagramm, linien_diagramm
from uebersicht.models import AntragAufruf, TagesBesucher, TagesZahl
from verfahren.models import Antrag

OFFEN = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]
ENTSCHIEDEN = [Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value]


def _mitglieder_verlauf(heute) -> list[tuple[str, float]]:
    """Kumulierte Mitgliederzahl über die Zeit (höchstens ~60 Stützpunkte)."""
    beitritte = sorted(
        Mitglied.objects.filter(is_active=True).exclude(beitritt=None).values_list("beitritt", flat=True)
    )
    if not beitritte:
        return []
    start = beitritte[0]
    tage = max((heute - start).days, 1)
    schritt = max(1, tage // 60)
    punkte = []
    d = start
    while d <= heute:
        punkte.append((d.strftime("%d.%m.%y"), float(bisect_right(beitritte, d))))
        d += timedelta(days=schritt)
    if punkte[-1][0] != heute.strftime("%d.%m.%y"):
        punkte.append((heute.strftime("%d.%m.%y"), float(len(beitritte))))
    return punkte


def _antraege_je_woche(heute, wochen: int = 8) -> list[tuple[str, float]]:
    montag = heute - timedelta(days=heute.weekday())
    start = montag - timedelta(weeks=wochen - 1)
    zaehler = {start + timedelta(weeks=i): 0 for i in range(wochen)}
    for zeitpunkt in Antrag.objects.filter(eingebracht_am__date__gte=start).values_list(
        "eingebracht_am", flat=True
    ):
        d = timezone.localtime(zeitpunkt).date()
        woche = d - timedelta(days=d.weekday())
        if woche in zaehler:
            zaehler[woche] += 1
    return [(f"ab {w.strftime('%d.%m.')}", float(n)) for w, n in sorted(zaehler.items())]


def _besuche_je_tag(heute, tage: int = 30) -> list[tuple[str, float]]:
    start = heute - timedelta(days=tage - 1)
    vorhanden = dict(TagesZahl.objects.filter(datum__gte=start).values_list("datum", "aufrufe"))
    return [
        ((start + timedelta(days=i)).strftime("%d.%m."), float(vorhanden.get(start + timedelta(days=i), 0)))
        for i in range(tage)
    ]


def _abstimmungen() -> list[dict]:
    """Je Abstimmung: Summen, Beteiligung und ein 100-%-Balken — laufende zuerst."""
    zeilen = []
    for a in Antrag.objects.filter(phase__in=[Phase.ABSTIMMUNG.value, *ENTSCHIEDEN]).order_by(
        "-phase_beginn"
    ):
        stimmen = dict(a.stimmabgaben.values_list("stimme").annotate(n=Count("id")))
        ja, nein, enthaltung = stimmen.get("ja", 0), stimmen.get("nein", 0), stimmen.get("enthaltung", 0)
        abgegeben = ja + nein + enthaltung
        beteiligung = (
            round(100 * abgegeben / a.stimmberechtigte_anzahl) if a.stimmberechtigte_anzahl else None
        )
        zeilen.append(
            {
                "antrag": a,
                "ja": ja,
                "nein": nein,
                "enthaltung": enthaltung,
                "abgegeben": abgegeben,
                "beteiligung": beteiligung,
                "laeuft": a.phase == Phase.ABSTIMMUNG.value,
                "balken": anteils_balken(
                    [("Ja", ja, BLAU), ("Nein", nein, ROT), ("Enthaltung", enthaltung, GOLD)],
                    f"Ergebnis zu „{a.titel}“: {ja} Ja, {nein} Nein, {enthaltung} Enthaltungen",
                ),
            }
        )
    return zeilen


def index(request):
    heute = timezone.localdate()
    je_phase = dict(Antrag.objects.values_list("phase").annotate(n=Count("id")))
    woche_start = heute - timedelta(days=6)

    meistgelesen = []
    top = AntragAufruf.objects.values("antrag").annotate(gesamt=Sum("aufrufe")).order_by("-gesamt")[:5]
    titel = {a.pk: a for a in Antrag.objects.filter(pk__in=[t["antrag"] for t in top])}
    for t in top:
        meistgelesen.append({"antrag": titel[t["antrag"]], "aufrufe": t["gesamt"]})

    kontext = {
        "mitglieder_gesamt": Mitglied.objects.filter(is_active=True).count(),
        "mitglieder_neu_woche": Mitglied.objects.filter(is_active=True, beitritt__gte=woche_start).count(),
        "antraege_gesamt": Antrag.objects.count(),
        "antraege_aktiv": sum(je_phase.get(p, 0) for p in OFFEN),
        "je_phase": [
            ("in Unterstützung", je_phase.get(Phase.UNTERSTUETZUNG.value, 0)),
            ("in Beratung", je_phase.get(Phase.BERATUNG.value, 0)),
            ("in Abstimmung", je_phase.get(Phase.ABSTIMMUNG.value, 0)),
            ("angenommen", je_phase.get(Phase.ANGENOMMEN.value, 0)),
            ("abgelehnt", je_phase.get(Phase.ABGELEHNT.value, 0)),
        ],
        "neu_diese_woche": Antrag.objects.filter(eingebracht_am__date__gte=woche_start).count(),
        "abstimmungen": _abstimmungen(),
        "aufrufe_heute": (TagesZahl.objects.filter(datum=heute).values_list("aufrufe", flat=True).first())
        or 0,
        "besucher_heute": TagesBesucher.objects.filter(datum=heute).count(),
        "aufrufe_woche": TagesZahl.objects.filter(datum__gte=woche_start).aggregate(s=Sum("aufrufe"))["s"]
        or 0,
        "meistgelesen": meistgelesen,
        "diagramm_mitglieder": linien_diagramm(
            _mitglieder_verlauf(heute), "Mitgliederentwicklung als Verlaufslinie"
        ),
        "diagramm_antraege": balken_diagramm(
            _antraege_je_woche(heute), "Neue Anträge je Woche, letzte acht Wochen"
        ),
        "diagramm_besuche": balken_diagramm(_besuche_je_tag(heute), "Seitenaufrufe je Tag, letzte 30 Tage"),
    }
    return render(request, "uebersicht/uebersicht.html", kontext)
