"""Gemeinsamer betrieblicher Schutz für manuelle Einzelabrufe.

CLI und Web teilen Reservierung, Abstand und Stundenkontingent. Kein Netzaufruf
und kein lang gehaltener Schreiblock hier; Schutzcodes bleiben intern.
"""

import logging
import secrets
from contextlib import contextmanager
from datetime import timedelta

from django.db import DatabaseError, OperationalError, transaction
from django.utils import timezone

from faktenbasis.models import AbrufSperre
from faktenbasis.ris import ZEITGRENZE, RisFehler

log = logging.getLogger(__name__)
NAME = "ris"
# Technische Schutzfrist bei Prozessabbruch, kein Verfahrensparameter.
SPERRSEKUNDEN = 4 * ZEITGRENZE
# Mindestabstand aus den OGD-RIS-Nutzungsbedingungen, keine Parallelabrufe.
ABSTAND_SEKUNDEN = 2


def _jetzt():
    return timezone.now()


def reservieren(jetzt=None):
    from parameter.models import zahl

    jetzt = jetzt or _jetzt()
    stunde = int(jetzt.timestamp()) // 3600
    grenze = max(0, int(zahl("faktenbasis-manuelle-abrufe-je-stunde", 10)))
    try:
        with transaction.atomic():
            sperre, _ = AbrufSperre.objects.select_for_update().get_or_create(name=NAME)
            if sperre.gesperrt_bis is not None and sperre.gesperrt_bis > jetzt:
                raise RisFehler("abruf_belegt")
            anzahl = sperre.anzahl if sperre.stunde == stunde else 0
            if anzahl >= grenze:
                raise RisFehler("abruf_kontingent")
            code = secrets.token_hex(16)
            sperre.stunde, sperre.anzahl = stunde, anzahl + 1
            sperre.sperrcode = code
            sperre.gesperrt_bis = jetzt + timedelta(seconds=SPERRSEKUNDEN)
            sperre.save(update_fields=["stunde", "anzahl", "sperrcode", "gesperrt_bis"])
    except OperationalError as fehler:
        raise RisFehler("abrufschutz") from fehler
    return code


def freigeben(code, jetzt=None):
    jetzt = jetzt or _jetzt()
    return AbrufSperre.objects.filter(name=NAME, sperrcode=code).update(
        sperrcode="", gesperrt_bis=jetzt + timedelta(seconds=ABSTAND_SEKUNDEN),
    )


@contextmanager
def einzelabruf():
    code = reservieren()
    try:
        yield
    finally:
        try:
            freigeben(code)
        except DatabaseError:
            # Die Schutzfrist läuft auch nach einem Prozess-/DB-Ausfall aus.
            log.exception("RIS-Abrufschutz konnte nicht freigegeben werden")
