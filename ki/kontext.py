"""Öffentlichen Textstand und Herkunft vor dem Einreihen festhalten (H6-Fundament).

Die Nummernräume der Antragsfassungen und
der Vorschläge bleiben getrennt. Fehlende Quellen werden nie durch einen
neueren Text ersetzt. Weder Modellaufruf noch Verfahrenshandlung in diesem Modul.
"""

import copy
import hashlib
import hmac
import json

from django.utils import timezone, translation

VERSION = 1


def _hash(daten):
    return hashlib.sha256(json.dumps(
        daten, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def festhalten(antrag, *, vorschlagsfassung=None, fassung_nummer=None, jetzt=None):
    """Nur tatsächlich gespeicherte, diesem Antrag gehörende Texte festhalten."""
    from gremien.models import EntwurfsFassung
    from verfahren.models import Antrag

    if vorschlagsfassung is not None and fassung_nummer is not None:
        raise ValueError("Nur eine Textquelle auswählen.")
    if not antrag.pk:
        raise ValueError("Der Antrag ist nicht gespeichert.")
    antrag = Antrag.objects.get(pk=antrag.pk)
    if vorschlagsfassung is not None:
        if not isinstance(vorschlagsfassung, EntwurfsFassung) or not vorschlagsfassung.pk:
            raise ValueError("Die Vorschlagsfassung ist nicht gespeichert.")
        fassung = EntwurfsFassung.objects.filter(
            pk=vorschlagsfassung.pk, entwurf__antrag_id=antrag.pk,
        ).first()
        art = "vorschlag"
    else:
        fassungen = antrag.fassungen.all()
        fassung = (fassungen.filter(nummer=fassung_nummer).first() if fassung_nummer is not None
                   else fassungen.order_by("-nummer").first())
        art = "antrag"
    if fassung is None:
        raise ValueError("Die verlangte Textfassung gehört nicht zu diesem Antrag oder fehlt.")
    with translation.override("de"):
        ebene_wort = str(antrag.get_ebene_display())
    daten = {
        "version": VERSION, "antrag": antrag.pk, "quellenart": art,
        "fassung_id": fassung.pk, "fassung_nummer": fassung.nummer,
        "titel": antrag.titel, "wortlaut": fassung.wortlaut, "begruendung": fassung.begruendung,
        "ebene": antrag.ebene, "ebene_wort": ebene_wort, "gebiet": antrag.gebiet,
        "erfasst_am": (jetzt or timezone.now()).isoformat(),
    }
    return {**daten, "sha256": _hash(daten)}


def pruefen(kontext):
    if not isinstance(kontext, dict):
        raise ValueError("Kein gespeicherter Textkontext.")
    daten = copy.deepcopy(kontext)
    pruefsumme = daten.pop("sha256", None)
    if (
        daten.get("version") != VERSION or daten.get("quellenart") not in {"antrag", "vorschlag"}
        or not isinstance(pruefsumme, str) or not pruefsumme.isascii()
        or not hmac.compare_digest(pruefsumme, _hash(daten))
    ):
        raise ValueError("Textkontext oder Prüfsumme stimmt nicht.")
    return daten


def eingabe(kontext):
    """Nur den festgehaltenen Stand verwenden, ohne spätere Datenbank-Lesezugriffe."""
    d = pruefen(kontext)
    quelle = "Antrag" if d["quellenart"] == "antrag" else "Vorschlag des Expertenrats"
    teile = [
        f"Textquelle: {quelle}, Fassung {d['fassung_nummer']}",
        f"Titel: {d['titel']}",
        f"Ebene: {d['ebene_wort']}" + (f" ({d['gebiet']})" if d["gebiet"] else ""),
        "", "Wortlaut:", d["wortlaut"],
    ]
    if d["begruendung"]:
        teile += ["", "Begründung:", d["begruendung"]]
    return "\n".join(teile)
