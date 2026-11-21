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


def _adresswechsel() -> dict:
    from mitglieder.models import Adresswechsel

    return {"wirksam": Adresswechsel.faellige_anwenden()}


def _drossel() -> dict:
    """Die Datenschutzerklärung sagt: Die Verbindungsadresse hält die Drossel „rund zwei Stunden“.
    Bisher räumte nur ein neuer Zähler im Vorbeigehen auf (mitglieder/botschutz.py) — ohne neuen
    Verkehr blieb die Adresse liegen (GP-159). Dieselbe Grenze wie dort: laufende und vorige Stunde."""
    import time

    from mitglieder.botschutz import TAGESZWECKE
    from mitglieder.models import Drosselzaehler

    stunde = int(time.time() // 3600)
    # Tageszähler je Konto (ein Kontoabruf je Tag) tragen die Stunde des Tagesbeginns und bleiben zwei
    # Tage — sonst wäre die Tagesgrenze nach zwei Stunden wieder frei (wie in botschutz.drossel_zuviel).
    geloescht, _ = (
        Drosselzaehler.objects.filter(stunde__lt=stunde - 1)
        .exclude(zweck__in=TAGESZWECKE, stunde__gte=stunde - 48)
        .delete()
    )
    return {"geloescht": geloescht}


def _zukunftswerkstatt() -> dict:
    from ki.warteschlange import abarbeiten

    return abarbeiten()


LAEUFE: list[Lauf] = [
    Lauf("fristen", lambda: max(1, int(getattr(settings, "DDOE_WAECHTER_MINUTEN", 10))), _fristen),
    # Die Warteschlange der Zukunftswerkstatt (ki/warteschlange.py): jede Minute die fälligen
    # Aufträge im Tageskontingent — betroffene Gesetze, nachgezogene Textvektoren.
    Lauf("zukunftswerkstatt", lambda: 1, _zukunftswerkstatt),
    # Bestätigte Adresswechsel nach Ablauf der Einspruchsfrist wirksam machen (GP-211) — bisher nur
    # beiläufig beim Öffnen einer Verwaltungsseite oder beim Anfordern eines Anmeldelinks.
    Lauf("adresswechsel", lambda: max(1, int(getattr(settings, "DDOE_WAECHTER_MINUTEN", 10))), _adresswechsel),
    Lauf("drossel", lambda: max(1, int(getattr(settings, "DDOE_WAECHTER_MINUTEN", 10))), _drossel),
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


#: Ab wie vielen Takten ohne neuen Beginn ein Lauf als überfällig gilt (GP-155): Ein Takt kann sich um
#: einen Neustart oder Deploy verschieben, drei Takte in Folge nicht. Registerwert folgt.
UEBERFAELLIG_TAKTE = 3


def betriebsstand(name: str, jetzt=None) -> dict:
    """Der Stand eines Laufs für die Maschinenadresse (GP-155) — ohne Fehlertext und ohne Inhalte.

    `status` ist „ok“, „noch_nicht_gelaufen“, „ueberfaellig“ (der letzte Beginn liegt mehr als
    `UEBERFAELLIG_TAKTE` Takte zurück: der Faden steht oder ein Lauf hängt) oder „fehler“ (der Lauf brach
    ab, oder einzelne Verfahren scheiterten — `fehler` zählt sie, wie der Lauf sie in seinem Stand
    zählt). Zeilen von früheren Fassungen ohne Fehlerzähler gelten als fehlerfrei."""
    jetzt = jetzt or timezone.now()
    lauf = next(lauf for lauf in LAEUFE if lauf.name == name)
    takt = lauf.takt_minuten()
    zeile = Hintergrundlauf.objects.filter(name=name).first()
    begonnen = zeile.zuletzt_begonnen if zeile else None
    beendet = zeile.zuletzt_beendet if zeile else None
    stand = zeile.zuletzt_stand if zeile and isinstance(zeile.zuletzt_stand, dict) else {}
    zahl = stand.get("fehler")
    fehler = zahl if isinstance(zahl, int) and not isinstance(zahl, bool) and zahl > 0 else 0
    abgebrochen = bool(zeile and zeile.fehler)
    ueberfaellig = begonnen is not None and jetzt - begonnen > timedelta(minutes=UEBERFAELLIG_TAKTE * takt)
    if begonnen is None:
        status = "noch_nicht_gelaufen"
    elif ueberfaellig:
        status = "ueberfaellig"
    elif fehler or abgebrochen:
        status = "fehler"
    else:
        status = "ok"
    return {
        "lauf": name,
        "status": status,
        "takt_minuten": takt,
        "zuletzt_begonnen": begonnen.isoformat() if begonnen else None,
        "zuletzt_beendet": beendet.isoformat() if beendet else None,
        "ueberfaellig": ueberfaellig,
        "fehler": fehler,
        "abgebrochen": abgebrochen,
    }


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
