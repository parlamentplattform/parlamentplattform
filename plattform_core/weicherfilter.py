"""Der WeicherFilter (P5, FB-B1–B6; § 5 Abs 10 lit d, § 2 Abs 6): die mitgliedereigene Reihung.

Der Bereich d des Parlaments gehorcht dem Mitglied, nicht umgekehrt: Neun offene
Regler bestimmen, wovon mehr erscheint, und ein Schalter „★ Favoriten zuerst"
stellt Anträge aus den abonnierten Lebensbereichen nach vorn. Dieser Kern ist
die gesamte Regel — framework-frei, versioniert, mit Punkteaufschlüsselung je
Antrag, damit jede Reihenfolge von Hand nachgerechnet werden kann (§ 2 Abs 6:
offengelegt, versioniert, nachrechenbar; keine verdeckte Kuration).

Regel v2 (FB-B2, 2.9.2026):

- Voreinstellung streng neutral (alle Regler 0): Grundordnung nach Phase und
  Frist, chronologisch — exakt die Reihenfolge, in der die Einträge übergeben
  werden. Punkte entstehen ausschließlich aus Reglern, die das Mitglied selbst
  gesetzt hat; bei Punktgleichheit bleibt die Grundordnung erhalten (stabil).
- Jedes Merkmal liegt in [0, 1]; Punkte = Σ Regler × Merkmal über die neun Regler.
- „★ Favoriten zuerst" (Voreinstellung an, abschaltbar): Einträge mit dem
  Kennzeichen `favorit` stehen vor allen anderen; innerhalb beider Teile gilt
  die Punkteordnung bzw. die Grundordnung. Das ist keine verdeckte Reihung —
  der Schalter ist sichtbar und gehört dem Mitglied (§ 5 Abs 10 lit a).
- Die alte, richtungslose Regel v1 („gestimmt") ist in `ja` und `nein`
  aufgeteilt (D-B2); `regler_bereinigen` übernimmt einen alten Wert in beide."""

from __future__ import annotations

VERSION = 2

# Die neun Regler (FB-B2) in Anzeigereihenfolge — Schlüssel sind Teil der offenen Regel.
REGLER = (
    "ja",  # mehr wie das, wofür ich gestimmt habe
    "nein",  # mehr wie das, wogegen ich gestimmt habe
    "unterstuetzt",  # mehr wie das, was ich unterstützt habe
    "entdeckungen",  # Interessantes außerhalb meiner Favoriten
    "unterstuetzungsphase",  # mehr Unterstützungsanträge
    "abstimmungen",  # mehr Abstimmungen
    "chronologisch",  # mehr chronologisch (Neues zuerst)
    "ablaufend",  # nur noch kurz online
    "schwelle",  # wenig fehlt
)

HOECHSTWERT = 100
SCHRITT = 5

# Regel v1 kannte einen richtungslosen Regler „gestimmt“; er lebt in beiden Richtungen weiter.
ALTE_NAMEN = {"gestimmt": ("ja", "nein")}


def regler_bereinigen(werte) -> dict[str, int]:
    """Nur bekannte Regler, ganzzahlig, auf [0, 100] begrenzt — alles andere 0.
    Alte Schlüssel (Regel v1) werden übersetzt, wenn der neue Schlüssel fehlt."""
    quelle = dict(werte) if isinstance(werte, dict) else {}
    for alt, neue in ALTE_NAMEN.items():
        if alt in quelle:
            for neu in neue:
                quelle.setdefault(neu, quelle[alt])
    sauber = {}
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


def reihen(eintraege, werte, favoriten_zuerst: bool = False) -> list[dict]:
    """Reiht Einträge nach den Reglern des Mitglieds.

    `eintraege`: Folge von Mappings {id, merkmale: {reglername: 0..1}, favorit: bool}
    in der NEUTRALEN Grundordnung (Phase und Frist, chronologisch). `werte`: die
    Reglerstellungen. Rückgabe je Eintrag: id, punkte, favorit und die
    Aufschlüsselung `anteile` (nur gesetzte Regler) — die vollständige Rechnung,
    offen für alle. Bei Punktgleichheit bleibt die Grundordnung erhalten (stabile
    Sortierung); mit `favoriten_zuerst` stehen Favoriten vor allen anderen."""
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
        ergebnis.append({
            "id": eintrag["id"],
            "punkte": round(punkte, 1),
            "anteile": anteile,
            "favorit": bool(eintrag.get("favorit")),
        })
    # stabil: Gleichstand behält die Grundordnung; Favoriten (wenn gewünscht) vor allen anderen
    ergebnis.sort(key=lambda e: (0 if (favoriten_zuerst and e["favorit"]) else 1, -e["punkte"]))
    return ergebnis
