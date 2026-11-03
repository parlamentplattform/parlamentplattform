"""Betroffene Gesetze — ungeprüfte Modellvorschläge und ihre festgehaltenen Quellen.

Beim Einbringen wird ein Auftrag „rechtsbezug“ eingereiht (`ki/warteschlange.py`); der Lauf
fragt den Anbieter mit dem versionierten Auftragstext `ki/auftraege/rechtsbezug-v<n>.md` und
archiviert die Antwort im `KILauf`. Dieses Modul ist die **Leseschicht**: Es parst die jüngste
erfolgreiche Antwort tolerant (JSON aus der Antwort ziehen; bei Parse-Fehler bleibt der rohe
Text als Hinweis) und beschreibt den Zustand für die Antragsseite. Nichts hier schreibt.

Ohne unabhängige Relevanzprüfung trägt jede Modellnorm „nicht verifiziert“ und keinen Link (FB-H3:
Halluzinationsschutz). Der Vorschlag ist gekennzeichnet — Modell, Auftragsversion, Stand —
und entscheidet nichts (Grundregel 5, § 2 Abs 6)."""

from __future__ import annotations

import json
import re
from typing import Any

from django.utils.translation import gettext_lazy as _

from plattform_core.modellantwort import HOECHSTZEICHEN, pruefen

EBENEN = ("EU", "Bund", "Land")
AENDERUNGEN = {
    "aendern": _("zu ändern"),
    "aufheben": _("aufzuheben"),
    "neu": _("neu zu schaffen"),
    "beruehrt": _("berührt"),
    "unklar": _("unklar"),
}
UNSICHERHEITEN = {
    "niedrig": _("niedrig"),
    "mittel": _("mittel"),
    "hoch": _("hoch"),
    "unbekannt": _("nicht angegeben"),
}
HOECHSTNORMEN = 12
_ZAUN = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def _text(wert: Any, laenge: int = 600) -> str:
    return wert.strip()[:laenge].encode("utf-8", errors="replace").decode("utf-8") if isinstance(wert, str) else ""


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
        "aenderung": aenderung if aenderung in AENDERUNGEN else "unklar",
        "aenderung_wort": AENDERUNGEN.get(aenderung, AENDERUNGEN["unklar"]),
        "begruendung": _text(roh.get("begruendung")),
        "verifiziert": False,  # Kontextkandidaten sind noch keine Verifikation der rechtlichen Deutung
    }


def antwort_parsen(text: str) -> dict:
    """Die Modellantwort in die feste Form bringen. Tolerant: Zäune (```json) und Text um das Objekt
    herum werden ignoriert; ist kein JSON zu finden oder ist es kaputt, wird der rohe Text der Hinweis
    und die Unsicherheit „unbekannt“ — `roh` sagt, dass so gelesen wurde."""
    formatstand = pruefen(text)
    # Übergröße/Tiefe nicht anschließend doch im toleranten Parser verarbeiten.
    gesperrt = any(f["code"] in {"groesse", "tiefe", "kodierung", "typ", "doppelte_schluessel"} and f["pfad"] == "$"
                   for f in formatstand["fehler"])
    bereinigt = _ZAUN.sub("", (text or "")[:HOECHSTZEICHEN]).strip() if isinstance(text, str) and not gesperrt else ""
    daten: Any = None
    anfang, ende = bereinigt.find("{"), bereinigt.rfind("}")
    if anfang != -1 and ende > anfang:
        try:
            def objekt(paare):
                wert = {}
                for schluessel, inhalt in paare:
                    if schluessel in wert:
                        raise ValueError("Doppelter JSON-Schlüssel")
                    wert[schluessel] = inhalt
                return wert
            def nicht_endlich(_):
                raise ValueError("Kein JSON-Zahlenwert")
            daten = json.loads(bereinigt[anfang : ende + 1], object_pairs_hook=objekt, parse_constant=nicht_endlich)
        except (ValueError, RecursionError):
            daten = None
    if not isinstance(daten, dict):
        return {"normen": [], "hinweis": _text(text, 2000), "unsicherheit": "unbekannt", "roh": True,
                "formatpruefung": formatstand}
    normen_roh = daten.get("normen")
    normen = []
    if isinstance(normen_roh, list):
        normen = [n for n in (_norm(r) for r in normen_roh[:HOECHSTNORMEN]) if n]
    unsicherheit = _text(daten.get("unsicherheit"), 10)
    return {
        "normen": normen,
        "hinweis": _text(daten.get("hinweis"), 2000),
        "unsicherheit": unsicherheit if unsicherheit in UNSICHERHEITEN else "unbekannt",
        "roh": False,
        "formatpruefung": formatstand,
    }


def antrag_eingabe(antrag, fassung_nummer: int | None = None) -> str:
    """Eine verlangte erhaltene Fassung; nie auf einen anderen Wortlaut ausweichen."""
    from ki.kontext import eingabe, festhalten

    return eingabe(festhalten(antrag, fassung_nummer=fassung_nummer))


def _aktueller_textstand(antrag):
    from gremien.models import Entwurf

    vorschlag = Entwurf.objects.filter(antrag=antrag).values_list("eingereichte_fassung", flat=True).first()
    if vorschlag:
        return "vorschlag", vorschlag
    return "antrag", antrag.fassungen.order_by("-nummer").values_list("nummer", flat=True).first()


def rechtsbezug_fuer(antrag, lauf=None, *, ziel=None) -> dict | None:
    """Der jüngste erfolgreiche Lauf „rechtsbezug“ zu diesem Antrag, geparst — oder None.
    `fassung` ist die Fassung, zu der der Lauf gerechnet hat (aus seinem Auftrag; None ohne Auftrag),
    `frueher` sagt, dass der Antrag inzwischen eine jüngere Fassung hat (§ 6 Abs 11 lit b, Kontextstand)."""
    from ki.models import KILauf, Zweck

    lauf = lauf or (
        KILauf.objects.filter(antrag=antrag, zweck=Zweck.RECHTSBEZUG, erfolgreich=True)
        .prefetch_related("auftraege").order_by("-erstellt_am", "-pk")
        .first()
    )
    if lauf is None or lauf.antrag_id != antrag.pk or lauf.zweck != Zweck.RECHTSBEZUG:
        return None
    from ki.nachlese import quellenstand, textstand

    ergebnis = antwort_parsen(lauf.antwort) if lauf.erfolgreich else {"normen": [], "hinweis": "", "unsicherheit": "hoch"}
    quelle = textstand(lauf)
    zuordnungen = {(a.quellenart, a.fassung_nummer) for a in lauf.auftraege.all()}
    if not quelle["festgehalten"] and len(zuordnungen) == 1:
        art, nummer = zuordnungen.pop()
        quelle.update(quellenart=art, fassung=nummer)
    fassung = quelle.get("fassung")
    ziel = ziel or _aktueller_textstand(antrag)
    ergebnis.update(
        lauf=lauf,
        modell=lauf.modell,
        auftrag_version=lauf.auftrag_version,
        stand=lauf.erstellt_am,
        unsicherheit_wort=UNSICHERHEITEN[ergebnis["unsicherheit"]],
        fassung=fassung,
        frueher=bool(fassung and (quelle.get("quellenart"), fassung) != ziel),
        textstand=quelle,
        quellenstand=quellenstand(
            lauf.kontext.get("quellen") if isinstance(lauf.kontext, dict) else None,
            text_sha256=lauf.kontext.get("text", {}).get("sha256") if isinstance(lauf.kontext, dict) and isinstance(lauf.kontext.get("text"), dict) else None,
        ),
    )
    return ergebnis


def rechtsbezug_lage(antrag, betrachter=None, seite=None) -> dict:
    """Der Zustand der Karte „Betroffene Gesetze“ in Zone 2:

    - `nicht_angeschlossen`: kein Anbieter am Steckplatz — es wird nichts gerechnet.
    - `wartet`: Auftrag in der Warteschlange (mit Platz), noch kein Ergebnis.
    - `erledigt`: Ergebnis liegt vor.
    - `gescheitert`: der Auftrag hat alle Versuche aufgebraucht.
    - `keiner`: nichts eingereiht (Altbestand, Kandidaturen).

    `mail_zusage` ist wahr, wenn der Betrachter der Antragsteller ist und Verfahrenspost
    zugestimmt hat — nur dann verspricht die Karte eine E-Mail."""
    from django.core.paginator import Paginator

    from ki.anbieter import anbieter_waehlen
    from ki.models import Auftragsstatus, KIAuftrag, KILauf, Zweck
    from ki.nachlese import quellenstand
    from ki.warteschlange import platz_in_der_schlange
    from parameter.models import zahl

    auftrag = KIAuftrag.objects.filter(antrag=antrag, zweck=Zweck.RECHTSBEZUG).select_related("lauf").order_by("-erstellt_am", "-pk").first()
    ziel = _aktueller_textstand(antrag)
    ergebnis = rechtsbezug_fuer(antrag, auftrag.lauf, ziel=ziel) if (
        auftrag and auftrag.status == Auftragsstatus.ERLEDIGT and auftrag.lauf and auftrag.lauf.erfolgreich
    ) else (rechtsbezug_fuer(antrag, ziel=ziel) if auftrag is None else None)
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
    laeufe = KILauf.objects.filter(antrag=antrag, zweck=Zweck.RECHTSBEZUG).prefetch_related("auftraege").order_by("-erstellt_am", "-pk")
    if ergebnis:
        laeufe = laeufe.exclude(pk=ergebnis["lauf"].pk)
    historie = Paginator(laeufe, max(1, min(100, zahl("ki-einschaetzungen-je-seite", 20)))).get_page(seite)
    historie.object_list = [rechtsbezug_fuer(antrag, lauf, ziel=ziel) for lauf in historie.object_list]
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
        "historie": historie,
        "quellenstand": ergebnis["quellenstand"] if ergebnis else quellenstand(
            auftrag.quellenkontext if auftrag else None,
            text_sha256=auftrag.kontext.get("sha256") if auftrag and isinstance(auftrag.kontext, dict) else None,
        ),
    }
