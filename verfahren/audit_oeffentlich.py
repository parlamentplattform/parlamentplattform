"""Was vom Audit-Log öffentlich ist (Schritt 2 · 0.52.0) — für den Export je Antrag und `/audit/`.

Die Kette ist vollständig, damit sie nachrechenbar bleibt; einige Einträge nennen aber die Kennung eines
Mitglieds, das Pseudonym einer Stimme oder eine Begründung zu einer Person. Öffentlich wird ein solcher
Wert durch „•“ ersetzt, der Eintrag ist dann als geschwärzt markiert (Entscheidung des Gründers
29.9.2026, F2 a). Sein Inhalt lässt sich von außen nicht nachrechnen — das leistet täglich
`audit_pruefen` über die ganze Kette, dessen Ergebnis und Kettenkopf in den Kennzahlen stehen. Jeder
ungeschwärzte Eintrag bleibt einzeln nachrechenbar (verify/nachrechnen.py).

Schwärzen allein genügt nicht (gegnerische Prüfung 0.52.0): Mitgliedsnummern und Pseudonyme haben kleine
Wertebereiche, und mit Hash und Vorgänger fände ein Gast den geschwärzten Wert durch Durchprobieren.
Deshalb trägt jeder neue Eintrag mit schutzwürdigen Werten ein geheimes Zufallssalz (`salz`, selbst
geschwärzt), das beim Anhängen unter den Hash kommt. Ältere Einträge ohne Salz zeigen öffentlich weder
ihren Hash noch — beim nächsten Eintrag — den Vorgänger-Hash."""

from __future__ import annotations

import secrets

from django.db.models import BooleanField, Case, OuterRef, Q, Subquery, Value, When
from django.utils import timezone

#: Das Zeichen, das einen ausgeblendeten Wert ersetzt.
MASKE = "•"

#: Der Schlüssel des Zufallssalzes (128 Bit) in schutzwürdigen Ereignissen.
SALZ = "salz"

#: Schlüssel, deren Wert eine Mitgliedskennung ist. `mitglied` und `durch` als Zahl oder Liste von
#: Zahlen — ein Text wie `durch: "verwaltung"` nennt niemanden; `konten` nur als Liste — eine Zahl dort
#: ist eine Anzahl.
KENNUNGEN = {"mitglied": (int, list), "durch": (int, list), "konten": (list,)}

#: Schlüssel, deren Wert öffentlich nie erscheint, gleich welcher Art: Das Pseudonym einer Stimme mit
#: ihrer Zeit verriete zusammen mit der Stimmliste (Pseudonym → Stimme), wer wann wie gestimmt hat
#: (§ 5 Abs 3 lit e). Die Stimmliste selbst bleibt, wie sie ist. Das Salz ist geheim.
IMMER = ("pseudonym", SALZ)

#: Ereignisarten, deren Begründung eine Person betrifft: Pausieren, Ausschluss, Adresswechsel
#: („verwaltung“), die vorzeitig beendete Rolle und die Streichung von der Fachliste — beide Gründe
#: schreibt die Verwaltung frei. Den Grund der Streichung schreibt die Plattform derzeit nicht in die
#: Kette, er steht nur am Eintrag der Fachliste (GP-009, Entscheidung des Gründers offen); der Eintrag
#: hier sichert, dass ein Grund dieser Art öffentlich nie lesbar würde.
PERSONENGRUENDE = ("verwaltung", "rolle_beendet", "fachliste_gestrichen")

#: Je Art die Anfänge einer Begründung, die Personen nennt: Gibt Gruppe 2 einen Vorschlag zurück, setzt
#: sich der Grund aus den Stimmen mit dem Anzeigenamen der Prüfenden zusammen (GP-011). Die Rechnung des
#: Abstimmungs-Chats und der Austausch durch den Koordinationsrat nennen niemanden und bleiben lesbar.
PERSONENGRUENDE_ANFANG = {"vorschlag_zurueckgegeben": ("Gruppe 2:",)}

#: Je Art weitere Schlüssel: Der gemeldete Beitrag stünde sonst am Pranger, bevor die Verwaltung
#: über die Meldung entschieden hat — und danach, wenn sie keine Maßnahme ergriffen hat (GP-014).
#: Das Ausblenden bleibt lesbar; sein Vermerk steht ohnehin öffentlich am Beitrag. Die Berichtigung eines
#: Mandats zeigt den alten Wortlaut nicht: Berichtigt wird auch, weil er Persönliches enthielt; der neue
#: Wert steht ohnehin am Mandat.
JE_ART = {"beitrag_gemeldet": ("beitrag",), "meldung_ohne_massnahme": ("beitrag",), "mandat_berichtigt": ("alt",)}

#: Stimm-Ereignisse: Solange ihre Abstimmung läuft, tragen sie öffentlich nur das Tagesdatum (GP-210,
#: Fahrtenbuch D-D2b, § 5 Abs 3 lit e) — wer wann gestimmt hat, ließe sich sonst mit anderem Wissen
#: über den Zeitpunkt eingrenzen. Nach der Abstimmung steht die genaue Zeit wieder da.
STIMMARTEN = ("stimme", "stimme_geaendert", "personenwahl_stimme", "personenwahl_stimme_zurueckgenommen")


def _ist_kennung(wert, arten) -> bool:
    if isinstance(wert, bool):
        return False
    if int in arten and isinstance(wert, int):
        return True
    return list in arten and isinstance(wert, list) and any(
        isinstance(w, int) and not isinstance(w, bool) for w in wert
    )


def art_von(ereignis: dict) -> str:
    """Die Art des Eintrags. Zwei ältere Ereignisse tragen sie unter `art` statt `typ` (Beitrag
    gemeldet, Einschätzung beanstandet) — sie bleiben, wie sie sind, gelesen wird beides."""
    return str(ereignis.get("typ") or ereignis.get("art") or "")


def ereignis_oeffentlich(ereignis: dict) -> tuple[dict, bool]:
    """Das Ereignis, wie es öffentlich erscheint, und ob etwas geschwärzt wurde."""
    oeffentlich, geschwaerzt = dict(ereignis), False
    for schluessel, arten in KENNUNGEN.items():
        if _ist_kennung(oeffentlich.get(schluessel), arten):
            oeffentlich[schluessel], geschwaerzt = MASKE, True
    art = art_von(ereignis)
    for schluessel in (*IMMER, *JE_ART.get(art, ())):
        if oeffentlich.get(schluessel) not in (None, ""):
            oeffentlich[schluessel], geschwaerzt = MASKE, True
    grund = oeffentlich.get("grund")
    if grund and (art in PERSONENGRUENDE or str(grund).startswith(PERSONENGRUENDE_ANFANG.get(art, ()))):
        oeffentlich["grund"], geschwaerzt = MASKE, True
    return oeffentlich, geschwaerzt


def gesalzen(ereignis: dict) -> dict:
    """Beim Anhängen: ein schutzwürdiges Ereignis bekommt ein Zufallssalz, bevor es versiegelt wird."""
    if SALZ in ereignis or not ereignis_oeffentlich(ereignis)[1]:
        return ereignis
    return {**ereignis, SALZ: secrets.token_hex(16)}


def hash_oeffentlich(ereignis: dict | None) -> bool:
    """Ob der Hash eines Eintrags offen stehen darf: ja, wenn nichts geschwärzt ist oder ein Salz das
    Durchprobieren vereitelt."""
    if ereignis is None:
        return True
    return SALZ in ereignis or not ereignis_oeffentlich(ereignis)[1]


def mit_vorgaenger(eintraege):
    """Hängt an jeden Eintrag das Ereignis seines Vorgängers (`vorher`) — eine Abfrage. Die Reihenfolge
    der Kette ist die der laufenden Nummer: Die Eindeutigkeit von `vorgaenger` lässt keinen Eintrag mit
    kleinerer Nummer nach einem größeren an die Kette."""
    from verfahren.models import AuditEintrag

    davor = AuditEintrag.objects.filter(lfd__lt=OuterRef("lfd")).order_by("-lfd").values("ereignis")[:1]
    laufend = laufende_abstimmungen()
    return eintraege.annotate(
        vorher=Subquery(davor),
        abstimmung_laeuft=Case(
            When(Q(ereignis__typ__in=STIMMARTEN, ereignis__antrag__in=laufend), then=Value(True)),
            default=Value(False),
            output_field=BooleanField(),
        )
        if laufend
        else Value(False, output_field=BooleanField()),
    )


def laufende_abstimmungen() -> list[int]:
    """Die Anträge, deren Abstimmung läuft — solange die Phase nicht fortgeschrieben ist, auch kurz
    nach dem Fristende (dann bleibt es beim Tagesdatum, bis der Antrag weiterrückt)."""
    from plattform_core.phases import Phase
    from verfahren.models import Antrag

    return list(Antrag.objects.filter(phase=Phase.ABSTIMMUNG).values_list("pk", flat=True))


def _abstimmung_laeuft(eintrag) -> bool:
    if art_von(eintrag.ereignis) not in STIMMARTEN:
        return False
    if hasattr(eintrag, "abstimmung_laeuft"):
        return bool(eintrag.abstimmung_laeuft)
    return eintrag.ereignis.get("antrag") in laufende_abstimmungen()


def nur_tag(zeit: str) -> str:
    """Ein Zeitpunkt auf den Tag gekürzt (Ortszeit, ohne Uhrzeit): „2026-11-18T00:00:00“."""
    from datetime import datetime

    try:
        wann = datetime.fromisoformat(zeit)
    except (TypeError, ValueError):
        return str(zeit)[:10] + "T00:00:00"
    if timezone.is_aware(wann):
        wann = timezone.localtime(wann)
    return wann.date().isoformat() + "T00:00:00"


def eintrag_oeffentlich(eintrag) -> dict:
    """Ein Audit-Eintrag für Export und Seite: Hash, Vorgänger und der öffentliche Inhalt. Hash bzw.
    Vorgänger sind None, wo sie ein Durchprobieren erlaubten (`hash_oeffentlich`). Die Zeit ist die
    versiegelte im Ereignis (seit 0.45); nur ältere Einträge ohne sie zeigen die Spalte (GP-158)."""
    ereignis, geschwaerzt = ereignis_oeffentlich(eintrag.ereignis)
    vorher = getattr(eintrag, "vorher", None)
    versiegelt = eintrag.ereignis.get("zeit")
    zeit = versiegelt if isinstance(versiegelt, str) and versiegelt else eintrag.zeit.isoformat()
    tag = _abstimmung_laeuft(eintrag)
    if tag:
        zeit = nur_tag(zeit)
        if ereignis.get("zeit"):
            ereignis["zeit"] = nur_tag(ereignis["zeit"])
    return {
        "lfd": eintrag.lfd,
        "typ": art_von(eintrag.ereignis),
        "zeit": zeit,
        "nur_tag": tag,
        "vorgaenger": eintrag.vorgaenger if hash_oeffentlich(vorher) else None,
        "hash": eintrag.hash if hash_oeffentlich(eintrag.ereignis) else None,
        "geschwaerzt": geschwaerzt,
        "grund": ereignis.get("grund", ""),
        "ereignis": ereignis,
    }
