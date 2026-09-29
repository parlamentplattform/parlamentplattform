"""Der Ähnlichkeitshinweis beim Einbringen — beide Stufen, ein Aufrufer (FB-H2, ADR-011).

Stufe 1b (Wortvergleich) rechnet `plattform_core.similarity` ohne Modell. Stufe 2 (Bedeutung)
holt Textvektoren über den Modell-Steckplatz: einen Aufruf für den neuen Text und die offenen
Anträge, denen noch ein Vektor fehlt (höchstens „aehnlichkeit-einbettungen-je-aufruf“ je
Einbringen); gespeicherte Vektoren kommen aus `AntragsEinbettung`. Ist der Steckplatz stumm
(kein Anbieter, Budget, Anbieterfehler), bleibt es still beim Wortvergleich — nichts bricht,
und die Karte sagt, was gerechnet wurde.

Treffer = Vereinigung beider Stufen, sortiert nach dem höheren Wert (`similarity.vereinigen`).
Jeder Treffer bringt die Rechtsbezug-Normen des bestehenden Antrags mit (Erbschaft, FB-H2),
damit sichtbar ist, was eine Unterstützung „erbt“. Nichts hier entscheidet oder blockiert."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from ki.anbieter import SteckplatzStumm, anbieter_waehlen
from ki.models import einbettung_ausfuehren
from parameter.models import zahl
from plattform_core import Phase
from plattform_core.similarity import aehnlichkeit, kosinus, vereinigen
from verfahren.models import Antrag, AntragsEinbettung

log = logging.getLogger(__name__)

OFFENE_PHASEN = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]
EINBETTUNGEN_JE_AUFRUF_STANDARD = 20
#: Zeitgrenze (Sekunden je Socket-Operation) für den Anbieter-Aufruf in der Anfrage „Einbringen“.
#: Eine Grenze der Maschine, kein Verfahrenswert: Die Person wartet vor dem Formular, und ein
#: Sync-Worker ist so lange belegt — die 45 s des Steckplatzes (Warteschlange, ohne wartende Person)
#: hielten die Seite fest. Wer länger braucht, fällt still auf den Wortvergleich zurück; den Vektor
#: des neuen Antrags zieht die Warteschlange nach.
ZEITGRENZE_ANFRAGE_SEKUNDEN = 8


@dataclass
class Ergebnis:
    """Was die Karte „Ähnliche Anträge“ braucht — und der Vektor des neuen Texts, wenn einer gerechnet wurde."""

    treffer: list[dict] = field(default_factory=list)
    #: Modellname der Bedeutungsstufe, "" wenn sie nicht lief.
    bedeutungsmodell: str = ""
    #: Warum die Bedeutungsstufe nicht lief (leer, wenn sie lief) — für die ehrliche Karte.
    bedeutung_grund: str = ""
    neuer_vektor: list[float] | None = None

    @property
    def bedeutung_aktiv(self) -> bool:
        return bool(self.bedeutungsmodell)


def _fassung(antrag: Antrag):
    """Die jüngste Fassung aus dem Vorab-Laden (`prefetch_related("fassungen")`), ohne neue Abfrage."""
    return max(antrag.fassungen.all(), key=lambda f: f.nummer, default=None)


def antragstext(antrag: Antrag) -> str:
    """Titel und aktueller Wortlaut — genau der Text, der eingebettet wird."""
    fassung = _fassung(antrag)
    return f"{antrag.titel}\n{fassung.wortlaut if fassung else ''}"


def einbettung_speichern(antrag: Antrag, fassung_nummer: int, modell: str, vektor: list[float]) -> AntragsEinbettung:
    """Idempotent je Antrag, Fassung und Modell."""
    zeile, _neu = AntragsEinbettung.objects.get_or_create(
        antrag=antrag, fassung_nummer=fassung_nummer, modell=modell, defaults={"vektor": vektor}
    )
    return zeile


def _bedeutung(neuer_text: str, offene: list[Antrag], mitglied, ergebnis: Ergebnis) -> dict[int, float]:
    """Stufe 2: Vektoren beschaffen und Kosinus je offenem Antrag. Leer, wenn der Steckplatz stumm ist."""
    anbieter = anbieter_waehlen()
    if anbieter is None:
        ergebnis.bedeutung_grund = "kein Anbieter angeschlossen"
        return {}
    modell = getattr(anbieter, "einbettungsmodell", "")
    fassungen = {a.pk: (_fassung(a).nummer if _fassung(a) else 1) for a in offene}
    vorhanden = {
        (e.antrag_id, e.fassung_nummer): e.vektor
        for e in AntragsEinbettung.objects.filter(antrag__in=offene, modell=modell)
    }
    fehlende = [a for a in offene if (a.pk, fassungen[a.pk]) not in vorhanden]
    fehlende = fehlende[: max(0, zahl("aehnlichkeit-einbettungen-je-aufruf", EINBETTUNGEN_JE_AUFRUF_STANDARD))]
    try:
        _lauf, einbettung = einbettung_ausfuehren(
            [neuer_text, *(antragstext(a) for a in fehlende)], mitglied, zeitgrenze=ZEITGRENZE_ANFRAGE_SEKUNDEN
        )
    except SteckplatzStumm as grund:
        ergebnis.bedeutung_grund = str(grund)
        log.info("Bedeutungsstufe übersprungen: %s", grund)
        return {}
    ergebnis.neuer_vektor = einbettung.vektoren[0]
    ergebnis.bedeutungsmodell = einbettung.modell
    for a, vektor in zip(fehlende, einbettung.vektoren[1:], strict=True):
        einbettung_speichern(a, fassungen[a.pk], einbettung.modell, vektor)
        vorhanden[(a.pk, fassungen[a.pk])] = vektor
    return {
        a.pk: kosinus(ergebnis.neuer_vektor, vorhanden[(a.pk, fassungen[a.pk])])
        for a in offene
        if (a.pk, fassungen[a.pk]) in vorhanden
    }


def aehnliche_antraege(titel: str, wortlaut: str, mitglied) -> Ergebnis:
    """Beide Stufen für einen neuen Text gegen die offenen Anträge."""
    from ki.rechtsbezug import rechtsbezug_fuer

    ergebnis = Ergebnis()
    offene = list(Antrag.objects.filter(phase__in=OFFENE_PHASEN).prefetch_related("fassungen").order_by("pk"))
    if not offene:
        return ergebnis
    wortwerte = {
        a.pk: aehnlichkeit((titel, wortlaut), (a.titel, _fassung(a).wortlaut if _fassung(a) else ""))
        for a in offene
    }
    bedeutungswerte = _bedeutung(f"{titel}\n{wortlaut}", offene, mitglied, ergebnis)
    zeilen = vereinigen(
        wortwerte,
        bedeutungswerte,
        wort_schwelle=zahl("aehnlichkeit-schwelle-prozent", 30) / 100,
        bedeutung_schwelle=zahl("aehnlichkeit-bedeutung-schwelle-prozent", 78) / 100,
        limit=zahl("aehnlichkeit-treffer", 3),
    )
    nach_id = {a.pk: a for a in offene}
    for kid, wort, bedeutung in zeilen:
        antrag = nach_id[kid]
        rechtsbezug = rechtsbezug_fuer(antrag)
        ergebnis.treffer.append(
            {
                "antrag": antrag,
                "prozent": round(wort * 100),
                "bedeutung_prozent": round(bedeutung * 100) if bedeutung is not None else None,
                "beteiligung": antrag.unterstuetzungen.filter(zurueckgezogen_am__isnull=True).count(),
                "normen": rechtsbezug["normen"] if rechtsbezug else [],
                "rechtsbezug": rechtsbezug,
            }
        )
    return ergebnis
