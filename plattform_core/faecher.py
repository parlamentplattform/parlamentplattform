"""Der Favoriten-Fächer (P2, F-46): Layout-Mathematik für den grafischen
Themenbaum im Favoriten-Bereich des Parlaments.

Framework-frei und rein: Eingabe sind die Kategoriezeilen (id, slug, name,
eltern_id) und der Fokus-Slug, Ausgabe sind Knotenpositionen, Fäden und der
Anzeigemodus — das Template setzt daraus klickbare HTML-Knoten über einer
SVG-Fadenebene zusammen (ohne JavaScript voll bedienbar).

Gestaltregeln aus dem Fahrplan (Beschluss 1.9.2026):
- unten (bzw. in der Mitte) der aktuelle Knoten in Schrift 24, darüber die
  Unterebenen in 2-Punkt-Schritten kleiner, mit Fäden verbunden;
- ab der dritten Ebene sitzt der gewählte Knoten als 24er-Anker in der
  Mitte — darunter bleibt der Weg zurück nach oben klickbar, darüber
  öffnen sich die Unterebenen;
- Enkel erscheinen nur, solange sie lesbar bleiben (höchstens zwölf,
  gestaffelt über drei Reihen); sonst zeigt jedes Kind „+n".

Der Fächer ist bewusst kompakt gerechnet: Anker, Kinder und Enkel liegen in
den ersten ~300 Punkten, damit sie im Feld ohne Scrollen sichtbar sind; nur
ein langer Rückweg ragt darunter hinaus.
"""

from __future__ import annotations

BREITE = 1000  # Koordinatenraum; die Darstellung skaliert per Prozent/viewBox
ENKEL_HOECHSTZAHL = 12
KURZ_KIND = 23
KURZ_ENKEL = 16


def _kuerzen(name: str, laenge: int) -> str:
    return name if len(name) <= laenge else name[: laenge - 1].rstrip() + "…"


def _reihe_x(i: int, n: int, rand: float = 100.0) -> float:
    if n == 1:
        return BREITE / 2
    return rand + (BREITE - 2 * rand) * (i + 0.5) / n


def faecher_layout(zeilen, fokus_slug: str | None = None):
    """Berechnet den Fächer. `zeilen`: Iterierbares aus Mappings mit den
    Schlüsseln id, slug, name, eltern_id (nur aktive Kategorien).
    Unbekannter oder leerer Fokus fällt auf die Wurzel zurück."""
    je_id = {z["id"]: z for z in zeilen}
    je_slug = {z["slug"]: z for z in zeilen}
    kinder: dict[int | None, list[dict]] = {}
    for z in zeilen:
        kinder.setdefault(z["eltern_id"], []).append(z)
    for liste in kinder.values():
        liste.sort(key=lambda z: z["name"])

    wurzeln = kinder.get(None, [])
    fokus = je_slug.get(fokus_slug or "")
    if fokus is None:
        fokus = wurzeln[0] if wurzeln else None
    if fokus is None:
        return {"modus": "boden", "hoehe": 200, "knoten": [], "faeden": [], "fokus": None}

    # Weg zur Wurzel (ohne den Fokus selbst) und Tiefe (Wurzel = Ebene 1)
    weg = []
    lauf = fokus
    while lauf["eltern_id"] is not None:
        lauf = je_id[lauf["eltern_id"]]
        weg.append(lauf)
    tiefe = len(weg) + 1
    modus = "mitte" if tiefe >= 3 else "boden"

    fokus_kinder = kinder.get(fokus["id"], [])
    enkel_gesamt = sum(len(kinder.get(k["id"], [])) for k in fokus_kinder)
    enkel_zeigen = 0 < enkel_gesamt <= ENKEL_HOECHSTZAHL

    # Zeilenraster von oben nach unten (kompakt, Anker früh sichtbar)
    if enkel_zeigen:
        enkel_y = 30.0  # drei versetzte Reihen: +0 / +30 / +60
        kinder_y = 166.0
    else:
        enkel_y = 0.0
        kinder_y = 44.0
    anker_y = kinder_y + 96
    if not fokus_kinder:
        anker_y = 64.0

    weg_zeigen = []
    wurzel_dazu = False
    if modus == "mitte":
        weg_zeigen = weg[:2]
        wurzel_dazu = len(weg) > 2
    weg_stufen = len(weg_zeigen) + (1 if wurzel_dazu else 0)
    hoehe = anker_y + 52 * weg_stufen + 44

    knoten, faeden = [], []

    def merken(z, x, y, groesse, rolle, mehr=0):
        knoten.append(
            {
                "slug": z["slug"],
                "name": z["name"],
                "kurz": _kuerzen(z["name"], 30 if groesse == 24 else KURZ_KIND if groesse >= 22 else KURZ_ENKEL),
                "x": round(x, 1),
                "x_prozent": round(x / 10, 2),
                "y": round(y, 1),
                "groesse": groesse,
                "rolle": rolle,
                "mehr": mehr,
                "unterbereiche": len(kinder.get(z["id"], [])),
            }
        )
        return knoten[-1]

    anker = merken(fokus, BREITE / 2, anker_y, 24, "anker")

    # Unterebenen über dem Anker: Kinder auf leichtem Fächerbogen
    kind_lage = {}
    n = len(fokus_kinder)
    for i, k in enumerate(fokus_kinder):
        x = _reihe_x(i, n)
        t = (i + 0.5) / n if n > 1 else 0.5
        y = kinder_y + 22 * (2 * t - 1) ** 2  # außen etwas tiefer — der Fächerbogen
        if n >= 4:
            y += 34 * (i % 2)  # breite Reihen zusätzlich versetzen
        mehr = 0 if enkel_zeigen else len(kinder.get(k["id"], []))
        kn = merken(k, x, y, 22, "kind", mehr=mehr)
        kind_lage[k["id"]] = kn
        faeden.append((anker["x"], anker["y"] - 16, kn["x"], kn["y"] + 14))

    if enkel_zeigen:
        alle_enkel = [(k, e) for k in fokus_kinder for e in kinder.get(k["id"], [])]
        m = len(alle_enkel)
        for j, (elter, e) in enumerate(alle_enkel):
            x = _reihe_x(j, m, rand=110.0)
            y = enkel_y + 30 * (j % 3)  # drei Reihen gegen Überlappung
            kn = merken(e, x, y, 20, "enkel")
            el = kind_lage[elter["id"]]
            faeden.append((el["x"], el["y"] - 14, kn["x"], kn["y"] + 12))

    # Der Weg zurück nach oben, klickbar, unter dem Mitte-Anker
    vorher = anker
    for stufe, elter in enumerate(weg_zeigen):
        kn = merken(elter, BREITE / 2, anker_y + 52 * (stufe + 1), 22 - 2 * stufe, "weg")
        faeden.append((vorher["x"], vorher["y"] + 16, kn["x"], kn["y"] - 14))
        vorher = kn
    if wurzel_dazu:
        kn = merken(weg[-1], BREITE / 2, anker_y + 52 * (len(weg_zeigen) + 1), 18, "weg")
        faeden.append((vorher["x"], vorher["y"] + 16, kn["x"], kn["y"] - 14))

    return {
        "modus": modus,
        "hoehe": int(hoehe),
        "knoten": knoten,
        "faeden": [
            {"x1": round(a, 1), "y1": round(b, 1), "x2": round(c, 1), "y2": round(d, 1)}
            for a, b, c, d in faeden
        ],
        "fokus": {"slug": fokus["slug"], "name": fokus["name"], "tiefe": tiefe},
    }
