# Sichtprüfung 0.33.0 — S1 App-Rahmen

Erzeugt am 2.9.2026 aus `tests/e2e/test_sichtpruefung.py` (Chromium, Demo-Daten aus `demo_seed`):

```bash
DDOE_SICHTPRUEFUNG=1 python -m pytest tests/e2e/test_sichtpruefung.py -q
```

| Bild | Was darauf zu sehen sein soll |
|---|---|
| `parlament-desktop-hell-gast.png` | 1440×900: eine App-Leiste, darunter das 32-px-Gastband, vier gleich große Felder bis zur Unterkante, keine Fußzeile |
| `parlament-desktop-hell-mitglied.png` | dasselbe als Mitglied: kein Band, Gold-Knopf „＋ Antrag einbringen“, Konto-Avatar |
| `parlament-desktop-dunkel-mitglied.png` | dunkles Erscheinungsbild ohne helle Flächen |
| `konto-menue.png` | Konto-Popover: Mein Gremium · Beitrag · Sprache · Erscheinungsbild · Mehr · Abmelden |
| `anstoss-popover.png` | Anstoß in der Leiste, Karte öffnet darunter — „Meine Region“ bleibt frei |
| `parlament-handy-hell.png` | 390×844: ein Feld füllt den Bildschirm, Tableiste unten mit Gold-＋ in der Mitte |
| `parlament-handy-dunkel.png` | dasselbe dunkel |
| `handy-menue.png` | Burger-Menü als Panel von rechts mit Schleier |
| `parlament-ohne-javascript.png` | dieselbe Ansicht mit abgeschaltetem JavaScript (Grundschicht) |
| `antragsseite-mit-fusszeile.png` | zum Vergleich: außerhalb des Parlaments gibt es die Fußzeile weiterhin |

## Was in diesem Schritt bewusst offen bleibt

- Der **Fächer** zeigt weiterhin drei Ebenen und schneidet lange Namen ab (FB-C1, FB-C2) — das ist Schritt S4.
- Die **Kacheln** haben noch kein 2×2/3×2-Raster, keinen Fristring und keinen Themen-Stern (FB-D1, FB-D2) — das ist S2.
- „**Meine Region**“ hat noch keine wischbaren Bänder (FB-E1) — ebenfalls S2.
- Der **„mehr vorhanden“-Hinweis** an den Feldern (FB-A5) kommt mit S2.
- Die **Rückmeldung in der Kachel** statt im Meldungsstapel (FB-A2) kommt mit S2.
