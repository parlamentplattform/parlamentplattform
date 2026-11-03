"""Vorhandene amtliche Schnappschüsse auswählen; kein Abruf und kein Schreibrecht."""

from django.db.models import Count, OuterRef, Q, Subquery, Window
from django.db.models.functions import Substr
from django.utils import timezone

from faktenbasis.kontext import festhalten
from faktenbasis.models import Norm
from plattform_core.quellenauswahl import METADATENZEICHEN, auswaehlen
from plattform_core.quellenumfang import BUNDESLAENDER


def erfassen(textkontext, *, jetzt=None):
    from ki.kontext import pruefen
    from parameter.models import zahl

    text = pruefen(textkontext)
    moment = jetzt or timezone.now()
    tag = timezone.localdate(moment, timezone.get_default_timezone())
    hoechstzahl = max(0, min(20, zahl("quellenkontext-hoechstzahl", 3)))
    textzeichen = max(0, min(20_000, zahl("quellenkontext-textzeichen", 1200)))
    wortlaenge = max(2, min(12, zahl("quellenkontext-mindestwortlaenge", 3)))
    grenze = max(1, min(2000, zahl("quellenkontext-bestandsgrenze", 500)))
    verfuegbar = Norm.objects.filter(
        stand__lte=tag, importlauf__erfolgreich=True, importlauf__beendet_am__lte=moment,
    ).filter(Q(ebene="Bund", bundesland="") | Q(ebene="Land", bundesland__in=list(BUNDESLAENDER.values())))
    neueste = verfuegbar.filter(ris_id=OuterRef("ris_id")).order_by("-stand", "-pk").values("pk")[:1]
    # Anzahl und begrenzte ID-Liste stammen aus derselben SQL-Sicht. Kein alter
    # Titel kann die neuere Fassung derselben amtlichen Kennung verdrängen.
    pool = list(verfuegbar.filter(pk=Subquery(neueste)).order_by("ris_id", "pk").annotate(
        anzahl=Window(Count("pk")), kurz=Substr("kurztitel", 1, METADATENZEICHEN),
        lang=Substr("titel", 1, METADATENZEICHEN), teil=Substr("abschnitt", 1, METADATENZEICHEN),
    ).values("pk", "ris_id", "kurz", "lang", "teil", "anzahl")[:grenze])
    auswahl = auswaehlen(
        "\n".join(text[k] for k in ("titel", "wortlaut", "begruendung")),
        [(q["pk"], q["ris_id"], "\n".join((q["kurz"], q["lang"], q["teil"]))) for q in pool],
        hoechstzahl=hoechstzahl, mindestlaenge=wortlaenge,
    )
    gesamt = pool[0]["anzahl"] if pool else 0
    auswahl.update(
        bestand_ids=[q["pk"] for q in pool], bestand_gesamt=gesamt, bestandsgrenze=grenze,
        bestand_begrenzt=gesamt > len(pool), metadatenzeichen=METADATENZEICHEN,
    )
    return festhalten(
        auswahl["ausgewaehlt"], hoechstzahl=hoechstzahl, textzeichen=textzeichen, jetzt=moment, auswahl=auswahl,
        text_sha256=textkontext["sha256"],
    )
