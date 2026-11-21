"""Folgen eines Mandatsendes für die Öffentlichkeit der Gemeinde (GP-116, MG-01/MV-19/MG-21).

Endet ein Gemeindemandat (Mandatsende, Vertretungsende, geänderte Zuordnung) oder wird das Konto
gesperrt, verschwand eine angekündigte Sprechstunde bisher kommentarlos von der Ortsseite, und eine
laufende Sitzung lief öffentlich weiter. `mandatsende_folgen` sagt die kommenden Sprechstunden mit
Anlass ab (sie bleiben bis zum Termin als „Abgesagt“ sichtbar) und beendet laufende Sitzungen —
idempotent, mit Audit ohne personenbezogene Werte, in einer Transaktion.
"""

from __future__ import annotations

from django.db import transaction
from django.utils import timezone

from verfahren.models import AuditEintrag

#: Anlässe, die im Audit-Eintrag „sprechstunde_abgesagt“ stehen.
ANLAESSE = frozenset({"mandatsende", "vertretungsende", "zuordnung", "kontosperre"})


def mandatsende_folgen(mandate, anlass: str, jetzt=None) -> tuple[int, int]:
    """Sagt die kommenden Sprechstunden der Mandate ab und beendet ihre laufenden Sitzungen.
    `mandate` ist ein QuerySet oder eine Liste von Mandaten. Gibt (abgesagt, beendet) zurück."""
    from mandatare.models import Sitzung, Sprechstunde
    from mandatare.sitzung import SitzungFehler, sitzung_beenden

    assert anlass in ANLAESSE, anlass
    jetzt = jetzt or timezone.now()
    abgesagt = beendet = 0
    with transaction.atomic():
        termine = (
            Sprechstunde.objects.select_for_update()
            .filter(mandat__in=mandate, abgesagt_am__isnull=True, ende__gt=jetzt)
            .select_related("gemeinde")
            .order_by("pk")
        )
        for termin in termine:
            termin.abgesagt_am = jetzt
            termin.save(update_fields=["abgesagt_am"])
            AuditEintrag.anhaengen({
                "typ": "sprechstunde_abgesagt", "mandat": termin.mandat_id, "termin": termin.pk,
                "gemeinde": termin.gemeinde.kennziffer, "anlass": anlass,
            })
            abgesagt += 1
        for sitzung in Sitzung.objects.filter(mandat__in=mandate, ende__isnull=True).order_by("pk"):
            if not sitzung.laeuft(jetzt):
                continue  # über die Höchstdauer hinaus: das Ende schreibt `fortschreiben` fest
            try:
                sitzung_beenden(sitzung, jetzt)
            except SitzungFehler:
                continue  # inzwischen beendet
            beendet += 1
    return abgesagt, beendet
