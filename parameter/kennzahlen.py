"""Die Kennzahlen dieser Instanz als Mapping (FB-M5, FB-J3) — aggregiert, nie über einen Menschen.

`/kennzahlen.json` und die Messgrößen der Parametertests lesen dieselbe Quelle: Was ein Test
misst, muss das sein, was die Plattform ohnehin veröffentlicht — sonst gäbe es eine zweite,
unveröffentlichte Zählung, und die Auswertung wäre nicht nachrechenbar (§ 6 Abs 11 lit d)."""

from __future__ import annotations


def abgegeben_je_antrag(antraege) -> dict[int, int]:
    """Abgegebene Stimmen je Antrag — in zwei Abfragen für beliebig viele Anträge.

    Sachanträge zählen ihre Stimmabgaben; Personenwahlen (§ 7 Abs 1) haben keine, dort zählen
    die Pseudonyme mit mindestens einer Zustimmung zu einer nicht zurückgezogenen Bewerbung —
    dieselbe Zählweise wie `Antrag.kandidatur_auszaehlen`, damit Anzeige und Auszählung nie
    auseinanderlaufen. Ohne diese Unterscheidung ginge jede Kandidatur mit 0 Stimmen in
    Beteiligung und Kennzahlen ein."""
    from django.db.models import Count

    from verfahren.models import Antragsart, BewerbungsZustimmung, Stimmabgabe

    antraege = list(antraege)
    sach_ids = [a.pk for a in antraege if a.art != Antragsart.MANDAT]
    mandat_ids = [a.pk for a in antraege if a.art == Antragsart.MANDAT]
    ergebnis = dict.fromkeys((a.pk for a in antraege), 0)
    if sach_ids:
        ergebnis.update(
            Stimmabgabe.objects.filter(antrag__in=sach_ids).values_list("antrag_id").annotate(n=Count("id"))
        )
    if mandat_ids:
        paare = (
            BewerbungsZustimmung.objects.filter(bewerbung__antrag__in=mandat_ids, bewerbung__zurueckgezogen=False)
            .values_list("bewerbung__antrag_id", "pseudonym")
            .distinct()
        )
        for antrag_id, _pseudonym in paare:
            ergebnis[antrag_id] += 1
    return ergebnis


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
    entschieden = list(
        antraege.filter(phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value], stimmberechtigte_anzahl__gt=0)
    )
    abgegeben = abgegeben_je_antrag(entschieden)
    anteile = [abgegeben[a.pk] / a.stimmberechtigte_anzahl for a in entschieden]
    register = _register_zeilen()
    je_status = {wert: sum(1 for z in register if z["status"] == wert) for wert, _name in Vollzugsstatus.choices}
    return {
        "members.active": Mitglied.objects.filter(is_active=True).count(),
        "motions.total": antraege.count(),
        "motions.by_phase": je_phase,
        "votes.completed": len(entschieden),
        "votes.turnout_mean": turnout_mean(anteile),
        "implementation.by_status": je_status,
        "areas_of_life.active": Kategorie.objects.filter(aktiv=True).count(),
    }
