"""Servergerenderte SVG-Diagramme für die Übersichtsseite (F-50).

Bewusst ohne JavaScript und ohne Diagramm-Bibliothek: Die Plattform verspricht
Nachvollziehbarkeit ohne Skriptpflicht — also entstehen die Bilder als reines
SVG auf dem Server. Native <title>-Elemente liefern Tooltips beim Überfahren.

Farbwahl ist geprüft, nicht geschätzt: Die drei Reihenfarben (Blau, Gold,
Dunkelrot) bestehen die Farbfehlsichtigkeits-Prüfung (Deutan/Protan/Tritan-
Abstand, Helligkeitsband, Chroma) auf hellem Grund; Gold liegt unter 3:1
Kontrast und wird deshalb nie ohne sichtbare Beschriftung eingesetzt.
"""

from __future__ import annotations

from xml.sax.saxutils import escape

# Reihenfarben (validiert) und Textfarben (identisch mit dem Seitenstil).
BLAU = "#2C89B0"
GOLD = "#D9A441"
ROT = "#8C2B2B"
TINTE = "#0E2230"
GRAU = "#6b7a84"
RASTER = "#0E2230"  # wird mit geringer Deckkraft gezeichnet

SCHRIFT = "font-family='system-ui,-apple-system,Segoe UI,Roboto,sans-serif'"


def _kopf(breite: int, hoehe: int, beschreibung: str) -> str:
    """SVG-Wurzel samt eigenem Papiergrund: Das Diagramm bleibt auch auf
    dunklen Seiten (Dark Mode) ein lesbares Blatt — die validierte Farbwahl
    gilt für hellen Grund, also bringt jedes Diagramm ihn selbst mit."""
    return (
        f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 {breite} {hoehe}' "
        f"width='100%' role='img' aria-label='{escape(beschreibung)}' "
        f"style='max-width:{breite}px;display:block'>"
        f"<rect width='{breite}' height='{hoehe}' rx='10' fill='#FDFCF8'/>"
    )


def _achsenwerte(maximum: float) -> list[int]:
    """Drei bis vier „runde“ Rasterwerte von 0 bis knapp über das Maximum."""
    if maximum <= 0:
        return [0, 1]
    roh = maximum / 3
    stufe = 1
    for kandidat in (1, 2, 5, 10, 20, 25, 50, 100, 200, 500, 1000, 2000, 5000, 10000, 50000, 100000):
        if kandidat >= roh:
            stufe = kandidat
            break
    else:
        stufe = 10 ** len(str(int(roh)))
    obergrenze = stufe
    while obergrenze < maximum:
        obergrenze += stufe
    return list(range(0, obergrenze + 1, stufe))


def _raster_und_achse(werte: list[int], links: int, rechts: int, oben: int, unten: int) -> tuple[str, float]:
    """Zeichnet zurückhaltende Rasterlinien samt Beschriftung; gibt (svg, skala) zurück."""
    spanne = max(werte[-1], 1)
    hoehe = unten - oben
    teile = []
    for w in werte:
        y = unten - hoehe * (w / spanne)
        teile.append(
            f"<line x1='{links}' y1='{y:.1f}' x2='{rechts}' y2='{y:.1f}' "
            f"stroke='{RASTER}' stroke-opacity='0.1' stroke-width='1'/>"
            f"<text x='{links - 8}' y='{y + 4:.1f}' text-anchor='end' font-size='11' "
            f"fill='{GRAU}' {SCHRIFT}>{w}</text>"
        )
    return "".join(teile), hoehe / spanne


def linien_diagramm(punkte: list[tuple[str, float]], beschreibung: str, breite: int = 640) -> str:
    """Verlaufslinie (z. B. Mitgliederentwicklung). punkte = [(beschriftung, wert), …]."""
    if not punkte:
        return ""
    hoehe = 220
    links, rechts, oben, unten = 46, breite - 16, 14, 186
    werte = _achsenwerte(max(w for _, w in punkte))
    raster, skala = _raster_und_achse(werte, links, rechts, oben, unten)
    schritt = (rechts - links) / max(len(punkte) - 1, 1)
    xy = [(links + i * schritt, unten - w * skala) for i, (_, w) in enumerate(punkte)]
    pfad = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in xy)

    marken = []
    letzte_x, letzte_y = xy[-1]
    for (beschriftung, wert), (x, y) in zip(punkte, xy, strict=True):
        marken.append(
            f"<circle cx='{x:.1f}' cy='{y:.1f}' r='6' fill='transparent'>"
            f"<title>{escape(beschriftung)}: {wert:g}</title></circle>"
        )
    # Direkte Beschriftung nur am letzten Punkt — nie an jedem (Lesbarkeit).
    endwert = punkte[-1][1]
    endtext_x = min(letzte_x, rechts - 8)
    beschriftungen = (
        f"<circle cx='{letzte_x:.1f}' cy='{letzte_y:.1f}' r='4' fill='{BLAU}'/>"
        f"<text x='{endtext_x:.1f}' y='{max(letzte_y - 10, 12):.1f}' text-anchor='end' "
        f"font-size='12.5' font-weight='600' fill='{TINTE}' {SCHRIFT}>{endwert:g}</text>"
    )
    # X-Beschriftung: erster, mittlerer, letzter Punkt (Ränder nicht abschneiden).
    x_indizes = sorted({0, len(punkte) // 2, len(punkte) - 1})
    x_texte = "".join(
        f"<text x='{xy[i][0]:.1f}' y='{unten + 18}' "
        f"text-anchor='{'start' if i == 0 else 'end' if i == len(punkte) - 1 else 'middle'}' "
        f"font-size='11' fill='{GRAU}' {SCHRIFT}>{escape(punkte[i][0])}</text>"
        for i in x_indizes
    )
    return (
        _kopf(breite, hoehe, beschreibung)
        + raster
        + f"<path d='{pfad}' fill='none' stroke='{BLAU}' stroke-width='2' "
        f"stroke-linejoin='round' stroke-linecap='round'/>"
        + beschriftungen
        + "".join(marken)
        + x_texte
        + "</svg>"
    )


def _saeule(x: float, y: float, b: float, h: float, farbe: str, hinweis: str) -> str:
    """Eine Säule mit oben abgerundeten Ecken, unten bündig auf der Grundlinie."""
    r = min(3.0, b / 2, max(h, 0.1))
    return (
        f"<path d='M{x:.1f},{y + h:.1f} v{-(h - r):.1f} q0,-{r} {r},-{r} h{b - 2 * r:.1f} "
        f"q{r},0 {r},{r} v{h - r:.1f} z' fill='{farbe}'>"
        f"<title>{escape(hinweis)}</title></path>"
    )


def balken_diagramm(werte: list[tuple[str, float]], beschreibung: str, breite: int = 640) -> str:
    """Säulen je Zeitraum (z. B. neue Anträge je Woche, Besuche je Tag)."""
    if not werte:
        return ""
    hoehe = 220
    links, rechts, oben, unten = 46, breite - 16, 14, 186
    raster, skala = _raster_und_achse(_achsenwerte(max(w for _, w in werte)), links, rechts, oben, unten)
    n = len(werte)
    schritt = (rechts - links) / n
    saeulenbreite = max(min(schritt - 2, 46), 3)  # mindestens 2 Einheiten Luft je Seite

    teile, hoechster = [], max(w for _, w in werte)
    for i, (beschriftung, w) in enumerate(werte):
        x = links + i * schritt + (schritt - saeulenbreite) / 2
        h = w * skala
        if w > 0:
            teile.append(_saeule(x, unten - h, saeulenbreite, h, BLAU, f"{beschriftung}: {w:g}"))
        # Direkte Beschriftung nur für Maximum und letzten Wert (selektiv, nie überall).
        if w > 0 and (w == hoechster or i == n - 1):
            teile.append(
                f"<text x='{x + saeulenbreite / 2:.1f}' y='{unten - h - 6:.1f}' text-anchor='middle' "
                f"font-size='12' font-weight='600' fill='{TINTE}' {SCHRIFT}>{w:g}</text>"
            )
    x_indizes = sorted({0, n // 2, n - 1}) if n > 6 else range(n)
    x_texte = "".join(
        f"<text x='{links + i * schritt + schritt / 2:.1f}' y='{unten + 18}' text-anchor='middle' "
        f"font-size='11' fill='{GRAU}' {SCHRIFT}>{escape(werte[i][0])}</text>"
        for i in x_indizes
    )
    return _kopf(breite, hoehe, beschreibung) + raster + "".join(teile) + x_texte + "</svg>"


def anteils_balken(teile: list[tuple[str, int, str]], beschreibung: str, breite: int = 640) -> str:
    """Ein liegender 100-%-Balken (Ja/Nein/Enthaltung) mit 2 px Zwischenraum.

    Die Zahlen stehen als normaler Text NEBEN dem Balken (im Template) —
    Farbe trägt nie allein die Information."""
    gesamt = sum(anzahl for _, anzahl, _ in teile)
    hoehe = 22
    if gesamt <= 0:
        return (
            _kopf(breite, hoehe, beschreibung)
            + f"<rect width='{breite}' height='{hoehe}' rx='6' fill='{RASTER}' fill-opacity='0.07'/>"
            + "</svg>"
        )
    svg, x = [], 0.0
    sichtbar = [(n, a, f) for n, a, f in teile if a > 0]
    luecke = 2 if len(sichtbar) > 1 else 0
    nutzbreite = breite - luecke * (len(sichtbar) - 1)
    for name, anzahl, farbe in sichtbar:
        b = nutzbreite * (anzahl / gesamt)
        prozent = 100 * anzahl / gesamt
        svg.append(
            f"<rect x='{x:.1f}' y='0' width='{b:.1f}' height='{hoehe}' rx='4' fill='{farbe}'>"
            f"<title>{escape(name)}: {anzahl} ({prozent:.0f} %)</title></rect>"
        )
        x += b + luecke
    return _kopf(breite, hoehe, beschreibung) + "".join(svg) + "</svg>"
