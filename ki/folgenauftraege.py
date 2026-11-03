"""Vorbereiteter eigener Rechtsfolgenauftrag; bisherige automatische Aufträge bleiben alt.

Einreihen benötigt ausdrücklich die vollständige Eingabegrenze. Noch kein Aufruf
aus einem Formular oder Verfahrensübergang. Kein weiterer automatischer Modelllauf.
"""

import logging

from django.db import transaction

from ki import folgenkontext
from ki.models import Auftragsstatus, KIAuftrag, Zweck

log = logging.getLogger(__name__)


def einreihen(antrag, mitglied, *, hoechstzeichen, vorschlagsfassung=None):
    if type(hoechstzeichen) is not int or not 1 <= hoechstzeichen <= 100000:
        raise ValueError("Rechtsfolgen benötigen einen ausdrücklichen vollständigen Eingaberahmen.")
    if vorschlagsfassung is not None:
        # Ein bereits beauftragter öffentlicher Vorschlag bleibt abrufbar, auch
        # wenn inzwischen eine andere Fassung eingereicht wurde. Nicht neu erfassen.
        vorhanden = KIAuftrag.objects.filter(
            zweck=Zweck.RECHTSFOLGEN, antrag_id=antrag.pk,
            quellenart="vorschlag", vorschlagsfassung_id=vorschlagsfassung.pk,
        ).first()
        if vorhanden is not None:
            return vorhanden
    text = folgenkontext.text_festhalten(antrag, vorschlagsfassung=vorschlagsfassung)
    identitaet = {"zweck": Zweck.RECHTSFOLGEN, "antrag_id": text["antrag"],
                  "quellenart": text["quellenart"], "fassung_nummer": text["fassung_nummer"]}
    vorhanden = KIAuftrag.objects.filter(**identitaet).first()
    if vorhanden is not None:
        return vorhanden
    defaults = {"kontext": text, "angefordert_von": mitglied, "vorschlagsfassung": vorschlagsfassung}
    try:
        with transaction.atomic():
            rahmen = folgenkontext.mit_grundlagen(text, hoechstzeichen=hoechstzeichen)
        defaults.update(folgenkontext=rahmen, quellenkontext=rahmen["quellen"])
    except Exception as fehler:
        # Ein Fehler oder zu langer vollständiger Kontext wird nie als Quellen-
        # leerstand umgedeutet oder durch einen älteren Prompt ersetzt.
        log.warning("Rechtsfolgengrundlagen für Antrag %s nicht erfassbar (%s)", text["antrag"], type(fehler).__name__)
        defaults.update(status=Auftragsstatus.GESCHEITERT, fehler="folgenkontext_erfassung")
    auftrag, _neu = KIAuftrag.objects.get_or_create(**identitaet, defaults=defaults)
    return auftrag


def rahmen_pruefen(auftrag):
    d = folgenkontext.pruefen(auftrag.folgenkontext)
    t = d["text"]
    if (auftrag.zweck != Zweck.RECHTSFOLGEN or t != auftrag.kontext
            or d["quellen"] != auftrag.quellenkontext or t["antrag"] != auftrag.antrag_id
            or t["quellenart"] != auftrag.quellenart or t["fassung_nummer"] != auftrag.fassung_nummer
            or auftrag.beanstandung_id is not None or auftrag.ursprung_id is not None or auftrag.korrekturkontext
            or (t["quellenart"] == "vorschlag" and t["fassung_id"] != auftrag.vorschlagsfassung_id)
            or (t["quellenart"] == "antrag" and auftrag.vorschlagsfassung_id is not None)):
        raise ValueError("Rechtsfolgenrahmen gehört nicht zu diesem Auftrag.")
    return d


def ausfuehren(auftrag):
    from ki.auftraege import auftrag_laden
    from ki.models import lauf_ausfuehren

    d = rahmen_pruefen(auftrag)
    prompt = auftrag_laden("rechtsfolgen", nummer=1)
    # Keine heutigen Quellen, keine erneute Textfassung und kein Kontobeifang.
    return lauf_ausfuehren(
        Zweck.RECHTSFOLGEN, prompt.text, folgenkontext.eingabe(auftrag.folgenkontext),
        auftrag.angefordert_von, antrag=auftrag.antrag, auftrag_version=prompt.version,
        kontext={"text": d["text"], "quellen": d["quellen"], "folgen": auftrag.folgenkontext,
                 "auftrag": auftrag.pk, "versuch": auftrag.versuche},
    )


def antwort_pruefen(lauf):
    """Nur bekannte ursprüngliche Eingabe, ohne heutige Daten oder Teilantwort."""
    from plattform_core.rechtsfolgen import pruefen

    k = lauf.kontext if isinstance(lauf.kontext, dict) else {}
    d = folgenkontext.pruefen(k.get("folgen"))
    if (lauf.zweck != Zweck.RECHTSFOLGEN or lauf.auftrag_version != folgenkontext.AUFTRAG
            or lauf.antrag_id != d["text"]["antrag"] or not lauf.erfolgreich
            or k.get("text") != d["text"] or k.get("quellen") != d["quellen"]
            or lauf.eingabe != folgenkontext.eingabe(k["folgen"])):
        raise ValueError("Kein eindeutig festgehaltener erfolgreicher Rechtsfolgenlauf.")
    return pruefen(lauf.antwort, **folgenkontext.antwortangebot(k["folgen"]))
