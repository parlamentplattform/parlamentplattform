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
import unicodedata
from dataclasses import dataclass, field

from django.db.models import F, OuterRef, Subquery
from django.utils import timezone

from ki.anbieter import SteckplatzStumm, anbieter_waehlen
from ki.betriebszugang import SteckplatzWartet
from ki.models import einbettung_ausfuehren
from parameter.models import zahl
from plattform_core import Phase
from plattform_core.similarity import _wert, kosinus, merkmale, vereinigen
from verfahren.models import Antrag, Antragsart, AntragsEinbettung, AntragsFassung

log = logging.getLogger(__name__)

OFFENE_PHASEN = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]
#: Personenanträge — sie bleiben außerhalb der Bedeutungsstufe (GP-023).
PERSONENARTEN = (Antragsart.MANDAT, Antragsart.VERTRAUENSFRAGE)
EINBETTUNGEN_JE_AUFRUF_STANDARD = 20
#: Zeitgrenze (Sekunden je Socket-Operation) für den Anbieter-Aufruf in der Anfrage „Einbringen“ —
#: Erstbestand und Rückfall des Registerwerts „aehnlichkeit-zeitgrenze-sekunden“ (Entscheidung des
#: Gründers 29.9.2026). Die Person wartet vor dem Formular, und ein Sync-Worker ist so lange belegt —
#: die 45 s des Steckplatzes (Warteschlange, ohne wartende Person) hielten die Seite fest. Wer länger
#: braucht, fällt still auf den Wortvergleich zurück; den Vektor des neuen Antrags zieht die
#: Warteschlange nach.
ZEITGRENZE_ANFRAGE_SEKUNDEN = 8
#: Höchstens so viele Anbieteraufrufe der Bedeutungsstufe je Konto und Stunde — Erstbestand und
#: Rückfall des Registerwerts „aehnlichkeit-bedeutung-je-stunde“. Jeder Einbringen-Versuch ohne
#: „Trotzdem“ ruft sonst den Anbieter, und ein Konto könnte per Skript das Monatsbudget aller leeren.
#: Darüber rechnet nur der Wortvergleich — der Hinweis bleibt, nichts blockiert.
BEDEUTUNG_JE_KONTO_UND_STUNDE = 5


@dataclass
class Ergebnis:
    """Was die Karte „Ähnliche Anträge“ braucht — und der Vektor des neuen Texts, wenn einer gerechnet wurde."""

    treffer: list[dict] = field(default_factory=list)
    #: Modellname der Bedeutungsstufe, "" wenn sie nicht lief.
    bedeutungsmodell: str = ""
    #: Warum die Bedeutungsstufe nicht lief (leer, wenn sie lief) — für die ehrliche Karte.
    bedeutung_grund: str = ""
    #: Die Bedeutungsstufe lief nicht, weil das Konto seine Aufrufe dieser Stunde verbraucht hat.
    gedrosselt: bool = False
    neuer_vektor: list[float] | None = None

    @property
    def bedeutung_aktiv(self) -> bool:
        return bool(self.bedeutungsmodell)


def drossel_zuruecknehmen(zweck: str, kennung: str) -> None:
    """Einen gezählten Versuch zurücknehmen, der den Anbieter nie erreicht hat (`SteckplatzWartet`:
    Zugang belegt, kein Anbieter, Budget erschöpft) — die Stundengrenze je Konto zählt Anbieteraufrufe,
    nicht Wartezeit (GP-207). Trifft den jüngsten Eimer dieses Zwecks und dieser Kennung."""
    from mitglieder.models import Drosselzaehler

    zeile = Drosselzaehler.objects.filter(zweck=zweck, kennung=kennung, anzahl__gt=0).order_by("-stunde").first()
    if zeile is not None:
        Drosselzaehler.objects.filter(pk=zeile.pk, anzahl__gt=0).update(anzahl=F("anzahl") - 1)


def _fassung(antrag: Antrag):
    """Die jüngste Fassung aus dem Vorab-Laden (`prefetch_related("fassungen")`), ohne neue Abfrage."""
    return max(antrag.fassungen.all(), key=lambda f: f.nummer, default=None)


def _gemeinsames_wort(stammformen: tuple[str, ...], titel: str, wortlaut: str) -> bool:
    """Notwendige Bedingung für einen Wert über 0 (GP-153): Jede Stammform, die der Kandidat mit dem
    neuen Text teilt, steht als Zeichenfolge in seinem Text nach Unicode-Normalform und Kleinschreibung,
    denn Wortzeichen bleiben beim Normalisieren (`similarity.normalisieren`) unverändert stehen. Fehlt
    jede, sind Wortanteil und Paaranteil 0 — der Kandidat muss nicht zerlegt werden."""
    roh = unicodedata.normalize("NFKC", f"{titel}\n{wortlaut}").casefold()
    return any(s in roh for s in stammformen)


def antragstext(antrag: Antrag, fassung_nummer: int | None = None) -> str:
    """Titel und aktueller Wortlaut — genau der Text, der eingebettet wird. Mit `fassung_nummer` der
    Wortlaut dieser Fassung (ein Auftrag der Warteschlange rechnet mit seiner Fassung)."""
    fassung = (
        next((f for f in antrag.fassungen.all() if f.nummer == fassung_nummer), None) if fassung_nummer else None
    ) or _fassung(antrag)
    return f"{antrag.titel}\n{fassung.wortlaut if fassung else ''}"


def einbettung_speichern(antrag: Antrag, fassung_nummer: int, modell: str, vektor: list[float]) -> AntragsEinbettung:
    """Idempotent je Antrag, Fassung und Modell."""
    zeile, _neu = AntragsEinbettung.objects.get_or_create(
        antrag=antrag, fassung_nummer=fassung_nummer, modell=modell, defaults={"vektor": vektor}
    )
    return zeile


@dataclass(frozen=True)
class _Kandidat:
    """Ein offener Sachantrag, wie ihn die Bedeutungsstufe braucht — ohne Modellobjekt (GP-153)."""

    pk: int
    #: Nummer der jüngsten Fassung, 1 ohne Fassung (wie `_fassung`).
    fassung_nummer: int
    #: Titel und jüngster Wortlaut wie `antragstext` — nur für Anträge, denen ein Vektor fehlt.
    text: str = ""


#: Zeilen je Datenbankabruf beim Durchgehen der offenen Anträge und der gespeicherten Vektoren
#: (GP-153). Bestimmt nur, wie viel zugleich im Speicher liegt, nicht das Ergebnis — Registerwert folgt.
VERGLEICH_SEITE_ZEILEN = 200


def _offene_zeilen():
    """Alle offenen Anträge mit Titel und jüngstem Wortlaut, seitenweise gelesen (GP-153): Ältere
    Fassungen und alle übrigen Felder bleiben in der Datenbank."""
    juengste = AntragsFassung.objects.filter(antrag=OuterRef("pk")).order_by("-nummer")
    return (
        Antrag.objects.filter(phase__in=OFFENE_PHASEN)
        .order_by("pk")
        .annotate(
            juengste_nummer=Subquery(juengste.values("nummer")[:1]),
            juengster_wortlaut=Subquery(juengste.values("wortlaut")[:1]),
        )
        .values_list("pk", "titel", "art", "juengste_nummer", "juengster_wortlaut")
        .iterator(chunk_size=VERGLEICH_SEITE_ZEILEN)
    )


def _bedeutung(
    neuer_text: str, sachlich: dict[int, _Kandidat], fehlende: list[_Kandidat], modell: str, mitglied,
    ergebnis: Ergebnis,
) -> dict[int, float]:
    """Stufe 2: Vektoren beschaffen und Kosinus je offenem Sachantrag. Leer, wenn der Steckplatz stumm ist.
    Gespeicherte Vektoren werden seitenweise gelesen und sofort verglichen, nie alle zugleich gehalten
    (GP-153)."""
    from mitglieder.botschutz import drossel_zuviel

    je_stunde = max(0, zahl("aehnlichkeit-bedeutung-je-stunde", BEDEUTUNG_JE_KONTO_UND_STUNDE))
    kennung = f"konto:{mitglied.pk}"
    if drossel_zuviel(None, "bedeutung", je_stunde, kennung=kennung):
        ergebnis.gedrosselt = True
        ergebnis.bedeutung_grund = "Anbieteraufrufe dieses Kontos für diese Stunde verbraucht"
        return {}
    try:
        _lauf, einbettung = einbettung_ausfuehren(
            [neuer_text, *(k.text for k in fehlende)],
            mitglied,
            zeitgrenze=max(1, zahl("aehnlichkeit-zeitgrenze-sekunden", ZEITGRENZE_ANFRAGE_SEKUNDEN)),
        )
    except SteckplatzStumm as grund:
        if isinstance(grund, SteckplatzWartet):
            drossel_zuruecknehmen("bedeutung", kennung)
        ergebnis.bedeutung_grund = str(grund)
        log.info("Bedeutungsstufe übersprungen: %s", grund)
        return {}
    ergebnis.neuer_vektor = einbettung.vektoren[0]
    ergebnis.bedeutungsmodell = einbettung.modell
    werte: dict[int, float] = {}
    for k, vektor in zip(fehlende, einbettung.vektoren[1:], strict=True):
        AntragsEinbettung.objects.get_or_create(
            antrag_id=k.pk, fassung_nummer=k.fassung_nummer, modell=einbettung.modell, defaults={"vektor": vektor}
        )
        werte[k.pk] = kosinus(ergebnis.neuer_vektor, vektor)
    gespeichert = (
        AntragsEinbettung.objects.filter(modell=modell, antrag__phase__in=OFFENE_PHASEN)
        .values_list("antrag_id", "fassung_nummer", "vektor")
        .iterator(chunk_size=VERGLEICH_SEITE_ZEILEN)
    )
    for antrag_id, nummer, vektor in gespeichert:
        k = sachlich.get(antrag_id)
        if k is not None and k.fassung_nummer == nummer and antrag_id not in werte:
            werte[antrag_id] = kosinus(ergebnis.neuer_vektor, vektor)
    return werte


def aehnliche_antraege(titel: str, wortlaut: str, mitglied, *, bedeutung: bool = True) -> Ergebnis:
    """Beide Stufen; mit bedeutung=False ruft die lokale Vorschau keinen Anbieter auf.

    Gerechnet wird wie bisher über alle offenen Anträge, aber ohne sie alle zugleich zu halten
    (GP-153): Je Antrag werden Titel und jüngster Wortlaut gelesen, verglichen und verworfen; die
    Merkmale des neuen Texts entstehen einmal. Ein Antrag ohne gemeinsames Wort erhält ohne Zerlegung
    den Wert 0, genau den Wert des vollen Vergleichs."""
    from ki.rechtsbezug import rechtsbezug_fuer

    ergebnis = Ergebnis()
    neu = merkmale((titel, wortlaut))
    stammformen = tuple(neu[0])
    anbieter = anbieter_waehlen() if bedeutung else None
    modell = getattr(anbieter, "einbettungsmodell", "") if anbieter is not None else ""
    vorhanden = set(
        AntragsEinbettung.objects.filter(modell=modell, antrag__phase__in=OFFENE_PHASEN).values_list(
            "antrag_id", "fassung_nummer"
        )
    ) if anbieter is not None else set()
    je_aufruf = max(0, zahl("aehnlichkeit-einbettungen-je-aufruf", EINBETTUNGEN_JE_AUFRUF_STANDARD))
    wortwerte: dict[int, float] = {}
    sachlich: dict[int, _Kandidat] = {}
    fehlende: list[_Kandidat] = []
    for pk, a_titel, art, nummer, a_wortlaut in _offene_zeilen():
        a_wortlaut = a_wortlaut or ""
        wortwerte[pk] = (
            _wert(*neu, *merkmale((a_titel, a_wortlaut)))
            if stammformen and _gemeinsames_wort(stammformen, a_titel, a_wortlaut)
            else 0.0
        )
        # Über Personen rechnet keine Maschine (FB-F4, ADR-011): Titel und Wortlaut von Kandidaturen und
        # Vertrauensfragen gehen nie an den Anbieter, und ihre Vektoren werden nicht gelesen. Der
        # Wortvergleich oben rechnet ohne Modell und bleibt für alle offenen Anträge.
        if anbieter is None or art in PERSONENARTEN:
            continue
        k = _Kandidat(pk, nummer or 1)
        if (pk, k.fassung_nummer) not in vorhanden and len(fehlende) < je_aufruf:
            k = _Kandidat(pk, k.fassung_nummer, f"{a_titel}\n{a_wortlaut}")
            fehlende.append(k)
        sachlich[pk] = k
    if not wortwerte:
        return ergebnis
    bedeutungswerte = {}
    if bedeutung and anbieter is None:
        ergebnis.bedeutung_grund = "kein Anbieter angeschlossen"
    elif anbieter is not None:
        bedeutungswerte = _bedeutung(f"{titel}\n{wortlaut}", sachlich, fehlende, modell, mitglied, ergebnis)
    zeilen = vereinigen(
        wortwerte,
        bedeutungswerte,
        wort_schwelle=zahl("aehnlichkeit-schwelle-prozent", 30) / 100,
        bedeutung_schwelle=zahl("aehnlichkeit-bedeutung-schwelle-prozent", 78) / 100,
        limit=zahl("aehnlichkeit-treffer", 3),
    )
    nach_id = Antrag.objects.filter(pk__in=[z[0] for z in zeilen]).prefetch_related("fassungen").in_bulk()
    zeilen = [z for z in zeilen if z[0] in nach_id]
    jetzt = timezone.now()
    from verfahren.views import (
        _frist_fuer,
        _vertrauensfragen,
        _vf_abstimmung_ab,
        abstimmung_beginnt,
        resttage,
    )

    # Vertrauensfragen enden ihre Sammelphase mit dem veröffentlichten Abstimmungsbeginn — wie Kachel und Zeile
    vfs = _vertrauensfragen([nach_id[kid] for kid, _w, _b in zeilen])
    for kid, wort, bedeutung in zeilen:
        antrag = nach_id[kid]
        rechtsbezug = rechtsbezug_fuer(antrag)
        vf = vfs.get(antrag.pk)
        beginn = antrag.wirksamer_phase_beginn(jetzt)
        frist = _frist_fuer(antrag, beginn=beginn, vf=vf)
        ergebnis.treffer.append(
            {
                "antrag": antrag,
                "prozent": round(wort * 100),
                "bedeutung_prozent": round(bedeutung * 100) if bedeutung is not None else None,
                "beteiligung": antrag.unterstuetzungen.filter(zurueckgezogen_am__isnull=True, mitglied__testkonto=False).count(),
                # GP-175: dieselbe Rechnung wie Kachel und Zeile (Wiener Kalendertage, 0 = endet heute)
                "rest_tage": resttage(frist, jetzt),
                "frist_abgelaufen": frist is not None and frist <= jetzt,
                # E-43 Zeile 2: nach der Beratung beginnt die Abstimmung, ausgewertet wird dort nichts
                "abstimmung_beginnt": abstimmung_beginnt(
                    antrag, frist, jetzt, _vf_abstimmung_ab(vf, antrag, antrag.policy(), beginn)
                ),
                "normen": rechtsbezug["normen"] if rechtsbezug else [],
                "rechtsbezug": rechtsbezug,
            }
        )
    return ergebnis
