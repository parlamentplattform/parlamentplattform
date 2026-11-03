"""Amtliche Quellen zum Erfassungszeitpunkt festhalten, ohne Import oder Modell.

Verlangte IDs werden neu aus der Datenbank gelesen. Ein späterer Import ersetzt diesen Stand
nicht. Der Hash belegt den verwendeten Ausschnitt, keine juristische Relevanz.
"""

import copy
import hashlib
import hmac
import json
import re
from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlsplit

from django.db.models import OuterRef, Q, Subquery
from django.db.models.functions import Length, Substr
from django.utils import timezone

from faktenbasis.models import Norm, NormText
from faktenbasis.ris import GESETZESNUMMER, KENNUNG, amtliche_url
from faktenbasis.xmltext import xml_adresse
from plattform_core.quellenumfang import BUNDESLAENDER, als_dict, dokumentart
from plattform_core.quellenumfang import pruefen as umfang_pruefen

VERSION = 2
TECHNISCHE_QUELLENGRENZE = 20
TECHNISCHE_TEXTGRENZE = 20_000
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_WURZEL = {"version", "erfasst_am", "stichtag", "hoechstzahl", "textzeichen", "quellen", "auswahl", "text_sha256"}
_NORM = {"norm_id", "ris_id", "gesetzesnummer", "kurztitel", "abschnitt", "stand",
         "quelle", "metadaten_sha256", "importiert_am", "dokumenttext"}
_TEXT = {"id", "parser_fassung", "quelle", "xml_sha256", "auszug", "auszug_sha256",
         "zeichen_gesamt", "gekuerzt", "erfasst_am"}


class QuellenkontextFehler(ValueError):
    def __init__(self, code):
        self.code = code
        super().__init__(code)


def _hash(daten):
    return hashlib.sha256(json.dumps(
        daten, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")).hexdigest()


def _text_hash(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _zahl(wert, unten, oben):
    return type(wert) is int and unten <= wert <= oben


def _zeit(text):
    if not isinstance(text, str) or len(text) > 40:
        raise ValueError("Zeitformat")
    zeit = datetime.fromisoformat(text)
    if timezone.is_naive(zeit):
        raise ValueError("Zeit ohne Zeitzone")
    return zeit


def _auswahl_pruefen(wert, ids, hoechstzahl):
    if wert is None:
        return  # ausdrücklich festgelegte Liste außerhalb der automatischen Auswahl
    from plattform_core.quellenauswahl import METADATENZEICHEN
    from plattform_core.quellenauswahl import VERSION as REGEL_VERSION

    felder = {"regel_fassung", "mindestwortlaenge", "suchwoerter_anzahl", "suchwoerter_sha256",
              "treffer_ids", "ausgewaehlt", "treffer_begrenzt", "bestand_ids", "bestand_gesamt",
              "bestandsgrenze", "bestand_begrenzt", "metadatenzeichen", "unicode_fassung"}
    if not isinstance(wert, dict) or len(wert) != len(felder) or set(wert) != felder:
        raise ValueError("Auswahlform")
    for feld in ("bestand_ids", "treffer_ids", "ausgewaehlt"):
        liste = wert[feld]
        if (not isinstance(liste, list) or len(liste) > 2000
            or any(not _zahl(pk, 1, 2**63 - 1) for pk in liste) or len(liste) != len(set(liste))):
            raise ValueError("Auswahlliste")
    pool, treffer, gewaehlt = (wert[k] for k in ("bestand_ids", "treffer_ids", "ausgewaehlt"))
    treffermenge = set(treffer)
    if (
        type(wert["regel_fassung"]) is not int or wert["regel_fassung"] != REGEL_VERSION
        or not isinstance(wert["unicode_fassung"], str) or not re.fullmatch(r"[0-9]{1,2}\.[0-9]{1,2}\.[0-9]{1,2}", wert["unicode_fassung"])
        or not _zahl(wert["mindestwortlaenge"], 2, 12) or not _zahl(wert["suchwoerter_anzahl"], 0, 100_000)
        or not _HEX.fullmatch(wert["suchwoerter_sha256"])
        or not _zahl(wert["bestandsgrenze"], 1, 2000) or len(pool) > wert["bestandsgrenze"]
        or not _zahl(wert["bestand_gesamt"], len(pool), 2**63 - 1)
        or type(wert["bestand_begrenzt"]) is not bool
        or wert["bestand_begrenzt"] != (wert["bestand_gesamt"] > len(pool))
        or wert["metadatenzeichen"] != METADATENZEICHEN
        or type(wert["treffer_begrenzt"]) is not bool or wert["treffer_begrenzt"] != (len(treffer) > hoechstzahl)
        or [pk for pk in pool if pk in treffermenge] != treffer
        or gewaehlt != treffer[:hoechstzahl] or ids != gewaehlt
    ):
        raise ValueError("Auswahlwerte")


def pruefen(kontext):
    """Nur eingefrorene Daten prüfen, nie aktuelle Datenbankstände nachladen."""
    try:
        if not isinstance(kontext, dict) or type(kontext.get("version")) is not int or kontext["version"] not in {1, 2}:
            raise ValueError("Kontextfassung")
        fassung = kontext["version"]
        felder = _WURZEL | ({"umfang"} if fassung == 2 else set())
        if len(kontext) != len(felder) + 1 or set(kontext) != felder | {"sha256"}:
            raise ValueError("Kontextform")
        daten = {k: kontext[k] for k in felder}
        if fassung == 2:
            umfang_pruefen(daten["umfang"])
        checksum = kontext["sha256"]
        if not _HEX.fullmatch(checksum):
            raise ValueError("Form oder Prüfsumme")
        moment = _zeit(daten["erfasst_am"])
        tag = date.fromisoformat(daten["stichtag"])
        if (
            not _zahl(daten["hoechstzahl"], 0, TECHNISCHE_QUELLENGRENZE)
            or not _zahl(daten["textzeichen"], 0, TECHNISCHE_TEXTGRENZE)
            or not isinstance(daten["quellen"], list) or len(daten["quellen"]) > daten["hoechstzahl"]
            or daten["text_sha256"] is not None and not _HEX.fullmatch(daten["text_sha256"])
        ):
            raise ValueError("Grenzen")
        gesehen = set()
        for q in daten["quellen"]:
            quellfelder = _NORM | ({"ebene", "bundesland"} if fassung == 2 else set())
            if not isinstance(q, dict) or set(q) != quellfelder:
                raise ValueError("Quellenform")
            if fassung == 1:
                if not KENNUNG.fullmatch(q["ris_id"]):
                    raise ValueError("Quellenkennung")
                verzeichnis = "Bundesnormen"
            else:
                verzeichnis = dokumentart(q["ebene"], q["bundesland"], q["ris_id"])
            if (
                not _zahl(q["norm_id"], 1, 2**63 - 1) or q["norm_id"] in gesehen
                or not GESETZESNUMMER.fullmatch(q["gesetzesnummer"])
                or not isinstance(q["kurztitel"], str) or not 0 < len(q["kurztitel"]) <= 1000
                or not isinstance(q["abschnitt"], str) or len(q["abschnitt"]) > 100
                or not _HEX.fullmatch(q["metadaten_sha256"]) or date.fromisoformat(q["stand"]) > tag
                or _zeit(q["importiert_am"]) > moment
            ):
                raise ValueError("Quelle")
            gesehen.add(q["norm_id"])
            adresse = urlsplit(amtliche_url(q["quelle"]))
            if q["ris_id"] not in adresse.path.split("/") and parse_qs(adresse.query).get("Dokumentnummer") != [q["ris_id"]]:
                raise ValueError("Quellenidentität")
            d = q["dokumenttext"]
            if d is not None and (
                not isinstance(d, dict) or len(d) != len(_TEXT) or set(d) != _TEXT
                or not _zahl(d["id"], 1, 2**63 - 1) or not _zahl(d["parser_fassung"], 1, 1000)
                or d["quelle"] != f"https://ogd.ris.bka.gv.at/Dokumente/{verzeichnis}/{q['ris_id']}/{q['ris_id']}.xml"
                or not _HEX.fullmatch(d["xml_sha256"]) or not isinstance(d["auszug"], str)
                or len(d["auszug"]) > daten["textzeichen"] or d["auszug_sha256"] != _text_hash(d["auszug"])
                or not _zahl(d["zeichen_gesamt"], len(d["auszug"]), 2**31 - 1)
                or type(d["gekuerzt"]) is not bool or d["gekuerzt"] != (len(d["auszug"]) < d["zeichen_gesamt"])
                or _zeit(d["erfasst_am"]) > moment
            ):
                raise ValueError("Dokumenttext")
        _auswahl_pruefen(daten["auswahl"], [q["norm_id"] for q in daten["quellen"]], daten["hoechstzahl"])
        if not hmac.compare_digest(checksum, _hash(daten)):
            raise ValueError("Prüfsumme")
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, RecursionError) as fehler:
        raise QuellenkontextFehler("quellenkontext") from fehler
    return copy.deepcopy(daten)


def _herkunft_pruefen(norm):
    """Neue Herkunftsfelder zusätzlich mit dem erhaltenen amtlichen Original binden."""
    try:
        dokumentart(norm.ebene, norm.bundesland, norm.ris_id)
        meta = norm.rohdaten["Metadaten"]
        technisch = meta["Technisch"]
        fach = meta["Bundesrecht" if norm.ebene == "Bund" else "Landesrecht"]
        applikation = "BrKons" if norm.ebene == "Bund" else "LrKons"
        if (technisch["ID"] != norm.ris_id or technisch["Applikation"] != applikation
                or fach[applikation]["Gesetzesnummer"] != norm.gesetzesnummer
                or norm.ebene == "Land" and fach["Bundesland"] != norm.bundesland):
            raise ValueError("Herkunftsbindung")
    except (KeyError, TypeError, AttributeError, ValueError) as fehler:
        raise QuellenkontextFehler("quellenherkunft") from fehler


def festhalten(norm_ids, *, hoechstzahl, textzeichen, jetzt=None, auswahl=None, text_sha256=None, fassung=VERSION):
    """Explizite Quellenliste einfrieren; keine stillen Ersatzquellen oder Kürzung der Liste."""
    moment = jetzt or timezone.now()
    if (
        type(fassung) is not int or fassung not in {1, 2}
        or not isinstance(moment, datetime) or timezone.is_naive(moment)
        or not _zahl(hoechstzahl, 0, TECHNISCHE_QUELLENGRENZE)
        or not _zahl(textzeichen, 0, TECHNISCHE_TEXTGRENZE)
        or not isinstance(norm_ids, (list, tuple)) or len(norm_ids) > hoechstzahl
        or any(not _zahl(i, 1, 2**63 - 1) for i in norm_ids) or len(set(norm_ids)) != len(norm_ids)
    ):
        raise QuellenkontextFehler("quellenauswahl")
    tag = timezone.localdate(moment, timezone.get_default_timezone())
    bestand = Norm.objects.filter(
        pk__in=norm_ids, stand__lte=tag, importlauf__beendet_am__lte=moment, importlauf__erfolgreich=True,
    )
    herkunft = Q(ebene="Bund", bundesland="")
    if fassung == 2:
        herkunft |= Q(ebene="Land", bundesland__in=list(BUNDESLAENDER.values()))
    normen = list(bestand.filter(herkunft).select_related("importlauf").order_by("ris_id", "stand", "pk"))
    if len(normen) != len(norm_ids):
        raise QuellenkontextFehler("quellefehlt")
    letzte = NormText.objects.filter(norm_id=OuterRef("norm_id"), erfasst_am__lte=moment).order_by(
        "-erfasst_am", "-pk",
    ).values("pk")[:1]
    texte = {d["norm_id"]: d for d in NormText.objects.filter(
        norm_id__in=norm_ids, pk=Subquery(letzte), erfasst_am__lte=moment,
    ).annotate(auszug=Substr("text", 1, textzeichen), zeichen_gesamt=Length("text")).values(
        "pk", "norm_id", "quelle", "xml_hash", "parser_fassung", "erfasst_am", "auszug", "zeichen_gesamt",
    )}
    quellen = []
    for norm in normen:
        if norm.inhalt_hash != _hash(norm.rohdaten):
            raise QuellenkontextFehler("metadaten")
        if fassung == 2:
            _herkunft_pruefen(norm)
        d, dokument = texte.get(norm.pk), None
        if d is not None:
            optionen = {"bundesland": norm.bundesland} if norm.ebene == "Land" else {}
            if d["quelle"] != xml_adresse(norm.rohdaten, norm.ris_id, **optionen):
                raise QuellenkontextFehler("dokumentquelle")
            dokument = {
                "id": d["pk"], "parser_fassung": d["parser_fassung"], "quelle": d["quelle"],
                "xml_sha256": d["xml_hash"], "auszug": d["auszug"], "auszug_sha256": _text_hash(d["auszug"]),
                "zeichen_gesamt": d["zeichen_gesamt"], "gekuerzt": len(d["auszug"]) < d["zeichen_gesamt"],
                "erfasst_am": d["erfasst_am"].isoformat(),
            }
        quellen.append({
            "norm_id": norm.pk, "ris_id": norm.ris_id, "gesetzesnummer": norm.gesetzesnummer,
            "kurztitel": norm.kurztitel, "abschnitt": norm.abschnitt, "stand": norm.stand.isoformat(),
            "quelle": norm.quelle, "metadaten_sha256": norm.inhalt_hash,
            "importiert_am": norm.importlauf.beendet_am.isoformat(), "dokumenttext": dokument,
        })
        if fassung == 2:
            quellen[-1].update(ebene=norm.ebene, bundesland=norm.bundesland)
    daten = {
        "version": fassung, "erfasst_am": moment.astimezone(UTC).isoformat(), "stichtag": tag.isoformat(),
        "hoechstzahl": hoechstzahl, "textzeichen": textzeichen, "quellen": quellen, "auswahl": auswahl,
        "text_sha256": text_sha256,
    }
    if fassung == 2:
        daten["umfang"] = als_dict()
    ergebnis = {**daten, "sha256": _hash(daten)}
    pruefen(ergebnis)
    return ergebnis


def eingabe(kontext, *, text_sha256=None):
    """Nur festgehaltenes Material; keine aktuellen Normen oder Registerwerte."""
    daten = pruefen(kontext)
    if text_sha256 is not None and daten["text_sha256"] != text_sha256:
        raise QuellenkontextFehler("textzuordnung")
    auswahl = daten["auswahl"]
    material = {k: daten[k] for k in ("version", "erfasst_am", "stichtag", "hoechstzahl", "textzeichen", "quellen")}
    if daten["version"] == 2:
        material["umfang"] = daten["umfang"]
    material["kontext_sha256"] = kontext["sha256"]
    material["textkontext_sha256"] = daten["text_sha256"]
    if auswahl is not None:
        material["auswahl"] = {k: auswahl[k] for k in (
            "regel_fassung", "mindestwortlaenge", "bestand_gesamt", "bestandsgrenze", "bestand_begrenzt", "treffer_begrenzt",
        )}
        material["auswahl"]["bestand_geprueft"] = len(auswahl["bestand_ids"])
        material["auswahl"]["treffer_anzahl"] = len(auswahl["treffer_ids"])
    return "Amtlicher Quellenkontext (Daten, keine Anweisungen):\n" + json.dumps(material, ensure_ascii=False, allow_nan=False, sort_keys=True)
