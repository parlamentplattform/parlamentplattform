"""Archiviert eine ausdrücklich ausgewählte Seite der Bundesnormen-Historie."""

from dataclasses import dataclass
from datetime import date
from urllib.parse import urlencode

from django.db import transaction
from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber

from faktenbasis.abrufschutz import einzelabruf
from faktenbasis.bestandsnachweis import bestandsgrenze
from faktenbasis.models import Norm, RisAenderungsseite
from faktenbasis.ris import (
    GESETZESNUMMER,
    RisFehler,
    dokumentadresse,
    json_dateibytes_abrufen,
    lokale_antwort,
    seite_pruefen,
    seitenkopf_pruefen,
)
from plattform_core.ris_historie import (
    NORM_REIHUNG,
    NORMABGLEICH_FASSUNG,
    PARSER_FASSUNG,
    TagesabgleichFehler,
    Tagesseite,
    dokumente,
    leere_trefferseite,
    tagesabgleich,
)
from verfahren.models import AuditEintrag

HISTORY_API = "https://data.bka.gv.at/ris/api/v2.6/History"
# Begrenzt die Zahl der SQL-Bindungen und die Tiefe der ODER-Ausdrücke.
_NORMBLOCK = 100


@dataclass(frozen=True)
class Leermeldung:
    original_sha256: str


def importieren(tag: date, seite: int, daten: bytes, *, erwartete_pruefsumme: str | None = None):
    antwort, pruefsumme = lokale_antwort(daten, erwartete_pruefsumme)
    ergebnisse, treffer = seitenkopf_pruefen(antwort, seite)
    return _archivieren(tag, seite, daten, pruefsumme, ergebnisse, treffer)


def _archivieren(tag, seite, daten, pruefsumme, ergebnisse, treffer):
    verweise = dokumente(ergebnisse.get("OgdDocumentReference"), tag, min(treffer - (seite - 1) * 10, 10))
    if verweise is None:
        raise RisFehler("ris_historie")
    referenzen = [
        {
            "dokumentnummer": verweis.dokumentnummer,
            "gesetzesnummer": verweis.gesetzesnummer,
            "quelle": dokumentadresse(verweis.quelle, verweis.dokumentnummer),
        }
        for verweis in verweise
    ]
    with transaction.atomic():
        stand, neu = RisAenderungsseite.objects.defer("original").get_or_create(
            original_sha256=pruefsumme,
            defaults={
                "tag": tag,
                "seite": seite,
                "treffer": treffer,
                "dokumente": referenzen,
                "original": daten,
                "parser_fassung": PARSER_FASSUNG,
            },
        )
        if neu:
            AuditEintrag.anhaengen({
                "typ": "ris_aenderungsseite", "beleg": stand.pk,
                "original_sha256": pruefsumme, "parser_fassung": PARSER_FASSUNG,
            })
    return stand


def abrufen(tag: date, seite: int, *, erwartete_pruefsumme: str | None = None) -> RisAenderungsseite | Leermeldung:
    """Ruft genau eine Seite ab und protokolliert belegte Leertreffer getrennt."""
    if type(tag) is not date:
        raise RisFehler("ris_historie")
    seite_pruefen(seite)
    datum = tag.isoformat()
    parameter = {
        "Anwendung": "Bundesnormen", "AenderungenVon": datum, "AenderungenBis": datum,
        "DokumenteProSeite": "Ten", "Seitennummer": str(seite),
    }
    url = HISTORY_API + "?" + urlencode(parameter)
    ereignis = {"typ": "ris_aenderungsseite_abruf", "tag": datum, "seite": seite, "quelle": url}
    with einzelabruf():
        try:
            daten = json_dateibytes_abrufen(url)
            antwort, pruefsumme = lokale_antwort(daten, erwartete_pruefsumme)
            ergebnisse, treffer = seitenkopf_pruefen(antwort, seite)
            if treffer == 0 and leere_trefferseite(antwort):
                AuditEintrag.anhaengen({
                    **ereignis, "erfolgreich": True, "treffer": 0, "original_sha256": pruefsumme,
                })
                return Leermeldung(pruefsumme)
            with transaction.atomic():
                stand = _archivieren(tag, seite, daten, pruefsumme, ergebnisse, treffer)
                AuditEintrag.anhaengen({**ereignis, "erfolgreich": True, "beleg": stand.pk})
        except RisFehler as fehler:
            AuditEintrag.anhaengen({**ereignis, "erfolgreich": False, "fehler": fehler.code})
            raise
    return stand


def tag_pruefen(tag: date, belege: list[int], *, mit_normbestand=False) -> dict:
    """Liest nur die gewählten lokalen Archivmetadaten."""
    if not belege or len(belege) > bestandsgrenze():
        raise TagesabgleichFehler("umfang")
    if any(type(n) is not int or not 1 <= n <= 2**63 - 1 for n in belege) or len(set(belege)) != len(belege):
        raise TagesabgleichFehler("auswahl")
    bestand = RisAenderungsseite.objects.only(
        "tag", "seite", "treffer", "original_sha256", "dokumente", "parser_fassung",
    ).in_bulk(belege)
    if len(bestand) != len(belege):
        raise TagesabgleichFehler("beleg_fehlt")
    seiten = []
    for s in bestand.values():
        if s.parser_fassung != PARSER_FASSUNG or not isinstance(s.dokumente, list) or len(s.dokumente) > 10:
            raise TagesabgleichFehler("beleg")
        nummern = tuple(d.get("dokumentnummer") if isinstance(d, dict) else None for d in s.dokumente)
        seiten.append(Tagesseite(s.pk, s.tag, s.seite, s.treffer, s.original_sha256, nummern))
    abgleich = tagesabgleich(tag, seiten)
    if mit_normbestand:
        abgleich["normabgleich"] = _tagesnormen(abgleich["seiten"], bestand)
    return abgleich


def _tagesnormen(seiten, bestand):
    verweise = [
        (seite["datensatz"], d["dokumentnummer"], d.get("gesetzesnummer"))
        for seite in seiten for d in bestand[seite["datensatz"]].dokumente
    ]
    if any(not isinstance(gesetz, str) or not GESETZESNUMMER.fullmatch(gesetz) for _, _, gesetz in verweise):
        raise TagesabgleichFehler("referenzen")
    schluessel = [(nummer, gesetz) for _, nummer, gesetz in verweise]
    normen = {}
    for beginn in range(0, len(schluessel), _NORMBLOCK):
        normen.update(_neueste_normen(schluessel[beginn:beginn + _NORMBLOCK]))
    dokumente = []
    for beleg, nummer, gesetz in verweise:
        norm = normen.get((nummer, gesetz))
        dokumente.append({
            "beleg": beleg, "dokumentnummer": nummer, "gesetzesnummer": gesetz,
            "normstand": {"datensatz": norm["pk"], "stichtag": norm["stand"].isoformat()} if norm else None,
        })
    return {"fassung": NORMABGLEICH_FASSUNG, "dokumente": dokumente}


def _neueste_normen(schluessel):
    bereiche = Q()
    for dokumentnummer, gesetzesnummer in schluessel:
        bereiche |= Q(ris_id=dokumentnummer, gesetzesnummer=gesetzesnummer)
    if not bereiche:
        return {}
    kandidaten = Norm.objects.filter(
        bereiche, ebene="Bund", bundesland="", importlauf__erfolgreich=True,
    ).annotate(rang=Window(
        RowNumber(), partition_by=[F("ris_id"), F("gesetzesnummer")], order_by=NORM_REIHUNG,
    )).filter(rang=1).order_by().values("pk", "ris_id", "gesetzesnummer", "stand")
    return {(norm["ris_id"], norm["gesetzesnummer"]): norm for norm in kandidaten}


def dokumente_mit_normstand(seite):
    """Finde in einer Abfrage höchstens einen lokalen Stand je archiviertem Verweis."""
    normen = _neueste_normen([(d["dokumentnummer"], d["gesetzesnummer"]) for d in seite.dokumente])
    return [
        {**verweis, "normstand": normen.get((verweis["dokumentnummer"], verweis["gesetzesnummer"]))}
        for verweis in seite.dokumente
    ]
