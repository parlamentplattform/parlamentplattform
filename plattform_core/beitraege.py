"""Beitragsabgleich (F-59, § 4 Abs 3): Kontoumsätze den Mitgliedern zuordnen.

Frameworkfrei und ohne Netzzugriff — hier lebt nur die Logik. Grundsätze:

* **Datensparsamkeit:** Diese Funktionen lesen Umsätze, geben aber nur weiter,
  was die Plattform wirklich braucht: Referenztreffer, Betrag, Buchungstag und
  ein einziges Ja/Nein („passt der Absendername zum Mitglied?"). IBAN und
  Klarname des Absenders verlassen den Abgleich nicht.
* **Nur Gutschriften:** Ausgaben des Vereinskontos gehen die Plattform nichts an.
* **Die Referenz entscheidet** (F-38): `DDOE-0042-A1B2C3` im Verwendungszweck.
  Banken stauchen Verwendungszwecke gern (Großschreibung, verlorene Trenner),
  deshalb wird tolerant gesucht und kanonisch zurückgegeben.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

# DDOE-0042-A1B2C3 — Trenner optional, Kleinschreibung erlaubt (Banken mangeln).
_REFERENZ = re.compile(r"DDOE[\s\-]?(\d{4})[\s\-]?([A-F0-9]{6})", re.IGNORECASE)


def referenz_finden(text: str) -> str | None:
    """Findet die Beitragsreferenz in einem Verwendungszweck — kanonisch formatiert."""
    treffer = _REFERENZ.search(text or "")
    if not treffer:
        return None
    return f"DDOE-{treffer.group(1)}-{treffer.group(2).upper()}"


def _vereinfachen(text: str) -> str:
    """Namen vergleichbar machen: Kleinschreibung, Umlaute auflösen, Akzente ab."""
    text = text.casefold().replace("ß", "ss")
    for a, b in (("ä", "ae"), ("ö", "oe"), ("ü", "ue")):
        text = text.replace(a, b)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def name_passt(absender: str, vorname: str, nachname: str) -> bool:
    """Prüft, ob der Absendername plausibel zum Mitglied gehört.

    Bewusst großzügig: Der Nachname (oder ersatzweise der Vorname) muss im
    Absendernamen vorkommen — Reihenfolge, Titel und Zweitnamen sind egal.
    Fehlt eine der beiden Seiten, gibt es nichts zu beanstanden (True):
    Ein Hinweis entsteht nur bei einer ERKENNBAREN Abweichung.
    """
    absender_norm = _vereinfachen(absender or "").strip()
    if not absender_norm:
        return True
    for teil in (nachname, vorname):
        teil_norm = _vereinfachen(teil or "").strip()
        if teil_norm:
            return teil_norm in absender_norm
    return True


@dataclass(frozen=True)
class Eingang:
    """Ein normalisierter Zahlungseingang — mehr weiß die Plattform nie."""

    umsatz_id: str
    betrag: Decimal
    waehrung: str
    gebucht_am: date
    verwendungszweck: str
    absender: str  # nur für den Namensvergleich; wird nie gespeichert


def umsatz_normalisieren(roh: dict) -> Eingang | None:
    """Bringt einen Umsatz aus dem Kontoinformationsdienst (Berlin-Group-Schema,
    z. B. GoCardless Bank Account Data) in unsere schmale Form.

    Gibt None zurück für alles, was kein Zahlungseingang ist (Abbuchungen,
    fremde Währungssalden, unlesbare Datensätze) — solche Umsätze werden
    kommentarlos übergangen und nirgends festgehalten.
    """
    try:
        betrag = Decimal(str(roh["transactionAmount"]["amount"]))
        waehrung = str(roh["transactionAmount"].get("currency", "EUR"))
    except (KeyError, TypeError, InvalidOperation):
        return None
    if betrag <= 0:
        return None

    umsatz_id = str(
        roh.get("internalTransactionId") or roh.get("transactionId") or ""
    ).strip()
    datum_roh = str(roh.get("bookingDate") or roh.get("valueDate") or "").strip()
    if not umsatz_id or not datum_roh:
        return None
    try:
        gebucht_am = date.fromisoformat(datum_roh[:10])
    except ValueError:
        return None

    zweck_teile = [str(roh.get("remittanceInformationUnstructured") or "")]
    zweck_teile += [str(t) for t in (roh.get("remittanceInformationUnstructuredArray") or [])]
    zweck_teile += [
        str(roh.get("remittanceInformationStructured") or ""),
        str(roh.get("creditorReference") or ""),
        str(roh.get("endToEndId") or ""),
    ]
    verwendungszweck = " ".join(t for t in zweck_teile if t).strip()

    return Eingang(
        umsatz_id=umsatz_id,
        betrag=betrag,
        waehrung=waehrung,
        gebucht_am=gebucht_am,
        verwendungszweck=verwendungszweck,
        absender=str(roh.get("debtorName") or "").strip(),
    )


def eingaenge_zuordnen(umsaetze: list[dict], referenzen: dict[str, int]) -> list[tuple[int, Eingang]]:
    """Ordnet rohe Umsätze den Mitgliedern zu: [(mitglieds_id, Eingang), …].

    `referenzen` bildet kanonische Beitragsreferenzen auf Mitglieds-IDs ab.
    Umsätze ohne (bekannte) Referenz fallen still heraus — Spenden und sonstige
    Eingänge sind Sache der Buchhaltung, nicht der Plattform.
    """
    treffer = []
    for roh in umsaetze:
        eingang = umsatz_normalisieren(roh)
        if eingang is None or eingang.waehrung != "EUR":
            continue
        referenz = referenz_finden(eingang.verwendungszweck)
        if referenz and referenz in referenzen:
            treffer.append((referenzen[referenz], eingang))
    return treffer
