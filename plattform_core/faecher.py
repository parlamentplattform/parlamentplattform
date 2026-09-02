"""Der Favoriten-Fächer (FB-C1–C4, F-46): Layout-Regel v2 für den grafischen
Themenbaum im Favoriten-Feld des Parlaments.

Framework-frei und rein: Eingabe sind die Kategoriezeilen (id, slug, name,
eltern_id, optional reihenfolge), der Fokus-Slug und die abonnierten Slugs;
Ausgabe sind Knotenpositionen und -breiten in Prozent, Fäden, Brotkrume und
der entfaltete Ast — das Template setzt daraus klickbare HTML-Pillen über einer
SVG-Fadenebene zusammen (ohne JavaScript voll bedienbar).

Gestaltregeln (Fahrtenbuch FB-C1 bis FB-C3, Design-Spezifikation 4):

- Unten (Modus „boden“) oder mittig (Modus „mitte“, ab Tiefe 3) sitzt der
  Anker in 24 px; darüber bis zu vier Ebenen in 22/20/18/16 px, jede mit
  ihrer Überkategorie durch einen Faden verbunden — fünf Ebenen sichtbar.
- Auffächer-Regel: Eine Ebene wird vollständig gezeichnet, solange sie unter
  dem Anker höchstens zwölf Knoten hat. Die erste zu große Ebene wird nur für
  den **entfalteten Ast** gezeichnet: einen Knoten der letzten vollständigen
  Ebene (im Ruhezustand der Ast des ersten Favoriten, sonst der erste Knoten;
  mit Zeiger oder Tipp wechselbar). Dort erscheinen höchstens drei Kinder
  nebeneinander und deren Kinder als kleine Säule senkrecht darüber; ab dem
  vierten Kind steht „+n“. Für alle Äste werden die Knoten vorab berechnet
  (Schlüssel `ast`), sichtbar ist immer nur einer — so kostet das Entfalten
  keine Netzlast.
- Waagrecht verteilen sich die Knoten einer Ebene gleichmäßig über 92 % der
  Breite in Elternreihenfolge (Geschwister nebeneinander) auf einem flachen
  Bogen, die Randpillen bündig am Rand. Passen die Beschriftungen nicht in
  eine Zeile, staffelt sich die Ebene in bis zu drei versetzte Reihen. Jede
  Pille bekommt die Breite b = r·Spanne/(n−1+r) zugeteilt, so dass sich
  Reihennachbarn nie berühren; längere Namen werden per CSS-Ellipse gekürzt
  (nie unter sechs Zeichen, voller Name als Titel).
- Im Modus „mitte“ steht unter dem Anker der vollständige Rückweg bis zur
  Wurzel, jede Stufe klickbar.

Die Rechnung läuft in einem nominalen Pixelraum (Breite 600 = Mindestbreite
des Feldes, Höhe = Bedarf); ausgegeben werden Prozentwerte, damit der Fächer
das Feld füllt und bei mehr Platz nur luftiger, nie enger wird. Der Test über
alle 312 Knoten des Kategorienbaums sichert, dass nie zwei sichtbare Pillen
überlappen — gerechnet mit der zugeteilten Höchstbreite, also unabhängig von
der Schrift.
"""

from __future__ import annotations

from statistics import median

VERSION = 2

BREITE = 600.0  # nominale Feldbreite in px (= min-width des Fächers)
RAND = 0.04  # 4 % Rand links und rechts — 92 % Nutzbreite
GROESSEN = (22, 20, 18, 16)  # Schriftgrößen der Ebenen über dem Anker
ANKER_GROESSE = 24
VOLL_HOECHSTZAHL = 12  # bis hierhin wird eine Ebene vollständig gezeichnet
KINDER_HOECHSTZAHL = 3  # im entfalteten Ast je Knoten
ZEICHEN = 0.52  # mittlere Zeichenbreite in Anteilen der Schriftgröße
PILLE_RAND = 36  # Stern (18), Fuge, Innenabstände (5+8) und Rand einer Pille (px)
KURZ_MAX = 22
KURZ_MIN = 6
REIHEN_MAX = 3
# Die Höhe ist knapp gerechnet: an der Wurzel passen fünf Ebenen in 336 px (Feldkörper bei
# 1440×900 als Gast). Ist das Feld höher, dehnt sich der Fächer proportional (Prozentlagen);
# ist es niedriger, rollt der Körper — von unten, damit der Anker zuerst sichtbar ist.
LUECKEN = (8, 8, 8, 8)  # Fuge zwischen den Ebenenbändern, von unten nach oben
AST_ABSTAND = 160.0  # Rasterbreite der Kinder im entfalteten Ast
STAPEL_FUGE = 1  # senkrechte Säule der letzten Ebene: Pillenhöhe + 1 px
WEG_ABSTAND = 34  # Rückweg unter dem Mitte-Anker
BOGEN = 5.0  # Bogenhöhe: Mitte einer Ebene liegt so viel höher als der Rand
OBEN = 4.0  # Rand oben
UNTEN = 4.0  # Rand unten
FUGE = 4.0  # Mindestabstand zweier Pillen


def pillen_hoehe(groesse: int) -> int:
    """Zeilenhöhe 1.15 + je 1 px Innenabstand und Rand oben und unten (base.html `.fknoten`)."""
    return round(groesse * 1.15) + 4


def pillen_breite(zeichen: int, groesse: int) -> float:
    """Geschätzte Breite einer Pille mit so vielen Zeichen (Stern und Abstände inklusive)."""
    return zeichen * ZEICHEN * groesse + PILLE_RAND


def _zeichen_je_pille(breite: float, groesse: int) -> int:
    return max(KURZ_MIN, int((breite - PILLE_RAND) // (ZEICHEN * groesse)))


def _kuerzen(name: str, laenge: int) -> str:
    laenge = max(KURZ_MIN, laenge)
    return name if len(name) <= laenge else name[: laenge - 1].rstrip() + "…"


def faecher_layout(zeilen, fokus_slug: str | None = None, abos=()):
    """Berechnet den Fächer. `zeilen`: Iterierbares aus Mappings mit den Schlüsseln
    id, slug, name, eltern_id (nur aktive Kategorien; `reihenfolge` optional).
    Unbekannter oder leerer Fokus fällt auf die Wurzel zurück."""
    zeilen = list(zeilen)
    je_id = {z["id"]: z for z in zeilen}
    je_slug = {z["slug"]: z for z in zeilen}
    kinder: dict[int | None, list[dict]] = {}
    for z in zeilen:
        kinder.setdefault(z["eltern_id"], []).append(z)
    for liste in kinder.values():
        liste.sort(key=lambda z: (z.get("reihenfolge", 0), z["name"]))

    leer = {
        "version": VERSION, "modus": "boden", "hoehe": 200, "breite": int(BREITE), "knoten": [],
        "faeden": [], "aeste": [], "ast_standard": "", "brotkrume": [], "fokus": None,
    }
    wurzeln = kinder.get(None, [])
    fokus = je_slug.get(fokus_slug or "")
    if fokus is None:
        fokus = wurzeln[0] if wurzeln else None
    if fokus is None:
        return leer

    # Weg zur Wurzel (ohne den Fokus), Tiefe, Säule je Knoten
    weg = []
    lauf = fokus
    while lauf["eltern_id"] is not None:
        lauf = je_id[lauf["eltern_id"]]
        weg.append(lauf)
    tiefe = len(weg) + 1
    modus = "mitte" if tiefe >= 3 else "boden"
    abos = set(abos or ())

    saeulen = {s["id"]: i + 1 for i, s in enumerate(kinder.get(wurzeln[0]["id"], []))} if wurzeln else {}

    def saeule_von(z) -> int:
        lauf = z
        while lauf is not None and lauf["id"] not in saeulen:
            lauf = je_id.get(lauf["eltern_id"]) if lauf["eltern_id"] is not None else None
        return saeulen.get(lauf["id"], 0) if lauf else 0

    def hat_abo(z) -> bool:
        if z["slug"] in abos:
            return True
        return any(hat_abo(k) for k in kinder.get(z["id"], []))

    # ── Ebenen über dem Anker: vollständig, solange ≤ 12 Knoten ──
    ebenen: list[list[dict]] = []
    aktuell = kinder.get(fokus["id"], [])
    while aktuell and len(ebenen) < len(GROESSEN):
        ebenen.append(aktuell)
        aktuell = [k for e in aktuell for k in kinder.get(e["id"], [])]
    voll = 0
    for i, ebene in enumerate(ebenen):
        if i == 0 or len(ebene) <= VOLL_HOECHSTZAHL:
            voll = i + 1
        else:
            break
    volle_ebenen = ebenen[:voll]
    naechste = ebenen[voll] if voll < len(ebenen) else []

    # Entfaltbare Äste: Knoten der letzten vollen Ebene mit Kindern (nur wenn eine Ebene zu groß ist)
    aeste: list[dict] = []
    if naechste and 1 <= voll < len(GROESSEN):
        aeste = [k for k in volle_ebenen[-1] if kinder.get(k["id"])]
    ast_standard = ""
    if aeste:
        ast_standard = next((a["slug"] for a in aeste if hat_abo(a)), aeste[0]["slug"])
    ast_slugs = {a["slug"] for a in aeste}

    # ── Waagrechte Zuteilung je volle Ebene: Reihen und Pillenbreite ──
    x0, x1 = RAND * BREITE, (1 - RAND) * BREITE
    spanne = x1 - x0

    def breite_bei(n: int, reihen: int) -> float:
        # Randpillen bündig am Rand, Reihennachbarn berühren sich gerade nicht
        return spanne if n == 1 else reihen * spanne / (n - 1 + reihen) - FUGE

    reihen_je_ebene: list[int] = []
    breite_je_ebene: list[float] = []
    for i, ebene in enumerate(volle_ebenen):
        groesse, n = GROESSEN[i], len(ebene)
        wunsch = pillen_breite(min(KURZ_MAX, int(median(len(z["name"]) for z in ebene))), groesse)
        hoechst = max(1, min(REIHEN_MAX, -(-n // 2)))
        reihen = next((r for r in range(1, hoechst + 1) if breite_bei(n, r) >= wunsch), hoechst)
        breite = max(breite_bei(n, reihen), pillen_breite(KURZ_MIN, groesse))
        reihen_je_ebene.append(reihen)
        breite_je_ebene.append(breite)

    def versatz(groesse: int, n: int) -> float:
        # Reihenabstand: Pillenhöhe + Fuge + Bogenunterschied benachbarter Knoten
        return pillen_hoehe(groesse) + FUGE + (4 * BOGEN / n if n > 1 else 0)

    # ── Senkrechte Ordnung, von oben nach unten ──
    y = OBEN
    stapel_y_oben = None
    seitlich_y = None
    if aeste:
        g_stapel = GROESSEN[voll + 1] if voll + 1 < len(GROESSEN) else GROESSEN[-1]
        stapel_abstand = pillen_hoehe(g_stapel) + STAPEL_FUGE
        stapel_y_oben = y + pillen_hoehe(g_stapel) / 2  # oberste Pille einer vollen Säule
        y = stapel_y_oben + (KINDER_HOECHSTZAHL - 1) * stapel_abstand + pillen_hoehe(g_stapel) / 2
        g_seit = GROESSEN[voll]
        seitlich_y = y + LUECKEN[min(voll + 1, 3)] + pillen_hoehe(g_seit) / 2
        y = seitlich_y + pillen_hoehe(g_seit) / 2
    basis_je_ebene: list[float] = [0.0] * len(volle_ebenen)
    for i in range(len(volle_ebenen) - 1, -1, -1):
        groesse, n = GROESSEN[i], len(volle_ebenen[i])
        h = pillen_hoehe(groesse)
        luecke = LUECKEN[min(i + 1, 3)] if (i < len(volle_ebenen) - 1 or aeste) else 0
        oberste = y + luecke + h / 2 + BOGEN
        basis_je_ebene[i] = oberste + (reihen_je_ebene[i] - 1) * versatz(groesse, n)
        y = basis_je_ebene[i] + h / 2
    anker_h = pillen_hoehe(ANKER_GROESSE)
    anker_y = y + (LUECKEN[0] if volle_ebenen else 0) + anker_h / 2
    y = anker_y + anker_h / 2
    weg_y: list[float] = []
    if modus == "mitte":
        for _ in weg:
            y += WEG_ABSTAND
            weg_y.append(y)
        y += pillen_hoehe(20) / 2
    hoehe = y + UNTEN

    # ── Knoten und Fäden ──
    knoten: list[dict] = []
    faeden: list[dict] = []
    lage: dict[int, tuple[float, float]] = {}

    def merken(z, x, yy, groesse, rolle, breite, *, ebene=0, ast="", mehr=0, stapel=False):
        eltern = je_id.get(z["eltern_id"]) if z["eltern_id"] is not None else None
        eintrag = {
            "slug": z["slug"], "name": z["name"],
            "kurz": _kuerzen(z["name"], _zeichen_je_pille(breite, groesse)),
            "x": round(x, 1), "y": round(yy, 1),
            "x_prozent": round(100 * x / BREITE, 2), "y_prozent": round(100 * yy / hoehe, 2),
            "breite_max": round(breite, 1), "breite_prozent": round(100 * breite / BREITE, 2),
            "groesse": groesse, "rolle": rolle, "ebene": ebene, "eltern": eltern["slug"] if eltern else "",
            "saeule": saeule_von(z), "ast": ast, "ast_kandidat": z["slug"] in ast_slugs,
            "mehr": mehr, "stapel": stapel, "unterbereiche": len(kinder.get(z["id"], [])),
            "sichtbar": not ast or ast == ast_standard, "abonniert": z["slug"] in abos,
        }
        knoten.append(eintrag)
        lage[z["id"]] = (x, yy)
        return eintrag

    def faden(von_id, bis, ast=""):
        vx, vy = lage[von_id]
        bx, by = lage[bis["id"]]
        faeden.append({
            "x1": round(100 * vx / BREITE, 2), "y1": round(100 * vy / hoehe, 2),
            "x2": round(100 * bx / BREITE, 2), "y2": round(100 * by / hoehe, 2),
            "ym": round(100 * (vy + by) / 2 / hoehe, 2), "bis": bis["slug"], "ast": ast,
        })

    merken(fokus, BREITE / 2, anker_y, ANKER_GROESSE, "anker", spanne)
    rollen = ("kind", "enkel", "urenkel", "ururenkel")

    for i, ebene in enumerate(volle_ebenen):
        groesse, reihen, breite = GROESSEN[i], reihen_je_ebene[i], breite_je_ebene[i]
        n = len(ebene)
        for j, z in enumerate(ebene):
            t = (j + 0.5) / n
            x = BREITE / 2 if n == 1 else x0 + breite / 2 + FUGE / 2 + (spanne - breite - FUGE) * j / (n - 1)
            yy = basis_je_ebene[i] - (j % reihen) * versatz(groesse, n) + BOGEN * (2 * t - 1) ** 2 - BOGEN
            merken(z, x, yy, groesse, rollen[i], breite, ebene=i + 1)
            faden(z["eltern_id"], z)

    # Entfaltete Äste: für jeden Kandidaten die Kinder nebeneinander, deren Kinder als Säule
    if aeste:
        g_seit = GROESSEN[voll]
        g_stapel = GROESSEN[voll + 1] if voll + 1 < len(GROESSEN) else GROESSEN[-1]
        breite_ast = AST_ABSTAND - FUGE
        for ast in aeste:
            ax, _ay = lage[ast["id"]]
            kids = kinder.get(ast["id"], [])
            gezeigt = kids[:KINDER_HOECHSTZAHL]
            gesamt = AST_ABSTAND * len(gezeigt)
            links = min(max(x0, ax - gesamt / 2), x1 - gesamt)
            for j, k in enumerate(gezeigt):
                x = links + AST_ABSTAND * (j + 0.5)
                letzte = j == len(gezeigt) - 1
                mehr = len(kids) - KINDER_HOECHSTZAHL if (letzte and len(kids) > KINDER_HOECHSTZAHL) else 0
                merken(k, x, seitlich_y, g_seit, rollen[voll], breite_ast, ebene=voll + 1, ast=ast["slug"], mehr=mehr)
                faden(ast["id"], k, ast=ast["slug"])
                if voll + 1 >= len(GROESSEN):
                    continue
                enkel = kinder.get(k["id"], [])
                gezeigte_enkel = enkel[:KINDER_HOECHSTZAHL]
                for s, e in enumerate(gezeigte_enkel):
                    yy = stapel_y_oben + (KINDER_HOECHSTZAHL - 1 - s) * stapel_abstand
                    letzter = s == len(gezeigte_enkel) - 1
                    mehr_e = len(enkel) - KINDER_HOECHSTZAHL if (letzter and len(enkel) > KINDER_HOECHSTZAHL) else 0
                    merken(e, x, yy, g_stapel, rollen[voll + 1], breite_ast, ebene=voll + 2, ast=ast["slug"],
                           mehr=mehr_e, stapel=True)
                    faden(k["id"], e, ast=ast["slug"])

    # Der Rückweg unter dem Mitte-Anker: vollständige Kette bis zur Wurzel
    if modus == "mitte":
        vorher = fokus
        for stufe, elter in enumerate(weg):
            groesse = 22 if stufe == 0 else 20 if stufe == 1 else 18
            merken(elter, BREITE / 2, weg_y[stufe], groesse, "weg", spanne, ebene=-(stufe + 1))
            faden(vorher["id"], elter)
            vorher = elter

    brotkrume = [{"slug": z["slug"], "name": z["name"]} for z in reversed(weg)] + [
        {"slug": fokus["slug"], "name": fokus["name"]}
    ]
    return {
        "version": VERSION,
        "modus": modus,
        "hoehe": int(round(hoehe)),
        "breite": int(BREITE),
        "knoten": knoten,
        "faeden": faeden,
        "aeste": [{"slug": a["slug"], "name": a["name"]} for a in aeste],
        "ast_standard": ast_standard,
        "brotkrume": brotkrume,
        "fokus": {"slug": fokus["slug"], "name": fokus["name"], "tiefe": tiefe},
    }
