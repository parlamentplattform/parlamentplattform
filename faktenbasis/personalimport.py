"""Expliziter Einzelbezug eines bekannten amtlichen Personalbelegs, keine Modellwerte."""

import urllib.error
import urllib.request
from time import monotonic

from django.db import transaction
from django.utils import timezone

from faktenbasis.abrufschutz import einzelabruf
from faktenbasis.models import PersonalAbruf, PersonalAggregat
from faktenbasis.personalbeleg import HOECHSTBYTES, QUELLE, lesen
from faktenbasis.ris import ZEITGRENZE, _KeineUmleitung
from verfahren.models import AuditEintrag


def _herunterladen():
    request = urllib.request.Request(QUELLE, headers={
        "Accept": "application/pdf", "User-Agent": "DDOE-ParlamentPlattform-Einzelimport (plattform@ddoe.at)",
    })
    beginn = monotonic()
    try:
        with urllib.request.build_opener(_KeineUmleitung()).open(request, timeout=ZEITGRENZE) as antwort:
            if antwort.status != 200 or antwort.headers.get_content_type() not in {"application/pdf", "application/octet-stream"}:
                raise ValueError("personal_antwort")
            teile, gesamt = [], 0
            while True:
                if monotonic() - beginn > ZEITGRENZE:
                    raise ValueError("personal_zeit")
                teil = antwort.read(min(65536, HOECHSTBYTES + 1 - gesamt))
                if not teil:
                    return b"".join(teile)
                gesamt += len(teil)
                if gesamt > HOECHSTBYTES:
                    raise ValueError("personal_groesse")
                teile.append(teil)
    except (OSError, urllib.error.URLError) as fehler:
        raise ValueError("personal_abruf") from fehler


def _uebernehmen(lieferung, weg):
    beginn = timezone.now()
    try:
        daten = lesen(lieferung())
    except ValueError as fehler:
        code = str(fehler)
        if code not in {"personal_antwort", "personal_zeit", "personal_groesse", "personal_abruf", "personal_datei",
                        "personal_unbekannter_beleg", "personal_pdf", "personal_text", "personal_seite",
                        "personal_spalten", "personal_einheit", "personal_jahr", "personal_zahlen", "personal_summe"}:
            code = "personal_format"
        with transaction.atomic():
            a = PersonalAbruf.objects.create(begonnen_am=beginn, beendet_am=timezone.now(),
                erfolgreich=False, weg=weg, fehlercode=code)
            AuditEintrag.anhaengen({"typ": "personal_import", "abruf": a.pk, "erfolgreich": False})
        raise ValueError(code) from fehler
    with transaction.atomic():
        a, neu = PersonalAggregat.objects.get_or_create(
            original_sha256=daten["original_sha256"], parser_fassung=daten["parser_fassung"],
            datenjahr=daten["datenjahr"], bereich=daten["bereich"],
            defaults={k: v for k, v in daten.items() if k not in {"original_sha256", "parser_fassung", "datenjahr", "bereich"}},
        )
        lauf = PersonalAbruf.objects.create(aggregat=a, begonnen_am=beginn, beendet_am=timezone.now(),
            erfolgreich=True, neu=neu, weg=weg)
        AuditEintrag.anhaengen({"typ": "personal_import", "abruf": lauf.pk, "aggregat": a.pk, "erfolgreich": True, "neu": neu})
    return lauf


def datei_importieren(inhalt):
    return _uebernehmen(lambda: inhalt, "datei")


def amtlich_importieren():
    # Dasselbe Kontingent wie die bisherigen Verwaltungs-/CLI-Einzelabrufe.
    with einzelabruf():
        return _uebernehmen(_herunterladen, "amtlich")
