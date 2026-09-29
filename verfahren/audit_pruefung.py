"""Die Audit-Kette nachrechnen (Bestandsaufnahme A7, Schritt 2 · 0.52.0).

Die Kette wurde seit dem Fundament geschrieben, aber nirgends geprüft. Hier wird sie nachgerechnet —
täglich als Hintergrundlauf „audit“ (verfahren/hintergrund.py), jederzeit mit `manage.py audit_pruefen`.

Stückweise: Der Lauf merkt sich in `Hintergrundlauf.zuletzt_stand` die laufende Nummer und den Hash des
letzten geprüften Eintrags und rechnet beim nächsten Mal nur die neuen nach. Dass der gemerkte Eintrag
selbst unverändert ist, prüft jeder Lauf mit (Anker). Alle `audit-vollpruefung-tage` Tage rechnet er
die ganze Kette von vorn — sonst fiele eine Änderung an einem alten Eintrag vor dem Anker nie auf.

Die Rechnung selbst steht in `plattform_core.hashchain.kette_nachrechnen`; hier wird nur gelesen."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

from django.utils import timezone

from plattform_core.hashchain import GENESIS, ereignis_hash, kette_nachrechnen
from verfahren.models import AuditEintrag, Hintergrundlauf

log = logging.getLogger(__name__)

#: Name der Zeile in `Hintergrundlauf` — dort steht der zuletzt geprüfte Stand.
LAUF = "audit"
#: Rückfallwert; der gültige steht im Register unter „audit-vollpruefung-tage“ (FB-J2).
VOLLPRUEFUNG_TAGE = 7


def vollpruefung_tage() -> int:
    from parameter.models import zahl

    return max(1, zahl("audit-vollpruefung-tage", VOLLPRUEFUNG_TAGE))


def gemerkter_stand() -> dict:
    """Der Stand des letzten Laufs — leer, solange nie geprüft wurde."""
    zeile = Hintergrundlauf.objects.filter(name=LAUF).only("zuletzt_stand").first()
    return dict(zeile.zuletzt_stand or {}) if zeile else {}


def _zeilen(ab_nummer: int | None):
    eintraege = AuditEintrag.objects.order_by("lfd")
    if ab_nummer is not None:
        eintraege = eintraege.filter(lfd__gt=ab_nummer)
    return eintraege.values_list("lfd", "ereignis", "vorgaenger", "hash").iterator(chunk_size=2000)


def _faellig_voll(stand: dict, jetzt) -> bool:
    letzte = stand.get("letzte_volle")
    if not letzte or stand.get("geprueft_bis") is None:
        return True
    try:
        return jetzt - datetime.fromisoformat(letzte) >= timedelta(days=vollpruefung_tage())
    except (TypeError, ValueError):
        return True


def _anker_stimmt(nummer: int, kopf: str) -> bool:
    """Der zuletzt geprüfte Eintrag ist noch da und ergibt noch denselben Hash."""
    zeile = AuditEintrag.objects.filter(lfd=nummer).values_list("ereignis", "vorgaenger", "hash").first()
    if zeile is None:
        return False
    ereignis, vorgaenger, gespeichert = zeile
    return gespeichert == kopf and ereignis_hash(vorgaenger, ereignis) == kopf


def pruefen(voll: bool = False, stand: dict | None = None, jetzt=None) -> dict:
    """Rechnet die Kette nach und gibt den neuen Stand zurück (JSON-fähig, ohne Personenbezug).

    `stand` ist der des letzten Laufs; ohne ihn, mit `voll` oder wenn die Vollprüfung fällig ist, wird
    von vorn gerechnet. Bei einem Bruch bleibt der Anker am letzten stimmigen Eintrag — der nächste Lauf
    findet den Bruch wieder, bis ihn jemand erklärt hat."""
    jetzt = jetzt or timezone.now()
    stand = dict(stand or {})
    voll = voll or _faellig_voll(stand, jetzt)
    if voll:
        befund = kette_nachrechnen(_zeilen(None))
        letzte_volle = jetzt.isoformat()
    else:
        nummer, kopf = int(stand["geprueft_bis"]), str(stand["kopf"])
        letzte_volle = stand.get("letzte_volle")
        if nummer and not _anker_stimmt(nummer, kopf):
            befund = None
            ergebnis = {"intakt": False, "bruch": nummer, "grund": "anker", "geprueft": 0,
                        "geprueft_bis": nummer, "kopf": kopf}
        else:
            befund = kette_nachrechnen(_zeilen(nummer), start_hash=kopf if nummer else GENESIS, start_nummer=nummer)
    if befund is not None:
        ergebnis = {
            "intakt": befund.intakt,
            "bruch": befund.bruch,
            "grund": befund.grund,
            "geprueft": befund.geprueft,
            "geprueft_bis": befund.letzte_nummer or 0,
            "kopf": befund.kopf,
        }
    ergebnis.update(
        voll=voll,
        eintraege=AuditEintrag.objects.count(),
        geprueft_am=jetzt.isoformat(),
        letzte_volle=letzte_volle,
    )
    if not ergebnis["intakt"]:
        log.error("Audit-Kette gebrochen bei Eintrag %s (%s)", ergebnis["bruch"], ergebnis["grund"])
    return ergebnis


def lauf() -> dict:
    """Der tägliche Hintergrundlauf: ab dem gemerkten Stand weiter."""
    return pruefen(stand=gemerkter_stand())
