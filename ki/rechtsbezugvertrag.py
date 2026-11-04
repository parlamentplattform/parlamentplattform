"""Öffentliche Altverträge lesen, ohne heutige Daten oder unbekannte Beifänge.

Kein neues Eingabeformat: kontextlose frühe Archive bleiben erhalten. Seit der
Textstandserfassung sind ausschließlich die damals geschriebenen Felder und
der daraus rekonstruierbare Eingabetext öffentlich nachweisbar.
"""

from datetime import datetime

from ki.eingabevertrag import rechtsbezug
from ki.kontext import pruefen

_TEXTFELDER = {"version", "antrag", "quellenart", "fassung_id", "fassung_nummer", "titel", "wortlaut",
               "begruendung", "ebene", "ebene_wort", "gebiet", "erfasst_am"}


def _oeffentlicher_text(roh):
    if (not isinstance(roh, dict) or set(roh) != _TEXTFELDER | {"sha256"}
            or type(roh.get("version")) is not int
            or any(type(roh.get(f)) is not int or roh[f] < 1 for f in ("antrag", "fassung_id", "fassung_nummer"))
            or any(not isinstance(roh.get(f), str) for f in (
                "titel", "wortlaut", "begruendung", "ebene", "ebene_wort", "gebiet", "erfasst_am"))):
        raise ValueError("Kein vollständig öffentlicher Textvertrag.")
    d = pruefen(roh)
    zeit = datetime.fromisoformat(d["erfasst_am"])
    if zeit.tzinfo is None or zeit.utcoffset() is None:
        raise ValueError("Kein eindeutiger Erfassungszeitpunkt.")
    return d


def lauf_pruefen(lauf):
    """Gültige alte Daten weder ergänzen noch umschreiben; keine Datenbank lesen."""
    if lauf.zweck != "rechtsbezug" or not isinstance(lauf.kontext, dict):
        raise ValueError("Kein öffentlicher Rechtsbezuglauf.")
    k = lauf.kontext
    if not k:
        if lauf.auftrag_version not in {"", "rechtsbezug-v1"}:
            raise ValueError("Ein neuerer Prompt ist kein kontextloses Altarchiv.")
        return  # Frühe Archive hatten ausdrücklich noch keinen Textkontext.
    basis = {"text", "auftrag", "versuch"}
    if (set(k) not in (basis, basis | {"quellen"})
            or type(k.get("auftrag")) is not int or k["auftrag"] < 1
            or type(k.get("versuch")) is not int or k["versuch"] < 1):
        raise ValueError("Unbekannter Beifang im öffentlichen Rechtsbezuglauf.")
    d = _oeffentlicher_text(k["text"])
    nummer, eingabe = rechtsbezug(k["text"], k.get("quellen", {}))
    if (d["antrag"] != lauf.antrag_id or lauf.auftrag_version != f"rechtsbezug-v{nummer}"
            or lauf.eingabe != eingabe):
        raise ValueError("Die ursprüngliche öffentliche Eingabe ist nicht eindeutig belegt.")


def auftrag_pruefen(auftrag):
    """Auch wartende Aufträge dürfen keine unbekannten Text-/Quellenfelder ausgeben."""
    if auftrag.zweck != "rechtsbezug" or not isinstance(auftrag.kontext, dict):
        raise ValueError("Kein öffentlicher Rechtsbezugauftrag.")
    if (not auftrag.kontext and auftrag.quellenkontext == {}
            and auftrag.quellenart == "antrag" and auftrag.vorschlagsfassung_id is None):
        return  # Unveränderte frühe Warteschlangeneinträge, ohne neue Erfassung.
    d = _oeffentlicher_text(auftrag.kontext)
    rechtsbezug(auftrag.kontext, auftrag.quellenkontext)
    if (d["antrag"] != auftrag.antrag_id or d["quellenart"] != auftrag.quellenart
            or d["fassung_nummer"] != auftrag.fassung_nummer
            or d["quellenart"] == "vorschlag" and d["fassung_id"] != auftrag.vorschlagsfassung_id
            or d["quellenart"] == "antrag" and auftrag.vorschlagsfassung_id is not None):
        raise ValueError("Textkontext gehört nicht zum öffentlichen Auftrag.")
