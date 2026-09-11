"""Die Kennzahlen dieser Instanz als Mapping (FB-M5, FB-J3) — aggregiert, nie über einen Menschen.

`/kennzahlen.json` und die Messgrößen der Parametertests lesen dieselbe Quelle: Was ein Test
misst, muss das sein, was die Plattform ohnehin veröffentlicht — sonst gäbe es eine zweite,
unveröffentlichte Zählung, und die Auswertung wäre nicht nachrechenbar (§ 6 Abs 11 lit d)."""

from __future__ import annotations


def werte() -> dict:
    from django.db.models import Count

    from mitglieder.models import Mitglied
    from plattform_core import Phase
    from plattform_core.schema import turnout_mean
    from verfahren.models import Antrag, Kategorie, Vollzugsstatus
    from verfahren.views import _register_zeilen

    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    je_phase = dict.fromkeys(("unterstuetzung", "beratung", "abstimmung", "angenommen", "abgelehnt", "verfallen"), 0)
    for zeile in antraege.values("phase").annotate(n=Count("pk")):
        if zeile["phase"] in je_phase:
            je_phase[zeile["phase"]] = zeile["n"]
    entschieden = antraege.filter(
        phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value], stimmberechtigte_anzahl__gt=0
    ).annotate(abgaben=Count("stimmabgaben"))
    anteile = [a.abgaben / a.stimmberechtigte_anzahl for a in entschieden]
    register = _register_zeilen()
    je_status = {wert: sum(1 for z in register if z["status"] == wert) for wert, _name in Vollzugsstatus.choices}
    return {
        "members.active": Mitglied.objects.filter(is_active=True).count(),
        "motions.total": antraege.count(),
        "motions.by_phase": je_phase,
        "votes.completed": entschieden.count(),
        "votes.turnout_mean": turnout_mean(anteile),
        "implementation.by_status": je_status,
        "areas_of_life.active": Kategorie.objects.filter(aktiv=True).count(),
    }
