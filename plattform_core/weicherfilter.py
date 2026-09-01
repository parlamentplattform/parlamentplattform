"""Der WeicherFilter (P5; § 5 Abs 10 lit d, § 2 Abs 6): die mitgliedereigene Reihung.

Der Bereich d des Parlaments gehorcht dem Mitglied, nicht umgekehrt: Acht
offene Regler bestimmen, wovon mehr erscheint. Dieser Kern ist die gesamte
Regel — framework-frei, versioniert, mit Punkteaufschlüsselung je Antrag,
damit jede Reihenfolge von Hand nachgerechnet werden kann (§ 2 Abs 6:
offengelegt, versioniert, nachrechenbar; keine verdeckte Kuration).

Die Voreinstellung ist streng neutral (alle Regler auf 0): Dann gilt die
Grundordnung nach Phase und Frist, chronologisch — exakt die Reihenfolge,
in der die Einträge übergeben werden. Punkte entstehen ausschließlich aus
Reglern, die das Mitglied selbst gesetzt hat; bei Punktgleichheit bleibt
die neutrale Grundordnung erhalten (stabile Sortierung).

Jedes Merkmal liegt in [0, 1]; die Punkte eines Antrags sind die Summe
Regler × Merkmal über alle acht Regler. Mehr ist es nicht."""

from __future__ import annotations

VERSION = 1

# Die acht Regler des Fahrplans (P5) — Schlüssel sind Teil der offenen Regel.
REGLER = (
    "gestimmt",  # mehr aus Lebensbereichen, in denen ich abgestimmt habe
    "unterstuetzt",  # mehr aus Lebensbereichen, in denen ich unterstützt habe
    "entdeckungen",  # mehr außerhalb meiner Favoriten-Lebensbereiche
    "unterstuetzungsphase",  # mehr Anträge in der Unterstützungsphase
    "abstimmungen",  # mehr laufende Abstimmungen
    "chronologisch",  # Neueres zuerst
    "ablaufend",  # bald ablaufende Fristen zuerst
    "schwelle",  # knapp vor der Unterstützungsschwelle zuerst
)

HOECHSTWERT = 100


def regler_bereinigen(werte) -> dict[str, int]:
    """Nur bekannte Regler, ganzzahlig, auf [0, 100] begrenzt — alles andere 0."""
    sauber = {}
    quelle = werte if isinstance(werte, dict) else {}
    for name in REGLER:
        wert = quelle.get(name, 0)
        try:
            zahl = int(wert)
        except (TypeError, ValueError):
            zahl = 0
        sauber[name] = min(HOECHSTWERT, max(0, zahl))
    return sauber


def ist_neutral(werte) -> bool:
    """Neutral heißt: kein einziger Regler gesetzt — es gilt die Grundordnung."""
    return all(w == 0 for w in regler_bereinigen(werte).values())


def reihen(eintraege, werte) -> list[dict]:
    """Reiht Einträge nach den Reglern des Mitglieds.

    `eintraege`: Folge von Mappings {id, merkmale: {reglername: 0..1}} in der
    NEUTRALEN Grundordnung (Phase und Frist, chronologisch). `werte`: die
    Reglerstellungen. Rückgabe je Eintrag: id, punkte und die Aufschlüsselung
    `anteile` (nur gesetzte Regler) — die vollständige Rechnung, offen für alle.
    Bei Punktgleichheit bleibt die Grundordnung erhalten (stabile Sortierung)."""
    regler = regler_bereinigen(werte)
    ergebnis = []
    for eintrag in eintraege:
        merkmale = eintrag.get("merkmale") or {}
        anteile = {}
        punkte = 0.0
        for name in REGLER:
            gewicht = regler[name]
            if gewicht == 0:
                continue
            merkmal = merkmale.get(name, 0.0)
            merkmal = 0.0 if merkmal < 0 else 1.0 if merkmal > 1 else float(merkmal)
            beitrag = gewicht * merkmal
            if beitrag:
                anteile[name] = round(beitrag, 1)
            punkte += beitrag
        ergebnis.append({"id": eintrag["id"], "punkte": round(punkte, 1), "anteile": anteile})
    ergebnis.sort(key=lambda e: -e["punkte"])  # stabil: Gleichstand behält die Grundordnung
    return ergebnis
