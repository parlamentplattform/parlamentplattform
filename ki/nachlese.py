"""Öffentlicher Textstand und Export ausschließlich des öffentlichen Rechtsbezugs."""

from django.utils.dateparse import parse_datetime
from django.utils.translation import gettext_lazy as _

from ki.kontext import pruefen
from plattform_core.modellantwort import pruefen as form_pruefen


def quellenstand(roh, *, text_sha256=None):
    from faktenbasis.kontext import QuellenkontextFehler
    from faktenbasis.kontext import pruefen as quellen_pruefen

    if not roh:
        return {"zustand": "alt"}
    try:
        daten = quellen_pruefen(roh)
        if text_sha256 is not None and daten["text_sha256"] != text_sha256:
            return {"zustand": "fehler"}
    except QuellenkontextFehler:
        return {"zustand": "fehler"}
    return {"zustand": "fest", **daten, "hash": roh["sha256"], "erfasst_am": parse_datetime(daten["erfasst_am"])}


def textstand(lauf):
    roh = lauf.kontext.get("text") if isinstance(lauf.kontext, dict) else None
    if not roh:
        return {"festgehalten": False, "quelle": _("Textquelle nicht eigens festgehalten")}
    try:
        daten = pruefen(roh)
        zeit = parse_datetime(daten["erfasst_am"])
        if zeit is None:
            raise ValueError("Kein Erfassungszeitpunkt")
    except (KeyError, TypeError, ValueError):
        return {"festgehalten": False, "quelle": _("Textkontext nicht prüfbar")}
    return {
        "festgehalten": True, "quelle": _("Antrag") if daten["quellenart"] == "antrag" else _("Vorschlag des Expertenrats"),
        "quellenart": daten["quellenart"], "fassung": daten["fassung_nummer"],
        "fassung_id": daten["fassung_id"], "hash": roh["sha256"], "erfasst_am": zeit,
    }


def lauf_export(lauf):
    """Kein Export interner Gremien-Eingaben, weder als Beifang noch über ein fremdes Zweckfeld."""
    from ki.models import Zweck

    if lauf.zweck != Zweck.RECHTSBEZUG:
        raise ValueError("Nur der öffentliche Rechtsbezug gehört in diesen Export.")
    return {
        "id": lauf.pk, "zweck": lauf.zweck, "modell": lauf.modell, "anbieter": lauf.anbieter,
        "auftrag_version": lauf.auftrag_version, "erstellt_am": lauf.erstellt_am.isoformat(),
        "erfolgreich": lauf.erfolgreich, "eingabe": lauf.eingabe, "antwort": lauf.antwort,
        "fehler": lauf.fehler, "kontext": lauf.kontext,
        "antwortformat": form_pruefen(lauf.antwort) if lauf.erfolgreich else None,
    }


def antrag_export(antrag):
    from ki.models import KIAuftrag, KILauf, Zweck

    return {
        "auftraege": [{
            "id": a.pk, "quellenart": a.quellenart, "fassung": a.fassung_nummer,
            "vorschlagsfassung": a.vorschlagsfassung_id, "kontext": a.kontext, "quellenkontext": a.quellenkontext,
            "status": a.status, "lauf": a.lauf_id, "versuche": a.versuche,
            "erstellt_am": a.erstellt_am.isoformat(), "erledigt_am": a.erledigt_am.isoformat() if a.erledigt_am else None,
        } for a in KIAuftrag.objects.filter(antrag=antrag, zweck=Zweck.RECHTSBEZUG).order_by("erstellt_am", "pk")],
        "laeufe": [lauf_export(lauf) for lauf in KILauf.objects.filter(
            antrag=antrag, zweck=Zweck.RECHTSBEZUG,
        ).order_by("erstellt_am", "pk")],
    }
