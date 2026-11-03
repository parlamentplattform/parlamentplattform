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
    from ki.kennungsabgleich import fuer_lauf
    from ki.models import Zweck

    if lauf.zweck != Zweck.RECHTSBEZUG:
        raise ValueError("Nur der öffentliche Rechtsbezug gehört in diesen Export.")
    return {
        "id": lauf.pk, "zweck": lauf.zweck, "modell": lauf.modell, "anbieter": lauf.anbieter,
        "auftrag_version": lauf.auftrag_version, "erstellt_am": lauf.erstellt_am.isoformat(),
        "erfolgreich": lauf.erfolgreich, "eingabe": lauf.eingabe, "antwort": lauf.antwort,
        "fehler": lauf.fehler, "kontext": lauf.kontext,
        "tokens_ein": lauf.tokens_ein, "tokens_aus": lauf.tokens_aus, "dauer_ms": lauf.dauer_ms,
        "antwortformat": form_pruefen(lauf.antwort) if lauf.erfolgreich else None,
        "kennungsabgleich": fuer_lauf(lauf),
    }


def antrag_export(antrag):
    from ki.models import KIAuftrag, KILauf, Zweck
    from ki.verbrauch import fuer_antrag

    daten = {
        "verbrauch": fuer_antrag(antrag),
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
    daten["quellenabgleich"] = aktueller_quellenabgleich(daten)
    from ki.korrekturen import export as korrektur_export

    daten["korrekturen"] = korrektur_export(antrag)
    return daten


def aktueller_quellenabgleich(daten):
    """Gleicher Ausgang wie die aktuelle Karte, ohne historische N+1-Abfragen.

    Der getrennte, heutige Lesebefund verändert weder die damaligen Aufträge
    noch ihre Modelleingaben. Kein Provider und keine öffentliche Modellantwort
    werden für diesen reinen Quellenvergleich benötigt.
    """
    from faktenbasis.nachlese import abgleichen

    auftrag = daten["auftraege"][-1] if daten["auftraege"] else None
    lauf = None
    if auftrag:
        if auftrag["status"] == "erledigt":
            lauf = next((eintrag for eintrag in daten["laeufe"] if eintrag["id"] == auftrag["lauf"] and eintrag["erfolgreich"]), None)
        roh = auftrag["quellenkontext"]
        text_hash = auftrag["kontext"].get("sha256") if isinstance(auftrag["kontext"], dict) else None
    else:
        lauf = next((eintrag for eintrag in reversed(daten["laeufe"]) if eintrag["erfolgreich"]), None)
        roh, text_hash = None, None
    if lauf:
        kontext = lauf["kontext"] if isinstance(lauf["kontext"], dict) else {}
        roh = kontext.get("quellen")
        text_hash = kontext.get("text", {}).get("sha256") if isinstance(kontext.get("text"), dict) else None
    return {"auftrag": auftrag["id"] if auftrag else None, "lauf": lauf["id"] if lauf else None,
            **abgleichen(roh, text_sha256=text_hash)}
