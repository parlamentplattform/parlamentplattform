"""Signierter Prüfstand und ausdrückliche Wahl beim Einbringen. Keine Entscheidung durch Ähnlichkeit."""

import hashlib
import json

from django.core import signing
from django.db import transaction
from django.utils import timezone

from plattform_core import Phase
from verfahren.aehnlichkeit import Ergebnis
from verfahren.models import Antrag, Antragsart, AuditEintrag, Eigenstaendigkeit

SALT = "verfahren.einbringwahl.v1"


def _fingerabdruck(daten):
    # Native Formulare und htmx kodieren Textarea-Zeilenenden unterschiedlich.
    daten = {k: v.replace("\r\n", "\n").replace("\r", "\n") if isinstance(v, str) else v for k, v in daten.items()}
    return hashlib.sha256(json.dumps(daten, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def pruefstand_fuer(daten, mitglied, pruefung):
    stand = {
        "konto": mitglied.pk,
        "text": _fingerabdruck(daten),
        "modell": pruefung.bedeutungsmodell,
        "treffer": [
            {
                "id": t["antrag"].pk,
                "titel": t["antrag"].titel,
                "fassung": max((f.nummer for f in t["antrag"].fassungen.all()), default=1),
                "wort": t["prozent"],
                "bedeutung": t["bedeutung_prozent"],
            }
            for t in pruefung.treffer
        ],
    }
    return signing.dumps(stand, salt=SALT, compress=True)


def pruefstand_lesen(token, daten, mitglied):
    try:
        stand = signing.loads(token, salt=SALT)
    except (signing.BadSignature, ValueError, TypeError):
        return None
    if not isinstance(stand, dict) or stand.get("konto") != mitglied.pk or stand.get("text") != _fingerabdruck(daten):
        return None
    return stand


def pruefung_aus_stand(stand):
    """Die angebotene Liste erhalten, ohne einen zweiten Modellaufruf beim Wählen."""
    ergebnis = Ergebnis(bedeutungsmodell=stand["modell"])
    antraege = Antrag.objects.in_bulk(t["id"] for t in stand["treffer"])
    for t in stand["treffer"]:
        antrag = antraege.get(t["id"])
        if antrag is not None:
            ergebnis.treffer.append({
                "antrag": antrag,
                "prozent": t["wort"],
                "bedeutung_prozent": t["bedeutung"],
                "beteiligung": antrag.unterstuetzungen.filter(
                    zurueckgezogen_am__isnull=True, mitglied__testkonto=False,
                ).count(),
                "normen": [],
            })
    return ergebnis


@transaction.atomic
def einstufung_festhalten(antrag, stand):
    if not stand or not stand["treffer"]:
        return
    Eigenstaendigkeit.objects.bulk_create([
        Eigenstaendigkeit(
            antrag=antrag, gegenueber_id=t["id"], titel=t["titel"], fassung_nummer=t["fassung"],
        )
        for t in stand["treffer"]
    ])
    AuditEintrag.anhaengen({
        "typ": "eigenstaendigkeit_erklaert", "antrag": antrag.pk,
        "gegenueber": [t["id"] for t in stand["treffer"]],
    })


def einstufungen(antrag):
    return [
        {"antrag": v.gegenueber_id, "titel": v.titel, "fassung": v.fassung_nummer, "erklaert_am": v.erklaert_am.isoformat()}
        for v in antrag.eigenstaendigkeitsvermerke.all()
    ]


@transaction.atomic
def direkt_unterstuetzen(mitglied, antrag_id):
    """Explizites Unterstützen eines Sachantrags; wiederholte Aufrufe nehmen nichts zurück."""
    from verfahren.hinweise import mitwirkungssperre

    if mitwirkungssperre(mitglied):
        return None
    antrag = Antrag.objects.select_for_update().filter(pk=antrag_id, art=Antragsart.SACHE).first()
    if antrag is None:
        return None
    antrag.fortschreiben()
    if antrag.phase != Phase.UNTERSTUETZUNG.value:
        return None
    eintrag, neu = antrag.unterstuetzungen.get_or_create(mitglied=mitglied)
    if neu or eintrag.zurueckgezogen_am is not None:
        if not neu:
            eintrag.zurueckgezogen_am = None
            eintrag.erklaert_am = timezone.now()
            eintrag.save(update_fields=["zurueckgezogen_am", "erklaert_am"])
        AuditEintrag.anhaengen({"typ": "unterstuetzung", "antrag": antrag.pk})
        antrag.fortschreiben()
    return antrag
