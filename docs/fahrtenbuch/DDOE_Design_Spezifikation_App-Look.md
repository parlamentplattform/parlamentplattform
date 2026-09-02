# ParlamentPlattform — Design-Spezifikation „App-Look"

Stand 2.9.2026 · Verbindlich für Claude Code · Gehört zu `DDOE_Fahrtenbuch_Detail_v1_2026-09-02.md` (Bereiche A, P) · Ersetzt Abschnitt E/E2 des alten Fahrplans

**Ziel in einem Satz:** *Das Parlament sieht aus und fühlt sich an wie eine gut gemachte App — eine Leiste, vier bildschirmfüllende Felder, alles direkt bedienbar, jede Bewegung gerichtet und kurz — und bleibt ohne JavaScript vollständig benutzbar.*

---

## 1. Grundsätze (nicht verhandelbar)

1. **Werkzeug, keine Werbefläche.** Kein Erklärsatz in Parlament, Antragsseite (außer Zone-2-Kennzeichnung), Gremien, Mandatare/mein, Profil. Erklärt wird auf `/`, `/mitgliedschaft/`, `/zukunftswerkstatt/`, `/partner/`.
2. **Progressive Verstärkung.** Server-gerendertes HTML + echte Formulare/Links = Grundschicht. htmx tauscht Teile, Alpine.js steuert lokale Zustände, CSS bewegt. Nichts davon ist Voraussetzung.
3. **Bewegung ist Bedeutung.** Jede Animation zeigt, *woher* etwas kommt oder *wohin* es geht. Nie dekorativ, nie länger als 420 ms, nie blockierend. `prefers-reduced-motion: reduce` → alle Dauern 1 ms, keine Transformationen.
4. **Keine Fremdlast.** Kein CDN, kein Webfont, kein Tracking, kein Chart-Framework. Alles eingecheckt.
5. **Ein System, zwei Themen.** Alle Farben über Tokens; hell und dunkel gleichwertig; kein hart kodiertes Hex außerhalb der Token-Definition.
6. **Touch zuerst.** Bedienziele ≥ 44 × 44 px, Abstände ≥ 8 px, Wischgesten wo Listen horizontal liegen.

---

## 2. Tokens

### 2.1 Farben (CSS-Custom-Properties auf `:root`; dunkel via `[data-theme=dark]` und `prefers-color-scheme` ohne gesetztes `data-theme`)

| Token | Hell | Dunkel | Verwendung |
|---|---|---|---|
| `--bg` | `#F4F1E9` (Papier) | `#0C151E` | Seitengrund |
| `--surface` | `#FFFFFF` | `#132029` | Felder, Karten, Kacheln |
| `--surface-2` | `#F8F6F0` | `#182833` | Profil-Leiste, Zeilenköpfe, Eingaben |
| `--ink` | `#14232E` | `#E9E4D8` | Text |
| `--muted` | `#5E6F7A` | `#98A6AE` | Nebentext, Meta |
| `--line` | `rgba(20,35,46,.14)` | `rgba(233,228,216,.16)` | Linien, Ränder |
| `--deep` | `#0E4C5C` | `#8CC0CF` | Petrol: Beratung, Links, sekundäre Aktion |
| `--gold` | `#D9A441` | `#D9A441` | Primäraktion, aktiv, Stern, Abstimmung |
| `--gold-soft` | `#E8C27A` | `#E8C27A` | Hover/Schein |
| `--gold-deep` | `#8A6415` | `#E0B866` | Goldtext auf hellem Grund |
| `--night-1/2/3` | `#0A1722 / #0E2230 / #10394A` | gleich | App-Leiste, Bühnen |
| `--ok` / `--ok-bg` | `#2E6B4F` / `#EFF6F1` | `#7FCBA4` / `#12291F` | Erfolg, „umgesetzt" |
| `--warn` / `--warn-bg` | `#8C2B2B` / `#F9EFEE` | `#E08A8A` / `#2E1616` | Fehler, überfällig, Kritik |
| `--info-bg` / `--info` | `#EDF3F5` / `#0E4C5C` | `#12222B` / `#9BCBD8` | Gastband, Hinweise |
| `--pillar-1…4` | `#2E6B4F`, `#B07A1C`, `#2C89B0`, `#7A4E9E` | aufgehellt | Säulenfarben im Fächer (12 % Deckung als Hintergrund) |
| `--shadow` | `0 1px 2px rgba(14,34,48,.06), 0 6px 18px rgba(14,34,48,.05)` | `0 1px 2px rgba(0,0,0,.4), 0 8px 24px rgba(0,0,0,.35)` | Felder |
| `--shadow-lift` | `0 2px 4px rgba(14,34,48,.08), 0 14px 34px rgba(14,34,48,.12)` | analog | Hover, Overlays |
| `--overlay` | `rgba(255,255,255,.86)` | `rgba(19,32,41,.9)` | Regler-Overlay (+ `backdrop-filter: blur(10px)`) |
| `--scrim` | `rgba(14,34,48,.35)` | `rgba(0,0,0,.55)` | Schleier hinter Panels |

Kontrastregel: Text auf `--bg`/`--surface` ≥ 4.5:1; Gold nie als Fließtextfarbe auf Weiß (2.25:1) — Gold ist Fläche oder Kante, Text darauf ist `--ink`.

### 2.2 Typografie
- **Familie:** `--sans: -apple-system, 'SF Pro Display', BlinkMacSystemFont, 'Segoe UI Variable Display', 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif` für **alles** (D-P2). `--serif: Georgia, 'Times New Roman', serif` nur in der Wortmarke und optional in Bühnen-H1 der Erklärseiten.
- **Skala** (px / Zeilenhöhe / Gewicht): Display 32/1.15/700 (Bühnen) · H1 26/1.2/700 · H2 19/1.25/600 (Feldtitel, Zonen) · H3 16/1.3/600 · Body 16/1.55/400 · Small 13.5/1.45/400 · Meta 12/1.4/500 · Kapitälchen 11/1.2/600 `letter-spacing:.14em; text-transform:uppercase`.
- **Fächer-Ebenen:** 24/22/20/18/16 px, Gewicht 600, `letter-spacing:-.01em` (Handy 20/18/16/15/14).
- **Zahlen** in Kacheln/Zählern: `font-variant-numeric: tabular-nums`.

### 2.3 Maße
- Radien: Feld 18 · Karte 16 · Kachel 12 · Eingabe 10 · Chip/Knopf/Badge 999.
- Abstände (4er-Raster): 4, 8, 12, 16, 24, 32.
- App-Leiste 56 px (Handy 52) · Tableiste 60 px · Profil-Leiste 40 px · Feldkopf 44 px · Zonen-Leiste 44 px.
- Rasterlücke 12 px · Außenrand 12 px (Handy 8).
- Breakpoints: `--bp-sm 640` · `--bp-md 760` · `--bp-lg 1024` · `--bp-xl 1100` (Antragsseite zweispaltig) · `--bp-xxl 1500` (max. Breite des Parlaments).

### 2.4 Bewegung
- **Dauern:** `--d-fast 160ms` (Hover, Chips) · `--d-base 260ms` (Leisten, Reiter) · `--d-slide 320ms` (Overlays, Panels, Fächer-Zoom) · `--d-grow 420ms` (Balken, Ringe, Grafiken).
- **Easing:** `--e-out cubic-bezier(.22,.8,.3,1)` (Erscheinen, Gleiten) · `--e-in cubic-bezier(.4,0,1,1)` (Verschwinden) · `--e-spring cubic-bezier(.3,1.6,.5,1)` (Stern-Pop, Reaktionen).
- **Richtungen:** von rechts = Overlay/Regler · von links = Chat-Panel · von oben = Profil-Leiste, Menü · von unten = Sprechblasen, Bestätigungen · vom Klickpunkt = Fächer-Zoom.
- **Reduced Motion:** ein einziger Block am Ende: `@media (prefers-reduced-motion: reduce){ *,*::before,*::after{animation-duration:1ms!important;transition-duration:1ms!important;scroll-behavior:auto!important} ::view-transition-group(*),::view-transition-old(*),::view-transition-new(*){animation:none!important} }` (die zwei heutigen Blöcke zusammenführen).

---

## 3. Layouts

### 3.1 App-Leiste (alle Seiten)
```
[Wortmarke]  Parlament  Mandatare  Gremien  Umsetzungsregister  Zukunftswerkstatt  Übersicht     [＋ Antrag einbringen] [💬] [◯ M]
```
- Höhe 56 px, Hintergrund `--night-2` mit 1 px Goldlinie unten; Punkte 14 px/500, aktiver Punkt als Pille `rgba(232,194,122,.16)` + Goldtext; Hover-Pille `.12`.
- `＋ Antrag einbringen`: gefüllte Goldpille 36 px, Text `--night-1` 14/600, Hover `--gold-soft` + Lift 1 px.
- `💬` = Anstoß (nur Symbol, Tooltip „Anstoß geben"), öffnet die Anstoß-Karte **unter der Leiste rechts** (Popover, 340 px).
- `◯ M` = Konto-Avatar (Initiale, 32 px Kreis, Rand Gold bei aktiver Gremienrolle); Klick öffnet Popover: Name · Mein Gremium · Profil · Beitrag · Verwaltung (Admins) · Sprache DE/EN · Dunkel/Hell/System · Abmelden.
- Gäste: … | `Anmelden` (Text) · `Mitglied werden` (Goldpille) · `EN`.
- Handy (< 760): Wortmarke + Burger rechts; Menü gleitet **von rechts** (Panel 84 %), Schleier; im Parlament zusätzlich die Tableiste unten.

### 3.2 Das Parlament (`/parlament/`)
```
┌ App-Leiste ──────────────────────────────────────────────┐
│ ┌ WeicherFilter ──────────┐ ┌ Meine Favoriten ─────────┐ │
│ │ Profil-Leiste (40) ▾    │ │ [Suche]           Brotkrume│ │
│ │ Zeile · Zeile · Zeile   │ │        Fächer (5 Ebenen)  │ │
│ │           ↓ 4 weitere   │ │       Lebensbereiche      │ │
│ └─────────────────────────┘ └───────────────────────────┘ │
│ ┌ Wichtige Abstimmungen ──┐ ┌ Meine Region ─────────────┐ │
│ │ [K] [K] [K]             │ │ GEMEINDE │ [K] [K] [K] › │ │
│ │ [K] [K] [K]  ↓ 1 weitere│ │ BEZIRK   │ [K]           │ │
│ └─────────────────────────┘ │ LAND     │ [K] [K]       │ │
└──────────────────────────────└───────────────────────────┘ │
```
- Container: `display:grid; grid-template-columns:1fr 1fr; grid-template-rows:1fr 1fr; gap:12px; height:calc(100dvh - 56px); padding:12px; max-width:1500px; margin:0 auto;` — **kein** `main`-Padding unten, keine Fußzeile.
- Feld: `display:flex; flex-direction:column; min-height:0; background:var(--surface); border-radius:18px; box-shadow:var(--shadow); overflow:hidden; position:relative`.
- Feldkopf: `height:44px; padding:0 16px; display:flex; align-items:center; gap:12px; border-bottom:1px solid var(--line)`; Titel H2 19/600; rechts Werkzeuge (Suche 220 px, Chips, Symbolknöpfe 32 px).
- Feldkörper: `flex:1; min-height:0; overflow:auto; padding:8px 16px 32px; scrollbar-width:thin; overscroll-behavior:contain`.
- Scroll-Hinweis (FB-A5): `.feld-mehr` absolut unten, `height:28px`, Verlauf `linear-gradient(transparent, var(--surface))`, Pille 26 px mittig „↓ 3 weitere" (`--surface-2`, Rand `--line`, 12/600), `pointer-events` nur auf der Pille; Alpine berechnet `rest = Anzahl Kacheln unter der Sichtkante`; ohne JS: `.feld-korpus{background: linear-gradient(var(--surface) 30%, transparent), linear-gradient(transparent, var(--surface) 70%) bottom; background-attachment: local, scroll…}` (Scroll-Schatten-Technik).
- Tablet (760–1023): gleiches Raster, `height:auto; min-height:calc(100dvh - 56px)`, Felder `min-height:380px`.
- Handy (< 760): `display:block; scroll-snap-type:y mandatory; height:calc(100dvh - 52px - 60px); overflow-y:auto;` Feld `height:100%; scroll-snap-align:start; margin-bottom:8px`. Tableiste `position:fixed; bottom:0; height:60px; background:var(--surface); border-top:1px solid var(--line)`; fünf Ziele: Filter · Stern · Megafon · Karte · Chats, in der Mitte `＋` als 48-px-Goldkreis, der 8 px über die Leiste ragt.

### 3.3 Antragsseite (`/antrag/<id>/`)
- Kopf (max-width 1200): `‹ Parlament` (Text-Link), H1, Chip-Zeile, Meta-Zeile, Stern rechts oben; Hervorhebungsband gold.
- Zonen-Leiste `position:sticky; top:56px; height:44px; background:var(--bg)`; Reiter 14/600, aktiver Reiter Goldstrich 3 px (bewegt sich gleitend, `--d-base`).
- Desktop ≥ 1100: `display:grid; grid-template-columns:58fr 42fr; gap:24px;` Zone 1 links, Zone 2 rechts `position:sticky; top:100px; align-self:start; max-height:calc(100dvh - 116px); overflow:auto`; Zone 3 `grid-column:1 / -1`.
- < 1100: einspaltig, Zonen in Reihenfolge 1 → 2 → 3; < 760: Reiter schalten (Alpine `x-show` mit gerichteter Transition: nach rechts wechseln = alte Zone gleitet nach links raus, neue von rechts rein; Wischgeste ≥ 60 px), ohne JS alle untereinander.
- Zone 2 Karten: `--surface`, Radius 16, Kopfkarte mit Goldrahmen 1.5 px und Plakette „Modellrechnung"; Skelett-Zustand: Formen in `--surface-2` mit sanftem Schimmer (`shimmer 1.6s linear infinite`, nur wenn nicht reduced).

### 3.4 Gremien-Bereiche
- KoRat und Integritätsrat als 2×2-Raster wie das Parlament (Aufgaben · Posteingang · Beschlüsse · Parameter/Regeln), gleiche Feldkomponente.
- ER1-Entwurfsfenster: Desktop dreispaltig `minmax(280px,3fr) 5fr 4fr`, jede Spalte eigen scrollend; Handy Reiter.

---

## 4. Komponenten (Anatomie, Zustände, Bewegung)

| Komponente | Anatomie | Zustände | Bewegung |
|---|---|---|---|
| **Kachel** (`.kachel`) | Thema-Chip + Themen-Stern · Titel (2 Zeilen) · Antrags-Stern · Phase-Chip · Balken 4 px · Standtext · Frist „noch **26** Tage" + Ring 20 px · Direkt-Handlung · (Grund) | Ruhe · Hover (Lift 3 px, Goldkante 1.5 px, `--shadow-lift`) · Fokus (Ring 2 px Gold außen) · Gewählt (Knopf gold umrandet) · Erledigt (Gold-Haken 1,5 s) · Überfällig (Frist rot) | Erscheinen gestaffelt 40 ms/Kachel (`auftauchen` 260 ms); Balken `wachsen` 420 ms; Ring `stroke-dashoffset` 420 ms |
| **Zeile** (WeicherFilter) | Titel · Stern · Chips · Mini-Balken · Stand · Direkt-Handlung · „Warum hier?" | Hover (Hintergrund 5 % Gold) · Umsortieren | FLIP/View-Transition beim Neuordnen (`view-transition-name` je Zeile = Antrags-ID) |
| **Chip** | Pille 26 px, 12.5/600 | neutral · aktiv (gold) · Zähler-Punkt | Hover Lift 1 px |
| **Profil-Leiste** | 40 px, Chips, ⚙, Pfeil ˄ | ausgefahren · eingefahren (Griff 14 px ˅) | `height`/`transform` 260 ms `--e-out`; Inhalt `opacity` 160 ms |
| **Regler-Overlay** | Kopf (Name, Stift, X) · Schalter · 9 Regler · Aktionszeile | offen · geschlossen · ungespeichert (● im Kopf) | von rechts `translateX(100%→0)` 320 ms; Schließen 220 ms `--e-in` |
| **Regler** | Label links, Wert rechts (tabular), Bahn 4 px `--line`, gefüllt bis Wert `--gold`, Griff 18 px | Fokus (Griff Ring) · gezogen (Griff 22 px) | Wert-Zahl „tickt" (transition 120 ms) |
| **Fächer-Knoten** | Stern · Text-Pille (Säulenfarbe 12 %) | Anker (Goldrand, 24 px) · normal · entfaltet · Hover (Faden bis Wurzel gold 2 px) | Zoom vom Klickpunkt 320 ms; Ebene-5-Pillen `scale(.8→1)` 180 ms gestaffelt 20 ms; Fäden `stroke-dashoffset` 260 ms |
| **Chat-Panel** | Griff 24×96 (links, mittig) · Panel 380 px · Kopf · Liste 3 Spalten | zu · offen · ungelesen-Zähler | von links 320 ms; Schleier `opacity` 200 ms |
| **Sprechblase** | Avatar 32 · Name · Zeit · Text · Zeile (Antworten · 👍 · #) | eigen (Goldkante) · Antwort (eingerückt 16 px + Linie) · Kritik (rotes Etikett) · System (gestrichelter Goldrahmen, „Passt alles") · ausgeblendet | Neue Blase von unten 260 ms; Reaktion `--e-spring` 220 ms; Anker-Hervorhebung 2 s Goldhintergrund → transparent |
| **Zonen-Leiste** | 3–4 Reiter, Goldstrich | aktiv · Scroll-Spy | Strich gleitet 260 ms |
| **Plakette** | Pille mit Symbol („Modellrechnung", „Ausschreibung: ja") | neutral · gold · warn | — |
| **Lastampel** | 3 Kreise 14 px | grün/gelb/rot aktiv | aktiver Kreis pulsiert 2 s (Deckung .7→1), reduced = statisch |
| **Zeitstrahl** | Linie + Etappen-Punkte + Monatsspannen | — | füllt sich von links 420 ms |
| **Ring** (Frist/Prozent) | SVG-Kreis 20–40 px, Bahn `--line`, Wert `--gold` | — | `stroke-dashoffset` 420 ms |
| **Zähler** (Zahlenband) | tabular-nums | — | zählt beim Erscheinen von 0 hoch (600 ms, nur einmal je Seite, IntersectionObserver) |
| **Skelett** | Formen `--surface-2`, Radius wie Ziel | — | Schimmer 1.6 s |
| **Toast in der Kachel** | Gold-Haken + „Erfasst" | — | Einblenden 160 ms, Halt 1,2 s, Ausblenden 260 ms |
| **Popover** (Konto, Anstoß) | Karte 16 px Radius, Pfeilspitze | — | von oben 200 ms, Schließen Escape/Außenklick |
| **Reiter-Tableiste** (Handy) | 5 Symbole, ＋ Mitte | aktiv gold | Symbol `scale(1.1)` 160 ms |

---

## 5. Muster für htmx + Alpine

- **Feldtausch:** `hx-get="…" hx-target="#feld-x" hx-select="#feld-x" hx-swap="outerHTML transition:true"` — mit `transition:true` nutzt htmx die View-Transition-API; `::view-transition-old/new(feld-x)` mit gerichteter Bewegung (Richtung als `data-richtung="links|rechts"` am Auslöser gesetzt, CSS wählt die Keyframes).
- **Rückmeldung statt Flash:** Views, die per htmx aufgerufen werden, liefern das Partial **mit** einem `hx-trigger`-Header (`HX-Trigger: {"erfasst": {"id": 4}}`); Alpine hört darauf und zeigt den Kachel-Toast. Ohne htmx: Redirect + Django-Messages wie heute.
- **Alpine-Zustände** (je Komponente ein `x-data`): `filterLeiste{offen}` (localStorage), `reglerOverlay{offen, geaendert}`, `chatPanel{offen}`, `zone{aktiv}`, `feldMehr{rest}`, `faecher{entfaltet, zoomVon}`.
- **Scroll-Gedächtnis:** `localStorage['ddoe.chat.<id>']`; `document.addEventListener('scroll', throttle(…))`; Wiederherstellung in `htmx:afterSettle` und `DOMContentLoaded`.
- **Live-Regler:** `hx-trigger="input changed delay:400ms from:#regler-form"`, Ziel `#filter-liste`, `hx-swap="outerHTML transition:true"`.
- **Zähler/Ringe/Balken:** Klasse `.animiert-beim-erscheinen`, IntersectionObserver setzt `.an`; CSS animiert.
- **Keine Inline-Handler** (`onclick`, `oninput`) mehr — alles über Alpine-Direktiven oder htmx-Attribute; CSP-fähig (`script-src 'self'`).

---

## 6. Zustände, Fehler, Leerzustände (Wortlaut)

| Ort | Leer | Fehler | Laden |
|---|---|---|---|
| WeicherFilter | „Gerade läuft nichts — Antrag einbringen ›" | „Konnte nicht laden — erneut versuchen" (Knopf) | Skelett 5 Zeilen |
| Favoriten (Suche) | „Nichts gefunden — anders schreiben?" | — | — |
| Wichtige Abstimmungen | „Derzeit nichts hervorgehoben." | — | Skelett 4 Kacheln |
| Meine Region (Zeile) | „Noch nichts in deiner Gemeinde — Antrag einbringen ›" / „…in deinem Bezirk…" / „…in deinem Land…" | — | Skelett 3 Kacheln |
| Chat | „Noch kein Beitrag — der erste kann deiner sein." | „Nicht gesendet — erneut versuchen" | — |
| Zone 2 | „Noch keine Einschätzung — sie entsteht in der Beratung." / „Kein Anbieter angeschlossen." | „Lauf gescheitert — im Archiv dokumentiert" | Skelett 5 Karten |
| Chat-Panel | „Noch keine Gespräche — antworte jemandem oder warte auf Antwort." | — | Skelett 6 Zeilen |

Fehlertexte nennen immer die nächste Handlung; keine Fehlercodes für Mitglieder (die stehen im Log).

---

## 7. Barrierefreiheit (Pflicht)

Skip-Link · Landmarken (`header`, `main`, `nav`, `section aria-labelledby`) · Fokusring 2 px Gold außen, nie entfernt · Tastatur: Overlays/Panels mit Fokusfalle + Escape, Rückgabe des Fokus · `aria-expanded/controls` an allen Auf-/Zuklappern · `aria-pressed` an Sternen und Reaktionen · Regler `aria-valuetext` · Live-Regionen (`aria-live=polite`) für Kachel-Toasts, Chat-Neuzugänge, Filter-Umsortierung („Liste neu geordnet") · Grafiken `role=img` + Textalternative + Zahlen als Text · Kontraste nach 2.1 · Bewegung nach Reduced Motion · Touch-Ziele ≥ 44 px · Sprache je Element (`lang`).

---

## 8. Abnahme des Looks (Bildschirmtests, in `tests/e2e/` mit Playwright)

1. `/parlament/` 1440×900: keine Seiten-Scrollbar; vier Felder gleich groß (± 1 px); Screenshot-Vergleich gegen `docs/sichtpruefung/<version>/parlament-desktop.png`.
2. `/parlament/` 390×844: Snap je Feld; Tableiste sichtbar; ＋ mittig.
3. Profil-Leiste ein-/ausfahren: Höhe 40 → 0 innerhalb 300 ms; Zustand nach Reload erhalten.
4. Regler ziehen: Liste ordnet innerhalb 1 s um; „Warum hier?" öffnet.
5. Fächer: kein überlappender Text (Bounding-Box-Test aller `.fknoten`); Klick zoomt (Screenshot-Sequenz 3 Frames).
6. Antragsseite: Zonen-Leiste klebt; Zone 2 klebt; Reiter markieren beim Scrollen.
7. Chat: Antwort eingerückt; Panel von links; Scroll-Gedächtnis nach Seitenwechsel.
8. Dark Mode: kein Element mit hellem Hintergrund außer Grafiken mit eigenem Papier; Kontrastprüfung automatisiert (axe).
9. Reduced Motion: keine `transform`-Animation läuft (computed `animation-duration` ≤ 1 ms).
10. Ohne JavaScript (Playwright `javaScriptEnabled:false`): alle Handlungen der Abnahmen 3–7 als Formular/Link erreichbar.

---

*Design-Spezifikation 1.0 · 2.9.2026 · Ergänzungen kommen über das Fahrtenbuch (Bereich P).*
