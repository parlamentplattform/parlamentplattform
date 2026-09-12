#!/usr/bin/env python3
"""Unabhängiges Nachrechnen eines Abstimmungsergebnisses (§ 5 Abs 8).

Dieses Skript benutzt AUSSCHLIESSLICH die Python-Standardbibliothek und ist
bewusst so geschrieben, dass es ohne Informatikstudium lesbar ist. Es ist die
zweite, unabhängige Implementierung der Auszählung — stimmen beide überein,
ist ein Fehler in einer von beiden nahezu ausgeschlossen.

Aufruf:
    python3 verify/nachrechnen.py export.json

Erwartetes Format (der JSON-Export jeder Ergebnisseite):

Sachantrag (Ja/Nein/Enthaltung):
{
  "art": "sache",
  "policy": {"mindestbeteiligung": 0.05, "mehrheitsbasis": "ja_nein"},
  "stimmberechtigte": 1234,
  "stimmen": [{"pseudonym": "…", "stimme": "ja"}, …]
}

Mandatsfrage (§ 7 Abs 9 — die Ja-Nein-Frage eines Mandatars, ohne Unterstützungs- und
Beratungsphase; gerechnet wird sie genau wie ein Sachantrag):
{
  "art": "mandatsfrage",
  "policy": {"mindestbeteiligung": 0.05, "mehrheitsbasis": "ja_nein"},
  "stimmberechtigte": 1234,
  "stimmen": [{"pseudonym": "…", "stimme": "nein"}, …]
}

Mandats-Kandidatur (Zustimmungswahl, § 7 Abs 1):
{
  "art": "mandat",
  "policy": {"mindestbeteiligung": 0.05},
  "stimmberechtigte": 1234,
  "bewerbungen": [{"bewerbung": 7, "name": "…", "eingereicht_am": "…", "zurueckgezogen": false}, …],
  "zustimmungen": [{"pseudonym": "…", "bewerbung": 7}, …]
}

Regeln der Zustimmungswahl, wie die Plattform sie rechnet (plattform_core/tally.py):
jede Person darf jeder Bewerbung höchstens einmal zustimmen, mehreren Bewerbungen
aber schon; zurückgezogene Bewerbungen und die Zustimmungen zu ihnen zählen nicht;
gereiht wird nach Zustimmungen, bei Gleichstand nach Einreichreihenfolge; die
Beteiligung ist die Zahl der Pseudonyme mit mindestens einer zählenden Zustimmung;
die Mindestbeteiligung gilt wie bei Sachfragen; gewählt ist der erste Platz, wenn
er mindestens eine Zustimmung hat.
"""

import json
import sys
from fractions import Fraction


def sachfrage_nachrechnen(daten: dict) -> dict:
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
        "art": "sache",
        **zaehler,
        "abgegeben": abgegeben,
        "stimmberechtigte": berechtigte,
        "beteiligung_erreicht": beteiligung_ok,
        "angenommen": beteiligung_ok and mehrheit,
    }


def personenwahl_nachrechnen(daten: dict) -> dict:
    policy = daten["policy"]
    berechtigte = int(daten["stimmberechtigte"])

    # Wählbar sind nur nicht zurückgezogene Bewerbungen, in Einreichreihenfolge.
    waehlbar = []  # Liste der Bewerbungsnummern, so wie sie eingereicht wurden
    namen = {}
    for eintrag in daten["bewerbungen"]:
        nummer = int(eintrag["bewerbung"])
        namen[nummer] = eintrag.get("name", f"#{nummer}")
        if not eintrag.get("zurueckgezogen", False):
            waehlbar.append(nummer)

    zaehler = {nummer: 0 for nummer in waehlbar}
    gesehen = set()
    waehler = set()
    for eintrag in daten["zustimmungen"]:
        paar = (eintrag["pseudonym"], int(eintrag["bewerbung"]))
        if paar in gesehen:
            raise SystemExit(f"FEHLER: Zustimmung doppelt: Pseudonym {paar[0]} zu Bewerbung {paar[1]}")
        gesehen.add(paar)
        if paar[1] not in zaehler:
            continue  # Zustimmung zu einer zurückgezogenen Bewerbung: zählt nicht
        zaehler[paar[1]] += 1
        waehler.add(paar[0])

    # Reihung: meiste Zustimmungen zuerst; bei Gleichstand die früher eingereichte Bewerbung.
    reihung = sorted(waehlbar, key=lambda nummer: (-zaehler[nummer], waehlbar.index(nummer)))
    plaetze = [
        {"platz": platz, "bewerbung": nummer, "name": namen[nummer], "zustimmungen": zaehler[nummer]}
        for platz, nummer in enumerate(reihung, start=1)
    ]
    beteiligung = len(waehler)
    schwelle = Fraction(str(policy["mindestbeteiligung"]))
    beteiligung_ok = Fraction(beteiligung, berechtigte) >= schwelle
    gewaehlt = reihung[0] if reihung and beteiligung_ok and zaehler[reihung[0]] > 0 else None
    return {
        "art": "mandat",
        "plaetze": plaetze,
        "beteiligung": beteiligung,
        "stimmberechtigte": berechtigte,
        "beteiligung_erreicht": beteiligung_ok,
        "angenommen": gewaehlt is not None,
        "gewaehlt": gewaehlt,
        "gewaehlt_name": namen.get(gewaehlt) if gewaehlt is not None else None,
    }


def nachrechnen(daten: dict) -> dict:
    """Verzweigt nach der Antragsart des Exports. Eine unbekannte Art wird abgewiesen —
    ein Skript, das etwas anderes still als Sachfrage mit 0 Stimmen rechnet, wäre
    schlimmer als eines, das nicht rechnet (§ 5 Abs 8)."""
    art = daten.get("art", "sache")
    if art == "sache":
        return sachfrage_nachrechnen(daten)
    if art == "mandatsfrage":
        # § 7 Abs 9: dieselben Regeln wie eine Sachfrage — nur der Weg dorthin war kürzer.
        return {**sachfrage_nachrechnen(daten), "art": "mandatsfrage"}
    if art == "mandat":
        return personenwahl_nachrechnen(daten)
    raise SystemExit(f"FEHLER: Antragsart {art!r} kennt dieses Skript nicht.")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    # Windows-Konsolen können nicht jedes Zeichen darstellen — lieber ein Ersatzzeichen als ein Absturz.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(errors="backslashreplace")
    with open(sys.argv[1], encoding="utf-8") as f:
        ergebnis = nachrechnen(json.load(f))
    for schluessel, wert in ergebnis.items():
        if schluessel == "plaetze":
            print("plaetze:")
            for platz in wert:
                print(f"  {platz['platz']}. Bewerbung {platz['bewerbung']} ({platz['name']}): {platz['zustimmungen']}")
        else:
            print(f"{schluessel}: {wert}")
    print("\nVergleichen Sie diese Werte mit der veröffentlichten Ergebnisseite.")
