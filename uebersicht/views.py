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
from django.utils.translation import gettext as _

from mitglieder.models import Mitglied
from parameter.kennzahlen import abgegeben_je_antrag
from parameter.models import zahl
from plattform_core import Phase
from plattform_core.diagramme import BLAU, GOLD, ROT, anteils_balken, balken_diagramm, linien_diagramm
from uebersicht.models import AntragAufruf, TagesBesucher, TagesZahl
from verfahren.models import Antrag, Antragsart, Stimmabgabe

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
    return [(_("ab %s") % w.strftime("%d.%m."), float(n)) for w, n in sorted(zaehler.items())]


def _besuche_je_tag(heute, tage: int = 30) -> list[tuple[str, float]]:
    start = heute - timedelta(days=tage - 1)
    vorhanden = dict(TagesZahl.objects.filter(datum__gte=start).values_list("datum", "aufrufe"))
    return [
        ((start + timedelta(days=i)).strftime("%d.%m."), float(vorhanden.get(start + timedelta(days=i), 0)))
        for i in range(tage)
    ]


def _abstimmungen() -> tuple[list[dict], int]:
    """Je Abstimmung eine Zeile — laufende zuerst, dann die jüngsten entschiedenen.

    Laufende Abstimmungen zeigen NUR die Beteiligung: Die Tendenz bleibt bis zum Fristende
    verdeckt (F-15, § 5 Abs 3 lit e) — wie auf der Kachel, der Antragsseite und im Export;
    diese öffentliche Seite darf den Bandwagon-Schutz nicht als vierte Stelle aushebeln.
    Ergebnisse erscheinen erst für entschiedene Anträge, und zwar begrenzt auf einen
    Registerwert: Entschiedenes verschwindet nie (Grundregel 7), die Seite muss also selbst
    eine Grenze ziehen. Die Stimmen aller gezeigten Anträge kommen aus je einer Abfrage,
    nicht aus einer je Antrag. Rückgabe: (Zeilen, Zahl der nicht gezeigten Entscheidungen).
    """
    laufende = list(Antrag.objects.filter(phase=Phase.ABSTIMMUNG.value).order_by("-phase_beginn"))
    hoechstzahl = max(1, zahl("uebersicht-abstimmungen", 20))
    entschiedene_alle = Antrag.objects.filter(phase__in=ENTSCHIEDEN).order_by("-phase_beginn")
    entschiedene = list(entschiedene_alle[:hoechstzahl])
    weitere = max(0, entschiedene_alle.count() - len(entschiedene))

    abgegeben = abgegeben_je_antrag(laufende + entschiedene)
    stimmen: dict[int, dict[str, int]] = {}
    sach_entschieden = [a.pk for a in entschiedene if a.art != Antragsart.MANDAT]
    if sach_entschieden:
        for antrag_id, stimme, n in (
            Stimmabgabe.objects.filter(antrag__in=sach_entschieden)
            .values_list("antrag_id", "stimme")
            .annotate(n=Count("id"))
        ):
            stimmen.setdefault(antrag_id, {})[stimme] = n

    zeilen = []
    for a in laufende + entschiedene:
        n = abgegeben.get(a.pk, 0)
        beteiligung = round(100 * n / a.stimmberechtigte_anzahl) if a.stimmberechtigte_anzahl else None
        zeile = {
            "antrag": a,
            "abgegeben": n,
            "beteiligung": beteiligung,
            "prozent": min(100, beteiligung or 0),
            "laeuft": a.phase == Phase.ABSTIMMUNG.value,
            "personenwahl": a.art == Antragsart.MANDAT,
            "ja": None,
            "nein": None,
            "enthaltung": None,
            "balken": "",
            "gewaehlt": None,
        }
        if zeile["laeuft"]:
            pass  # Tendenz verdeckt: keine Summen je Stimmwert, kein Ergebnisbalken
        elif zeile["personenwahl"]:
            wahl = a.kandidatur_auszaehlen()
            if wahl.gewonnen_id is not None:
                gewinner = a.bewerbungen.select_related("mitglied").filter(pk=wahl.gewonnen_id).first()
                zeile["gewaehlt"] = {
                    "name": gewinner.mitglied.anzeigename if gewinner else f"#{wahl.gewonnen_id}",
                    "stimmen": wahl.plaetze[0].stimmen if wahl.plaetze else 0,
                }
        else:
            s = stimmen.get(a.pk, {})
            ja, nein, enthaltung = s.get("ja", 0), s.get("nein", 0), s.get("enthaltung", 0)
            zeile.update(
                ja=ja,
                nein=nein,
                enthaltung=enthaltung,
                balken=anteils_balken(
                    [(_("Ja"), ja, BLAU), (_("Nein"), nein, ROT), (_("Enthaltung"), enthaltung, GOLD)],
                    _("Ergebnis zu „%(titel)s“: %(ja)s Ja, %(nein)s Nein, %(enthaltung)s Enthaltungen")
                    % {"titel": a.titel, "ja": ja, "nein": nein, "enthaltung": enthaltung},
                ),
            )
        zeilen.append(zeile)
    return zeilen, weitere


def index(request):
    heute = timezone.localdate()
    abstimmungen, weitere = _abstimmungen()
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
            (_("in Unterstützung"), je_phase.get(Phase.UNTERSTUETZUNG.value, 0)),
            (_("in Beratung"), je_phase.get(Phase.BERATUNG.value, 0)),
            (_("in Abstimmung"), je_phase.get(Phase.ABSTIMMUNG.value, 0)),
            (_("angenommen"), je_phase.get(Phase.ANGENOMMEN.value, 0)),
            (_("abgelehnt"), je_phase.get(Phase.ABGELEHNT.value, 0)),
        ],
        "neu_diese_woche": Antrag.objects.filter(eingebracht_am__date__gte=woche_start).count(),
        "abstimmungen": abstimmungen,
        "abstimmungen_weitere": weitere,
        "aufrufe_heute": (TagesZahl.objects.filter(datum=heute).values_list("aufrufe", flat=True).first())
        or 0,
        "besucher_heute": TagesBesucher.objects.filter(datum=heute).count(),
        "aufrufe_woche": TagesZahl.objects.filter(datum__gte=woche_start).aggregate(s=Sum("aufrufe"))["s"]
        or 0,
        "meistgelesen": meistgelesen,
        "diagramm_mitglieder": linien_diagramm(
            _mitglieder_verlauf(heute), _("Mitgliederentwicklung als Verlaufslinie")
        ),
        "diagramm_antraege": balken_diagramm(
            _antraege_je_woche(heute), _("Neue Anträge je Woche, letzte acht Wochen")
        ),
        "diagramm_besuche": balken_diagramm(
            _besuche_je_tag(heute), _("Seitenaufrufe je Tag, letzte 30 Tage")
        ),
    }

    # KI-Verbrauch des Modell-Steckplatzes (F-60): dieselbe Rechenschaft wie
    # auf der Zukunftswerkstatt-Seite, hier als Zahlenbild mit Budget-Meter.
    from ki.models import KILauf, steckplatz_stand

    steckplatz = steckplatz_stand()
    steckplatz["prozent"] = min(
        100, round(100 * steckplatz["monatsverbrauch"] / max(1, steckplatz["monatsbudget"]))
    )
    steckplatz["fehlgeschlagen"] = KILauf.objects.filter(erfolgreich=False).count()
    kontext["steckplatz"] = steckplatz
    return render(request, "uebersicht/uebersicht.html", kontext)
