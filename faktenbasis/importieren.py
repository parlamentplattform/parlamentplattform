"""Ein begrenzter manueller Import; kein Hintergrundlauf, keine Modellschreibrechte."""

from datetime import date

from django.db import transaction
from django.utils import timezone

from faktenbasis.abrufschutz import einzelabruf
from faktenbasis.models import Norm, RisImport
from faktenbasis.ris import GESETZESNUMMER, RisFehler, abrufen
from verfahren.models import AuditEintrag


def importieren(gesetzesnummer, stand, *, bundesland=""):
    if not isinstance(gesetzesnummer, str) or not GESETZESNUMMER.fullmatch(gesetzesnummer):
        raise RisFehler("gesetzesnummer")
    if type(stand) is not date:
        raise RisFehler("stichtag")
    if bundesland != "":
        from faktenbasis.landesrecht import argumente_pruefen

        argumente_pruefen(gesetzesnummer, stand, bundesland)
    with einzelabruf():
        return _uebernehmen(gesetzesnummer, stand, bundesland=bundesland)


def _uebernehmen(gesetzesnummer, stand, *, bundesland=""):
    beginn = timezone.now()
    herkunft = {"ebene": "Bund", "bundesland": ""}
    if bundesland:
        from faktenbasis.landesrecht import BUNDESLAENDER

        herkunft = {"ebene": "Land", "bundesland": BUNDESLAENDER[bundesland]}
    try:
        if bundesland:
            from faktenbasis.landesrecht import abrufen as land_abrufen

            antwort = land_abrufen(gesetzesnummer, stand, bundesland)
        else:
            antwort = abrufen(gesetzesnummer, stand)
    except RisFehler as fehler:
        with transaction.atomic():
            lauf = RisImport.objects.create(
                gesetzesnummer=gesetzesnummer, stand=stand, begonnen_am=beginn,
                beendet_am=timezone.now(), erfolgreich=False, fehlercode=fehler.code, **herkunft,
            )
            AuditEintrag.anhaengen({"typ": "ris_import", "import": lauf.pk, "erfolgreich": False})
        raise
    with transaction.atomic():
        neue = []
        # Den Importnachweis erst mit endgültigen Zahlen anlegen, danach nie ändern.
        for norm in antwort.normen:
            if not Norm.objects.filter(
                ris_id=norm.ris_id, stand=stand, inhalt_hash=norm.inhalt_hash,
            ).exists():
                neue.append(norm)
        lauf = RisImport.objects.create(
            gesetzesnummer=gesetzesnummer, stand=stand, begonnen_am=beginn,
            beendet_am=timezone.now(), erfolgreich=True, treffer=antwort.treffer,
            gelesen=len(antwort.normen), neu=len(neue), api_url=antwort.api_url,
            antwort_hash=antwort.antwort_hash, antwort=antwort.rohdaten, **herkunft,
        )
        for norm in neue:
            Norm.objects.create(
                ris_id=norm.ris_id, gesetzesnummer=norm.gesetzesnummer, kurztitel=norm.kurztitel,
                titel=norm.titel, typ=norm.typ, abschnitt=norm.abschnitt, stand=stand,
                quelle=norm.quelle, rohdaten=norm.rohdaten, inhalt_hash=norm.inhalt_hash, importlauf=lauf,
                ebene=norm.ebene, bundesland=norm.bundesland,
            )
        AuditEintrag.anhaengen({
            "typ": "ris_import", "import": lauf.pk, "erfolgreich": True, "neu": len(neue),
        })
    return lauf
