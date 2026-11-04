"""Den tatsächlichen öffentlichen Ursprung und die Beanstandung unverändert festhalten."""

import copy
import hashlib
import hmac
from datetime import datetime

from ki.kontext import _hash
from ki.kontext import pruefen as text_pruefen

VERSION = 1
_FELDER = {"version", "antrag", "ursprung", "eingabe", "eingabe_sha256", "antwort", "antwort_sha256",
           "text", "quellen", "beanstandung", "sha256"}
_TEXTFELDER = {"version", "antrag", "quellenart", "fassung_id", "fassung_nummer", "titel", "wortlaut",
               "begruendung", "ebene", "ebene_wort", "gebiet", "erfasst_am"}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _zeit(wert):
    if not isinstance(wert, str):
        return False
    try:
        zeit = datetime.fromisoformat(wert)
    except ValueError:
        return False
    return zeit.tzinfo is not None and zeit.utcoffset() is not None


def festhalten(beanstandung, lauf):
    if lauf.zweck == "rechtsfolgen":
        from ki.folgenkorrekturkontext import festhalten as folgen_festhalten

        return folgen_festhalten(beanstandung, lauf)
    from ki.rechtsbezugvertrag import lauf_pruefen

    lauf_pruefen(lauf)
    k = lauf.kontext if isinstance(lauf.kontext, dict) else {}
    text = text_pruefen(k.get("text"))
    if text["antrag"] != beanstandung.antrag_id or lauf.antrag_id != beanstandung.antrag_id:
        raise ValueError("Ursprung gehört nicht zum Antrag.")
    daten = {
        "version": VERSION, "antrag": lauf.antrag_id, "ursprung": lauf.pk,
        "eingabe": lauf.eingabe, "eingabe_sha256": _sha(lauf.eingabe),
        "antwort": lauf.antwort, "antwort_sha256": _sha(lauf.antwort),
        "text": copy.deepcopy(k["text"]), "quellen": copy.deepcopy(k.get("quellen", {})),
        "beanstandung": {"id": beanstandung.pk, "text": beanstandung.text,
                         "erstellt_am": beanstandung.erstellt_am.isoformat()},
    }
    return {**daten, "sha256": _hash(daten)}


def pruefen(roh):
    if isinstance(roh, dict) and roh.get("version") == 2:
        from ki.folgenkorrekturkontext import pruefen as folgen_pruefen

        return folgen_pruefen(roh)
    if not isinstance(roh, dict) or set(roh) != _FELDER:
        raise ValueError("Kein Korrekturrahmen.")
    d = copy.deepcopy(roh)
    sha = d.pop("sha256", None)
    if (not isinstance(sha, str) or not sha.isascii() or not hmac.compare_digest(sha, _hash(d))
            or type(d.get("version")) is not int or d["version"] != VERSION):
        raise ValueError("Korrekturrahmen oder Prüfsumme stimmt nicht.")
    t = text_pruefen(d.get("text"))
    b = d.get("beanstandung")
    if (set(t) != _TEXTFELDER or type(t.get("version")) is not int or t["version"] != 1
            or any(type(t.get(k)) is not int or t[k] < 1 for k in ("antrag", "fassung_id", "fassung_nummer"))
            or any(not isinstance(t.get(k), str) for k in ("titel", "wortlaut", "begruendung", "ebene", "ebene_wort", "gebiet"))
            or not _zeit(t.get("erfasst_am"))
            or type(d.get("antrag")) is not int or d["antrag"] != t["antrag"]
            or type(d.get("ursprung")) is not int or d["ursprung"] < 1
            or not isinstance(b, dict) or set(b) != {"id", "text", "erstellt_am"}
            or type(b.get("id")) is not int or b["id"] < 1
            or not isinstance(b.get("text"), str) or not b["text"].strip() or len(b["text"]) > 2000
            or not _zeit(b.get("erstellt_am"))):
        raise ValueError("Korrekturbezug stimmt nicht.")
    for feld in ("eingabe", "antwort"):
        if not isinstance(d.get(feld), str) or _sha(d[feld]) != d.get(feld + "_sha256"):
            raise ValueError("Ursprünglicher Wortlaut stimmt nicht.")
    # Auch wartende Aufträge ohne lauf_id können öffentlich nachgelesen werden.
    # Deshalb vor der Ausgabe den vollständigen alten Vertrag prüfen, nicht
    # erst beim späteren Modellaufruf. Keine heutigen Quellen nachladen.
    from ki.eingabevertrag import rechtsbezug

    _nummer, eingabe = rechtsbezug(d["text"], d["quellen"])
    if d["eingabe"] != eingabe:
        raise ValueError("Die ursprüngliche öffentliche Eingabe ist nicht eindeutig belegt.")
    return d
