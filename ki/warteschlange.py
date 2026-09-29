"""Die Warteschlange der Zukunftswerkstatt (FB-H1, FB-H6): einreihen, abarbeiten, Rechenschaft.

Was beim Einbringen nicht in der Anfrage selbst gerechnet werden soll, wird hier eingereiht:
die betroffenen Gesetze (`rechtsbezug`) und — nach „Trotzdem einbringen“ — der Textvektor des
neuen Antrags (`aehnlichkeit`). Der Hintergrundlauf „zukunftswerkstatt“ (`verfahren/hintergrund.py`,
Takt eine Minute) ruft `abarbeiten`:

- **Tageskontingent** „ki-tageslaeufe“: mehr Aufrufe beim Anbieter macht ein Kalendertag nicht
  (jeder Versuch zählt); der Rest wartet.
- **Atomare Reservierung** wie beim Postauftrag: ein UPDATE mit Sperrcode, damit zwei Worker nie
  denselben Auftrag zugleich rechnen; eine verlorene Reservierung läuft nach SPERRE_MINUTEN ab.
- **Rückzug bei Fehlern**: 2, 4, 8, 16, 32 Minuten; nach dem sechsten Fehlschlag (HOECHSTVERSUCHE)
  gilt der Auftrag als gescheitert (Stempel, nicht gelöscht).

Das Ergebnis bleibt im `KILauf` (Archiv); der Auftrag verweist darauf. Nichts hier entscheidet,
reiht oder blockiert ein Verfahren — die Werkstatt schlägt vor (Grundregel 5, § 2 Abs 6)."""

from __future__ import annotations

import logging
import secrets
from datetime import timedelta

from django.db.models import F, Q
from django.utils import timezone

from ki.anbieter import SteckplatzStumm, anbieter_waehlen
from ki.models import Auftragsstatus, KIAuftrag, KILauf, Zweck, einbettung_ausfuehren, lauf_ausfuehren

log = logging.getLogger(__name__)

SPERRE_MINUTEN = 15
HOECHSTVERSUCHE = 6
TAGESLAEUFE_STANDARD = 20
#: Zwecke, die die Warteschlange kennt — jeder mit seiner Arbeit.
ZWECKE = (Zweck.RECHTSBEZUG, Zweck.AEHNLICHKEIT)


def tageskontingent() -> int:
    from parameter.models import zahl

    return max(0, zahl("ki-tageslaeufe", TAGESLAEUFE_STANDARD))


def heute_gestartet(jetzt=None) -> int:
    """Wie viele Aufrufe beim Anbieter die Warteschlange an diesem Kalendertag (Wiener Zeit) schon
    gemacht hat — jeder Versuch zählt, auch ein gescheiterter (Entscheidung des Gründers 29.9.2026;
    bis dahin zählte ein Auftrag einmal, gleich wie oft er es versuchte). Jeder Aufruf steht als
    `KILauf` im Archiv: die betroffenen Gesetze und die Textvektoren eines Antrags. Der
    Bedeutungsvergleich beim Einbringen (Lauf ohne Antrag, eigene Drossel je Konto) gehört nicht
    zur Warteschlange und zählt nicht mit."""
    heute = timezone.localdate(jetzt or timezone.now())
    return (
        KILauf.objects.filter(erstellt_am__date=heute)
        .filter(Q(zweck=Zweck.RECHTSBEZUG) | Q(zweck=Zweck.AEHNLICHKEIT, antrag__isnull=False))
        .count()
    )


def einreihen(zweck: str, antrag, mitglied) -> KIAuftrag:
    """Idempotent je Antrag, Zweck und Fassung: Wer zweimal einreiht, bekommt denselben Auftrag."""
    if zweck not in ZWECKE:
        raise ValueError(f"Unbekannter Zweck für die Warteschlange: {zweck}")
    fassung = antrag.aktueller_text()
    auftrag, _neu = KIAuftrag.objects.get_or_create(
        zweck=zweck,
        antrag=antrag,
        fassung_nummer=fassung.nummer if fassung else 1,
        defaults={"angefordert_von": mitglied},
    )
    return auftrag


def platz_in_der_schlange(auftrag) -> int | None:
    """1 = als Nächstes dran. None, wenn der Auftrag nicht (mehr) wartet."""
    if auftrag is None or auftrag.status not in (Auftragsstatus.GEPLANT, Auftragsstatus.LAEUFT):
        return None
    return (
        KIAuftrag.objects.filter(status__in=(Auftragsstatus.GEPLANT, Auftragsstatus.LAEUFT), pk__lte=auftrag.pk).count()
    )


def _arbeit_rechtsbezug(auftrag: KIAuftrag) -> KILauf:
    from ki.auftraege import auftrag_laden
    from ki.rechtsbezug import antrag_eingabe

    text = auftrag_laden("rechtsbezug")
    lauf = lauf_ausfuehren(
        Zweck.RECHTSBEZUG,
        text.text,
        antrag_eingabe(auftrag.antrag, auftrag.fassung_nummer),
        auftrag.angefordert_von,
        antrag=auftrag.antrag,
        auftrag_version=text.version,
    )
    # Der Antragsteller bekommt Post, sobald das Ergebnis da ist — nur mit Einwilligung, über den
    # Postausgang (einmal je Antrag; der Brief liest den jüngsten Lauf beim Zustellen).
    from mitglieder.postausgang import beauftragen

    beauftragen(auftrag.antrag.eingebracht_von, "rechtsbezug", antrag=auftrag.antrag)
    return lauf


def _arbeit_aehnlichkeit(auftrag: KIAuftrag) -> KILauf:
    from verfahren.aehnlichkeit import antragstext, einbettung_speichern

    antrag = auftrag.antrag
    lauf, einbettung = einbettung_ausfuehren(
        [antragstext(antrag, auftrag.fassung_nummer)], auftrag.angefordert_von, antrag=antrag
    )
    einbettung_speichern(antrag, auftrag.fassung_nummer, einbettung.modell, einbettung.vektoren[0])
    return lauf


ARBEIT = {Zweck.RECHTSBEZUG: _arbeit_rechtsbezug, Zweck.AEHNLICHKEIT: _arbeit_aehnlichkeit}


def _reservieren(pk: int, jetzt) -> str | None:
    token = secrets.token_hex(16)
    frei = Q(gesperrt_bis__isnull=True) | Q(gesperrt_bis__lte=jetzt)
    faellig = Q(naechster_versuch__isnull=True) | Q(naechster_versuch__lte=jetzt)
    reserviert = (
        KIAuftrag.objects.filter(pk=pk, status__in=(Auftragsstatus.GEPLANT, Auftragsstatus.LAEUFT))
        .filter(frei, faellig)
        .update(
            status=Auftragsstatus.LAEUFT,
            sperrcode=token,
            gesperrt_bis=jetzt + timedelta(minutes=SPERRE_MINUTEN),
            zuletzt_versucht_am=jetzt,
            versuche=F("versuche") + 1,
        )
    )
    return token if reserviert else None


def auftrag_ausfuehren(pk: int, jetzt=None) -> str:
    """Einen Auftrag rechnen: „erledigt“, „verschoben“ (nächster Versuch später), „gescheitert“ —
    oder „uebersprungen“, wenn ein anderer Worker ihn hält oder er nicht fällig ist."""
    jetzt = jetzt or timezone.now()
    token = _reservieren(pk, jetzt)
    if token is None:
        return "uebersprungen"
    auftrag = KIAuftrag.objects.select_related("antrag", "angefordert_von").get(pk=pk)
    stand: dict = {"sperrcode": "", "gesperrt_bis": None}
    ausgang = "erledigt"
    try:
        lauf = ARBEIT[Zweck(auftrag.zweck)](auftrag)
        stand.update(status=Auftragsstatus.ERLEDIGT, lauf=lauf, erledigt_am=jetzt, fehler="", naechster_versuch=None)
    except Exception as fehler:  # der Faden darf nie sterben; der Grund steht am Auftrag
        if not isinstance(fehler, SteckplatzStumm):  # ein stummer Steckplatz ist kein Programmfehler
            log.exception("KI-Auftrag %s gescheitert", pk)
        letzter = KILauf.objects.filter(antrag=auftrag.antrag, zweck=auftrag.zweck).order_by("-erstellt_am").first()
        stand.update(fehler=f"{type(fehler).__name__}: {fehler}"[:300], lauf=letzter)
        if auftrag.versuche >= HOECHSTVERSUCHE:
            stand.update(status=Auftragsstatus.GESCHEITERT, naechster_versuch=None)
            ausgang = "gescheitert"
        else:
            stand.update(
                status=Auftragsstatus.GEPLANT,
                naechster_versuch=jetzt + timedelta(minutes=2 ** auftrag.versuche),
            )
            ausgang = "verschoben"
    finally:
        KIAuftrag.objects.filter(pk=pk, sperrcode=token).update(**stand)
    return ausgang


def abarbeiten(jetzt=None) -> dict:
    """Die fälligen Aufträge im Rahmen des Tageskontingents rechnen — der Einstieg für den
    Hintergrundlauf. Ohne Anbieter wird nichts reserviert: Die Aufträge warten, bis einer angeschlossen ist."""
    jetzt = jetzt or timezone.now()
    ergebnis = {"erledigt": 0, "verschoben": 0, "gescheitert": 0, "uebersprungen": 0}
    if anbieter_waehlen() is None:
        return {**ergebnis, "anbieter": False, "offen": offene_anzahl()}
    if KILauf.monatsverbrauch(jetzt) >= KILauf.monatsbudget():
        # Kein Versuch, der zählt: Die Aufträge warten still, bis der Monat wechselt.
        return {**ergebnis, "anbieter": True, "budget_erschoepft": True, "offen": offene_anzahl()}
    rest = tageskontingent() - heute_gestartet(jetzt)
    if rest <= 0:
        return {**ergebnis, "anbieter": True, "kontingent_erschoepft": True, "offen": offene_anzahl()}
    faellig = Q(naechster_versuch__isnull=True) | Q(naechster_versuch__lte=jetzt)
    frei = Q(gesperrt_bis__isnull=True) | Q(gesperrt_bis__lte=jetzt)
    ids = list(
        KIAuftrag.objects.filter(status__in=(Auftragsstatus.GEPLANT, Auftragsstatus.LAEUFT))
        .filter(faellig, frei)
        .order_by("pk")
        .values_list("pk", flat=True)[:rest]
    )
    for pk in ids:
        if KILauf.monatsverbrauch(jetzt) >= KILauf.monatsbudget():
            # Mitten im Stapel erschöpft: abbrechen, bevor die Reservierung einen Versuch zählt.
            return {**ergebnis, "anbieter": True, "budget_erschoepft": True, "offen": offene_anzahl()}
        ergebnis[auftrag_ausfuehren(pk, jetzt)] += 1
    return {**ergebnis, "anbieter": True, "offen": offene_anzahl()}


def offene_anzahl() -> int:
    return KIAuftrag.objects.filter(status__in=(Auftragsstatus.GEPLANT, Auftragsstatus.LAEUFT)).count()


def warteschlange_stand(jetzt=None) -> dict:
    """Die öffentliche Rechenschaft: je Zweck offen / erledigt / gescheitert, das Tageskontingent."""
    zeilen = []
    for zweck in ZWECKE:
        qs = KIAuftrag.objects.filter(zweck=zweck)
        zeilen.append(
            {
                "zweck": zweck,
                "name": Zweck(zweck).label,
                "offen": qs.filter(status__in=(Auftragsstatus.GEPLANT, Auftragsstatus.LAEUFT)).count(),
                "erledigt": qs.filter(status=Auftragsstatus.ERLEDIGT).count(),
                "gescheitert": qs.filter(status=Auftragsstatus.GESCHEITERT).count(),
            }
        )
    return {"zwecke": zeilen, "heute": heute_gestartet(jetzt), "kontingent": tageskontingent()}
