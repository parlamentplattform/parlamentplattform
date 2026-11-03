"""Den tatsächlichen öffentlichen Ursprung und die Beanstandung unverändert festhalten."""

import copy
import hashlib
import hmac

from ki.kontext import _hash
from ki.kontext import pruefen as text_pruefen

VERSION = 1


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def festhalten(beanstandung, lauf):
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
    if not isinstance(roh, dict):
        raise ValueError("Kein Korrekturrahmen.")
    d = copy.deepcopy(roh)
    sha = d.pop("sha256", None)
    if (not isinstance(sha, str) or not sha.isascii() or not hmac.compare_digest(sha, _hash(d))
            or d.get("version") != VERSION):
        raise ValueError("Korrekturrahmen oder Prüfsumme stimmt nicht.")
    t = text_pruefen(d.get("text"))
    b = d.get("beanstandung")
    if (type(d.get("antrag")) is not int or d["antrag"] != t["antrag"]
            or type(d.get("ursprung")) is not int or d["ursprung"] < 1
            or not isinstance(b, dict) or type(b.get("id")) is not int or b["id"] < 1
            or not isinstance(b.get("text"), str) or not b["text"].strip() or len(b["text"]) > 2000):
        raise ValueError("Korrekturbezug stimmt nicht.")
    for feld in ("eingabe", "antwort"):
        if not isinstance(d.get(feld), str) or _sha(d[feld]) != d.get(feld + "_sha256"):
            raise ValueError("Ursprünglicher Wortlaut stimmt nicht.")
    return d
