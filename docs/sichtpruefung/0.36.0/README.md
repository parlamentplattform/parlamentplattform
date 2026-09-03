# Sichtprüfung 0.36.0 — S14a: Internationale Zusammenarbeit

Erzeugt von `tests/e2e/test_sichtpruefung.py` (Playwright, Chromium) gegen die Demo-Daten:

```bash
DDOE_SICHTPRUEFUNG=1 python -m pytest tests/e2e/test_sichtpruefung.py -q
```

| Bild | Was zu prüfen ist |
|---|---|
| `partner-schaubild.png` | Die Partner-Seite: Gemeinsame Vision (Fassung 0.1), darunter „Ein Kern, viele Instanzen" — gemeinsamer Kern oben, drei Landesinstanzen unten, dazwischen die Brücke „Parameter-Schema" (FB-M6, FB-M8) |
| `partner-einstieg.png` | Die Schnittstellen-Tabelle mit allen offenen Adressen und der Einstieg in zwei Spuren (umgestalten / neu gründen) samt Paket-Knopf (FB-M5, FB-M7) |
| `partner-schaubild-dunkel.png` | Dasselbe im Dunkelmodus: Kern-Kasten, Instanzen und Fäden bleiben lesbar |
| `parlament-desktop-hell-gast.png` | Parlament als Gast: Sterne an jedem Antrag und Lebensbereich (führen zur Anmeldung) |
| `parlament-desktop-hell-mitglied.png` | Als Mitglied demo1: WeicherFilter mit Profil-Leiste, Fächer, Kacheln, Regionsbänder |
| `parlament-desktop-dunkel-mitglied.png` | Dunkelmodus |
| `filter-overlay.png`, `filter-vorschau-warum.png`, `filter-leiste-zu.png` | WeicherFilter: Overlay mit neun Reglern, Live-Vorschau mit „● Ungespeichert" und aufgeklapptem „Warum hier?", eingefahrene Leiste (FB-B1–B5) |
| `faecher-wurzel.png`, `faecher-hover-ast.png`, `faecher-mitte.png`, `faecher-handy.png` | Der Fächer: fünf Ebenen ohne Überlappung, entfalteter Ast beim Zeigen, Mitte-Modus mit Rückweg und Brotkrume, Handy (FB-C1–C3) |
| `parlament-handy-hell.png`, `parlament-handy-dunkel.png`, `handy-menue.png` | Handy-Ansichten und Burger-Panel |
| `parlament-ohne-javascript.png` | Grundschicht ohne JavaScript |
| `konto-menue.png`, `anstoss-popover.png`, `antragsseite-mit-fusszeile.png` | Konto-Menü, Anstoß, Antragsseite |

Abnahmen laut Fahrtenbuch: FB-M1 (Veranschaulichung), FB-M5 (Schema und Exporte), FB-M6 (ein Kern, viele Instanzen), FB-M7 (Übertragungspaket, zwei Spuren), FB-M8 (Gemeinsame Vision als Entwurf).

**Nicht auf den Bildern, aber Teil des Schritts:** `/parameter.json` und `/kennzahlen.json` (Schema 1.0), das Paket unter `/partner/paket/` und der Satzungs-Baukasten in `docs/partner/`.
