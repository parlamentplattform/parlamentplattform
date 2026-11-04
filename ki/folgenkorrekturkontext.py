"""Zweite Korrekturkontext-Fassung für den eigenen vollständigen Folgeninput.

Frühere Rechtsbezug-Korrekturrahmen bleiben Fassung1. Keine neuen Quellen lesen,
keine alte Eingabe nachträglich um Personalangaben ergänzen.
"""

import copy
import hashlib
from datetime import datetime

from django.utils import timezone

from ki import folgenkontext
from ki.kontext import _hash

VERSION = 2
_FELDER = {"version", "antrag", "ursprung", "ursprungszweck", "ursprungsauftrag", "eingabe", "eingabe_sha256",
           "antwort", "antwort_sha256", "text", "quellen", "folgen", "beanstandung", "sha256"}


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def festhalten(beanstandung, lauf):
    from ki.folgenauftraege import antwort_pruefen

    antwort_pruefen(lauf)  # Formfehler dürfen beanstandet werden, fremde Eingaben nicht.
    k = lauf.kontext
    if lauf.antrag_id != beanstandung.antrag_id or beanstandung.lauf_id != lauf.pk:
        raise ValueError("Ursprung gehört nicht zur Beanstandung.")
    d = {
        "version": VERSION, "antrag": lauf.antrag_id, "ursprung": lauf.pk,
        "ursprungszweck": "rechtsfolgen", "ursprungsauftrag": lauf.auftrag_version,
        "eingabe": lauf.eingabe, "eingabe_sha256": _sha(lauf.eingabe),
        "antwort": lauf.antwort, "antwort_sha256": _sha(lauf.antwort),
        "text": copy.deepcopy(k["text"]), "quellen": copy.deepcopy(k["quellen"]),
        "folgen": copy.deepcopy(k["folgen"]),
        "beanstandung": {"id": beanstandung.pk, "text": beanstandung.text,
                         "erstellt_am": beanstandung.erstellt_am.isoformat()},
    }
    rahmen = {**d, "sha256": _hash(d)}
    pruefen(rahmen)
    return rahmen


def _pruefen(rahmen):
    if not isinstance(rahmen, dict) or set(rahmen) != _FELDER:
        raise ValueError("Kein vollständiger Folgen-Korrekturrahmen.")
    d = copy.deepcopy(rahmen)
    sha = d.pop("sha256")
    if (not isinstance(sha, str) or sha != _hash(d) or type(d["version"]) is not int or d["version"] != VERSION
            or d["ursprungszweck"] != "rechtsfolgen" or d["ursprungsauftrag"] != folgenkontext.AUFTRAG):
        raise ValueError("Folgen-Korrekturvertrag oder Prüfsumme stimmt nicht.")
    f = folgenkontext.pruefen(d["folgen"])
    b = d["beanstandung"]
    if (d["text"] != f["text"] or d["quellen"] != f["quellen"]
            or type(d["antrag"]) is not int or d["antrag"] != f["text"]["antrag"]
            or type(d["ursprung"]) is not int or d["ursprung"] < 1
            or not isinstance(b, dict) or set(b) != {"id", "text", "erstellt_am"}
            or type(b["id"]) is not int or b["id"] < 1
            or not isinstance(b["text"], str) or not b["text"].strip() or len(b["text"]) > 2000
            or not isinstance(b["erstellt_am"], str) or timezone.is_naive(datetime.fromisoformat(b["erstellt_am"]))):
        raise ValueError("Folgen-Korrekturbezug stimmt nicht.")
    for feld in ("eingabe", "antwort"):
        if not isinstance(d[feld], str) or _sha(d[feld]) != d[feld + "_sha256"]:
            raise ValueError("Ursprünglicher Folgen-Wortlaut stimmt nicht.")
    if d["eingabe"] != folgenkontext.eingabe(d["folgen"]):
        raise ValueError("Keine tatsächliche öffentliche Folgen-Eingabe.")
    return d


def pruefen(rahmen):
    try:
        return _pruefen(rahmen)
    except (KeyError, TypeError, UnicodeEncodeError) as e:
        raise ValueError("Unlesbare Folgen-Korrekturstruktur.") from e
