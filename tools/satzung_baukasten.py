"""Erzeugt den Satzungs-Baukasten für Schwesterparteien (FB-M7, § 12 Abs 2).

    python tools/satzung_baukasten.py            # schreibt docs/partner/SATZUNG_BAUKASTEN.md
    python tools/satzung_baukasten.py --pruefen  # Rückgabe 1, wenn die Datei nicht mehr aktuell ist

Quelle ist die Satzung der DDÖ (docs/fahrtenbuch/Satzung_DDOE_2.5_Entwurf.md) — sie selbst bleibt
unangetastet (nur der Gründer ändert sie). Der Baukasten ersetzt die österreichischen Eigennamen und
Rechtsbezüge durch Platzhalter und stellt einen Kommentar voran, welche Paragrafen den Kern des
Modells bilden und welche Landesrecht sind. Deterministisch: gleiche Quelle, gleiche Ausgabe.
"""

from __future__ import annotations

import sys
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
QUELLE = WURZEL / "docs" / "fahrtenbuch" / "Satzung_DDOE_2.5_Entwurf.md"
ZIEL = WURZEL / "docs" / "partner" / "SATZUNG_BAUKASTEN.md"

# Reihenfolge ist wichtig: längere Fundstellen zuerst.
ERSETZUNGEN = [
    (
        "Der Sitz der Partei ist Unterfreundorf, Gemeinde Sankt Marienkirchen an der Polsenz, "
        "Bundesland Oberösterreich.",
        "Der Sitz der Partei ist [SITZ].",
    ),
    ("Direkte Demokratie Österreich", "[PARTEINAME]"),
    ("Republik Österreich", "[LAND]"),
    ("Österreich", "[LAND]"),
    ("DDÖ", "[KÜRZEL]"),
    ("Bundesminister für Inneres", "[REGISTRIERUNGSBEHÖRDE]"),
    ("Parteiengesetz 2012", "[PARTEIENGESETZ]"),
    ("Nationalrat", "[PARLAMENT]"),
    ("Landtag", "[LANDESPARLAMENT]"),
    (" Euro", " [WÄHRUNG]"),
    ("## Anhang: Punkte für die anwaltliche Prüfung", "## Anhang: Punkte für die rechtliche Prüfung im eigenen Land"),
]

PLATZHALTER = [
    ("[PARTEINAME]", "voller Name der Partei"),
    ("[KÜRZEL]", "Kurzbezeichnung"),
    ("[LAND]", "Staat, in dem die Partei wirkt"),
    ("[SITZ]", "Ort, Gemeinde, Region des Sitzes"),
    ("[REGISTRIERUNGSBEHÖRDE]", "Behörde, bei der die Satzung hinterlegt oder die Partei registriert wird"),
    ("[PARTEIENGESETZ]", "das Parteien- oder Vereinsrecht des Landes samt Fundstelle"),
    ("[PARLAMENT]", "das nationale Parlament"),
    ("[LANDESPARLAMENT]", "die Parlamente der Gliedstaaten oder Regionen — entfällt in Einheitsstaaten"),
    ("[WÄHRUNG]", "Landeswährung"),
]

KERN = [
    ("§ 2 Ziel, Zweck und Wesen", "Kern", "Werkzeug-Grundsatz, keine Programme, offene Reihung — unverändert übernehmen"),
    ("§ 3 Grundsätze des Wesenskerns", "Kern", "unverändert übernehmen"),
    ("§ 5 ParlamentPlattform und Verfahren", "Kern", "Phasen, Einfrieren der Regeln, Nachrechenbarkeit, die vier Bereiche, WeicherFilter, Entwurfsschleife — unverändert; Zahlenwerte gehören in die eigene Verfahrensordnung"),
    ("§ 6 Organe", "Kern", "Rollen, Expertenrat, Koordinationsrat, Zukunftswerkstatt, Umsetzungsregister — Namen der Organe dürfen dem Landesrecht folgen"),
    ("§ 7 Mandaterteilung", "Kern", "Kandidaturen als Anträge, Mandatsvereinbarung, Rechenschaft — Wahlrecht des Landes beachten"),
    ("§ 9 Stufen der Zielverwirklichung", "Kern", "Zeithorizont und Stufen ans Land anpassen"),
    ("§ 12 Internationale Zusammenarbeit", "Kern", "Abs 5 (Arbeitsweise: Schema, offene Werkzeuge, Austausch) unverändert; Abs 3 (Spenden aus dem Ausland) nach Landesrecht"),
    ("§ 1 Name, Sitz, Vertretung", "Landesrecht", "Platzhalter füllen; Vertretungsregel nach Landesrecht"),
    ("§ 4 Mitgliedschaft", "Landesrecht", "Beitritt, Beitrag, Anwartschaft: Grundsatz „ein Konto je Mensch, geprüfte Identität“ behalten, Fristen und Beiträge frei"),
    ("§ 8 Transparenz, Ethik, Datenschutz", "Landesrecht", "Datenschutzrecht des Landes einsetzen (DSGVO oder Entsprechung); der Grundsatz bleibt"),
    ("§ 10 Finanzierung", "Landesrecht", "Parteienfinanzierung des Landes"),
    ("§ 11 Schiedsgericht", "Landesrecht", "Streitbeilegung nach Landesrecht"),
    ("§ 13 Teilhabe, Barrierefreiheit", "Kern + Landesrecht", "Präsenz- und Schriftverfahren behalten; Identitätsfeststellung nach den Mitteln des Landes"),
    ("§ 14 Gliederung", "Landesrecht", "der territorialen Gliederung des Landes folgen"),
    ("§ 15–17 Satzungsänderung, Auflösung, Inkrafttreten", "Landesrecht", "Mehrheiten und Fristen nach Landesrecht; Änderungen bleiben Beschlüsse der Mitgliederversammlung auf der Plattform"),
]


def erzeugen() -> str:
    quelle = QUELLE.read_text(encoding="utf-8")
    anfang = quelle.index("## § 1 ")
    rumpf = quelle[anfang:]
    for alt, neu in ERSETZUNGEN:
        rumpf = rumpf.replace(alt, neu)
    kopf = [
        "# Satzungs-Baukasten — Vorlage für eine Schwesterpartei",
        "",
        "*Abgeleitet aus der Satzung der DDÖ, Version 2.5 (Entwurf vom 1. September 2026), erzeugt von "
        "`tools/satzung_baukasten.py`. Die Satzung der DDÖ selbst ändert nur ihr Gründer; diese Vorlage ist "
        "ein Vorschlag im Sinne von § 12 Abs 2 (Austausch bewährter Verfahren) — kein Rechtsrat.*",
        "",
        "## 1. Platzhalter ersetzen",
        "",
        "| Platzhalter | Bedeutung |",
        "|---|---|",
    ]
    kopf += [f"| `{p}` | {b} |" for p, b in PLATZHALTER]
    kopf += [
        "",
        "## 2. Kern behalten, Landesrecht anpassen",
        "",
        "Die Paragrafen des **Kerns** machen das Modell aus — wer sie ändert, betreibt eine andere Partei. "
        "Die **Landesrecht**-Paragrafen sind bewusst offen: Sie tragen das Modell in die eigene Rechtsordnung.",
        "",
        "| Paragraf | Einordnung | Hinweis |",
        "|---|---|---|",
    ]
    kopf += [f"| {p} | **{e}** | {h} |" for p, e, h in KERN]
    kopf += [
        "",
        "## 3. Prüfung im eigenen Land",
        "",
        "Der Anhang am Ende listet die Punkte, die in Österreich anwaltlich zu prüfen waren. Sie sind ein "
        "Raster für die eigene Prüfung — jedes Land hat seine eigenen Fallstricke (Registrierung, "
        "Parteienfinanzierung, Datenschutz, Wahlrecht).",
        "",
        "---",
        "",
    ]
    return "\n".join(kopf) + rumpf


def main(argv: list[str]) -> int:
    text = erzeugen()
    if "--pruefen" in argv:
        aktuell = ZIEL.exists() and ZIEL.read_text(encoding="utf-8") == text
        print("aktuell" if aktuell else "veraltet — bitte tools/satzung_baukasten.py ausführen")
        return 0 if aktuell else 1
    ZIEL.parent.mkdir(parents=True, exist_ok=True)
    ZIEL.write_text(text, encoding="utf-8", newline="\n")
    print(f"{ZIEL.relative_to(WURZEL)} geschrieben ({len(text)} Zeichen)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
