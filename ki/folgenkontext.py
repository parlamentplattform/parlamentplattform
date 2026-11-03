"""Vorbereitete öffentliche Rechtsfolgen-Eingabe, getrennt von früheren Aufträgen.

Noch kein Modellweg. Nur vorhandenen öffentlichen Text, Normkandidaten und den
gesonderten Personalbestand festhalten. Keine privaten Vergleichsentwürfe oder
internen Gremienfassungen als Beifang, keine späteren Quellen beim Rekonstruieren.
"""

import copy
import hashlib
import json
from datetime import datetime

from django.utils import timezone

from faktenbasis.auswahl import erfassen as normen_erfassen
from faktenbasis.kontext import eingabe as normen_eingabe
from faktenbasis.kontext import pruefen as normen_pruefen
from faktenbasis.personalrahmen import festhalten as personal_erfassen
from faktenbasis.personalrahmen import pruefen as personal_pruefen
from ki.kontext import _hash
from ki.kontext import eingabe as text_eingabe
from ki.kontext import festhalten as text_erfassen
from ki.kontext import pruefen as text_pruefen

VERSION = 1
AUFTRAG = "rechtsfolgen-v1"
_FELDER = {"version", "auftrag_version", "erfasst_am", "hoechstzeichen", "text", "quellen", "personal", "eingabe_sha256", "sha256"}
_TEXTFELDER = {"version", "antrag", "quellenart", "fassung_id", "fassung_nummer", "titel", "wortlaut", "begruendung",
               "ebene", "ebene_wort", "gebiet", "erfasst_am"}


def _zeit(s):
    if not isinstance(s, str):
        raise ValueError("Erfassungszeit fehlt.")
    d = datetime.fromisoformat(s)
    if timezone.is_naive(d):
        raise ValueError("Erfassungszeit braucht eine Zeitzone.")
    return d


def _teile(d):
    t = text_pruefen(d["text"])
    q = normen_pruefen(d["quellen"])
    p = personal_pruefen(d["personal"], text_sha256=d["text"]["sha256"])
    if (set(t) != _TEXTFELDER or type(t["version"]) is not int or t["version"] != 1
            or t["quellenart"] not in {"antrag", "vorschlag"}
            or any(type(t[k]) is not int or not 1 <= t[k] <= 2**63 - 1 for k in ("antrag", "fassung_id", "fassung_nummer"))
            or any(not isinstance(t[k], str) for k in ("titel", "wortlaut", "begruendung", "ebene", "ebene_wort", "gebiet"))
            or not t["titel"].strip() or not t["wortlaut"].strip()
            or q["text_sha256"] != d["text"]["sha256"]):
        raise ValueError("Öffentlicher Textstand ist nicht eindeutig gebunden.")
    moment = _zeit(d["erfasst_am"])
    if any(_zeit(x["erfasst_am"]) != moment for x in (t, q, p)):
        raise ValueError("Die Teile gehören nicht zum selben Erfassungszeitpunkt.")
    return t, q, p


def _angebot(q, p):
    refs = [f"norm:{n['norm_id']}" for n in q["quellen"]]
    bereiche = []
    if p["aggregat"] is not None:
        refs.append(f"personal_aggregat:{p['aggregat']['id']}")
        bereiche.append(p["aggregat"]["bereich"])
    if p["ressorttabelle"] is not None:
        refs.append(f"personal_ressorts:{p['ressorttabelle']['id']}")
        bereiche += [z["ressort"] for z in p["ressorttabelle"]["ressorts"]]
    return refs, bereiche


def _eingabe(d, q, p):
    refs, bereiche = _angebot(q, p)
    return json.dumps({
        "auftrag_version": AUFTRAG,
        "oeffentlicher_text": text_eingabe(d["text"]),
        "amtliche_normgrundlage": normen_eingabe(d["quellen"], text_sha256=d["text"]["sha256"]),
        "personal_bestandsgrundlage": p,
        "angebotene_quellen": refs, "angebotene_personalbereiche": bereiche,
    }, ensure_ascii=False, sort_keys=True, allow_nan=False)


def festhalten(antrag, *, hoechstzeichen, vorschlagsfassung=None, fassung_nummer=None):
    """Aktuell beobachteten öffentlichen Stand erfassen, ohne rückdatierbare Ausgabe."""
    from gremien.models import EntwurfsFassung
    from verfahren.models import Antrag, Antragsart

    if type(hoechstzeichen) is not int or not 1 <= hoechstzeichen <= 100000:
        raise ValueError("Unklarer Eingaberahmen.")
    a = Antrag.objects.filter(pk=antrag.pk).first()
    if a is None or a.art in (Antragsart.MANDAT, Antragsart.VERTRAUENSFRAGE):
        raise ValueError("Keine öffentliche Sachfrage für die Folgenprüfung.")
    if vorschlagsfassung is not None:
        v = EntwurfsFassung.objects.select_related("entwurf").filter(pk=vorschlagsfassung.pk, entwurf__antrag=a).first()
        if v is None or v.entwurf.eingereichte_fassung != v.nummer:
            raise ValueError("Keine eingereichte öffentliche Vorschlagsfassung.")
        vorschlagsfassung = v
    text = text_erfassen(a, vorschlagsfassung=vorschlagsfassung, fassung_nummer=fassung_nummer)
    moment = _zeit(text["erfasst_am"])
    q = normen_erfassen(text, jetzt=moment)
    p = personal_erfassen(text["sha256"], jetzt=moment)
    d = {"version": VERSION, "auftrag_version": AUFTRAG, "erfasst_am": text["erfasst_am"],
         "hoechstzeichen": hoechstzeichen, "text": text, "quellen": q, "personal": p}
    _, quellen, personal = _teile(d)
    roh = _eingabe(d, quellen, personal)
    if len(roh) > hoechstzeichen:
        raise ValueError("Der vollständige Kontext überschreitet den Eingaberahmen; er wird nicht gekürzt.")
    d["eingabe_sha256"] = hashlib.sha256(roh.encode("utf-8")).hexdigest()
    r = {**d, "sha256": _hash(d)}
    pruefen(r)
    return r


def _pruefen(rahmen):
    """Gespeicherten Input ohne Datenbank, Register, Dateiladen oder Anbieter prüfen."""
    if not isinstance(rahmen, dict) or set(rahmen) != _FELDER:
        raise ValueError("Kein vollständiger Rechtsfolgenrahmen.")
    d = copy.deepcopy(rahmen)
    sha = d.pop("sha256")
    if (not isinstance(sha, str) or sha != _hash(d) or type(d["version"]) is not int or d["version"] != VERSION
            or d["auftrag_version"] != AUFTRAG or type(d["hoechstzeichen"]) is not int or not 1 <= d["hoechstzeichen"] <= 100000):
        raise ValueError("Rechtsfolgenrahmen oder Prüfsumme stimmt nicht.")
    _, q, p = _teile(d)
    roh = _eingabe(d, q, p)
    if len(roh) > d["hoechstzeichen"] or hashlib.sha256(roh.encode("utf-8")).hexdigest() != d["eingabe_sha256"]:
        raise ValueError("Tatsächliche Eingabe oder ihre Grenze stimmt nicht.")
    return d


def pruefen(rahmen):
    """Auch beschädigte verschachtelte Altverträge als unbrauchbaren Rahmen melden."""
    try:
        return _pruefen(rahmen)
    except (KeyError, TypeError, UnicodeEncodeError) as e:
        raise ValueError("Rechtsfolgenrahmen hat eine unlesbare Struktur.") from e


def eingabe(rahmen):
    d = pruefen(rahmen)
    _, q, p = _teile(d)
    return _eingabe(d, q, p)


def antwortangebot(rahmen):
    d = pruefen(rahmen)
    _, q, p = _teile(d)
    refs, bereiche = _angebot(q, p)
    return {"quellen": refs, "personalbereiche": bereiche}
