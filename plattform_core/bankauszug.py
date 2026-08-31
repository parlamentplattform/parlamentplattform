"""Kontoauszug-Leser für den Beitragsabgleich (F-59): camt.053-XML und CSV.

Der sofort funktionierende Weg ohne Drittanbieter: Aus dem Online-Banking
(George: Umsatzliste exportieren) kommt eine Datei, hier wird sie gelesen.
Beide Leser geben Umsätze im selben schlanken Schema aus wie der
Kontoinformationsdienst (Berlin-Group-Feldnamen) — dahinter läuft exakt
derselbe Abgleich (`plattform_core.beitraege`), egal woher die Daten kommen.

* **camt.053** ist der ISO-20022-Standard-Kontoauszug; er trägt echte
  Umsatz-Kennungen (Dedupe ist exakt).
* **CSV** ist je Bank verschieden — der Leser sucht die Spalten tolerant über
  die Kopfzeile und bildet als Kennung einen Fingerabdruck aus Datum, Betrag
  und Verwendungszweck. Grenze (dokumentiert): Zwei völlig identische
  Zahlungen am selben Tag fallen im CSV zusammen; camt kennt das Problem nicht.
* Gelesen wird nur, was der Abgleich braucht; die Datei selbst wird nie
  gespeichert.
"""

from __future__ import annotations

import csv
import hashlib
import io
import re
from xml.etree import ElementTree

# --- camt.053 ----------------------------------------------------------------


def _text(knoten, pfad: str) -> str:
    gefunden = knoten.find(pfad)
    return (gefunden.text or "").strip() if gefunden is not None else ""


def camt053_lesen(inhalt: str) -> list[dict]:
    """Liest einen camt.053-Auszug (beliebige Versionsvariante) in Umsatz-Dicts."""
    wurzel = ElementTree.fromstring(inhalt)
    umsaetze = []
    for eintrag in wurzel.iter():
        if not eintrag.tag.endswith("}Ntry") and eintrag.tag != "Ntry":
            continue
        betrag = _text(eintrag, "{*}Amt")
        waehrung = ""
        amt = eintrag.find("{*}Amt")
        if amt is not None:
            waehrung = amt.get("Ccy", "")
        richtung = _text(eintrag, "{*}CdtDbtInd")
        datum = _text(eintrag, "{*}BookgDt/{*}Dt") or _text(eintrag, "{*}ValDt/{*}Dt")
        if richtung != "CRDT":
            continue  # nur Gutschriften — Ausgaben gehen die Plattform nichts an

        kennung = (
            _text(eintrag, "{*}AcctSvcrRef")
            or _text(eintrag, "{*}NtryRef")
            or _text(eintrag, "{*}NtryDtls/{*}TxDtls/{*}Refs/{*}AcctSvcrRef")
            or _text(eintrag, "{*}NtryDtls/{*}TxDtls/{*}Refs/{*}TxId")
        )
        zweck_teile = [
            k.text.strip()
            for k in eintrag.iter()
            if (k.tag.endswith("}Ustrd") or k.tag == "Ustrd") and k.text
        ]
        zweck_teile.append(_text(eintrag, "{*}NtryDtls/{*}TxDtls/{*}RmtInf/{*}Strd/{*}CdtrRefInf/{*}Ref"))
        zweck_teile.append(_text(eintrag, "{*}NtryDtls/{*}TxDtls/{*}Refs/{*}EndToEndId"))
        zweck = " ".join(t for t in zweck_teile if t)
        absender = _text(eintrag, "{*}NtryDtls/{*}TxDtls/{*}RltdPties/{*}Dbtr/{*}Nm") or _text(
            eintrag, "{*}NtryDtls/{*}TxDtls/{*}RltdPties/{*}Dbtr/{*}Pty/{*}Nm"
        )
        if not kennung:
            kennung = _fingerabdruck(datum, betrag, zweck)
        umsaetze.append(
            {
                "internalTransactionId": kennung,
                "transactionAmount": {"amount": betrag, "currency": waehrung or "EUR"},
                "bookingDate": datum,
                "remittanceInformationUnstructured": zweck,
                "debtorName": absender,
            }
        )
    return umsaetze


# --- CSV ---------------------------------------------------------------------

_SPALTEN = {
    "datum": ("buchungsdatum", "buchungstag", "datum", "booking date", "date"),
    "betrag": ("betrag", "amount", "umsatz"),
    "waehrung": ("währung", "waehrung", "currency"),
    "zweck": (
        "verwendungszweck",
        "zahlungsreferenz",
        "referenz",
        "buchungstext",
        "umsatztext",
        "details",
        "beschreibung",
        "reference",
    ),
    "name": ("auftraggeber", "teilnehmer", "partnername", "partner", "empfänger/auftraggeber", "name"),
}


def _fingerabdruck(*teile: str) -> str:
    norm = "|".join(re.sub(r"\s+", " ", (t or "")).strip().casefold() for t in teile)
    return "csv-" + hashlib.sha256(norm.encode()).hexdigest()[:32]


def _betrag_lesen(text: str) -> str:
    """Deutsche wie englische Schreibweise: „1.234,56" → „1234.56"."""
    t = text.strip().replace(" ", "").replace(" ", "").replace(" ", "")
    if "," in t and (t.rfind(",") > t.rfind(".")):
        t = t.replace(".", "").replace(",", ".")
    return t


def _datum_lesen(text: str) -> str:
    t = text.strip()
    m = re.match(r"(\d{1,2})\.(\d{1,2})\.(\d{4})", t)  # 24.08.2026
    if m:
        return f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}"
    return t[:10]  # ISO bleibt ISO


def csv_lesen(inhalt: str) -> list[dict]:
    """Liest einen Umsatz-CSV-Export (z. B. aus George) in Umsatz-Dicts.

    Trennzeichen und Spalten werden aus der Kopfzeile erkannt; ohne
    brauchbare Kopfzeile kommt eine leere Liste zurück (kein Ratespiel)."""
    probe = inhalt[:2000]
    trenner = ";" if probe.count(";") >= probe.count(",") else ","
    zeilen = list(csv.reader(io.StringIO(inhalt), delimiter=trenner))
    if not zeilen:
        return []

    kopf, start = None, 0
    for i, zeile in enumerate(zeilen[:10]):
        felder = [f.strip().casefold().lstrip("﻿") for f in zeile]
        if any(any(name in f for name in _SPALTEN["betrag"]) for f in felder) and any(
            any(name in f for name in _SPALTEN["datum"]) for f in felder
        ):
            kopf, start = felder, i + 1
            break
    if kopf is None:
        return []

    def spalte(art: str) -> int | None:
        for kandidat in _SPALTEN[art]:
            for i, f in enumerate(kopf):
                if kandidat in f:
                    return i
        return None

    idx = {art: spalte(art) for art in _SPALTEN}
    umsaetze = []
    for zeile in zeilen[start:]:
        if len(zeile) < 2:
            continue

        def wert(art: str, zeile: list[str] = zeile) -> str:
            i = idx.get(art)
            return zeile[i].strip() if i is not None and i < len(zeile) else ""

        datum = _datum_lesen(wert("datum"))
        betrag = _betrag_lesen(wert("betrag"))
        zweck = wert("zweck")
        umsaetze.append(
            {
                "internalTransactionId": _fingerabdruck(datum, betrag, zweck),
                "transactionAmount": {"amount": betrag, "currency": wert("waehrung") or "EUR"},
                "bookingDate": datum,
                "remittanceInformationUnstructured": zweck,
                "debtorName": wert("name"),
            }
        )
    return umsaetze


def auszug_lesen(inhalt: str) -> list[dict]:
    """Erkennt das Format selbst: XML (camt.053) oder CSV."""
    anfang = inhalt.lstrip()[:200]
    if anfang.startswith("<"):
        try:
            return camt053_lesen(inhalt)
        except ElementTree.ParseError:
            return []
    return csv_lesen(inhalt)
