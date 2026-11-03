"""Privater Vergleichsstand aus einem an Konto und Formular gebundenen Angebot.

Keine Anbieteranbindung. Die Projektion an ein Modell enthält nur Titel und
Wortlaute, öffentliche Paarreferenzen sowie ihre Prüfsummen. Der private Rahmen
bindet zusätzlich das Konto und das vollständige Formular. Keine Quellen aus
internen Gremienentwürfen und kein stilles Kürzen langer Texte.
"""

import copy
import hashlib
import hmac
import json
from datetime import datetime

from django.utils import timezone

from ki.kontext import _hash
from plattform_core.gegenueberstellung import HOECHSTPAARE

VERSION = 1
TECHNISCHE_TEXTGRENZE = 100_000
_TEXTFELDER = {"titel", "wortlaut"}
_PAARFELDER = {"antrag", "fassung", "fassung_id", "titel", "wortlaut", "text_sha256"}
_FELDER = {"version", "konto", "formular_sha256", "erfasst_am", "entwurf", "gegenueber", "rahmen"}


def _text(text):
    if not isinstance(text, str) or not text.strip():
        raise ValueError("Vergleichstext fehlt.")
    try:
        text.encode("utf-8")
    except UnicodeEncodeError as e:
        raise ValueError("Vergleichstext ist nicht lesbar.") from e
    if any(ord(c) < 32 and c not in "\n\r\t" or ord(c) == 127 for c in text):
        raise ValueError("Vergleichstext enthält Steuerzeichen.")
    return text


def _nummer(wert):
    return type(wert) is int and 1 <= wert <= 2**63 - 1


def _sha(wert):
    return isinstance(wert, str) and len(wert) == 64 and all(c in "0123456789abcdef" for c in wert)


def _textsumme(titel, wortlaut):
    return _hash({"titel": titel, "wortlaut": wortlaut})


def _rahmen(zeichen, paare):
    if (type(zeichen) is not int or not 1 <= zeichen <= TECHNISCHE_TEXTGRENZE
            or type(paare) is not int or not 1 <= paare <= HOECHSTPAARE):
        raise ValueError("Ungültiger Vergleichsrahmen.")


def festhalten(daten, mitglied, token, *, hoechstzeichen, hoechstpaare, jetzt=None):
    """Nur die signiert angebotenen öffentlichen aktuellen Sachantragsfassungen lesen.

    Ein zwischenzeitlich geänderter Titel oder eine neue Fassung verlangt ein neues
    Angebot. Die menschliche Wahl wird dadurch weder ausgeführt noch eingeschränkt.
    """
    from verfahren.aehnlichkeit import OFFENE_PHASEN
    from verfahren.einbringwahl import _fingerabdruck, pruefstand_lesen
    from verfahren.models import Antrag, Antragsart

    _rahmen(hoechstzeichen, hoechstpaare)
    stand = pruefstand_lesen(token, daten, mitglied)
    if stand is None or daten.get("art") != Antragsart.SACHE or not _nummer(mitglied.pk):
        raise ValueError("Der Prüfstand gehört nicht zu diesem Konto und Text.")
    treffer = stand.get("treffer")
    if not isinstance(treffer, list) or not 1 <= len(treffer) <= hoechstpaare:
        raise ValueError("Die angebotene Trefferzahl passt nicht zum Vergleichsrahmen.")
    ids = []
    for t in treffer:
        if (not isinstance(t, dict) or not _nummer(t.get("id")) or not _nummer(t.get("fassung"))
                or t["id"] in ids):
            raise ValueError("Die angebotenen Fassungen sind nicht eindeutig.")
        ids.append(t["id"])
    antraege = Antrag.objects.filter(pk__in=ids, art=Antragsart.SACHE,
                                    phase__in=OFFENE_PHASEN).prefetch_related("fassungen").in_bulk()
    gegenueber = []
    for t in treffer:
        antrag = antraege.get(t["id"])
        fassung = max(antrag.fassungen.all(), key=lambda f: f.nummer, default=None) if antrag else None
        if fassung is None or fassung.nummer != t["fassung"] or antrag.titel != t.get("titel"):
            raise ValueError("Ein angebotener öffentlicher Text hat sich geändert oder fehlt.")
        gegenueber.append({"antrag": antrag.pk, "fassung": fassung.nummer, "fassung_id": fassung.pk,
                           "titel": _text(antrag.titel), "wortlaut": _text(fassung.wortlaut),
                           "text_sha256": _textsumme(antrag.titel, fassung.wortlaut)})
    entwurf = {k: _text(daten.get(k)).replace("\r\n", "\n").replace("\r", "\n") for k in _TEXTFELDER}
    d = {"version": VERSION, "konto": mitglied.pk, "formular_sha256": _fingerabdruck(daten),
         "erfasst_am": (jetzt or timezone.now()).isoformat(), "entwurf": entwurf,
         "gegenueber": gegenueber, "rahmen": {"hoechstzeichen": hoechstzeichen, "hoechstpaare": hoechstpaare}}
    ergebnis = {**d, "sha256": _hash(d)}
    pruefen(ergebnis)
    return ergebnis


def pruefen(kontext):
    """Exakten gespeicherten Stand ohne aktuelle Datenbank oder Anbieter prüfen."""
    if not isinstance(kontext, dict) or set(kontext) != _FELDER | {"sha256"}:
        raise ValueError("Kein eindeutiger Vergleichskontext.")
    d = copy.deepcopy(kontext)
    sha = d.pop("sha256")
    try:
        korrekt = _sha(sha) and hmac.compare_digest(sha, _hash(d))
    except (TypeError, ValueError, UnicodeEncodeError) as e:
        raise ValueError("Vergleichskontext ist nicht lesbar.") from e
    if not korrekt or type(d["version"]) is not int or d["version"] != VERSION:
        raise ValueError("Vergleichskontext oder Prüfsumme stimmt nicht.")
    if not _nummer(d["konto"]) or not _sha(d["formular_sha256"]):
        raise ValueError("Private Formularbindung fehlt.")
    if not isinstance(d["erfasst_am"], str):
        raise ValueError("Erfassungszeit fehlt.")
    try:
        zeit = datetime.fromisoformat(d["erfasst_am"])
    except ValueError as e:
        raise ValueError("Erfassungszeit ist nicht lesbar.") from e
    if timezone.is_naive(zeit):
        raise ValueError("Erfassungszeit braucht eine Zeitzone.")
    rahmen, entwurf = d["rahmen"], d["entwurf"]
    if not isinstance(rahmen, dict) or set(rahmen) != {"hoechstzeichen", "hoechstpaare"}:
        raise ValueError("Vergleichsrahmen fehlt.")
    _rahmen(rahmen["hoechstzeichen"], rahmen["hoechstpaare"])
    if not isinstance(entwurf, dict) or set(entwurf) != _TEXTFELDER:
        raise ValueError("Der eigene Vergleichstext fehlt.")
    laenge = sum(len(_text(entwurf[k])) for k in _TEXTFELDER)
    paare = d["gegenueber"]
    if not isinstance(paare, list) or not 1 <= len(paare) <= rahmen["hoechstpaare"]:
        raise ValueError("Vergleichspaare fehlen oder überschreiten den Rahmen.")
    gesehen = set()
    for p in paare:
        if (not isinstance(p, dict) or set(p) != _PAARFELDER
                or any(not _nummer(p[k]) for k in ("antrag", "fassung", "fassung_id")) or p["antrag"] in gesehen):
            raise ValueError("Vergleichspaar ist nicht eindeutig.")
        gesehen.add(p["antrag"])
        laenge += len(_text(p["titel"])) + len(_text(p["wortlaut"]))
        if not _sha(p["text_sha256"]) or not hmac.compare_digest(p["text_sha256"], _textsumme(p["titel"], p["wortlaut"])):
            raise ValueError("Öffentlicher Text und Prüfsumme stimmen nicht.")
    if laenge > rahmen["hoechstzeichen"]:
        raise ValueError("Die vollständigen Texte sind für diesen Modellvergleich zu lang.")
    return d


def eingabe(kontext):
    """Anbieterprojektion ohne Konto, Begründung, Gebiet, Scores oder Formularfelder."""
    d = pruefen(kontext)
    return json.dumps({"version": VERSION, "entwurf": d["entwurf"],
                       "gegenueber": d["gegenueber"]}, ensure_ascii=False, sort_keys=True, allow_nan=False)


def eingabe_hash(kontext):
    return hashlib.sha256(eingabe(kontext).encode("utf-8")).hexdigest()
