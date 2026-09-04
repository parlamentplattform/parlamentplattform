# Sichtprüfung 0.37.0 — S5: Die Antragsseite in drei Zonen

Erzeugt von `tests/e2e/test_sichtpruefung.py` (Playwright, Chromium) gegen die Demo-Daten:

```bash
DDOE_SICHTPRUEFUNG=1 python -m pytest tests/e2e/test_sichtpruefung.py -q
```

| Bild | Was zu prüfen ist |
|---|---|
| `antragsseite-drei-zonen.png` | 1440×900: Text links (58 %), Einschätzung rechts (42 %), Reiterleiste unter der App-Leiste mit „Text" markiert; Kopf mit Chips, Stern und Meta-Zeile (FB-F1) |
| `antragsseite-chat-unten.png` | Ans Seitenende gescrollt: der Chat steht über die volle Breite, die Einschätzung klebt weiter, der Reiter „Chat" ist markiert (Scroll-Spy) |
| `antragsseite-handy-text.png` | 390×844: nur die Zone „Text" ist sichtbar, die Reiter schalten um (FB-F1) |
| `antragsseite-handy-einschaetzung.png` | Nach Tipp auf „Einschätzung": Kopfkarte mit Kennzeichnung „Modellrechnung — sie schlägt vor, sie entscheidet nie", Leerzustand mit den fünf Skelett-Karten (FB-F2) |
| `antragsseite-mit-fusszeile.png` | Eine hervorgehobene Abstimmung: Gold-Band, Handlungskarte „Abstimmen" |
| `partner-schaubild.png`, `partner-einstieg.png`, `partner-schaubild-dunkel.png` | Partner-Seite aus 0.36.0 |
| `parlament-desktop-hell-gast.png`, `parlament-desktop-hell-mitglied.png`, `parlament-desktop-dunkel-mitglied.png` | Das Parlament mit allen vier Feldern |
| `filter-overlay.png`, `filter-vorschau-warum.png`, `filter-leiste-zu.png` | WeicherFilter (FB-B1–B5) |
| `faecher-wurzel.png`, `faecher-hover-ast.png`, `faecher-mitte.png`, `faecher-handy.png` | Der Fächer (FB-C1–C3) |
| `parlament-handy-hell.png`, `parlament-handy-dunkel.png`, `handy-menue.png`, `parlament-ohne-javascript.png`, `konto-menue.png`, `anstoss-popover.png` | Handy, Menüs, Grundschicht |

Abnahme FB-F1: Text links, Einschätzung rechts klebend, Chat unten; die Reiterleiste bleibt beim Scrollen sichtbar und markiert die Zone; auf 390 px schalten die Reiter; **kein JSON-Block im Sichtbereich** — die eingefrorenen Regeln stehen lesbar, das JSON eine Ebene tiefer unter „Rohdaten".
