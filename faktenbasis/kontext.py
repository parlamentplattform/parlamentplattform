"""Amtliche Quellen zum Erfassungszeitpunkt festhalten, ohne Import oder Modell.

Noch ohne automatische Auswahl oder Warteschlangen-Anbindung. Verlangte IDs
werden neu aus der Datenbank gelesen. Ein späterer Import ersetzt diesen Stand
nicht. Der Hash belegt den verwendeten Ausschnitt, keine juristische Relevanz.
"""

import copy
import hashlib
import hmac
import json
import re
from datetime import UTC, date, datetime
from urllib.parse import parse_qs, urlsplit

from django.db.models import OuterRef, Subquery
from django.db.models.functions import Length, Substr
from django.utils import timezone

from faktenbasis.models import Norm, NormText
from faktenbasis.ris import GESETZESNUMMER, KENNUNG, amtliche_url
from faktenbasis.xmltext import xml_adresse

VERSION = 1
TECHNISCHE_QUELLENGRENZE = 20
TECHNISCHE_TEXTGRENZE = 20_000
_HEX = re.compile(r"[0-9a-f]{64}\Z", re.ASCII)
_WURZEL = {"version", "erfasst_am", "stichtag", "hoechstzahl", "textzeichen", "quellen"}
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


def pruefen(kontext):
    """Nur eingefrorene Daten prüfen, nie aktuelle Datenbankstände nachladen."""
    try:
        if not isinstance(kontext, dict) or len(kontext) != len(_WURZEL) + 1 or set(kontext) != _WURZEL | {"sha256"}:
            raise ValueError("Kontextform")
        daten = {k: kontext[k] for k in _WURZEL}
        checksum = kontext["sha256"]
        if not _HEX.fullmatch(checksum):
            raise ValueError("Form oder Prüfsumme")
        moment = _zeit(daten["erfasst_am"])
        tag = date.fromisoformat(daten["stichtag"])
        if (
            type(daten["version"]) is not int or daten["version"] != VERSION
            or not _zahl(daten["hoechstzahl"], 0, TECHNISCHE_QUELLENGRENZE)
            or not _zahl(daten["textzeichen"], 0, TECHNISCHE_TEXTGRENZE)
            or not isinstance(daten["quellen"], list) or len(daten["quellen"]) > daten["hoechstzahl"]
        ):
            raise ValueError("Grenzen")
        gesehen = set()
        for q in daten["quellen"]:
            if (
                not isinstance(q, dict) or len(q) != len(_NORM) or set(q) != _NORM
                or not _zahl(q["norm_id"], 1, 2**63 - 1) or q["norm_id"] in gesehen
                or not KENNUNG.fullmatch(q["ris_id"]) or not GESETZESNUMMER.fullmatch(q["gesetzesnummer"])
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
                or d["quelle"] != f"https://ogd.ris.bka.gv.at/Dokumente/Bundesnormen/{q['ris_id']}/{q['ris_id']}.xml"
                or not _HEX.fullmatch(d["xml_sha256"]) or not isinstance(d["auszug"], str)
                or len(d["auszug"]) > daten["textzeichen"] or d["auszug_sha256"] != _text_hash(d["auszug"])
                or not _zahl(d["zeichen_gesamt"], len(d["auszug"]), 2**31 - 1)
                or type(d["gekuerzt"]) is not bool or d["gekuerzt"] != (len(d["auszug"]) < d["zeichen_gesamt"])
                or _zeit(d["erfasst_am"]) > moment
            ):
                raise ValueError("Dokumenttext")
        if not hmac.compare_digest(checksum, _hash(daten)):
            raise ValueError("Prüfsumme")
    except (AttributeError, KeyError, TypeError, ValueError, OverflowError, RecursionError) as fehler:
        raise QuellenkontextFehler("quellenkontext") from fehler
    return copy.deepcopy(daten)


def festhalten(norm_ids, *, hoechstzahl, textzeichen, jetzt=None):
    """Explizite Quellenliste einfrieren; keine stillen Ersatzquellen oder Kürzung der Liste."""
    moment = jetzt or timezone.now()
    if (
        not isinstance(moment, datetime) or timezone.is_naive(moment)
        or not _zahl(hoechstzahl, 0, TECHNISCHE_QUELLENGRENZE)
        or not _zahl(textzeichen, 0, TECHNISCHE_TEXTGRENZE)
        or not isinstance(norm_ids, (list, tuple)) or len(norm_ids) > hoechstzahl
        or any(not _zahl(i, 1, 2**63 - 1) for i in norm_ids) or len(set(norm_ids)) != len(norm_ids)
    ):
        raise QuellenkontextFehler("quellenauswahl")
    tag = timezone.localdate(moment)
    normen = list(Norm.objects.filter(
        pk__in=norm_ids, stand__lte=tag, importlauf__beendet_am__lte=moment, importlauf__erfolgreich=True,
    ).select_related("importlauf").order_by("ris_id", "stand", "pk"))
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
        d, dokument = texte.get(norm.pk), None
        if d is not None:
            if d["quelle"] != xml_adresse(norm.rohdaten, norm.ris_id):
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
    daten = {
        "version": VERSION, "erfasst_am": moment.astimezone(UTC).isoformat(), "stichtag": tag.isoformat(),
        "hoechstzahl": hoechstzahl, "textzeichen": textzeichen, "quellen": quellen,
    }
    ergebnis = {**daten, "sha256": _hash(daten)}
    pruefen(ergebnis)
    return ergebnis
