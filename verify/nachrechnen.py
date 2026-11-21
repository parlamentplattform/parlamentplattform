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

Vertrauensfrage (§ 7 Abs 10 — Ja heißt „Vertrauen versagen“, Nein heißt „Vertrauen aussprechen“;
gerechnet wie ein Sachantrag: „angenommen“ heißt „Vertrauensfrage verloren“, alles andere
— auch eine verfehlte Mindestbeteiligung — heißt „gewonnen“). Der Block "vertrauensfrage" ist
Einordnung, nicht Eingabe der Auszählung: Steht dort "art": "bestaetigung", ist es der
Bestätigungsantrag nach lit f Z 3 — gleiche Auszählung, das Ergebniswort lautet dann
„bestaetigt“ (Annahme) oder „nicht_bestaetigt“ (Ablehnung), wie in rechenschaft.json:
{
  "art": "vertrauensfrage",
  "vertrauensfrage": {"art": "vertrauensfrage" | "bestaetigung", …},
  "policy": {"mindestbeteiligung": 0.05, "mehrheitsbasis": "ja_nein"},
  "stimmberechtigte": 1234,
  "stimmen": [{"pseudonym": "…", "stimme": "ja"}, …]
}

Mandats-Kandidatur (Zustimmungswahl, § 7 Abs 1):
{
  "art": "mandat",
  "policy": {"mindestbeteiligung": 0.05},
  "stimmberechtigte": 1234,
  "bewerbungen": [{"bewerbung": 7, "name": "…", "eingereicht_am": "…", "zurueckgezogen": false}, …],
  "zustimmungen": [{"pseudonym": "…", "bewerbung": 7, "zurueckgenommen": false}, …]
}
Eine zurückgenommene Zustimmung bleibt als Zeile stehen (nichts wird gelöscht) und trägt
"zurueckgenommen": true; ältere Exporte nennen stattdessen "zurueckgenommen_am" mit einer
Zeitangabe. Beides liest dieses Skript; gezählt wird eine solche Zeile nicht.

Regeln der Zustimmungswahl, wie die Plattform sie rechnet (plattform_core/tally.py):
jede Person darf jeder Bewerbung höchstens einmal zustimmen, mehreren Bewerbungen
aber schon; zurückgezogene Bewerbungen und die Zustimmungen zu ihnen zählen nicht;
zurückgenommene Zustimmungen zählen nicht, weder für die Bewerbung noch für die Beteiligung;
gereiht wird nach Zustimmungen, bei Gleichstand nach Einreichreihenfolge; die
Beteiligung ist die Zahl der Pseudonyme mit mindestens einer zählenden Zustimmung;
die Mindestbeteiligung gilt wie bei Sachfragen; gewählt ist der erste Platz, wenn
er mindestens eine Zustimmung hat.

Abgleich mit der Audit-Spur: Jeder Export nennt zusätzlich "stichtag" (der Tag, an dem die Zahl der
Stimmberechtigten festgestellt wurde) und im Block "audit" die Audit-Einträge des Antrags. Das Skript
vergleicht den Export damit (siehe nenner_gegen_kette und stimmliste_gegen_kette). Ältere Exporte ohne
diese Angaben rechnet es wie bisher und weist aus, was nicht versiegelt ist. Mehr Stimmen als
Stimmberechtigte sind in jedem Export ein Fehler.
"""

import hashlib
import json
import sys
from fractions import Fraction


def _beteiligung_erreicht(daten, abgegeben, berechtigte, schwelle):
    if berechtigte == 0:
        gebiet = daten.get("teilnahmegebiet") or {}
        if gebiet.get("ebene") in ("gemeinde", "bezirk", "land") and not abgegeben:
            return False
        raise SystemExit("FEHLER: Nenner 0 ohne gültigen leeren örtlichen Kreis.")
    if berechtigte < 0:
        raise SystemExit("FEHLER: Negativer Nenner.")
    if abgegeben > berechtigte:
        # Es können nicht mehr Menschen stimmen, als bei Abstimmungsbeginn als stimmberechtigt
        # festgestellt wurden — eine solche Liste wird nicht ausgezählt.
        raise SystemExit(f"FEHLER: mehr Stimmen als Stimmberechtigte ({abgegeben} bei {berechtigte}).")
    return Fraction(abgegeben, berechtigte) >= schwelle


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
    beteiligung_ok = _beteiligung_erreicht(daten, abgegeben, berechtigte, schwelle)
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
    zurueckgenommen = 0
    for eintrag in daten["zustimmungen"]:
        paar = (eintrag["pseudonym"], int(eintrag["bewerbung"]))
        if paar in gesehen:
            raise SystemExit(f"FEHLER: Zustimmung doppelt: Pseudonym {paar[0]} zu Bewerbung {paar[1]}")
        gesehen.add(paar)
        if eintrag.get("zurueckgenommen") or eintrag.get("zurueckgenommen_am"):
            zurueckgenommen += 1
            continue  # zurückgenommene Zustimmung: steht im Export, zählt aber nicht
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
    beteiligung_ok = _beteiligung_erreicht(daten, beteiligung, berechtigte, schwelle)
    gewaehlt = reihung[0] if reihung and beteiligung_ok and zaehler[reihung[0]] > 0 else None
    return {
        "art": "mandat",
        "plaetze": plaetze,
        "beteiligung": beteiligung,
        "zurueckgenommen": zurueckgenommen,
        "stimmberechtigte": berechtigte,
        "beteiligung_erreicht": beteiligung_ok,
        "angenommen": gewaehlt is not None,
        "gewaehlt": gewaehlt,
        "gewaehlt_name": namen.get(gewaehlt) if gewaehlt is not None else None,
    }


def audit_nachrechnen(eintraege: list) -> dict:
    """Rechnet die Audit-Einträge des Exports nach (Block "audit", seit 0.52.0).

    Jeder Eintrag trägt seinen Inhalt ("ereignis"), den Hash seines Vorgängers und seinen eigenen Hash.
    Sein Hash muss SHA-256 über den Vorgänger-Hash und den Inhalt sein — der Inhalt als JSON mit
    sortierten Schlüsseln, ohne Leerzeichen, UTF-8. Stimmt das, wurde der Eintrag seit dem Schreiben
    nicht verändert. Die Einträge eines Antrags liegen nicht nebeneinander in der Kette (dazwischen
    stehen andere Anträge), deshalb wird jeder für sich geprüft; die ganze Kette prüft die Plattform
    täglich, ihr Kopf steht in /kennzahlen.json. Einträge mit "geschwaerzt": true enthalten ausgeblendete
    personenbezogene Werte („•“) und lassen sich von außen nicht nachrechnen — sie werden gezählt."""
    geprueft, geschwaerzt = 0, 0
    for eintrag in eintraege:
        if eintrag.get("geschwaerzt") or not eintrag.get("hash") or not eintrag.get("vorgaenger"):
            geschwaerzt += 1
            continue
        inhalt = json.dumps(eintrag["ereignis"], sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        h = hashlib.sha256()
        h.update(eintrag["vorgaenger"].encode("ascii"))
        h.update(inhalt.encode("utf-8"))
        if h.hexdigest() != eintrag["hash"]:
            raise SystemExit(f"FEHLER: Audit-Eintrag {eintrag.get('lfd')} passt nicht zu seinem Hash.")
        geprueft += 1
    return {"audit_nachgerechnet": geprueft, "audit_geschwaerzt": geschwaerzt}


def nenner_gegen_kette(daten: dict) -> dict:
    """Vergleicht die Zahl der Stimmberechtigten und ihren Stichtag mit der Audit-Spur des Exports.

    Die Zahl der Stimmberechtigten entscheidet über die Mindestbeteiligung. Die Plattform stellt sie
    bei Abstimmungsbeginn fest und schreibt sie samt Stichtag in das Audit-Ereignis "phasenwechsel",
    mit dem die Abstimmung beginnt ("neue_phase": "abstimmung", Felder "stimmberechtigte" und
    "stichtag"). Nennt der Export eine andere Zahl oder einen anderen Stichtag als dieses Ereignis,
    wurde eines von beiden nachträglich verändert — das Skript bricht ab.

    Abstimmungen, die vor dieser Prüfung begonnen haben, tragen die Felder im Ereignis nicht. Dann ist
    der Nenner nicht versiegelt ("nenner_versiegelt": False); das ist kein Fehler, nur weniger Nachweis."""
    versiegelt = False
    for eintrag in daten.get("audit") or []:
        ereignis = eintrag.get("ereignis") or {}
        if eintrag.get("typ") != "phasenwechsel" or ereignis.get("neue_phase") != "abstimmung":
            continue
        if "stimmberechtigte" not in ereignis:
            continue  # Ereignis von vor dieser Prüfung: nicht versiegelt
        versiegelt = True
        if ereignis["stimmberechtigte"] != daten.get("stimmberechtigte"):
            raise SystemExit(
                f"FEHLER: Stimmberechtigte im Export ({daten.get('stimmberechtigte')}) weichen vom "
                f"Audit-Ereignis des Abstimmungsbeginns ab ({ereignis['stimmberechtigte']}, Eintrag {eintrag.get('lfd')})."
            )
        if ereignis.get("stichtag") != daten.get("stichtag"):
            raise SystemExit(
                f"FEHLER: Stichtag im Export ({daten.get('stichtag')}) weicht vom "
                f"Audit-Ereignis des Abstimmungsbeginns ab ({ereignis.get('stichtag')}, Eintrag {eintrag.get('lfd')})."
            )
    return {"nenner_versiegelt": versiegelt}


def stimmliste_pruefsumme(daten: dict) -> str:
    """Die Prüfsumme der Stimmliste, wie die Plattform sie bildet (plattform_core/tally.py):
    je Stimmzettel eine Zeile, die Zeilen sortiert, als JSON ohne Leerzeichen, darüber SHA-256.

    Sachfragen: je Stimme [Pseudonym, Stimme]. Zustimmungswahl: je Bewerbung
    ["bewerbung", Platz in der Einreichreihenfolge, Nummer, zurückgezogen] und je Zustimmung
    ["zustimmung", Pseudonym, Bewerbung, zurückgenommen] — dort entscheiden Reihenfolge und Rückzüge
    mit über das Ergebnis."""
    if daten.get("art", "sache") == "mandat":
        zeilen = [
            ["bewerbung", platz, int(b["bewerbung"]), bool(b.get("zurueckgezogen", False))]
            for platz, b in enumerate(daten["bewerbungen"], start=1)
        ]
        zeilen += [
            ["zustimmung", z["pseudonym"], int(z["bewerbung"]), bool(z.get("zurueckgenommen") or z.get("zurueckgenommen_am"))]
            for z in daten["zustimmungen"]
        ]
    else:
        zeilen = [[s["pseudonym"], s["stimme"]] for s in daten["stimmen"]]
    text = json.dumps(sorted(zeilen), separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def stimmliste_gegen_kette(daten: dict) -> dict:
    """Vergleicht die Stimmliste des Exports mit dem, was die Audit-Spur über sie festhält.

    Mit dem Ergebnis schreibt die Plattform einen Abschluss in die Kette: Das Ereignis "phasenwechsel",
    das das Ergebnis feststellt, nennt die Zahl der gezählten Stimmzettel ("stimmzettel"), die Prüfsumme
    der Stimmliste ("stimmliste_sha256") und die Zahl der Stimm-Ereignisse, die die Kette bis dahin
    führte ("stimmereignisse"). Das Skript bricht ab, wenn
    - die Prüfsumme der Liste im Export nicht zu diesem Abschluss passt (ein Stimmzettel wurde
      geändert, hinzugefügt oder entfernt),
    - die Zahl der Stimmzettel eine andere ist als im Abschluss, oder
    - die Audit-Spur nicht so viele Stimm-Ereignisse zeigt, wie Stimmzettel gezählt wurden. Bei
      Sachfragen sind das die Ereignisse "stimme"; bei der Zustimmungswahl die Ereignisse
      "personenwahl_stimme" abzüglich "personenwahl_stimme_zurueckgenommen".

    Abstimmungen, die vor dieser Prüfung endeten, haben keinen Abschluss mit Prüfsumme. Dann ist die
    Stimmliste nicht versiegelt ("stimmliste_versiegelt": False) — kein Fehler, nur weniger Nachweis."""
    audit = daten.get("audit") or []
    abschluesse = [
        e for e in audit if e.get("typ") == "phasenwechsel" and "stimmliste_sha256" in (e.get("ereignis") or {})
    ]
    if not abschluesse:
        return {"stimmliste_versiegelt": False}
    abschluss = abschluesse[-1]["ereignis"]
    nummer = abschluesse[-1].get("lfd")
    if stimmliste_pruefsumme(daten) != abschluss["stimmliste_sha256"]:
        raise SystemExit(
            f"FEHLER: Die Prüfsumme der Stimmliste passt nicht zum Abschluss in der Audit-Spur (Eintrag {nummer})."
        )
    if daten.get("art", "sache") == "mandat":
        zettel = sum(
            1 for z in daten["zustimmungen"] if not (z.get("zurueckgenommen") or z.get("zurueckgenommen_am"))
        )
        ereignisse = sum(1 for e in audit if e.get("typ") == "personenwahl_stimme") - sum(
            1 for e in audit if e.get("typ") == "personenwahl_stimme_zurueckgenommen"
        )
    else:
        zettel = len(daten["stimmen"])
        ereignisse = sum(1 for e in audit if e.get("typ") == "stimme")
    if zettel != abschluss.get("stimmzettel"):
        raise SystemExit(
            f"FEHLER: {zettel} Stimmzettel im Export, der Abschluss in der Audit-Spur nennt {abschluss.get('stimmzettel')}."
        )
    if "stimmereignisse" in abschluss and not (ereignisse == abschluss["stimmereignisse"] == zettel):
        raise SystemExit(
            f"FEHLER: {zettel} Stimmzettel, aber {ereignisse} Stimm-Ereignisse in der Audit-Spur "
            f"(der Abschluss nennt {abschluss['stimmereignisse']})."
        )
    return {"stimmliste_versiegelt": True}


def nachrechnen(daten: dict) -> dict:
    """Zählt aus und vergleicht danach den Export mit seiner Audit-Spur."""
    ergebnis = auszaehlung_nachrechnen(daten)
    ergebnis.update(nenner_gegen_kette(daten))
    ergebnis.update(stimmliste_gegen_kette(daten))
    return ergebnis


def auszaehlung_nachrechnen(daten: dict) -> dict:
    """Verzweigt nach der Antragsart des Exports. Eine unbekannte Art wird abgewiesen —
    ein Skript, das etwas anderes still als Sachfrage mit 0 Stimmen rechnet, wäre
    schlimmer als eines, das nicht rechnet (§ 5 Abs 8)."""
    art = daten.get("art", "sache")
    if art == "sache":
        return sachfrage_nachrechnen(daten)
    if art == "mandatsfrage":
        # § 7 Abs 9: dieselben Regeln wie eine Sachfrage — nur der Weg dorthin war kürzer.
        return {**sachfrage_nachrechnen(daten), "art": "mandatsfrage"}
    if art == "vertrauensfrage":
        # § 7 Abs 10 lit e: ausgezählt wie eine Sachfrage; „angenommen“ heißt verloren, sonst gewonnen.
        # Beim Bestätigungsantrag (lit f Z 3, Block vertrauensfrage.art) heißt Annahme „bestätigt“ —
        # dieselben Wörter wie die Plattform, sonst sähe der Prüfende einen Widerspruch, wo keiner ist.
        ergebnis = sachfrage_nachrechnen(daten)
        art_fach = (daten.get("vertrauensfrage") or {}).get("art", "vertrauensfrage")
        if art_fach == "bestaetigung":
            wort = "bestaetigt" if ergebnis["angenommen"] else "nicht_bestaetigt"
        else:
            wort = "verloren" if ergebnis["angenommen"] else "gewonnen"
        return {**ergebnis, "art": "vertrauensfrage", "vertrauensfrage": wort}
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
        daten = json.load(f)
    ergebnis = nachrechnen(daten)
    if "audit" in daten:
        ergebnis.update(audit_nachrechnen(daten["audit"]))
    for schluessel, wert in ergebnis.items():
        if schluessel == "plaetze":
            print("plaetze:")
            for platz in wert:
                print(f"  {platz['platz']}. Bewerbung {platz['bewerbung']} ({platz['name']}): {platz['zustimmungen']}")
        else:
            print(f"{schluessel}: {wert}")
    print("\nVergleichen Sie diese Werte mit der veröffentlichten Ergebnisseite.")
