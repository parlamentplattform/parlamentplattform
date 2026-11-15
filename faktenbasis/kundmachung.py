"""Ausdrückliche Offline-Zuordnung eines authentischen Kundmachungsbelegs."""

from django.db import transaction

from faktenbasis.models import Kundmachungsnachweis, Norm
from faktenbasis.ris import RisFehler, lokale_antwort
from plattform_core.novellenfundstelle import (
    VERSION,
    bundeskundmachung,
    landeskundmachung,
    novellenfundstelle,
)
from verfahren.models import AuditEintrag


def zuordnen(norm_id: int, daten: bytes, *, erwartete_pruefsumme: str | None = None):
    antwort, pruefsumme = lokale_antwort(daten, erwartete_pruefsumme)

    with transaction.atomic():
        norm = Norm.objects.select_for_update(of=("self",)).filter(
            pk=norm_id, importlauf__erfolgreich=True,
        ).first()
        if norm is None or (norm.ebene, norm.bundesland) not in {("Bund", ""), ("Land", "Oberösterreich")}:
            raise RisFehler("normstand")
        fundstelle = novellenfundstelle(norm.rohdaten, norm.ris_id, norm.stand, bundesland=norm.bundesland)
        pruefen = bundeskundmachung if norm.ebene == "Bund" else landeskundmachung
        beleg = pruefen(antwort, fundstelle, norm.stand) if fundstelle else None
        if beleg is None:
            raise RisFehler("kundmachungsbeleg")
        vorhanden = Kundmachungsnachweis.objects.filter(norm=norm).defer("original").first()
        if vorhanden is not None:
            if vorhanden.original_sha256 == pruefsumme:
                return vorhanden
            raise RisFehler("bereits_belegt")
        materialien = {
            "periode": beleg.gesetzgebungsperiode,
            "nationalrat": list(beleg.ausschussberichte_nationalrat),
            "bundesrat": list(beleg.ausschussberichte_bundesrat),
        }
        nachweis = Kundmachungsnachweis.objects.create(
            norm=norm, dokumentnummer=beleg.dokumentnummer, kundgemacht_am=beleg.datum,
            eli=beleg.eli, original=daten, original_sha256=pruefsumme, parser_fassung=VERSION,
            parlamentsmaterialien={name: wert for name, wert in materialien.items() if wert},
        )
        AuditEintrag.anhaengen({
            "typ": "ris_kundmachungsbeleg", "norm": norm.pk, "nachweis": nachweis.pk,
            "original_sha256": pruefsumme, "parser_fassung": VERSION,
        })
        return nachweis
