#!/usr/bin/env python3
"""Unabhängiges Nachrechnen eines Abstimmungsergebnisses (§ 5 Abs 8).

Dieses Skript benutzt AUSSCHLIESSLICH die Python-Standardbibliothek und ist
bewusst so geschrieben, dass es ohne Informatikstudium lesbar ist. Es ist die
zweite, unabhängige Implementierung der Auszählung — stimmen beide überein,
ist ein Fehler in einer von beiden nahezu ausgeschlossen.

Aufruf:
    python3 verify/nachrechnen.py export.json

Erwartetes Format (der JSON-Export jeder Ergebnisseite):
{
  "policy": {"mindestbeteiligung": 0.05, "mehrheitsbasis": "ja_nein"},
  "stimmberechtigte": 1234,
  "stimmen": [{"pseudonym": "…", "stimme": "ja"}, …]
}
"""
import json
import sys
from fractions import Fraction


def nachrechnen(daten: dict) -> dict:
    policy = daten["policy"]
    berechtigte = int(daten["stimmberechtigte"])
    gesehen = set()
    zaehler = {"ja": 0, "nein": 0, "enthaltung": 0}
    for eintrag in daten["stimmen"]:
        p = eintrag["pseudonym"]
        if p in gesehen:
            raise SystemExit(f"FEHLER: Pseudonym doppelt: {p}")
        gesehen.add(p)
        wert = eintrag["stimme"]
        if wert not in zaehler:
            raise SystemExit(f"FEHLER: unbekannter Stimmwert: {wert}")
        zaehler[wert] += 1

    abgegeben = sum(zaehler.values())
    schwelle = Fraction(str(policy["mindestbeteiligung"]))
    beteiligung_ok = Fraction(abgegeben, berechtigte) >= schwelle
    if policy.get("mehrheitsbasis", "ja_nein") == "ja_nein":
        mehrheit = zaehler["ja"] > zaehler["nein"]
    else:
        mehrheit = 2 * zaehler["ja"] > abgegeben
    return {
        **zaehler,
        "abgegeben": abgegeben,
        "stimmberechtigte": berechtigte,
        "beteiligung_erreicht": beteiligung_ok,
        "angenommen": beteiligung_ok and mehrheit,
    }


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as f:
        ergebnis = nachrechnen(json.load(f))
    for schluessel, wert in ergebnis.items():
        print(f"{schluessel}: {wert}")
    print("\n→ Vergleichen Sie diese Werte mit der veröffentlichten Ergebnisseite.")
