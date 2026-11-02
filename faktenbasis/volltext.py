"""Expliziter Bezug eines amtlichen Dokumenttexts; kein Sammel- oder Modellauftrag."""

import urllib.error
import urllib.request

from django.db import transaction
from django.utils import timezone

from faktenbasis.models import NormText, NormTextAbruf
from faktenbasis.ris import HOECHSTBYTES, ZEITGRENZE, RisFehler, _KeineUmleitung
from faktenbasis.xmltext import PARSER_FASSUNG, xml_adresse, xmltext_parsen
from verfahren.models import AuditEintrag


def abrufen(url):
    """Nur die zuvor mit xml_adresse geprüfte URL aufrufen, genau ein Request."""
    anfrage = urllib.request.Request(url, headers={
        "Accept": "application/xml, text/xml, application/octet-stream",
        "User-Agent": "DDOE-ParlamentPlattform-Einzelimport (plattform@ddoe.at)",
    })
    try:
        opener = urllib.request.build_opener(_KeineUmleitung())
        with opener.open(anfrage, timeout=ZEITGRENZE) as antwort:
            if antwort.status != 200 or antwort.headers.get_content_type() not in {
                "application/xml", "text/xml", "application/octet-stream",
            }:
                raise RisFehler("volltextformat")
            daten = antwort.read(HOECHSTBYTES + 1)
        if len(daten) > HOECHSTBYTES:
            raise RisFehler("antwortgroesse")
        return daten
    except RisFehler:
        raise
    except (OSError, urllib.error.URLError) as fehler:
        raise RisFehler("abruf") from fehler


def importieren(norm):
    beginn = timezone.now()
    quelle = ""
    try:
        quelle = xml_adresse(norm.rohdaten, norm.ris_id)
        daten = xmltext_parsen(abrufen(quelle), norm.ris_id, norm.gesetzesnummer)
    except RisFehler as fehler:
        with transaction.atomic():
            lauf = NormTextAbruf.objects.create(
                norm=norm, quelle=quelle, begonnen_am=beginn, beendet_am=timezone.now(),
                erfolgreich=False, fehlercode=fehler.code,
            )
            AuditEintrag.anhaengen({"typ": "ris_volltext", "abruf": lauf.pk, "erfolgreich": False})
        raise
    with transaction.atomic():
        inhalt, neu = NormText.objects.get_or_create(
            norm=norm, xml_hash=daten.xml_hash, parser_fassung=PARSER_FASSUNG,
            defaults={"quelle": quelle, "xml": daten.xml, "text": daten.text},
        )
        lauf = NormTextAbruf.objects.create(
            norm=norm, inhalt=inhalt, quelle=quelle, begonnen_am=beginn,
            beendet_am=timezone.now(), erfolgreich=True, neu=neu,
        )
        AuditEintrag.anhaengen({
            "typ": "ris_volltext", "abruf": lauf.pk, "inhalt": inhalt.pk,
            "erfolgreich": True, "neu": neu,
        })
    return lauf
