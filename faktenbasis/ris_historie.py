"""Archiviert eine ausdrücklich übergebene Seite der Bundesnormen-Historie."""

from datetime import date

from django.db import transaction
from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber

from faktenbasis.models import Norm, RisAenderungsseite
from faktenbasis.ris import RisFehler, dokumentadresse, lokale_antwort, seitenkopf_pruefen
from plattform_core.ris_historie import NORM_REIHUNG, PARSER_FASSUNG, dokumente
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
                "parser_fassung": PARSER_FASSUNG,
            },
        )
        if neu:
            AuditEintrag.anhaengen({
                "typ": "ris_aenderungsseite", "beleg": stand.pk,
                "original_sha256": pruefsumme, "parser_fassung": PARSER_FASSUNG,
            })
    return stand


def dokumente_mit_normstand(seite):
    """Finde in einer Abfrage höchstens einen lokalen Stand je archiviertem Verweis."""
    bereiche = Q()
    for verweis in seite.dokumente:
        bereiche |= Q(ris_id=verweis["dokumentnummer"], gesetzesnummer=verweis["gesetzesnummer"])
    if not bereiche:
        return []
    kandidaten = Norm.objects.filter(
        bereiche, ebene="Bund", bundesland="", importlauf__erfolgreich=True,
    ).annotate(rang=Window(
        RowNumber(), partition_by=[F("ris_id"), F("gesetzesnummer")], order_by=NORM_REIHUNG,
    )).filter(rang=1).order_by().values("pk", "ris_id", "gesetzesnummer", "stand")
    normen = {(norm["ris_id"], norm["gesetzesnummer"]): norm for norm in kandidaten}
    return [
        {**verweis, "normstand": normen.get((verweis["dokumentnummer"], verweis["gesetzesnummer"]))}
        for verweis in seite.dokumente
    ]
