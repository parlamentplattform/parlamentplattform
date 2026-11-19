"""Archiviert eine ausdrücklich übergebene Seite der Bundesnormen-Historie."""

from datetime import date

from django.db import transaction

from faktenbasis.models import RisAenderungsseite
from faktenbasis.ris import RisFehler, dokumentadresse, lokale_antwort, seitenkopf_pruefen
from plattform_core.ris_historie import VERSION, dokumente
from verfahren.models import AuditEintrag


def importieren(tag: date, seite: int, daten: bytes, *, erwartete_pruefsumme: str | None = None):
    antwort, pruefsumme = lokale_antwort(daten, erwartete_pruefsumme)
    ergebnisse, treffer = seitenkopf_pruefen(antwort, seite)
    verweise = dokumente(ergebnisse.get("OgdDocumentReference"), tag, min(treffer - (seite - 1) * 10, 10))
    if verweise is None:
        raise RisFehler("ris_historie")
    referenzen = [
        {
            "dokumentnummer": verweis.dokumentnummer,
            "gesetzesnummer": verweis.gesetzesnummer,
            "quelle": dokumentadresse(verweis.quelle, verweis.dokumentnummer),
        }
        for verweis in verweise
    ]
    with transaction.atomic():
        stand, neu = RisAenderungsseite.objects.defer("original").get_or_create(
            original_sha256=pruefsumme,
            defaults={
                "tag": tag,
                "seite": seite,
                "treffer": treffer,
                "dokumente": referenzen,
                "original": daten,
                "parser_fassung": VERSION,
            },
        )
        if neu:
            AuditEintrag.anhaengen({
                "typ": "ris_aenderungsseite", "beleg": stand.pk,
                "original_sha256": pruefsumme, "parser_fassung": VERSION,
            })
    return stand
