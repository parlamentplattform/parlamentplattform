# Sichtprüfung 0.34.0 — S2/S4: Kacheln nach Vorgabe und der Favoriten-Fächer mit fünf Ebenen

Erzeugt von `tests/e2e/test_sichtpruefung.py` (Playwright, Chromium) gegen die Demo-Daten:

```bash
DDOE_SICHTPRUEFUNG=1 python -m pytest tests/e2e/test_sichtpruefung.py -q
```

| Bild | Was zu prüfen ist |
|---|---|
| `parlament-desktop-hell-gast.png` | 1440×900, Gast: Gastband, vier Felder bildschirmfüllend; im Feld „Meine Favoriten" der Fächer mit fünf Ebenen (Lebensbereiche · 4 Säulen · 12 Bereiche · Hauptkategorien des entfalteten Bereichs · deren Unterkategorien als Säule) |
| `parlament-desktop-hell-mitglied.png` | dasselbe als Mitglied demo1: Sterne an jedem Knoten, Kacheln mit Thema-Chip, Themen-Stern, Fristring und Direkt-Handlung |
| `parlament-desktop-dunkel-mitglied.png` | Dunkelmodus: Säulentöne und Fäden bleiben lesbar |
| `faecher-wurzel.png` | Nahaufnahme des Fächers an der Wurzel (FB-C1, FB-C2): nichts überlappt, Randpillen bündig, Beschriftungen mit Ellipse, Säulentöne |
| `faecher-hover-ast.png` | Zeiger über dem siebten Bereich: sein Ast ist entfaltet (drei Kinder + Säule, „+n"), der Faden bis zur Wurzel ist gold (FB-C2, FB-C1) |
| `faecher-mitte.png` | Tiefe 3 (Bereich): Anker in der Mitte, darunter der vollständige Rückweg Säule › Lebensbereiche, oben die Brotkrume (FB-C3) |
| `faecher-handy.png` | 390×844: Schriftgrößen 20/18/16/15/14, Fächer waagrecht rollbar, der Anker zuerst sichtbar |
| `konto-menue.png`, `anstoss-popover.png` | unverändert aus S1 |
| `parlament-handy-hell.png`, `handy-menue.png`, `parlament-handy-dunkel.png` | Handy-Ansichten, Tableiste, Burger-Panel |
| `parlament-ohne-javascript.png` | Grundschicht ohne JavaScript: der Ruhe-Ast des Fächers bleibt sichtbar, jeder Knoten ein Link |
| `antragsseite-mit-fusszeile.png` | Vergleich: eine Seite mit Fußzeile |

Abnahmen laut Fahrtenbuch: FB-C1 (Fäden, Säulentöne, Hover), FB-C2 (fünf Ebenen, Auffächer-Regel, keine Überlappung — Rechenprobe über alle 312 Anker in `tests/test_faecher_layout.py`), FB-C3 (Zoom beim Klick, Mitte-Modus, Rückweg, Brotkrume), FB-C4 (Stern-Tausch ohne Feldflackern), FB-D1–D3 und FB-A2 (Kacheln).
