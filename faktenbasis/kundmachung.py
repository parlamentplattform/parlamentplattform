"""Ausdrückliche Offline-Zuordnung eines authentischen Landesbelegs zu einem Normstand."""

import json
from hashlib import sha256

from django.db import transaction

from faktenbasis.models import Kundmachungsnachweis, Norm
from faktenbasis.ris import HOECHSTBYTES, RisFehler
from plattform_core.novellenfundstelle import VERSION, landeskundmachung, novellenfundstelle
from verfahren.models import AuditEintrag


def _eindeutiges_objekt(paare):
    objekt = dict(paare)
    if len(objekt) != len(paare):
        raise ValueError("doppelte JSON-Schlüssel")
    return objekt


def zuordnen(norm_id: int, daten: bytes, *, erwartete_pruefsumme: str | None = None):
    if not daten or len(daten) > HOECHSTBYTES:
        raise RisFehler("antwortgroesse")
    pruefsumme = sha256(daten).hexdigest()
    if erwartete_pruefsumme is not None and pruefsumme != erwartete_pruefsumme.lower():
        raise RisFehler("pruefsumme")
    try:
        antwort = json.loads(daten.decode("utf-8-sig"), object_pairs_hook=_eindeutiges_objekt)
    except (ValueError, RecursionError) as exc:
        raise RisFehler("antwortformat") from exc

    with transaction.atomic():
        norm = Norm.objects.select_for_update(of=("self",)).filter(
            pk=norm_id, ebene="Land", bundesland="Oberösterreich", importlauf__erfolgreich=True,
        ).first()
        if norm is None:
            raise RisFehler("normstand")
        fundstelle = novellenfundstelle(norm.rohdaten, norm.ris_id, norm.stand, bundesland=norm.bundesland)
        beleg = landeskundmachung(antwort, fundstelle, norm.stand) if fundstelle else None
        if beleg is None:
            raise RisFehler("kundmachungsbeleg")
        vorhanden = Kundmachungsnachweis.objects.filter(norm=norm).defer("original").first()
        if vorhanden is not None:
            if vorhanden.original_sha256 == pruefsumme:
                return vorhanden
            raise RisFehler("bereits_belegt")
        nachweis = Kundmachungsnachweis.objects.create(
            norm=norm, dokumentnummer=beleg.dokumentnummer, kundgemacht_am=beleg.datum,
            eli=beleg.eli, original=daten, original_sha256=pruefsumme, parser_fassung=VERSION,
        )
        AuditEintrag.anhaengen({
            "typ": "ris_kundmachungsbeleg", "norm": norm.pk, "nachweis": nachweis.pk,
            "original_sha256": pruefsumme, "parser_fassung": VERSION,
        })
        return nachweis
