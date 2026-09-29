"""Die Tendenz einer laufenden Abstimmung — nur, wo die Ordnung sie freigibt (D-D2 b, 0.51.0).

Voreinstellung ist (a): verdeckt bis zum Fristende (§ 5 Abs 3 lit e: veröffentlicht wird nach der
Abstimmung; Lastenheft F-15: kein Mitläufereffekt). Die Ordnung kann das ab erreichter
Mindestbeteiligung ändern (`Policy.tendenz_ab_mindestbeteiligung = 1`) — eingefroren beim Einbringen,
also für eine Abstimmung vom ersten bis zum letzten Tag gleich (§ 5 Abs 5). Das betrifft nur
Sachanträge: Mandatsfrage (FB-L5: „keine Tendenz vor Fristende“), Vertrauensfrage und Kandidatur nie.

Kachel, Antragsseite und Übersicht lesen dieselbe Schranke (`plattform_core.tally.tendenz_sichtbar`),
damit keine Seite verrät, was eine andere verdeckt (Befund #4 der Gesamtprüfung 0.45)."""

from __future__ import annotations

from django.db.models import Count

from plattform_core import Phase
from plattform_core.tally import tendenz_sichtbar

#: Ob eine laufende Abstimmung mit dem Schalter 1 läuft, die Mindestbeteiligung aber noch fehlt.
VERDECKT_BIS_MINDESTBETEILIGUNG = "bis_mindestbeteiligung"


def _betroffen(antrag) -> bool:
    from verfahren.models import Antragsart

    return (
        antrag.phase == Phase.ABSTIMMUNG.value
        and antrag.art == Antragsart.SACHE
        and (antrag.policy_snapshot or {}).get("tendenz_ab_mindestbeteiligung") == 1
    )


def tendenzen(antraege, abgegeben: dict[int, int]) -> dict[int, dict | str]:
    """Für viele Anträge in einer Abfrage: je laufendem Sachantrag, dessen Ordnung die Tendenz freigibt,
    entweder die Anteile (dict) oder den Vermerk, dass die Mindestbeteiligung noch fehlt. Anträge mit
    Schalter 0 fehlen — für sie gilt „verdeckt bis Fristende“. Ohne betroffenen Antrag keine Abfrage."""
    from verfahren.models import Stimmabgabe

    offen, ergebnis = [], {}
    for a in antraege:
        if not _betroffen(a):
            continue
        n = abgegeben.get(a.pk, 0)
        if tendenz_sichtbar(a.policy(), n, max(1, a.stimmberechtigte_anzahl or 1)):
            offen.append(a.pk)
        else:
            ergebnis[a.pk] = VERDECKT_BIS_MINDESTBETEILIGUNG
    if offen:
        je: dict[int, dict[str, int]] = {}
        for antrag_id, stimme, n in (
            Stimmabgabe.objects.filter(antrag_id__in=offen).order_by().values_list("antrag_id", "stimme").annotate(n=Count("id"))
        ):
            je.setdefault(antrag_id, {})[stimme] = n
        for pk in offen:
            z = je.get(pk, {})
            summe = sum(z.values()) or 1
            ergebnis[pk] = {
                wert: {"n": z.get(wert, 0), "prozent": round(100 * z.get(wert, 0) / summe)}
                for wert in ("ja", "nein", "enthaltung")
            }
    return ergebnis
