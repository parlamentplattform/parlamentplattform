"""Eine bekannte amtliche Aggregatzeile lesen, keine Kapazität oder Prognose bilden."""

import re

VERSION = 1
DATENJAHR = 2025
REIHUNG = ("-datenjahr", "bereich", "-pk")
ABRUF_REIHUNG = ("-beendet_am", "-pk")
_ZAHL = r"(?:0|[1-9][0-9]{0,2}(?:\.[0-9]{3})*)"


def aus_text(text):
    if not isinstance(text, str) or not text or len(text) > 20_000:
        raise ValueError("personal_text")
    text = text.replace("\u00a0", " ")
    if not re.match(r"\s*75\s*Das Personal des Bundes 2026\b", text):
        raise ValueError("personal_seite")
    kopf = re.search(
        r"Tabelle 20: Bundespersonal nach Art des Dienstverhältnisses\*\s+"
        r"Jahr\s+Beamtinnen\s+und Beamte\s+vertragliches\s+Personal\s+Gesamtpersonalstand\s*",
        text,
    )
    if kopf is None:
        raise ValueError("personal_spalten")
    tabellenende = text.find("* in VBÄ", kopf.end())
    if tabellenende < 0:
        raise ValueError("personal_einheit")
    zeilen = text[kopf.end():tabellenende].splitlines()
    kandidaten = [s.strip() for s in zeilen if re.match(r"2025(?:\s|$)", s.strip())]
    if len(kandidaten) != 1:
        raise ValueError("personal_jahr")
    treffer = re.fullmatch(rf"2025\s+({_ZAHL})\s+({_ZAHL})\s+({_ZAHL})", kandidaten[0], flags=re.ASCII)
    if treffer is None:
        raise ValueError("personal_zahlen")
    beamte, vertragliche, gesamt = (int(s.replace(".", "")) for s in treffer.groups())
    if beamte + vertragliche != gesamt or gesamt == 0:
        raise ValueError("personal_summe")
    return {"datenjahr": DATENJAHR, "einheit": "VBÄ", "beamte": beamte,
            "vertragliches_personal": vertragliche, "gesamt": gesamt}
