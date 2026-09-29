"""Betroffene Gesetze — die erste Stufe von FB-H3, ohne RIS-Faktenbasis.

Beim Einbringen wird ein Auftrag „rechtsbezug“ eingereiht (`ki/warteschlange.py`); der Lauf
fragt den Anbieter mit dem versionierten Auftragstext `ki/auftraege/rechtsbezug-v<n>.md` und
archiviert die Antwort im `KILauf`. Dieses Modul ist die **Leseschicht**: Es parst die jüngste
erfolgreiche Antwort tolerant (JSON aus der Antwort ziehen; bei Parse-Fehler bleibt der rohe
Text als Hinweis) und beschreibt den Zustand für die Antragsseite. Nichts hier schreibt.

Ohne RIS-Prüfung trägt jede Norm das Etikett „nicht verifiziert“ und keinen Link (FB-H3:
Halluzinationsschutz). Der Vorschlag ist gekennzeichnet — Modell, Auftragsversion, Stand —
und entscheidet nichts (Grundregel 5, § 2 Abs 6)."""

from __future__ import annotations

import json
import re
from typing import Any

from django.utils.translation import gettext_lazy as _

EBENEN = ("EU", "Bund", "Land")
AENDERUNGEN = {
    "aendern": _("zu ändern"),
    "aufheben": _("aufzuheben"),
    "neu": _("neu zu schaffen"),
    "beruehrt": _("berührt"),
}
UNSICHERHEITEN = {
    "niedrig": _("niedrig"),
    "mittel": _("mittel"),
    "hoch": _("hoch"),
}
HOECHSTNORMEN = 12
_ZAUN = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _text(wert: Any, laenge: int = 600) -> str:
    return str(wert).strip()[:laenge] if wert is not None else ""


def _norm(roh: Any) -> dict | None:
    if not isinstance(roh, dict):
        return None
    titel = _text(roh.get("titel"), 200)
    if not titel:
        return None
    ebene = _text(roh.get("ebene"), 10)
    aenderung = _text(roh.get("aenderung"), 20)
    return {
        "titel": titel,
        "ebene": ebene if ebene in EBENEN else "",
        "kennung": _text(roh.get("kennung"), 120),
        "aenderung": aenderung if aenderung in AENDERUNGEN else "beruehrt",
        "aenderung_wort": AENDERUNGEN.get(aenderung, AENDERUNGEN["beruehrt"]),
        "begruendung": _text(roh.get("begruendung")),
        "verifiziert": False,  # ohne RIS-Faktenbasis nie
    }


def antwort_parsen(text: str) -> dict:
    """Die Modellantwort in die feste Form bringen. Tolerant: Zäune (```json) und Text um das Objekt
    herum werden ignoriert; ist kein JSON zu finden oder ist es kaputt, wird der rohe Text der Hinweis
    und die Unsicherheit „hoch“ — `roh` sagt, dass so gelesen wurde."""
    bereinigt = _ZAUN.sub("", text or "").strip()
    daten: Any = None
    anfang, ende = bereinigt.find("{"), bereinigt.rfind("}")
    if anfang != -1 and ende > anfang:
        try:
            daten = json.loads(bereinigt[anfang : ende + 1])
        except ValueError:
            daten = None
    if not isinstance(daten, dict):
        return {"normen": [], "hinweis": _text(text, 2000), "unsicherheit": "hoch", "roh": True}
    normen_roh = daten.get("normen")
    normen = []
    if isinstance(normen_roh, list):
        normen = [n for n in (_norm(r) for r in normen_roh[:HOECHSTNORMEN]) if n]
    unsicherheit = _text(daten.get("unsicherheit"), 10)
    return {
        "normen": normen,
        "hinweis": _text(daten.get("hinweis"), 2000),
        "unsicherheit": unsicherheit if unsicherheit in UNSICHERHEITEN else "hoch",
        "roh": False,
    }


def antrag_eingabe(antrag, fassung_nummer: int | None = None) -> str:
    """Was der Anbieter zu sehen bekommt: nur, was ohnehin öffentlich auf der Antragsseite steht —
    mit `fassung_nummer` der Text dieser Fassung (der Auftrag rechnet mit seiner), sonst der jüngste."""
    fassung = (antrag.fassungen.filter(nummer=fassung_nummer).first() if fassung_nummer else None) or antrag.aktueller_text()
    teile = [
        f"Titel: {antrag.titel}",
        f"Ebene: {antrag.get_ebene_display()}" + (f" ({antrag.gebiet})" if antrag.gebiet else ""),
        "",
        "Wortlaut:",
        fassung.wortlaut if fassung else "",
    ]
    if fassung and fassung.begruendung:
        teile += ["", "Begründung:", fassung.begruendung]
    return "\n".join(teile)


def rechtsbezug_fuer(antrag) -> dict | None:
    """Der jüngste erfolgreiche Lauf „rechtsbezug“ zu diesem Antrag, geparst — oder None.
    `fassung` ist die Fassung, zu der der Lauf gerechnet hat (aus seinem Auftrag; None ohne Auftrag),
    `frueher` sagt, dass der Antrag inzwischen eine jüngere Fassung hat (§ 6 Abs 11 lit b, Kontextstand)."""
    from ki.models import KILauf, Zweck

    lauf = (
        KILauf.objects.filter(antrag=antrag, zweck=Zweck.RECHTSBEZUG, erfolgreich=True)
        .order_by("-erstellt_am")
        .first()
    )
    if lauf is None:
        return None
    ergebnis = antwort_parsen(lauf.antwort)
    fassung = lauf.auftraege.values_list("fassung_nummer", flat=True).first()
    aktuell = antrag.aktueller_text()
    ergebnis.update(
        lauf=lauf,
        modell=lauf.modell,
        auftrag_version=lauf.auftrag_version,
        stand=lauf.erstellt_am,
        unsicherheit_wort=UNSICHERHEITEN[ergebnis["unsicherheit"]],
        fassung=fassung,
        frueher=bool(fassung and aktuell and aktuell.nummer > fassung),
    )
    return ergebnis


def rechtsbezug_lage(antrag, betrachter=None) -> dict:
    """Der Zustand der Karte „Betroffene Gesetze“ in Zone 2:

    - `nicht_angeschlossen`: kein Anbieter am Steckplatz — es wird nichts gerechnet.
    - `wartet`: Auftrag in der Warteschlange (mit Platz), noch kein Ergebnis.
    - `erledigt`: Ergebnis liegt vor.
    - `gescheitert`: der Auftrag hat alle Versuche aufgebraucht.
    - `keiner`: nichts eingereiht (Altbestand, Kandidaturen).

    `mail_zusage` ist wahr, wenn der Betrachter der Antragsteller ist und Verfahrenspost
    zugestimmt hat — nur dann verspricht die Karte eine E-Mail."""
    from ki.anbieter import anbieter_waehlen
    from ki.models import Auftragsstatus, KIAuftrag, Zweck
    from ki.warteschlange import platz_in_der_schlange

    ergebnis = rechtsbezug_fuer(antrag)
    auftrag = KIAuftrag.objects.filter(antrag=antrag, zweck=Zweck.RECHTSBEZUG).order_by("-fassung_nummer").first()
    angeschlossen = anbieter_waehlen() is not None
    if ergebnis is not None:
        zustand = "erledigt"
    elif not angeschlossen:
        zustand = "nicht_angeschlossen"
    elif auftrag is None:
        zustand = "keiner"
    elif auftrag.status == Auftragsstatus.GESCHEITERT:
        zustand = "gescheitert"
    else:
        zustand = "wartet"
    steller = getattr(antrag, "eingebracht_von", None)
    mail_zusage = bool(
        betrachter is not None
        and getattr(betrachter, "is_authenticated", False)
        and steller is not None
        and betrachter.pk == steller.pk
        and getattr(steller, "post_einwilligung", False)
    )
    return {
        "zustand": zustand,
        "auftrag": auftrag,
        "ergebnis": ergebnis,
        "platz": platz_in_der_schlange(auftrag) if zustand == "wartet" else None,
        "mail_zusage": mail_zusage and zustand == "wartet",
        "angeschlossen": angeschlossen,
    }
