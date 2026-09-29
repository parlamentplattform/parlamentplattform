"""Die wiederkehrenden Läufe des Webdiensts — ohne bezahlten Cron-Dienst (D-J1a).

Seit 0.49 startet `gunicorn.conf.py` je Worker einen Hintergrundfaden für den Postausgang. Er
trägt jetzt auch den **Fristen-Wächter**: alle `DDOE_WAECHTER_MINUTEN` wertet ein Worker die
fälligen Fristen aller Verfahren aus (`verfahren_fortschreiben`) — Phasenübergänge, Beschluss-
fristen, Aussetzungen, Parametertests, Stufe 2 der Vertrauensfrage. Ohne ihn liefen Fristen nur
beim Seitenaufruf ab; ein Antrag, den niemand öffnete, wechselte Abstimmung und Ergebnis erst
rückwirkend, und die Anfechtungsfrist des § 7 Abs 10 lit h konnte verstreichen, bevor jemand das
Ergebnis sah (Bestandsaufnahme 28.9.2026, A2; Freigabe des Gründers für den Faden am selben Tag).

Zwei Worker laufen zugleich — die Zeile `Hintergrundlauf` ist die Sperre: Reserviert wird atomar
per UPDATE (wie beim Postauftrag), damit nie zwei Worker denselben Lauf zugleich ausführen. Jeder
Lauf ist idempotent und schreibt nur, was fällig ist; er tut nichts, was ein Seitenaufruf nicht
auch täte. Die Zeile hält außerdem fest, wann der Lauf zuletzt lief und was er tat (Rechenschaft).
Weitere Läufe (etwa die Warteschlange der Zukunftswerkstatt) hängen sich an `LAEUFE` an.
"""

from __future__ import annotations

import logging
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import timedelta

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from verfahren.models import Hintergrundlauf

log = logging.getLogger(__name__)

#: Wie lange eine Reservierung höchstens hält — geht ein Worker verloren, läuft sie ab.
SPERRE_MINUTEN = 15


@dataclass(frozen=True)
class Lauf:
    name: str
    takt_minuten: Callable[[], int]
    arbeit: Callable[[], dict]


def _fristen() -> dict:
    from verfahren.management.commands.verfahren_fortschreiben import alles_fortschreiben

    return alles_fortschreiben()


def _audit() -> dict:
    from verfahren.audit_pruefung import lauf

    return lauf()


#: Einmal am Tag: Die Prüfung der Audit-Kette ist Rechenschaft, keine Frist — ein Tag Verzug schadet
#: niemandem, und die Vollprüfung von vorn hat ihren eigenen Registerwert (audit-vollpruefung-tage).
AUDIT_TAKT_MINUTEN = 24 * 60


def _zukunftswerkstatt() -> dict:
    from ki.warteschlange import abarbeiten

    return abarbeiten()


LAEUFE: list[Lauf] = [
    Lauf("fristen", lambda: max(1, int(getattr(settings, "DDOE_WAECHTER_MINUTEN", 10))), _fristen),
    # Die Warteschlange der Zukunftswerkstatt (ki/warteschlange.py): jede Minute die fälligen
    # Aufträge im Tageskontingent — betroffene Gesetze, nachgezogene Textvektoren.
    Lauf("zukunftswerkstatt", lambda: 1, _zukunftswerkstatt),
    # Die Audit-Kette nachrechnen (Bestandsaufnahme A7): stückweise ab dem gemerkten Stand.
    Lauf("audit", lambda: AUDIT_TAKT_MINUTEN, _audit),
]


def ausfuehren(lauf: Lauf, jetzt=None) -> bool:
    """Einen Lauf ausführen, wenn er fällig ist und kein anderer Worker ihn hält.

    Rückgabe: True, wenn dieser Aufruf den Lauf ausgeführt hat."""
    jetzt = jetzt or timezone.now()
    Hintergrundlauf.objects.get_or_create(name=lauf.name)
    faellig_ab = jetzt - timedelta(minutes=lauf.takt_minuten())
    token = secrets.token_hex(16)
    frei = Q(gesperrt_bis__isnull=True) | Q(gesperrt_bis__lte=jetzt)
    faellig = Q(zuletzt_begonnen__isnull=True) | Q(zuletzt_begonnen__lte=faellig_ab)
    reserviert = Hintergrundlauf.objects.filter(name=lauf.name).filter(frei, faellig).update(
        sperrcode=token,
        gesperrt_bis=jetzt + timedelta(minutes=SPERRE_MINUTEN),
        zuletzt_begonnen=jetzt,
        fehler="",
    )
    if not reserviert:
        return False
    stand: dict = {}
    fehler = ""
    try:
        stand = lauf.arbeit() or {}
    except Exception as ausnahme:  # der Faden darf nie sterben; der Fehler steht in der Zeile und im Log
        fehler = f"{type(ausnahme).__name__}: {ausnahme}"[:300]
        log.exception("Hintergrundlauf %s gescheitert", lauf.name)
    finally:
        felder = {"sperrcode": "", "gesperrt_bis": None, "zuletzt_beendet": timezone.now(), "fehler": fehler}
        if not fehler:
            # Ein gescheiterter Lauf lässt den letzten Stand stehen — sonst vergäße etwa die Prüfung der
            # Audit-Kette einen gemeldeten Bruch, weil die Datenbank kurz weg war (Prüfung 0.52.0).
            felder["zuletzt_stand"] = stand
        Hintergrundlauf.objects.filter(name=lauf.name, sperrcode=token).update(**felder)
    return True


def faellige_ausfuehren(jetzt=None) -> list[str]:
    """Alle fälligen Läufe — der Einstieg für den Faden in gunicorn.conf.py. Gibt die Namen der
    ausgeführten Läufe zurück."""
    ausgefuehrt = []
    for lauf in LAEUFE:
        try:
            if ausfuehren(lauf, jetzt):
                ausgefuehrt.append(lauf.name)
        except Exception:  # z. B. Datenbank kurz nicht erreichbar — nächster Takt
            log.exception("Hintergrundlauf %s konnte nicht reserviert werden", lauf.name)
    return ausgefuehrt
