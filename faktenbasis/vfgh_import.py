"""Einen ausdrücklich übergebenen VfGH-Metadatenstand unverändert archivieren."""

from django.db import transaction

from faktenbasis.models import VfghEntscheidungsstand
from faktenbasis.ris import RisFehler, lokale_antwort
from plattform_core.vfgh_metadaten import VERSION, entscheidung
from verfahren.models import AuditEintrag


def importieren(dokumentnummer: str, daten: bytes, *, erwartete_pruefsumme: str | None = None):
    antwort, pruefsumme = lokale_antwort(daten, erwartete_pruefsumme)
    beleg = entscheidung(antwort, dokumentnummer)
    if beleg is None:
        raise RisFehler("vfgh_metadaten")
    with transaction.atomic():
        stand, neu = VfghEntscheidungsstand.objects.defer("original").get_or_create(
            original_sha256=pruefsumme,
            defaults={
                "dokumentnummer": beleg.dokumentnummer,
                "entschieden_am": beleg.entschieden_am,
                "ecli": beleg.ecli,
                "geschaeftszahlen": list(beleg.geschaeftszahlen),
                "normangaben": list(beleg.normangaben),
                "quelle": beleg.quelle,
                "original": daten,
                "parser_fassung": VERSION,
            },
        )
        if neu:
            AuditEintrag.anhaengen({
                "typ": "ris_vfgh_metadaten", "beleg": stand.pk,
                "original_sha256": pruefsumme, "parser_fassung": VERSION,
            })
    return stand
