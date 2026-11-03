"""Heutigen lokalen Bestand neben den unveränderten damaligen Quellenrahmen stellen."""

from dataclasses import asdict
from datetime import date, datetime

from django.db.models import F, Q, Window
from django.db.models.functions import RowNumber
from django.utils import timezone

from faktenbasis.kontext import QuellenkontextFehler, pruefen
from faktenbasis.models import Norm, NormText
from plattform_core.quellenfortschritt import VERSION, Quelle, vergleichen


def _quelle(q):
    d = q["dokumenttext"]
    return Quelle(q["ris_id"], q["norm_id"], date.fromisoformat(q["stand"]), q["metadaten_sha256"],
                  datetime.fromisoformat(q["importiert_am"]),
                  d["id"] if d else None, d["xml_sha256"] if d else None,
                  d["parser_fassung"] if d else None, datetime.fromisoformat(d["erfasst_am"]) if d else None)


def abgleichen(roh, *, text_sha256=None, jetzt=None):
    """Höchstens zwei gebündelte Abfragen, niemals eine Abfrage je Quelle.

    Nur der aktuelle Block ruft dies auf. Die historische Nachlese und der
    Modelleingang bleiben unverändert. Texte können unabhängig von einer
    späteren Metadatenübernahme beim gleichen RIS-Dokument erfasst worden sein.
    """
    moment = jetzt or timezone.now()
    if timezone.is_naive(moment):
        raise ValueError("Vergleichszeit ohne Zeitzone")
    basis = {"fassung": VERSION, "ermittelt_am": moment.isoformat(), "ausgangs_sha256": None,
             "quellen": [], "gegenuebergestellte_quellen": [],
             "spaetere_staende": False, "vollstaendig_vergleichbar": False}
    if not roh:
        return {**basis, "zustand": "alt"}
    try:
        daten = pruefen(roh)
        if text_sha256 is not None and daten["text_sha256"] != text_sha256:
            raise QuellenkontextFehler("textzuordnung")
        aufnahme = datetime.fromisoformat(daten["erfasst_am"])
        if moment < aufnahme:
            raise ValueError("Vergleich vor Erfassung")
        alt = [_quelle(q) for q in daten["quellen"]]
    except (QuellenkontextFehler, TypeError, ValueError, KeyError):
        return {**basis, "zustand": "fehler"}
    basis["ausgangs_sha256"] = roh["sha256"]
    if not alt:
        return {**basis, "zustand": "leer"}
    tag = timezone.localdate(moment, timezone.get_default_timezone())
    kennungen = [q.kennung for q in alt]
    if len(set(kennungen)) != len(kennungen):
        return {**basis, "zustand": "fehler"}
    normen = list(Norm.objects.filter(
        ris_id__in=kennungen, stand__lte=tag,
        importlauf__beendet_am__lte=moment, importlauf__erfolgreich=True,
    ).annotate(rang=Window(RowNumber(), partition_by=[F("ris_id")], order_by=[F("stand").desc(), F("pk").desc()]))
      .filter(rang=1).values("pk", "ris_id", "stand", "inhalt_hash", "importlauf__beendet_am"))
    # Ein späterer Text zum ursprünglich verwendeten Metadatenstand darf durch
    # einen inzwischen zusätzlich importierten Metadatenstand nicht verschwinden.
    bereiche = Q()
    for q in alt:
        bereiche |= Q(norm__ris_id=q.kennung, norm__stand__gte=q.stand)
    texte = {d["norm__ris_id"]: d for d in NormText.objects.filter(
        bereiche, norm__stand__lte=tag, norm__importlauf__beendet_am__lte=moment,
        norm__importlauf__erfolgreich=True, erfasst_am__lte=moment,
    ).annotate(rang=Window(RowNumber(), partition_by=[F("norm__ris_id")],
                          order_by=[F("erfasst_am").desc(), F("pk").desc()]))
        .filter(rang=1).values("pk", "norm_id", "norm__ris_id", "xml_hash", "parser_fassung", "erfasst_am")}
    try:
        neu = []
        for n in normen:
            d = texte.get(n["ris_id"])
            neu.append(Quelle(n["ris_id"], n["pk"], n["stand"], n["inhalt_hash"], n["importlauf__beendet_am"],
                              d["pk"] if d else None, d["xml_hash"] if d else None,
                              d["parser_fassung"] if d else None, d["erfasst_am"] if d else None))
        befunde = vergleichen(alt, neu, aufnahme=aufnahme, jetzt=moment)
    except (TypeError, ValueError):
        return {**basis, "zustand": "fehler"}
    gegenueber = []
    for q in sorted(neu, key=lambda quelle: quelle.kennung):
        angaben = asdict(q)
        for feld in ("stand", "importiert", "text_erfasst"):
            angaben[feld] = angaben[feld].isoformat() if angaben[feld] is not None else None
        angaben["text_norm_id"] = texte[q.kennung]["norm_id"] if q.text_id is not None else None
        gegenueber.append(angaben)
    return {**basis, "zustand": "verglichen", "quellen": [asdict(b) for b in befunde],
            "gegenuebergestellte_quellen": gegenueber,
            "spaetere_staende": any(b.metadaten_spaeter or b.dokument_spaeter for b in befunde),
            "vollstaendig_vergleichbar": all(b.vergleichbar for b in befunde)}
