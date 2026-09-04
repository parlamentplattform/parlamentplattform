"""Der Abstimmungs-Chat zum Vorschlag des Expertenrats (FB-G6; § 5 Abs 12).

Der Gründer beschreibt in A0-07 eine Abstimmung, die als Gespräch geführt wird: Die
Unterstützer reagieren auf die Beiträge zum Vorschlag — zustimmend oder ablehnend —,
und was das meiste Engagement auf sich zieht, steht oben. Die Plattform legt beim
Öffnen einen Systembeitrag „Passt alles" an; er ist der Beitrag, auf den sich die
Auswertung bezieht, damit niemand raten muss, welcher Beitrag Zustimmung zum
Vorschlag bedeutet.

Regel `engagement-v1`:

- *Engagement* eines Beitrags = Zustimmungen + Ablehnungen. Es zählt die Beteiligung,
  nicht die Richtung — ein heftig umstrittener Beitrag steht so weit oben wie ein
  einhellig getragener.
- *Reihung:* Engagement absteigend; bei Gleichstand der höhere Zustimmungsanteil;
  bei erneutem Gleichstand der ältere Beitrag zuerst. Damit ist die Reihenfolge
  eindeutig und von Hand nachrechenbar (§ 2 Abs 6). Der Systembeitrag ordnet sich
  ein wie jeder andere — er steht nur oben, wenn er das meiste Engagement hat.
- *Auswertung nach Fristablauf:* Der Vorschlag geht zur Endabstimmung, wenn der
  Systembeitrag **an erster Stelle steht und mehr als die Schwelle an Zustimmung
  trägt** (Zustimmungen ÷ (Zustimmungen + Ablehnungen) > Schwelle; Voreinstellung
  50 %). Beides muss zutreffen — so verlangt es A0-07 („ganz oben" *und* „mehr als
  50 %"). Sonst geht der Vorschlag mit den Kritik-Beiträgen zurück an den Expertenrat.
- *Stille hemmt nie* (§ 5 Abs 12): Liegt keine einzige Reaktion vor, gilt der
  Vorschlag als angenommen. Wer nichts sagt, blockiert nicht.

Dieser Kern ist framework-frei: Beiträge kommen als schlichte Abbildungen herein
(`id`, `system`, `ist_kritik`, `ja`, `nein`, `zeit`), damit die Regel ohne Datenbank
geprüft und nachgerechnet werden kann.
"""

from __future__ import annotations

VERSION = 1

#: Kennung der Reihungsregel — steht im Parameterregister und im Zonenkopf.
REIHUNG = "engagement-v1"


def engagement(beitrag: dict) -> int:
    """Beteiligung an einem Beitrag: Zustimmungen + Ablehnungen."""
    return int(beitrag.get("ja", 0)) + int(beitrag.get("nein", 0))


def anteil(beitrag: dict) -> float:
    """Zustimmungsanteil in [0, 1]; ohne Reaktionen 0 — nicht undefiniert."""
    gesamt = engagement(beitrag)
    return (int(beitrag.get("ja", 0)) / gesamt) if gesamt else 0.0


def reihen(beitraege) -> list[dict]:
    """Beiträge nach Engagement reihen (Regel `engagement-v1`, siehe Kopf).

    Die Eingabereihenfolge bleibt bei völligem Gleichstand erhalten, weil `zeit`
    als letztes Merkmal entscheidet und die Sortierung stabil ist."""
    return sorted(beitraege, key=lambda b: (-engagement(b), -anteil(b), b.get("zeit")))


def auswerten(beitraege, schwelle: float = 0.5) -> dict:
    """Was nach Fristablauf mit dem Vorschlag geschieht.

    Gibt die vollständige Rechnung zurück, damit die Entscheidung nachvollziehbar
    im Audit und im Archiv steht — nicht nur ihr Ergebnis."""
    beitraege = list(beitraege)
    gereiht = reihen(beitraege)
    system = next((b for b in beitraege if b.get("system")), None)
    stimmen = sum(engagement(b) for b in beitraege)
    if system is None:
        # Ohne Systembeitrag gibt es nichts auszuwerten — der Vorschlag geht weiter
        # (Untätigkeit hemmt nie), die Rechnung sagt offen, dass er fehlte.
        return {
            "angenommen": True,
            "grund": "kein_systembeitrag",
            "oben": False,
            "ja": 0,
            "nein": 0,
            "anteil": 0.0,
            "prozent": 0,
            "schwelle": schwelle,
            "stimmen": stimmen,
            "reihung": REIHUNG,
        }
    oben = bool(gereiht) and gereiht[0].get("id") == system.get("id")
    quote = anteil(system)
    if stimmen == 0:
        angenommen, grund = True, "stille"
    elif oben and quote > schwelle:
        angenommen, grund = True, "passt_alles_oben"
    else:
        angenommen, grund = False, "rueckgabe"
    return {
        "angenommen": angenommen,
        "grund": grund,
        "oben": oben,
        "ja": int(system.get("ja", 0)),
        "nein": int(system.get("nein", 0)),
        "anteil": quote,
        "prozent": round(quote * 100),
        "schwelle": schwelle,
        "stimmen": stimmen,
        "reihung": REIHUNG,
    }


def kritik_uebergeben(beitraege) -> list[dict]:
    """Die Kritik-Beiträge als Wunschliste für die nächste Runde — nach Engagement
    gereiht, damit der Expertenrat sieht, was die Unterstützer am meisten bewegt."""
    return [b for b in reihen(beitraege) if b.get("ist_kritik") and not b.get("system")]
