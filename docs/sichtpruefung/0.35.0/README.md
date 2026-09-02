# Sichtprüfung 0.35.0 — S3: Der WeicherFilter komplett

Erzeugt von `tests/e2e/test_sichtpruefung.py` (Playwright, Chromium) gegen die Demo-Daten:

```bash
DDOE_SICHTPRUEFUNG=1 python -m pytest tests/e2e/test_sichtpruefung.py -q
```

| Bild | Was zu prüfen ist |
|---|---|
| `parlament-desktop-hell-mitglied.png` | 1440×900 als demo1: im WeicherFilter die Profil-Leiste (Neutral · ⚙ Regler · Pfeil), der Chip „★ Favoriten zuerst" im Feldkopf, Feed-Zeilen mit farbigen Chips, Mini-Balken, Frist und Direkt-Handlung rechts (FB-B1, FB-B4) |
| `filter-overlay.png` | Regler-Overlay von rechts (340 px, halbtransparent), Kopfzeile „Neutral", Schalter, neun Regler mit Wortlaut und Wert, Aktionszeile mit ausgegrautem „Speichern" (FB-B2, FB-B5) |
| `filter-vorschau-warum.png` | „Mehr Unterstützungsanträge" auf 100 gezogen: die Liste ist live umgeordnet, in der Leiste „● Ungespeichert", eine Zeile mit aufgeklapptem „Warum hier?" (FB-B1, FB-B2) |
| `filter-leiste-zu.png` | Profil-Leiste eingefahren: nur der 14-px-Griff bleibt, der aktive Name steht im Feldkopf (FB-B4) |
| `parlament-desktop-hell-gast.png` | Gast: WeicherFilter neutral ohne Leiste und Schalter, Zeilen mit „Anmelden" statt Stimmknöpfen |
| `parlament-desktop-dunkel-mitglied.png` | Dunkelmodus: Chips, Balken und Overlay-Töne bleiben lesbar |
| `faecher-wurzel.png`, `faecher-hover-ast.png`, `faecher-mitte.png`, `faecher-handy.png` | Fächer unverändert aus 0.34.0 |
| `parlament-handy-hell.png`, `parlament-handy-dunkel.png`, `handy-menue.png` | Handy: Feed-Zeilen umbrechen, Direkt-Handlung bleibt rechts |
| `parlament-ohne-javascript.png` | Grundschicht: Leiste ausgefahren ohne Pfeil, Regler als natives Aufklappen |
| `konto-menue.png`, `anstoss-popover.png`, `antragsseite-mit-fusszeile.png` | unverändert |

Abnahmen laut Fahrtenbuch: FB-B1 (Favoriten zuerst, Warum hier?), FB-B2 (neun Regler, Live-Vorschau), FB-B3 (Konfigurationen), FB-B4 (Leiste mit Pfeil, gemerkt), FB-B5 (Overlay, Escape), FB-B6 (Regel v2 nachlesen).
