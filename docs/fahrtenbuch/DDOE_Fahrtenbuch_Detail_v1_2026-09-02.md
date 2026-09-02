# DDÖ ParlamentPlattform — Das Fahrtenbuch (Detailfassung 1.0)

Stand: 2. September 2026 · Ersetzt `DDOE_Fahrplan_Oberflaeche_2026-09-01.md` als Arbeitsgrundlage · Maßstab: die wörtlichen Anweisungen des Gründers (`DDOE_Original_Anweisungen_A0.txt`, acht Nachrichten A0-01 … A0-08, aus `chatanweisungenvonmir.ods`)

---

## 0. Wie dieses Fahrtenbuch zu lesen ist

**Warum es dieses Dokument gibt.** Der bisherige Fahrplan hat die Anweisungen des Gründers zu Stichworten verdichtet („P2 · Der Favoriten-Fächer"). Beim Bauen wurde dann aus dem Stichwort heraus interpretiert — und die Details gingen verloren (drei statt fünf Fächer-Ebenen, feste Chip-Leiste statt einfahrbarer Leiste mit Pfeil, Antragsseite ohne die drei Zonen, kein Chatsystem). Dieses Fahrtenbuch macht es umgekehrt: **Jede Anweisung wird in ihre kleinsten prüfbaren Einzelforderungen zerlegt**, jede Einzelforderung bekommt eine Kennung, den wörtlichen Beleg, eine bis ins Kleinste ausgearbeitete Beschreibung von Aussehen und Verhalten, Abnahmekriterien und den heutigen Ist-Stand mit Beleg im Code.

**Aufbau eines Eintrags**

```
### FB-X1 · Kurztitel                                        Status
Quelle: A0-05 — „…wörtliches Zitat…"
Spezifikation: Aussehen · Verhalten · Zustände · Daten · Responsiv · Ohne JavaScript · Barrierefreiheit
Abnahme: prüfbare Kriterien (was ein Tester sieht und tut)
Ist (2.9.2026): was der Code heute macht, mit Datei:Zeile
Delta: was zu bauen oder zu ändern ist
Offen: Entscheidung des Gründers nötig (❓)
```

**Status-Legende**

| Zeichen | Bedeutung |
|---|---|
| ✅ | umgesetzt und gegen die Anweisung geprüft |
| 🟡 | teilweise umgesetzt — das Delta steht im Eintrag |
| ❌ | nicht umgesetzt |
| ⚠️ | bewusst anders umgesetzt als angewiesen (mit Grund); Bestätigung oder Rückbau nötig |
| ❓ | Entscheidung des Gründers nötig, bevor gebaut wird |

**Was „wörtlich" und was „Ausarbeitung" ist.** In jeder Spezifikation steht zuerst, was der Gründer gesagt hat (kursiv, mit A0-Nummer). Alles Weitere ist Ausarbeitung — sie füllt Lücken so, wie es zur Gesamtidee passt, und ist mit „Ausarbeitung:" gekennzeichnet. Wo eine Ausarbeitung eine echte Weiche stellt, steht ein ❓ und der Punkt erscheint in Teil D (Offene Entscheidungen).

**Die sieben Grundregeln, die über allem stehen** (aus Satzung 2.5, Lastenheft L1–L7 und den Anweisungen)

1. **Werkzeug, keine Werbefläche.** Im Parlament und in den Gremien-Bereichen steht kein Erklär- oder Werbesatz. Erklärt wird auf `/`, `/mitgliedschaft/`, `/zukunftswerkstatt/`, `/partner/` (A0-05: „eine Benutzeroberfläche, die mit so wenig Beschreibung wie möglich auskommt"; Vorgabe 2.9.).
2. **App, nicht Homepage.** Das Parlament füllt den Bildschirm, ist direkt bedienbar, bewegt sich weich und gerichtet (A0-05: „mehr nach App aussieht als nach Homepage").
3. **Ohne JavaScript bleibt alles bedienbar.** Bewegung, Teil-Austausch und Overlays sind Zugabe (htmx + Alpine.js, eingecheckt, kein CDN). `prefers-reduced-motion` schaltet Bewegung ab.
4. **Keine Stimmgewichtung, nie.** Der Demos darf atmen (Zuschnitt lernbar), die Stimme wiegt immer gleich (A0-02; § 5 Abs 6/7).
5. **Die KI schlägt vor, sie entscheidet nie.** Jede Ausgabe gekennzeichnet, mit Modell, Kontextstand, Quellen; archiviert; beanstandbar (§ 2 Abs 6, § 6 Abs 11, L7).
6. **Alle Stellgrößen sind Parameter** im Parameterregister — beschlossen, versioniert, lernbar (§ 6 Abs 11 lit c). Laufende Verfahren behalten ihre eingefrorenen Regeln (§ 5 Abs 5).
7. **Jede neue Detailbeschreibung wandert sofort wörtlich hierher** — bevor gebaut wird (Arbeitsregel vom 2.9.).

**Namen (entschieden 1.9.2026):** *Zukunftswerkstatt* (Werkzeug zur rekursiven Optimierung der gesamtgesellschaftlichen Selbstorganisation) mit der *StaatsSimulation* als Rechenkern · *WeicherFilter* (der selbst eingestellte Feed) · *Parlament* (das Hauptfenster) · *Umsetzungsregister* (Menüpunkt) · *Alpha-Phase* (nicht mehr „Prototyp") · *Vorschlag* des Expertenrats (nie „Vorlage") · *Anstoß* (Feedback-Widget). Verworfen: Gemeinwerk/Commonwork, Eigenstrom.

**Verweise:** Satzung = `Satzung_DDOE_2.5_Entwurf.md` · Lastenheft = `parlamentplattform-phase0/docs/CONCEPT.md` (F-01…F-71, L1–L7) · Strategie = `DDOE_StaatsSimulation_Strategie_2026-09-01.md` (Ringe 0a–5) · Ist-Inventar = `Funktionsinventar_Ist_2026-09-02.md` · Design = `DDOE_Design_Spezifikation_App-Look.md` · Mockup (klickbar, Desktop + Handy) = `mockups/parlament_app_mockup.html`.

---

## Teil A · Die Anweisungen, Satz für Satz zerlegt

Jede der acht Nachrichten ist hier in nummerierte Forderungen zerlegt (Spalte „FB"). Die Detailspezifikation steht in Teil B unter der jeweiligen FB-Kennung.

### A0-01 · Der Antragsweg mit KI (StaatsSimulation) — Nachricht vom ~29.8.

| Nr. | Forderung (sinngemäß, Zitat in Teil B) | FB |
|---|---|---|
| 1 | Eine (möglichst kostenlose, per API-Key angebundene) KI im Antragsweg | FB-H1 |
| 2 | Prüfen, ob ein ähnlicher Antrag bereits eingegangen ist; dem Nutzer zeigen; Wahl: bestehenden unterstützen oder eigenen stellen | FB-H2 |
| 3 | Einschätzung: welche Gesetze müssten geändert werden; Folgen für Judikatur und Exekutive inkl. Auf-/Abbau von Beamten und Vertragsbediensteten | FB-H3 |
| 4 | Einschätzung: Aufwand für den Staatsapparat; vertretbar im Licht der laufenden Umsetzungen; Dauer bis Inkrafttreten ohne Überlastung | FB-H4 |
| 5 | Prüfen, ob eine Ausschreibung nötig wäre | FB-H5 |
| 6 | Spezielle Kontexte (Simulation), die neue Anträge durchlaufen — außer der Nutzer wählt einen bestehenden (dessen Ergebnisse existieren schon) | FB-H6 |
| 7 | Kontext schrittweise vertiefen bis zu „welche Firmen könnten sich bewerben" | FB-H7 |
| 8 | Kontext aus geprüft korrekten Angaben: Gesetzesdatenbank mit Querverweisen; Datenbank Beamte/Vertragsbedienstete (soweit öffentlich); Firmendatenbank mit Kapazitäten | FB-H8 |
| 9 | Das System soll das gesellschaftliche Leben durchspielen können; Hin und Her, mit dem sich die Plattform selbst anpasst | FB-H9 |
| 10 | Beispiel: stabilisierende, unterbeteiligte Anträge auf die Frontseite stellen | FB-H10 |
| 11 | Beispiel: Muster erkennen (schnell revidierte Gesetze, Korruptionsgefahr) und Regelungen ableiten | FB-H11 |
| 12 | Expertenrat in zwei Gruppen (zweite = Redundanz und Korruptionsprüfung) | FB-I3 |
| 13 | Regelmäßige Kontext-Updates; bei Änderung der Gegebenheiten sofort | FB-H12 |
| 14 | Auf die Berufungsdauer begrenzte Sonderfunktionen für Ratsmitglieder (z. B. Abstimmung untereinander) | FB-I1 |

### A0-02 · Korrekturen und Grundsätze — Nachricht vom ~29.8.

| Nr. | Forderung | FB |
|---|---|---|
| 1 | Vorschläge der Simulation zu unterbeteiligten Anträgen gehen an den **Koordinationsrat**, nicht an den Integritätsrat | FB-H10, FB-I5 |
| 2 | Demos-Zuschnitt regional (Gemeinde/Land/Bund; Haupt- vs. Nebenwohnsitz) — lernbar über die Zeit | FB-J6 |
| 3 | Nicht-Wissen ist Teil der Strategie: das System spielt mit der Gesellschaft zusammen | FB-H9 |
| 4 | **Keine Stimmrechtsdifferenzierung**, besonders nicht bei der Endabstimmung | Grundregel 4 |
| 5 | Antragsweg führt über den Expertenrat, sobald genug Zustimmung (Schwellen lernbar); Plattform wartet auf den Vorschlag; dann Endabstimmung | FB-I2, FB-J1 |

### A0-03 · Gremien, Rollen, Koordinationsrat, Weltgedanke — Nachricht vom ~30.8.

| Nr. | Forderung | FB |
|---|---|---|
| 1 | Fähigkeiten-Zuweisung erweitern: als Admin, später automatisch, berufenen Experten die Expertenrolle zuteilen | FB-I1 |
| 2 | Expertenrolle macht eigenen Bereich sichtbar: roher unterstützter Antrag + Entwurfsfenster; Expertenrat stimmt sich ab und entwirft gemeinsam; einreichen | FB-I2 |
| 3 | Entwurf wird den Unterstützern vorgelegt; sie stimmen: zurück mit Verbesserungswünschen oder zur Endabstimmung; dann alle Wahlberechtigten | FB-G6, FB-I2 |
| 4 | Expertenrat 2: eigene Oberfläche, prüft den Vorschlag von Expertenrat 1 — nicht bei Gesetzen, bei direkten Aufgaben (Beschaffung); Korruptionsprüfung; abstimmen; validieren / begründet zurückgeben / Austausch von ER1 verlangen | FB-I3 |
| 5 | Diese Regelungen nutzt der Koordinationsrat für leichte Weichenstellungen ohne Stimmdifferenzierung | FB-I5, FB-J4 |
| 6 | Parameter benennen und nach und nach in die Simulation einbinden (Lerndatensatz); Infrastruktur für den Koordinationsrat dafür | FB-J4, FB-J5 |
| 7 | Koordinationsrat braucht eigene Oberfläche: Aufgaben, Vorschläge/Hinweise der Simulation empfangen, darüber abstimmen, was wie umgesetzt wird | FB-I5 |
| 8 | Zusammenarbeit mit Parteien weltweit ist ein Grundstein; gleiche Lernparameter in verschiedenen Systemen | FB-M1, FB-J5 |
| 9 | Gesamtstrategie überdenken und auf der Plattform öffentlich erklären | FB-N5 (✅ `/zukunftswerkstatt/`) |
| 10 | Menüpunkt „Umsetzung" heißt „Umsetzungsregister" | FB-N1 |

### A0-04 · Mitgliedschaft erklären, Menüpunkt Parlament — Nachricht vom ~30.8.

| Nr. | Forderung | FB |
|---|---|---|
| 1 | Nichtmitgliedern die Rechte eines Mitglieds plakativ zeigen, dann im Detail; Zukunftswerkstatt erklären; Grafiken; Flowchart Antrag → Gesetz | FB-K1 |
| 2 | Hauptfenster heißt „Parlament" und ist Menüpunkt | FB-N2 |
| 3 | Frage: Wichtige Abstimmungen durch Beschluss des Koordinationsrats? | FB-D4 (Antwort: Satzung sagt Integritätsrat; KoRat beantragt) |

### A0-05 · Die Oberfläche: WeicherFilter, Fächer, Kacheln, Chat, Fristen — Nachricht vom ~31.8. (die längste)

| Nr. | Forderung | FB |
|---|---|---|
| 1 | Feed, in dem man selbst einstellt, wie er funktioniert (Favoriten + Regler) | FB-B1 |
| 2 | Regler: wofür/wogegen gestimmt · unterstützt · Interessantes außerhalb der Favoriten · mehr Unterstützungsanträge · mehr Abstimmungen · mehr chronologisch · nur noch kurz online · wenig fehlt | FB-B2 |
| 3 | Bis zu 5 speicherbare Gesamteinstellungen, jederzeit umschalt- und anpassbar | FB-B3 |
| 4 | Umschalten über kleines Menü am oberen Rand mit Pfeil zum Einfahren (Slide-Animation) | FB-B4 |
| 5 | Rechter Rand: Reglerbereich als halbtransparentes Overlay; zeigt aktive Konfiguration; Einzelanpassung; „Speichern" bzw. „Neue Konfiguration speichern" (wenn < 5) | FB-B5 |
| 6 | Vier gleich große Bereiche im Rechteck über den ganzen Bildschirm; am Handy untereinander | FB-A1 |
| 7 | Bereiche: WeicherFilter, Meine Favoriten, Wichtige Abstimmungen, Meine Region — direkt bedienbar, selbsterklärend | FB-A2 |
| 8 | App-Optik statt Homepage; Mitmachen direkt und einfach | FB-A3, FB-P1 |
| 9 | Favoriten = grafischer Themenbaum: unten „Lebensbereiche" 24 pt, darüber Unterkategorien in 2er-Schritten kleiner, mit Fäden verbunden, ohne die vier Säulen zu benennen | FB-C1 |
| 10 | So weiter, dass ein Fächer mit 5 Ebenen entsteht | FB-C2 |
| 11 | Klick auf Element: Ansicht bewegt sich hinein; Element wird 24er-Anker unten | FB-C3 |
| 12 | Alle Elemente mit Favoriten-Stern | FB-C4 |
| 13 | Wichtige Abstimmungen: 4 oder 6 gleichmäßig positioniert; Thema + Stern; Stand (% abgestimmt und wofür); Resttage; Klick öffnet Antrag | FB-D1, FB-D2, FB-D3 |
| 14 | Antragsseiten immer mit drei Bereichen: Text · KI-Einschätzungen (mit Grafiken und Animationen) · Chat | FB-F1, FB-F2, FB-F3 |
| 15 | Eigenes Chatsystem: unterhalb (Scrollposition merken, auch nach Seitenwechsel) | FB-G1, FB-G2 |
| 16 | Ausklappmenü links auf der Parlament-Seite: chronologisch, drei Spalten (Thema, Antragsname, Chatpartner — implizit durch Antwort, ohne Nennung) | FB-G3 |
| 17 | Leiste scrollbar; Chats verschwinden bei jeder Hochstufung; Klick führt zur Antragsseite | FB-G4, FB-G5 |
| 18 | Meine Region: 3×3 Felder (Gemeinde/Bezirk/Land), direkt anklick- und abstimmbar; wie Wichtige Abstimmungen aufgebaut | FB-E1, FB-E2 |
| 19 | Bei beiden: erkennbar, wenn mehr da ist als sichtbar; dann scrollen | FB-A5 |
| 20 | Fristen: Unterstützung 2 Monate · Expertenrat 3 Wochen · Unterstützer 2 Wochen · Expertenrat 2 Wochen · Endabstimmung 4 Wochen | FB-J1 |
| 21 | Alles Parameter zum Lernen; KoRat mit Partnerparteien; gleiche Lernart, nicht gleiche Werte | FB-J2, FB-J5 |
| 22 | Button „Eigenen Antrag einbringen" aus dem Bereich weg; Menüeintrag prominenter | FB-N3 |
| 23 | Skills/Plugins/GitHub-Repo für die Umsetzung | FB-P4 (E: htmx + Alpine, eingecheckt) |
| 24 | Seite „Lebensbereiche" aus dem Menü | FB-N4 |
| 25 | Fahrplan führen | dieses Dokument |

### A0-06 · Satzung, Parameterverfahren, Kennzahlen, Namen — Nachricht vom ~31.8.

| Nr. | Forderung | FB |
|---|---|---|
| 1 | Beschlossenes in die Satzung schreiben; internationale Kooperation des KoRat mit Schnittstellen/Tools | ✅ Satzung 2.5 § 12 Abs 5, § 6 Abs 11 |
| 2 | Parameterverfahren: KoRat testet → Ergebnisse fließen in die Simulation → Vorschläge → Freigabe → Einführung → weiter lernen | FB-J3 (✅ Satzung § 6 Abs 11 lit c; ❌ Software) |
| 3 | Kennzahlen: Beteiligungsquote nach Erstaufruf binnen Zeit, Verweildauer, Themen-Attraktivität; kaskadierende Lernschleifen bis zum Optimum | FB-J7 |
| 4 | Fehlendes für die Satzung nennen; StaatsSimulation detaillierter | ✅ Satzung 2.5 § 6 Abs 11 (a–f) |
| 5 | Umbenennung → *später verworfen* (A0-07: Zukunftswerkstatt) | FB-N5 |
| 6 | Feed heißt WeicherFilter | FB-N6 ✅ |

### A0-07 · Beschlüsse: Fächer-Mitte, Abstimmungs-Chat, Archiv, Namen, Partner-Seite — Nachricht vom 1.9.

| Nr. | Forderung | FB |
|---|---|---|
| 1 | P1 starten wie vorgeschlagen | ✅ |
| 2 | Fächer: ab der dritten Ebene sitzt die Auswahl in der Mitte als 24er-Anker, damit man zurück nach oben klicken kann | FB-C3 |
| 3 | Nach Hochstufung zum Expertenrat ruht der Chat, bis der Expertenrat den Vorschlag geliefert hat | FB-G6 |
| 4 | Abstimmungs-Chat: Zustimmen/Ablehnen je Kommentar per Emoji/Zeichen; Kritik muss konkret sein; Reihung nach Engagement; „Passt alles"-Kommentar oben mit > 50 % → Hochstufung zur Endabstimmung nach Fristablauf; erster Entwurf dieser Funktion | FB-G6 |
| 5 | Terminus „Vorschlag" (nicht Vorlage); der Vorschlag ist der Text, der zur Endwahl hochgestuft wird | FB-N7 ✅ |
| 6 | Archiv-Registerkarte: alle Chats und Vorgänge von der Antragstellung bis zu den Vorschlägen, zum Hineinklicken, exportierbar | FB-G7 |
| 7 | Namen: Zukunftswerkstatt statt StaatsSimulation, WeicherFilter statt Feed | FB-N5, FB-N6 ✅ |
| 8 | Unterseite für Menschen aus anderen Ländern: Gesamtstrategie verständlich, Fahrplan der Zusammenarbeit, Kontakt-Button; später Schnittstelle zwischen Ländern; Software wird bereitgestellt; Lernfortschritt und Parameter austauschen; Teil der Plattform, verlinkt in der Fußzeile; Teaser auf ddoe.at; Konto mit Bestätigung; Rolle „Internationaler Partner" mit eigener Oberfläche | FB-M1 … FB-M5 |

### A0-08 · Mitglied werden nur über die Plattform, Anstoß, Homepage, Mandatar-Steuerung — Nachricht vom 1.9.

| Nr. | Forderung | FB |
|---|---|---|
| 1 | Mitglied werden nur noch über die Plattform; Alpha statt Prototyp | FB-K2 ✅ |
| 2 | Anstoß-Widget auf jeder Seite; Nachrichten speichern (Webserver/FTP) für spätere Auswertung | FB-K3 (⚠️ eigene DB statt FTP — Vorschlag) |
| 3 | Mitmachen-Seite auf ddoe.at weg bzw. auf die Plattform-Anmeldung führen | FB-O1 |
| 4 | „So funktioniert's" neu: systemischer Ansatz, 18 Jahre bis 2044, Volksabstimmung | FB-O2 ✅ |
| 5 | „Distanz zwischen Wissen und Macht": Minderheiten = Betroffene/Berufsgruppen; System muss sich selbst kennenlernen | FB-O3 ✅ |
| 6 | Plattform-Link im Menü; Alpha-Phase | FB-O4 ✅ |
| 7 | „Dieses Werkzeug baut sich nicht von selbst" ändern; Mitgliedwerden + Fähigkeiten einbringen → Plattform; Spenden-Button mit QR; Menü „Mitmachen" → „Spenden" | FB-O5 |
| 8 | „Minderheiten mit Sachkunde": Zukunftswerkstatt statt Simulation | FB-O6 ✅ |
| 9 | Plattform bis 2044 eingeschränkt nutzbar; Basisparameter gemeinsam erarbeiten | FB-J2, FB-L1 |
| 10 | Mandatar-Steuerung: Seite mit Foto, Aufgaben, Entscheidungsprozessen; Pflicht des Mandatars, Informationen einzustellen | FB-L1 |
| 11 | Mandatar-Rolle: Instant-Reports mit Fristen; betreute Abstimmungen | FB-L2 |
| 12 | Parlament von Anfang an für Abstimmungen nutzen: Kandidaturen als Anträge; Beteiligung am bestehenden Antrag; meiste Zustimmung gewinnt | FB-L3 ✅ |
| 13 | Ab wann? (Frage) — Vorgang gehört in die Satzung | FB-L4 (✅ § 7 Abs 1: von Anfang an) |

---
## Teil B · Die Detailspezifikationen

### Bereich A · Das Parlament als Ganzes (Hauptfenster)

#### FB-A1 · Vier gleich große Bereiche über den ganzen Bildschirm — ✅ (0.33.0, S1)
**Quelle:** A0-05 — *„Alles als halbtransparentes Overlay über dem Feed Bereich der einer von 4 im Rechteck über den ganzen Bildschirm (responsiv - bei handys untereinander) angeordneten gleichgroßen Bereichen ist."*

**Spezifikation**
- *Aussehen (Desktop ≥ 1024 px):* `/parlament/` ist ein 2×2-Raster, das **exakt die Höhe des Anzeigebereichs unter der App-Leiste füllt** — kein Seiten-Scroll, kein Fußbereich unter dem Raster. Höhe des Rasters = `100dvh − Höhe der App-Leiste`; Rasterlücke 12 px; Außenrand 12 px. Alle vier Felder sind gleich groß (`grid-template: 1fr 1fr / 1fr 1fr`), Ecken 18 px, Kartenhintergrund, weicher Schatten. Position: links oben **WeicherFilter**, rechts oben **Meine Favoriten**, links unten **Wichtige Abstimmungen**, rechts unten **Meine Region** (heutige Anordnung bleibt).
- *App-Leiste:* eine Zeile, 56 px hoch (mobil 52 px): Wortmarke links, Hauptpunkte in der Mitte, **„＋ Antrag einbringen"** als gefüllter Gold-Knopf rechts, dann Konto/Sprache. Die bisherige zweite Nav-Zeile (Beitrag · Name · Abmelden · EN) wandert in ein Konto-Menü (Avatar-Kreis mit Initiale, Klick öffnet ein kleines Menü: Beitrag · Mein Gremium · Verwaltung · Sprache · Abmelden). Ergebnis: **eine** Leiste statt zwei.
- *Fußzeile:* auf `/parlament/` **keine** Fußzeile (die Links sind über das Konto-Menü bzw. „⋯ Mehr" erreichbar); auf allen anderen Seiten bleibt sie.
- *Feld-Innenaufbau (für alle vier gleich):* Feldkopf 44 px (Titel 17 px semibold, rechts der Kontext-Chip bzw. Werkzeuge), Feldkörper scrollt **innen** (`overflow-y:auto`, dünne Scrollleiste), am unteren Rand der **„mehr vorhanden"-Hinweis** (FB-A5). Kein Feldfuß mit Erklärsätzen.
- *Responsiv (Tablet 760–1023 px):* 2 Spalten × 2 Zeilen bleiben, Feldhöhe `calc((100dvh − Leiste − 36px) / 2)`, mindestens 380 px; darunter scrollt die Seite.
- *Responsiv (Handy < 760 px):* Die vier Felder liegen **untereinander**, jedes Feld ist ein „Bildschirm": Höhe `calc(100dvh − Leiste − Tableiste)`, `scroll-snap-type: y mandatory` auf dem Container, `scroll-snap-align: start` je Feld. Unten eine **feste Tableiste** mit vier Symbolen (Filter · Stern · Megafon · Karte) und dem Gold-„＋" in der Mitte; Tipp springt zum Feld (Snap-Scroll). Die aktive Tab ist gold markiert. *(Ausarbeitung — der Gründer sagte nur „bei Handys untereinander".)*
- *Ohne JavaScript:* Raster und Snap sind reines CSS; die Tableiste besteht aus Anker-Links (`#feld-filter` …).
- *Barrierefreiheit:* jedes Feld ist ein `<section aria-labelledby>`; Tab-Reihenfolge Feld 1 → 4; Feldkörper mit `tabindex="0"` scrollbar per Tastatur.

**Abnahme**
1. Auf 1440×900 ist nach dem Laden von `/parlament/` **kein** vertikaler Seiten-Scroll möglich; alle vier Felder sind vollständig sichtbar und exakt gleich groß (± 1 px).
2. Auf 390×844 (Handy) rastet jedes Feld beim Scrollen ganz ein; die Tableiste bleibt stehen; Tipp auf „Stern" zeigt „Meine Favoriten" bildschirmfüllend.
3. Keine Fußzeile auf `/parlament/`; auf `/antrag/1/` ist sie da.
4. Mit deaktiviertem JavaScript gilt 1–3 unverändert.

**Ist (0.33.0):** ✅ Raster `minmax(0,1fr)`-Zeilen auf `calc(100dvh − var(--bar) − var(--band))`, Lücke/Rand 12 px, Feldkopf 44 px, Körper scrollt innen (`base.html:212-217`, `:230-233`); eine App-Leiste 56/52 px (`_leiste.html`, `base.html:74-77`); keine Fußzeile im Parlament (`parlament.html:7`, Block `fuss` in `base.html:396`); Handy-Snap + Tableiste (`base.html:257-270`, `_tabs.html`); Anstoß in der Leiste (FB-K3). Belegt durch `tests/e2e/test_app_rahmen.py` (Abnahmen 1–4, mit und ohne JavaScript) und `verfahren/test_app_rahmen.py:143-215`.
**Delta:** keiner für S1. Der „mehr vorhanden"-Hinweis (FB-A5) und das Kachel-Raster folgen mit S2; die Tableiste bekommt mit S6 ihr fünftes Ziel „Chats" (D-G3).

#### FB-A2 · Die vier Bereiche: direkt bedienbar, selbsterklärend — ✅
**Quelle:** A0-05 — *„Die anderen Bereiche sind Meine Favoriten, Wichtige Abstimmungen, Meine Region. Alle 4 Bereiche sollten so aufgebaut sein, dass sie direkt bedienbar sind und selbsterklärend sind."*

**Spezifikation**
- Jede Handlung, die auf der Antragsseite möglich ist, ist **auch in der Kachel** möglich, ohne die Seite zu verlassen: Unterstützen (Unterstützungsphase), Ja/Nein/Enthaltung (Abstimmung), Stern (immer). Nach der Handlung tauscht htmx nur das Feld; die Rückmeldung erscheint **in der Kachel** (kurzer Gold-Haken „Erfasst" für 1,5 s), nicht als Flash-Meldung oben.
- Kein Feld enthält Erklärsätze. Beschriftungen sind Verben oder Substantive („Unterstützen", „noch 26 Tage"), keine Sätze.
- Leerzustände sind **ein** kurzer Satz plus **eine** Handlung („Noch nichts in deiner Gemeinde — Antrag einbringen").
- Alles, was man anklicken kann, sieht anklickbar aus (Hover-Lift 2 px, Cursor, Fokusring).

**Abnahme:** In keinem der vier Felder kommt ein Satz mit mehr als 8 Wörtern vor, der nicht Antragstitel, Begründung oder Leerzustand ist. Jede Kachel-Handlung bleibt ohne Seitenwechsel; Flash-Meldungen (`messages`) erscheinen im Parlament nicht mehr oben, sondern in der Kachel.
**Ist (0.34.0):** ✅ Direktbedienung in Kacheln (`_kachel.html`); Acht-Wörter-Regel erfüllt und getestet (`verfahren/test_app_rahmen.py`); **Rückmeldung in der Kachel:** nach Unterstützen oder Abstimmen zeigt die neue Kachel 1,5 s den Gold-Haken „Erfasst" (`app.js` `parlament.markiere`, `.kachel.erfasst`), der Stern-Tausch bleibt ohne Feldtausch (FB-C4); Flash-Meldungen bleiben nur für Seitenwechsel ohne JavaScript.
**Ist (0.33.0):** 🟡 Direktbedienung in Kacheln ✅; Acht-Wörter-Regel ✅ — Regler-Hilfetext ist ein Link auf `/parameter/`, der Profil-Hinweis entfiel; Flash-Meldungen im festen Stapel unter der Leiste.
**Delta:** Rückmeldung in der Kachel statt im Stapel und kürzere Leerzustände bleiben S2 (FB-E3).

#### FB-A3 · App-Anmutung als Qualitätsmaßstab — 🟡
**Quelle:** A0-05 — *„Wir bauen eine benutzerfreundliche Oberfläche für die User, die mehr nach app aussieht als nach homepage und das mitmachen möglichst direkt und einfach gestaltet."*

**Spezifikation:** siehe Design-Spezifikation (`DDOE_Design_Spezifikation_App-Look.md`), verbindlich für Parlament, Antragsseite, Gremien-Bereiche, Mandatare, Einbringen. Kernpunkte: eine App-Leiste; Sans-Schrift für alles Bedienbare (Serif nur noch in der Wortmarke und auf Erklärseiten — ❓ FB-P2); Bewegungen gerichtet (Felder tauschen mit Wischrichtung, Overlays gleiten von ihrem Rand, Fächer zoomt vom Klickpunkt); Zustände (Laden = Skeleton, Leer, Fehler) gestaltet; Touch-Ziele ≥ 44 px; keine Tabellen im Parlament; Zahlen zählen beim ersten Erscheinen hoch.
**Ist (0.33.0):** 🟡 Rahmen steht: eine App-Leiste, Sans-Typografie, Tokens und Bewegungsdauern nach Spezifikation, Skelett-Zustände beim Feldtausch (`base.html:305-313`, `_skelett.html`), ein Reduced-Motion-Block (`base.html:400-403`). Offen bleiben die Feld-Innereien aus S2–S5 (Kachel-Raster, Fächer, Antragsseite) und gerichtete Übergänge je Wischrichtung.
**Delta:** Design-Spezifikation umsetzen, Feld für Feld, mit Sichtprüfung des Gründers.

#### FB-A4 · Willkommensseite und Parlament getrennt — ✅
**Quelle:** Klarstellung 1.9. (Fahrplan P1) — `/` erklärt, `/parlament/` ist Werkzeug. Bleibt so. **Ist:** ✅ (`index.html`, `parlament.html`).

#### FB-A5 · „Mehr vorhanden"-Hinweis an scrollenden Feldern — ✅
**Quelle:** A0-05 — *„Bei beiden Bereichen soll man erkennen wenn es mehr zum anzeigen gibt als auf dem ersten blick darstellbar ist und dann soll man scrollen können."*

**Spezifikation**
- Gilt für **alle vier Felder** (nicht nur Wichtige Abstimmungen und Meine Region) und für das Chat-Panel (FB-G3).
- *Aussehen:* Sobald der Feldkörper mehr Inhalt hat, als sichtbar ist, liegt am unteren Feldrand ein **weicher Verlauf** (28 px, Kartenfarbe → transparent) und darüber mittig eine kleine **Pille „↓ 3 weitere"** (Zahl = nicht sichtbare Kacheln/Zeilen; bei Listen ohne Zählbarkeit nur „↓ mehr"). Die Pille ist anklickbar und scrollt den Feldkörper um eine Feldhöhe weiter (sanft). Am Ende des Inhalts verschwinden Verlauf und Pille (200 ms Ausblenden).
- *Verhalten:* Berechnung beim Laden, bei Größenänderung und nach jedem htmx-Tausch (`scrollHeight > clientHeight`). Zahl = Anzahl der Kacheln, deren Oberkante unter dem sichtbaren Bereich liegt.
- *Ohne JavaScript:* reiner CSS-Verlauf per `mask-image`/`background-attachment: local` (Scroll-Schatten-Technik) — zeigt „mehr" ohne Zahl; die Scrollleiste ist sichtbar (`scrollbar-width: thin`).
- *Barrierefreiheit:* Pille ist ein `<button>` mit `aria-label="3 weitere Einträge anzeigen"`; `aria-hidden` auf dem Verlauf.

**Abnahme:** Mit 7 hervorgehobenen Anträgen zeigt „Wichtige Abstimmungen" auf 1440×900 vier Kacheln und die Pille „↓ 3 weitere"; Klick scrollt; am Ende verschwindet sie. In „Meine Region" mit 5 Gemeinde-Anträgen erscheint sie ebenso.
**Ist (0.34.0):** ✅ Alpine-Komponente `feldmehr` auf den Feldern WeicherFilter, Wichtige Abstimmungen und Meine Region (`app.js`, `_feld_mehr.html`): Pille „↓ n weitere" (n = Kacheln, Zeilen oder Bänder unter der Sichtkante, sonst „↓ mehr") über einem 28-px-Verlauf (`.feld.mehr-da::after`), Klick rollt eine Feldhöhe weiter, neu gerechnet beim Rollen, bei Größenänderung (ResizeObserver) und nach jedem htmx-Tausch; `aria-label`, am Ende verschwindet sie. In den Regionsbändern waagrecht als „› n weitere" (FB-E1). **Abweichungen:** Das Favoriten-Feld hat keine Pille — sein Fächer rollt von unten und zeigt zuerst den Anker; ohne JavaScript bleibt die dünne Scrollleiste der einzige Hinweis (der reine CSS-Verlauf scheitert an den deckenden Kacheln).
**Ist (0.33.0):** ❌ — `.feld::after` war ein leerer Stummel.

#### FB-A6 · Gäste im Parlament — ✅ (0.33.0, S1)
**Ausarbeitung:** Gäste sehen alle vier Felder lesend; statt der Regler ein Chip „Neutral"; statt Stern nichts; Kacheln ohne Stimmknöpfe, dafür „Anmelden zum Abstimmen" als Link in der Kachel. Der heutige Hinweisbalken oben („Sie sehen das Parlament als Gast…") wird zu einem **schmalen Band unter der App-Leiste** (32 px, Info-Farbe) mit zwei Links, damit das Raster nicht verrutscht. **Ist (0.33.0):** ✅ Gastband 32 px unter der App-Leiste (`parlament.html:9`, `base.html:167-171`), zählt über `--band` in der Höhenrechnung mit — das Raster verrutscht nicht; Kacheln zeigen Gästen „Anmelden zum Abstimmen" statt der Stimmknöpfe (`_kachel.html:25-26`). Dasselbe Band trägt den Pausiert-Hinweis auf allen Seiten (`base.html:329`).

---

### Bereich B · Der WeicherFilter (Feld links oben)

#### FB-B1 · Der selbstgesteuerte Feed — 🟡
**Quelle:** A0-05 — *„wie könnte ich einen Feed benennen in dem man selbst einstellt wie er funktioniert. Er basiert auf den ausgewählten Favoriten und auf selbst einstellbare Parameter was vermehrt angezeigt werden soll. Man steuert sozusagen selbst den Algorythmus."* · A0-06/07: Name **WeicherFilter**.

**Spezifikation**
- *Grundlage:* Kandidatenmenge = alle laufenden Verfahren (Unterstützung, Beratung, Abstimmung) — bundesweit **und** regional; abgeschlossene nur auf Wunsch (Regler „Abgeschlossene zeigen", Voreinstellung 0).
- *Basis Favoriten:* Ohne jeden Regler (neutral) ist die Reihung: Phase (Abstimmung → Beratung → Unterstützung), dann Frist aufsteigend, dann Datum — **aber Anträge aus abonnierten Lebensbereichen stehen innerhalb jeder Phase zuerst** (das ist „er basiert auf den ausgewählten Favoriten", § 5 Abs 10 lit a; Ausarbeitung: die Favoriten-Bevorzugung ist keine verdeckte Reihung, weil sie eine offene, vom Mitglied selbst gesetzte Regel ist — sie wird im Feldkopf als Chip „★ Favoriten zuerst" angezeigt und ist abschaltbar).
- *Reihungsregel:* Punkte = Σ Regler × Merkmal (Regel v2, versioniert in `plattform_core/weicherfilter.py`); jedes Merkmal in [0, 1]; Gleichstand → neutrale Grundordnung. **Jeder Eintrag zeigt auf Tipp/Hover ein kleines Aufklapp-Feld „Warum hier?"** mit der Aufschlüsselung (statt des heutigen `title`-Tooltips, der auf Touch nicht erreichbar ist).
- *Eintrag (Zeile) im Feed:* 1. Zeile Titel (16 px, 2 Zeilen max., Ellipse) + Stern rechts; 2. Zeile Chips: Phase (farbig: Abstimmung gold, Beratung petrol, Unterstützung grau), Ebene bei regionalen, Lebensbereich (kurz); 3. Zeile Stand: Mini-Balken (4 px) + Text „2 von 3 Unterstützungen · noch 59 Tage" bzw. „40 % Beteiligung · noch 26 Tage". Direkt-Handlung rechts als kleiner Knopf: „Unterstützen" / „Abstimmen ▸" (öffnet Ja/Nein/Enthaltung inline). Zeilenhöhe ~ 84 px; Trennlinie hell.
- *Gruppierung:* im neutralen Zustand mit Gruppenüberschriften (Laufende Abstimmungen · In Beratung · Sammeln Unterstützung); bei aktivem Profil **eine** durchgehende, punktgereihte Liste (Gruppen würden die Reihung zerstören).
- *Gäste:* immer neutral, ohne Favoriten-Bevorzugung, ohne Regler.

**Abnahme:** Als Mitglied mit Abo „Energie" steht ein Energie-Antrag in der Unterstützungsphase vor einem gleich alten Nicht-Energie-Antrag; Chip „★ Favoriten zuerst" ist sichtbar; Abschalten stellt die reine Grundordnung her. Tipp auf „Warum hier?" zeigt die Punkte je Regler.
**Ist:** Regel v1 mit 8 Reglern ✅ (`plattform_core/weicherfilter.py`); Favoriten-Bevorzugung in der Voreinstellung ❌ (Voreinstellung ist rein Phase/Frist, `views.py:321-334`); Aufschlüsselung nur als `title`-Tooltip 🟡; Direkt-Handlung in der Zeile ❌.

#### FB-B2 · Die Regler — 🟡 (7 von 9 vorhanden, einer falsch)
**Quelle:** A0-05 — *„Bspw. der Parameter: mehr von dem wofür oder wogegen ich bereits gestimmt habe. mehr von dem was ich bereits unterstützt habe. Abstimmungen oder Unterstützungsanträge die mich interessieren könnten außerhalb meiner Favoriten. vermehrt Unterstützungsanträge, vermehrt Abstimmungen, vermehrt chronologisch was mein Feed zeigt, vermehrt Anträge usw. die nur noch kurz online sind, Anträge usw. denen nur noch wenig Unterstützung fehlt oder Abstimmungen fehlen. Das alles sind Schieberegler…"*

**Spezifikation — die neun Regler (Reihenfolge = Anzeige), je 0–100 in 5er-Schritten, Voreinstellung 0**

| # | Beschriftung (wörtlich im UI) | Merkmal (nachrechenbar, in [0,1]) |
|---|---|---|
| 1 | **Mehr wie das, wofür ich gestimmt habe** | Anteil der Lebensbereiche des Antrags, die in Anträgen vorkommen, bei denen meine eigene Stimme *Ja* war (eigene Stimme ist dem Mitglied über das Stimmregister bekannt, nie anderen) |
| 2 | **Mehr wie das, wogegen ich gestimmt habe** | wie 1 mit *Nein* — damit man Gegenanträge und Wiedervorlagen im Blick behält |
| 3 | **Mehr wie das, was ich unterstützt habe** | Anteil der Lebensbereiche, die in meinen unterstützten Anträgen vorkommen |
| 4 | **Interessantes außerhalb meiner Favoriten** | 1, wenn kein Lebensbereich des Antrags in meinem Abo-Ast liegt; sonst 0 |
| 5 | **Mehr Unterstützungsanträge** | 1 in der Unterstützungsphase, sonst 0 |
| 6 | **Mehr Abstimmungen** | 1 in der Abstimmungsphase, sonst 0 |
| 7 | **Mehr chronologisch (Neues zuerst)** | Altersrang: jüngster Antrag 1, ältester 0 |
| 8 | **Nur noch kurz online** | max(0, 1 − Resttage / Phasendauer) — bezogen auf die *eigene* Phasendauer des Antrags, nicht auf 60 Tage pauschal |
| 9 | **Wenig fehlt** | Unterstützungsphase: Unterstützungen / Schwelle · Abstimmung: Beteiligung / Mindestbeteiligung (gedeckelt 1) · Beratung: 0 |

- *Ausarbeitung:* Der Gründer nannte „wofür oder wogegen" in einem Atemzug; als **zwei Regler** getrennt, weil sie entgegengesetzte Absichten bedienen (❓ D-B2: zusammenlegen zu einem Regler „Mehr wie das, worüber ich abgestimmt habe" ist eine Zeile Code). Der heutige Regler „Mehr, wo ich schon abgestimmt habe" (richtungslos) wird ersetzt.
- *Live-Vorschau:* Beim Ziehen eines Reglers ordnet sich die Liste nach 400 ms Ruhe neu (htmx `hx-trigger="input changed delay:400ms"`, Zieltausch nur der Liste, sanftes Umsortieren per View-Transition/FLIP). Der Zahlenwert steht rechts am Regler.
- *Ohne JavaScript:* Regler sind native `<input type=range>` in einem Formular; „Anwenden" lädt die Seite neu.
- *Barrierefreiheit:* `aria-valuetext="40 von 100"`, Beschriftung als `<label>`; Tastatur ±5.

**Abnahme:** Neun Regler in dieser Reihenfolge und mit diesem Wortlaut; Regler 1 auf 100 hebt einen Antrag aus einem Lebensbereich, in dem ich mit Ja gestimmt habe, über einen aus einem Lebensbereich, in dem ich mit Nein gestimmt habe (und Regler 2 umgekehrt); Ziehen ordnet live um.
**Ist:** 8 Regler (`views.py:31-40`); „gestimmt" richtungslos (`views.py:62-64,80`); `ablaufend` pauschal /60 (`views.py:77`); keine Live-Vorschau (Formular „Anwenden & speichern").

#### FB-B3 · Bis zu fünf gespeicherte Konfigurationen — ✅ (Feinschliff)
**Quelle:** A0-05 — *„…deren Gesamteinstellungen gespeichert werden können, bis zu 5, die man jederzeit umschalten oder anpassen kann."*

**Spezifikation:** Konfiguration = Name (≤ 24 Zeichen) + neun Reglerwerte + Schalter „★ Favoriten zuerst"; serverseitig beim Mitglied; höchstens 5; genau eine ist aktiv (oder „Neutral"). Umschalten wirkt sofort (Feldtausch). Umbenennen per Doppelklick/Stift-Symbol im Overlay. Löschen mit Rückfrage „Konfiguration ‚Abend' löschen?" (Inline-Bestätigung, kein Browser-Dialog). Reihenfolge der Chips = Reihenfolge der Erstellung; per Drag umsortierbar (Zugabe).
**Ist:** ✅ `FilterProfil` (max. 5, `verfahren/models.py:580-606`, `views_aktionen.py:321-336`); Umbenennen ❌, Löschen ohne Rückfrage 🟡.

#### FB-B4 · Das Umschaltmenü am oberen Rand mit Pfeil (Slide) — ❌
**Quelle:** A0-05 — *„Umschalten über ein kleines Menü wo diese gespeicherten Gesamteinstellungen schnell aktiviert werden können am oberen Rand mit Pfeil zum einfahren des Menüs (slide animation)."*

**Spezifikation**
- *Aussehen:* Direkt unter dem Feldkopf liegt die **Profil-Leiste**: 40 px hoch, Hintergrund um eine Stufe dunkler als das Feld (`--paper`), darin von links: Chip „Neutral", dann je gespeicherte Konfiguration ein Chip (aktiv = gold gefüllt, sonst Umriss), rechts ein Chip „⚙ Regler" (öffnet FB-B5). Am **rechten Rand der Leiste** ein runder Pfeil-Knopf (28 px, Chevron ˄).
- *Verhalten:* Klick auf den Pfeil **fährt die Leiste nach oben ein** (Höhe 40 → 0 px, Inhalt gleitet mit, 260 ms, `cubic-bezier(.4,0,.2,1)`), übrig bleibt ein 14 px hoher **Griff** mit Chevron ˅ am oberen Feldrand (mittig, halbtransparent). Klick auf den Griff fährt die Leiste wieder aus. Der Zustand (ein/aus) wird je Gerät gemerkt (`localStorage` `ddoe.filterleiste`), Voreinstellung: ausgefahren. Ist die Leiste eingefahren, zeigt der Feldkopf rechts den aktiven Namen als Chip („Profil: Abend"), damit man ihn nie verliert.
- *Ohne JavaScript:* Leiste ist immer ausgefahren; der Pfeil ist nicht vorhanden (`hidden`, wird von Alpine eingeblendet).
- *Barrierefreiheit:* Pfeil = `<button aria-expanded aria-controls="filter-leiste">`; Chips sind Formular-Knöpfe.

**Abnahme:** Pfeil sichtbar; Klick fährt die Leiste in ~0,25 s ein, Griff bleibt; erneuter Klick fährt aus; Zustand überlebt Neuladen; aktives Profil bleibt im Feldkopf lesbar.
**Ist:** ❌ feste Chip-Leiste (`parlament.html:20-56`), nur Lade-Animation `einfahren-oben` (`base.html:283`).

#### FB-B5 · Der Reglerbereich als halbtransparentes Overlay rechts — 🟡
**Quelle:** A0-05 — *„am rechten Rand ist der Schieberegler Bereich wo alle Schieberegler drauf sind, wobei die aktuell gewählte Konfiguration angezeigt wird aber man die Schieberegler einzeln anpassen kann und dann auf speichern drücken falls es eine ausgewählte Konfiguration ist oder auf neue Konfiguration speichern klicken falls man noch keine 5 Konfigurationen hat. Alles als halbtransparentes Overlay über dem Feed Bereich…"*

**Spezifikation**
- *Öffnen:* Chip „⚙ Regler" (Leiste) oder Regler-Symbol im Feldkopf. Das Overlay **gleitet vom rechten Feldrand herein** (translateX 100 % → 0, 280 ms), Breite 340 px (mobil: volle Feldbreite), Höhe = Feldkörper, Hintergrund `rgba(255,255,255,.86)` (dunkel: `rgba(19,32,41,.9)`) mit `backdrop-filter: blur(10px)`, linke Kante 1 px Linie + Schatten nach links; der Feed darunter bleibt sichtbar und **bewegt sich live** beim Ziehen.
- *Inhalt von oben nach unten:* Kopfzeile: aktive Konfiguration als Titel („Abend" / „Neutral" / „Ungespeichert ●" wenn geändert) + Stift (umbenennen) + X (schließen). Darunter Schalter „★ Favoriten zuerst". Darunter die neun Regler (Beschriftung links, Wert rechts, Bahn 4 px, Griff 18 px gold). Unten eine feste Aktionszeile: **„Speichern"** (gefüllt; nur aktiv, wenn eine gespeicherte Konfiguration gewählt ist und sich etwas geändert hat) · **„Als neue Konfiguration speichern"** (Umriss; nur sichtbar, wenn < 5 gespeichert; Klick öffnet ein Inline-Namensfeld mit „Anlegen") · „Zurücksetzen" (Textknopf, alle 0) · „Löschen" (nur bei gespeicherter Konfiguration, Inline-Rückfrage). Bei 5/5 steht statt des Neu-Knopfes: „5 von 5 — eine löschen oder überschreiben".
- *Schließen:* X, Escape, Klick außerhalb; ungespeicherte Änderungen bleiben als Zustand „Ungespeichert" aktiv, bis man speichert oder umschaltet (Chip in der Leiste zeigt dann „● Ungespeichert").
- *Ohne JavaScript:* `<details>` mit derselben Optik (heutiger Weg) — Overlay bleibt offen, „Anwenden" lädt neu.
- *Barrierefreiheit:* `role="dialog" aria-modal="false" aria-label="Regler des WeicherFilters"`; Fokus geht beim Öffnen auf die Kopfzeile, beim Schließen zurück auf den Auslöser.

**Abnahme:** Overlay gleitet von rechts, Feed bleibt sichtbar; „Speichern" ist bei „Neutral" ausgegraut; bei 5 Konfigurationen fehlt „Als neue…"; Escape schließt.
**Ist:** 🟡 `<details>`-Overlay mit `einfahren-rechts` (`base.html:146,284`); Aktionen „Anwenden & speichern" + „Als neues Profil" (`parlament.html:31-55`); keine Änderungsanzeige, kein Stift, kein Löschen mit Rückfrage, kein Escape/Fokus-Management.

#### FB-B6 · Voreinstellung neutral, Regel offen — ✅
**Quelle:** Satzung § 5 Abs 10 lit d, § 2 Abs 6 letzter Satz; L3. **Spezifikation:** Voreinstellung = neutral (Phase, Frist, chronologisch) + „★ Favoriten zuerst" (offen sichtbar, abschaltbar); die Regel steht versioniert im Code und in Kurzform als Link „Regel v2 nachlesen" im Overlay-Fuß (öffnet `/parameter/#weicherfilter`). **Ist:** ✅ neutral; Regeltext heute als Satz im Overlay (`parlament.html`) — wird zum Link.

---

### Bereich C · Meine Favoriten — der Fächer (Feld rechts oben)

#### FB-C1 · Der grafische Themenbaum mit Fäden — ✅
**Quelle:** A0-05 — *„Meine Favoriten sollte direkt einen Themenbaum anzeigen und zwar grafisch, ganz unten Lebensbereiche etwas größer, sagen wir Schriftgröße 24 und darunter die Unterkategorien in 2er schritten kleiner werden verbunden mit Fäden mit der Überkategorie, also in dem die vier Säulen aber ohne diese so zu benennen."*

**Spezifikation**
- *Aussehen:* Der Fächer **ist** das Feld — kein Umschalter, keine Liste, kein eigener Aufruf. Unten mittig die Wurzel **„Lebensbereiche"** (24 px, semibold, Sans). Darüber, fächerförmig auf einem Bogen: die 4 Säulen (22 px) — sie stehen dort **mit ihrem Namen** („Sicherheit & Soziales Fundament" …), aber es gibt keine Beschriftung „Säule" und keine Erklärung. Darüber die 12 Bereiche (20 px), dann Hauptkategorien (18 px), dann Unterkategorien (16 px). Jeder Knoten ist mit seiner Überkategorie durch einen **Faden** verbunden (SVG-Pfad, 1 px, `--line`, leichte Kurve; beim Hover des Knotens wird der Faden bis zur Wurzel gold und 2 px).
- *Knoten-Optik:* Pille mit Kartenhintergrund, 6/10 px Innenabstand, Text in der Ebenengröße, links davor der **Stern** (FB-C4). Lange Namen werden auf 22 Zeichen gekürzt (Ellipse), voller Name im Tooltip und als `aria-label`. Der Anker (aktueller Knoten) ist gold umrandet.
- *Farben:* Fäden und Knoten je Säule mit einem dezenten Farbton (vier Töne aus der Palette, 12 % Deckung im Knoten-Hintergrund), damit man Äste auseinanderhält, ohne sie zu benennen.
- *Suche:* bleibt oben im Feldkopf (Name, Beschreibung, Schlagworte); Treffer öffnen den Fächer am Treffer und heben ihn 1,5 s gold hervor.
- *Ohne JavaScript:* Knoten sind Links (`?fach=<slug>`), Sterne Formulare; Fäden SVG. Bereits heute so — bleibt.

**Abnahme:** Auf 1440×900 sind Wurzel (24 px), 4 Säulen (22 px) und 12 Bereiche (20 px) gleichzeitig lesbar, **kein Knotentext ist abgeschnitten oder überlappt** (heute: „Bildungssy", „Infrastruktu" — Screenshot 2.9.); Hover auf einen Bereich färbt den Faden bis zur Wurzel gold.
**Ist (0.34.0):** ✅ Layout-Regel v2 in `plattform_core/faecher.py` (VERSION 2): Randpillen bündig, bis zu drei versetzte Reihen, Pillenbreite b = r·Spanne/(n−1+r) als `max-width` in Prozent mit CSS-Ellipse, voller Name als `title`; **Rechenprobe über alle 312 Anker × alle Äste ohne Überlappung** (`tests/test_faecher_layout.py`) und Bildschirmprobe (`tests/e2e/test_faecher.py`). Säulentöne `.fknoten.p1–p4` (`base.html`, `color-mix` 12 %), Faden bis zur Wurzel gold beim Zeigen (`app.js` `faecher.hebe`), Suchtreffer 1,5 s gold (`treffer-link`, `parlament.treffer`). **Abweichung zur Abnahme:** die zwölf Bereiche stehen in 20 px in drei Reihen mit 7–11 sichtbaren Zeichen (Ellipse) — bei 26 Zeichen Median passen zwölf volle Namen in kein Feld; die vier Säulen zeigen ≥ 17 Zeichen, Wurzel und Anker immer voll.
**Ist (0.31.0):** 🟡 Fächer direkt im Feld ✅, Wurzel „Lebensbereiche" ✅, Fäden ✅, Schriftgrößen 24/22/20 ✅ — aber Beschriftungen überlappten und waren abgeschnitten, keine Säulenfarbe, keine Hover-Fadenhervorhebung.

#### FB-C2 · Fünf Ebenen im Fächer — ✅
**Quelle:** A0-05 — *„und so geht es weiter mit den weiteren Unterkategorien so, dass sich ein Fächer mit 5 Ebenen ergibt."*

**Spezifikation**
- *Grundsatz:* Der Fächer zeigt **immer fünf Ebenen**: den Anker (24 px) und vier Ebenen darüber (22/20/18/16 px). Der Baum hat 6 Ebenen (Wurzel → 4 → 12 → 24 → 96 → 175 Knoten); vollständig gezeichnet wären an der Wurzel 137 Knoten — unlesbar. Darum gilt die **Auffächer-Regel**:
  1. Eine Ebene wird **vollständig** gezeichnet, wenn sie unter dem Anker höchstens **12 Knoten** hat (an der Wurzel: Ebene 2 = 4 Säulen, Ebene 3 = 12 Bereiche → beide vollständig).
  2. Hat eine Ebene mehr als 12 Knoten (an der Wurzel: Ebene 4 = 24 Hauptkategorien, Ebene 5 = 96), wird sie **nur für den „entfalteten" Ast** gezeichnet: das ist der Ast des Knotens, über dem der Zeiger liegt oder der zuletzt angetippt wurde (Touch: erster Tipp entfaltet, zweiter Tipp navigiert). **Im Ruhezustand ist der Ast des ersten Favoriten entfaltet** (ohne Favoriten: der erste Bereich), damit immer fünf Ebenen sichtbar sind. Die übrigen Äste zeigen dort nichts (kein „+n"), damit das Bild ruhig bleibt. Beim Entfalten gleiten die Pillen aus ihrem Elternknoten heraus (180 ms, gestaffelt 20 ms).
  3. Innerhalb des entfalteten Astes zeigt jeder Knoten höchstens **3 Kinder**; die Ebene-5-Pillen hängen als **kleine Säule** senkrecht über ihrem Elternknoten (je 26 px Abstand), nicht nebeneinander — so kollidieren die Äste zweier Nachbarn nicht. Hat ein Knoten mehr als 3 Kinder, zeigt die oberste Pille „+n".
- *Geometrie (Desktop, Feldbreite ≥ 640 px):* Ebenenabstand 22 % / 20 % / 16 % / 11 % der Feldhöhe von unten nach oben; die Knoten jeder Ebene verteilen sich gleichmäßig über 92 % der Feldbreite auf einem flachen Bogen (Bogenhöhe 10 px an den Rändern), Geschwister gruppiert unter ihrem Elternknoten. Passen die Beschriftungen einer Ebene nicht in eine Zeile, wird die Ebene in **bis zu drei versetzte Zeilen** gestaffelt (Versatz = Schriftgröße + 12 px) und jede Beschriftung auf die verfügbare Breite gekürzt (Ellipse, Vollname im Tooltip; nie unter 6 Zeichen); jede Pille bleibt vollständig im Feld (Randklemmung). Deterministischer Layout-Algorithmus in `plattform_core/faecher.py`, mit Tests: keine zwei Pillen überlappen bei allen 312 Knoten als Anker. **Referenz: das Mockup `docs/fahrtenbuch/mockups/parlament_app_mockup.html` setzt genau diese Regeln um** (Feld „Meine Favoriten").
- *Handy (< 640 px):* Ebenen 1–3 vollständig, Ebene 4 nur für den entfalteten Ast, Ebene 5 nicht; horizontal wischbar, wenn breiter als das Feld (Scroll-Snap auf die Säulen). Schriftgrößen 20/18/16/15/14.
- *Ohne JavaScript:* Fünf Ebenen mit Regel 1–2 (Ebene 5 entfällt, weil kein Hover-Zustand) — voll bedienbar.
- *Performance:* Layout wird serverseitig berechnet (wie heute), die Ebene-5-Entfaltung liefert htmx als Teilantwort (`?fach=<slug>&entfalten=<slug>`) oder kommt vorab als versteckte Knoten mit (bevorzugt: vorab mitgeliefert, Alpine blendet ein — keine Netzlast beim Hover).

**Abnahme:** An der Wurzel sind 5 Ebenen sichtbar (Lebensbereiche · 4 · 12 · 24 · entfalteter Ast); nichts überlappt; Hover über „Gesundheitswesen & Prävention" fächert dessen Unterkategorien auf 16 px auf; ohne JavaScript sind vier Ebenen sichtbar.
**Ist (0.34.0):** ✅ fünf Ebenen (Anker 24 + 22/20/18/16), Auffächer-Regel mit Deckel 12 (`VOLL_HOECHSTZAHL`), die erste zu große Ebene nur im entfalteten Ast: drei Kinder nebeneinander (`AST_ABSTAND` 160 px), deren Kinder als senkrechte Säule (Pillenhöhe + 1 px), ab dem vierten „+n" (Link auf den Elternknoten). Alle Äste werden vorab mitgeliefert (`data-ast`, `x-show`, `x-cloak`), Ruhezustand = Ast des ersten Favoriten (`abos`), sonst der erste Bereich; ohne JavaScript bleibt der Ruhe-Ast mit allen fünf Ebenen sichtbar. Höhe knapp gerechnet (336 px an der Wurzel = Feldkörper bei 1440×900 als Gast), Prozentlagen dehnen sich mit dem Feld; ist das Feld niedriger, rollt der Körper und zeigt zuerst den Anker (`column-reverse`). Handy 20/18/16/15/14 px, `min-width:600px`, waagrecht rollbar. **Offen (klein):** Touch „erster Tipp entfaltet, zweiter navigiert" (der htmx-Klick geht vor; am Handy sieht man den Ruhe-Ast, andere Äste über den Klick auf den Bereich) und das gestaffelte Herausgleiten (180 ms/20 ms) — heute schlichtes Umblenden.
**Ist (0.33.0):** ❌ maximal drei Ebenen über dem Anker, Enkel-Deckel 12, ab Tiefe 5 Lücken.

#### FB-C3 · Hineinbewegen beim Klick; ab der dritten Ebene sitzt der Anker in der Mitte — ✅
**Quelle:** A0-05 — *„wenn man auf ein element klickt bewegt sich die ansicht hinein auf dieses element was dann zu dem in Schriftgröße 24 am unteren rand des bereiches ist."* · A0-07 — *„Bei P2 ist mir aufgefallen, dass wenn die ausgewählte kategorie dann nach ganz unten kommt, man nicht mehr herauszoomen kann. Wir sollten die Auswahl ab der dritten ebene immer in die Mitte des Fächers bringen als den 24er Anker damit man auch zurück nach oben klicken kann."*

**Spezifikation**
- *Bewegung:* Klick auf einen Knoten → die ganze Fächerfläche **zoomt auf den Knoten zu** (transform-origin = Knotenmitte, scale 1 → 1.12 und translate zum Ankerplatz, 320 ms, `cubic-bezier(.22,.8,.3,1)`), währenddessen blenden die nicht mehr sichtbaren Knoten aus; dann steht der Knoten als 24er-Anker, seine Nachkommen fächern sich über ihm auf (Fäden zeichnen sich mit `stroke-dashoffset`-Animation, 260 ms). Zurück (Klick auf einen Vorfahren) spielt dieselbe Bewegung rückwärts (Zoom heraus). Mit htmx wird nur das Feld getauscht; Alpine spielt die Zoom-Animation vor dem Tausch (`htmx:beforeSwap` verzögert um 220 ms), View-Transition glättet den Rest.
- *Modus „Boden" (Anker = Wurzel oder Säule, Tiefe 1–2):* Anker unten mittig; nichts darunter.
- *Modus „Mitte" (Anker ab Tiefe 3):* Anker **vertikal mittig** im Feld; **darunter** der Rückweg: die Vorfahren als Kette bis zur Wurzel (Säule 22 px, darunter Wurzel 20 px; bei längerem Weg alle Zwischenstufen in 20/18 px), jeder anklickbar; darüber die Nachkommen wie im Boden-Modus.
- *Zusätzlich (Ausarbeitung):* eine dezente **Brotkrume** im Feldkopf („Lebensbereiche › Wirtschaft … › Energie"), jede Stufe klickbar — verdoppelt den Rückweg für Tastatur- und Screenreader-Nutzer.
- *Ohne JavaScript:* Sprung ohne Zoom (Seitenwechsel), Modus Mitte/Boden identisch.

**Abnahme:** Klick auf „Energie" (Tiefe 4): Anker mittig, darunter Kette „Wirtschaft, Arbeit & Finanzen ‹ Lebensbereiche" klickbar; die Bewegung ist ein Zoom auf den Knoten (kein Springen); Klick auf „Lebensbereiche" zoomt heraus.
**Ist (0.34.0):** ✅ Klick zoomt vom Klickpunkt hinein (`app.js` `faecher.zoome`: `transform-origin` = Knotenmitte, `.faecher.zoom` scale 1 → 1.12, 320 ms `--e-out`), htmx tauscht erst danach (`hx-swap="outerHTML transition:true swap:220ms"`), die View-Transition glättet den Rest; Mitte-Modus ab Tiefe 3 mit **vollständigem Rückweg** bis zur Wurzel (22/20/18 px, `rolle: weg`) und **Brotkrume** im Feldkopf (`parlament.html`, `.brot`, `aria-label` „Pfad im Fächer"). Rückwärts (Klick auf einen Vorfahren oder die Brotkrume) spielt die View-Transition — kein eigener Zoom heraus. Ohne JavaScript Seitenwechsel ohne Zoom.
**Ist (0.33.0):** 🟡 Mitte-Modus ✅, Rückweg auf 2 Vorfahren begrenzt, kein Zoom, keine Brotkrume.

#### FB-C4 · Stern an jedem Element — ✅
**Quelle:** A0-05 — *„Alle mit dem Stern zum favorisieren daneben."* **Spezifikation:** Stern links vor dem Knotentext (☆ grau / ★ gold mit Schein), 18 px Klickfläche ≥ 32 px, Tipp schaltet das Abo (Ast-Wirkung) mit Pop-Animation (scale 1.25 → 1, 220 ms) — Tausch nur des Sterns, nicht des Feldes (kein Flackern). `aria-pressed`. **Ist (0.34.0):** ✅ Stern je Knoten, htmx tauscht **nur den Stern** (`views_aktionen.kategorie_abonnieren`, HX-Zweig → `_kategorie_stern.html`, `hx-swap="outerHTML"`), `aria-pressed`, Pop 220 ms (`stern-pop` auf `htmx-added`); derselbe Baustein in der Feldsuche und im Kachelkopf. Getestet in `verfahren/test_faecher.py` und `tests/e2e/test_faecher.py`.

#### FB-C5 · Was das Favoriten-Feld sonst noch zeigt — ❓
**Ausarbeitung:** § 5 Abs 10 lit a verlangt im persönlichen Bereich auch *„die dazu aktuell laufenden Abstimmungen"*. Vorschlag: Unter dem Anker-Knoten steht bei Fokus auf einen Lebensbereich eine kleine Zahl-Pille „3 laufend"; Tipp darauf blendet **im Feld** eine kompakte Liste der laufenden Verfahren dieses Astes ein (mit Direkt-Handlung wie im WeicherFilter), zurück per „‹ Fächer". Damit erfüllt das Feld Satzung und Anweisung zugleich. ❓ D-C5: Zustimmung des Gründers (er hatte die frühere Liste bewusst entfernt; dies ist die kleinstmögliche Form). **Ist:** ❌ (Ast-Zähler nur in der Suche).

---

### Bereich D · Wichtige Abstimmungen (Feld links unten)

#### FB-D1 · 4 oder 6 Kacheln, gleichmäßig — ✅
**Quelle:** A0-05 — *„Der Wichtige Abstimmungen Bereich ist ein Bereich der direkt 4 oder 6 wichtige Abstimmungen gleichmäßig positioniert anzeigt…"*

**Spezifikation**
- *Raster:* Der Feldkörper zeigt ein Kachelraster **2 Spalten × 2 Zeilen** (Feldhöhe < 420 px) oder **3 × 2** (Feldbreite ≥ 700 px und Höhe ≥ 420 px) — also 4 oder 6 Kacheln **auf einen Blick, gleich groß, das Feld ausfüllend** (`grid-auto-rows: 1fr`). Sind es mehr, scrollt der Körper in ganzen Reihen weiter und FB-A5 zeigt „↓ 2 weitere". Sind es weniger, füllen die vorhandenen Kacheln das Raster mit gleicher Größe (leere Plätze bleiben leer — keine Platzhalterkacheln).
- *Reihenfolge:* Frist aufsteigend (die dringlichste zuerst), dann Hervorhebungsdatum — offen im Feldkopf-Chip („nach Frist").
- *Kachel (gilt für D und E gleich, siehe FB-D2).*

**Abnahme:** Mit 6 hervorgehobenen Anträgen füllt das Feld auf 1440×900 ein 3×2-Raster ohne Scroll; mit 7 erscheint „↓ 1 weitere"; mit 1 ist die Kachel so groß wie ein Rasterplatz, nicht feldfüllend.
**Ist (0.34.0):** ✅ Raster 2 Spalten, ab 700 px Feldbreite 3 Spalten (Container-Query auf `.feld-korpus`), Zeilen `minmax(186px, calc(50% − 5px))` — 4 bzw. 6 gleich große Kacheln füllen das Feld, weitere rollen in ganzen Reihen (`base.html`, `verfahren/test_kachel_raster.py`). Der Hinweis „↓ n weitere" folgt mit FB-A5.
**Ist (0.33.0):** 🟡 `.kacheln` 2 Spalten, kein Zeilenmaß, Kacheln wuchsen mit Inhalt.

#### FB-D2 · Inhalt einer Kachel — ✅
**Quelle:** A0-05 — *„wobei bei jedem das Thema dabei steht, welches ebenfalls einen Favorisier-Stern daneben hat, dann steht dabei wo die Abstimmung gerade steht also wieviel % abgestimmt haben und wofür, wie lange noch bis zum Fristende in Tagen, Wenn man draufklickt wird der Antrag oder die Unterstützungserklärung usw. aufgerufen."*

**Spezifikation — Aufbau von oben nach unten (Kachel ≈ 300 × 190 px)**
1. **Thema-Zeile:** Lebensbereich als kleiner Chip (z. B. „Demokratie, Staat & Verwaltung", 11 px Kapitälchen) **mit Stern daneben** — der Stern gilt dem *Thema* (Lebensbereich-Abo), wie angewiesen; zusätzlich ganz rechts der Antrags-Stern (merken). *(Ausarbeitung: zwei Sterne mit klarer Tooltip-Unterscheidung „Lebensbereich abonnieren" / „Antrag merken".)*
2. **Titel** (16 px, max. 2 Zeilen, Ellipse), ist der Link zur Antragsseite (die ganze Kachel ist klickbar, außer Knöpfe).
3. **Stand:** Phasen-Chip + Fortschrittsbalken (4 px, wächst beim Erscheinen) + Text — je Phase: Unterstützung „2 von 3 Unterstützungen"; Beratung „5 Beiträge · Expertenrat arbeitet" (falls Entwurfsfenster); Abstimmung „**40 % haben abgestimmt**" und dahinter die Tendenz (siehe ❓ D-D2).
4. **Frist:** „noch **26** Tage" (Zahl fett; ≤ 3 Tage rot; „endet heute"), rechts daneben ein kleiner Kreisring, der den Anteil der verstrichenen Phase zeigt.
5. **Direkt-Handlung:** Unterstützungsphase → Knopf „Unterstützen" (oder ✓ „Unterstützt"); Abstimmung → drei Knöpfe Ja · Nein · Enthaltung (eigene Wahl gold umrandet); Beratung → „Mitreden" (Link zum Chat-Anker); Personenwahl → „Zur Wahl ›".
6. **Hervorhebungsgrund** (nur Feld D): eine Zeile, 12 px, kursiv, gekürzt auf 90 Zeichen, Tooltip voll: „Integritätsrat, 12.08.2026: …".
- *Klick:* öffnet `/antrag/<id>/` (Zone 1 oben); bei laufender Abstimmung mit `#abstimmen`.

**❓ D-D2 · „wieviel % abgestimmt haben und wofür".** Die Anweisung verlangt die Tendenz („wofür"). Lastenheft F-15 und die bisherige Umsetzung verbergen sie bis Fristende (Mitläufer-Effekt; § 5 Abs 3 lit e nennt Veröffentlichung *nach* der Abstimmung). Drei Wege: **(a)** verdeckt lassen und es in der Kachel sagen (heute); **(b)** Tendenz zeigen, sobald die Mindestbeteiligung erreicht ist (dann kann eine Stimme das Ergebnis nicht mehr durch Fernbleiben kippen); **(c)** immer zeigen. Empfehlung: (a) als Voreinstellung, (b) als Parameter `abstimmung-tendenz-ab-beteiligung` (Wert 0 = nie, 1 = immer) im Parameterregister — dann ist die Frage ein lernbarer Parameter statt einer Glaubensfrage. Bis zur Entscheidung: (a).

**Ist (0.34.0):** ✅ Thema-Chip mit eigenem Themen-Stern (Abo des Lebensbereichs, Tausch nur des Sterns, FB-C4), Antrags-Stern rechts, Titel, Phasen-Chip + Balken, Frist mit Kreisring (`_ring.html`, `phasen.rest_ring`), Direkt-Handlung je Phase (Unterstützen / Ja · Nein · Enthaltung / Mitreden / Zur Wahl), Hervorhebungsgrund nur im Feld D (`_kachel.html`). Tendenz verdeckt ⚠️ (D-D2).
**Ist (0.33.0):** 🟡 Titel, Stern (Antrag), Phase, Balken, Beteiligung, Resttage, Begründung, Direktabstimmung ✅; Thema-Chip ❌, Kreisring ❌, „Mitreden" ❌.

#### FB-D3 · Klick öffnet Antrag oder Unterstützungserklärung — ✅
**Ist (0.34.0):** ✅ Titel-Link; die ganze Kachel ist klickbar (`.k-titel::before` deckt die Kachel, Knöpfe und Sterne liegen darüber als eigene Ziele — `_kachel.html`, `base.html`).

#### FB-D4 · Wer hebt hervor — Integritätsrat mit Oberfläche, Koordinationsrat beantragt — ❌ (Oberfläche fehlt ganz)
**Quelle:** A0-04 — *„Wichtige Abstimmungen werden durch beschluss des koordinationsrates veröffentlicht so wie ich das in der satzung lese oder erinnere ich mich falsch?"* · A0-02 — *„Wieso dem Integritätsrat? Das müsste den Koordinationsrat betreffen."*

**Antwort und Spezifikation**
- Satzung 2.5 § 5 Abs 10 lit b: *Die Hervorhebung beschließt der Integritätsrat durch veröffentlichten, begründeten Beschluss; sie erfolgt niemals durch einen Algorithmus.* Die Erinnerung des Gründers trifft auf den **Weg** zu: Die Zukunftswerkstatt meldet unterbeteiligte, stabilisierende Anträge dem **Koordinationsrat** (Posteingang, FB-I5); der Koordinationsrat **beantragt** die Hervorhebung beim Integritätsrat; dieser beschließt und begründet. Zwei Räte, vier Augen (Strategie Kap. 9). ❓ D-D4: Soll das so bleiben (Empfehlung: ja — Aufmerksamkeit ist die härteste Währung, sie gehört zum Wächterorgan) — oder soll die Satzung auf den Koordinationsrat geändert werden?
- *Oberfläche Integritätsrat* (`/gremien/integritaet/`, Rolle `integritaetsrat`): Liste „Hervorhebungsanträge des Koordinationsrats" (mit dessen Begründung) + „Alle laufenden Verfahren"; je Antrag Knopf „Hervorheben" → Pflichtfeld Begründung (öffentlich) + Beschlussnummer (automatisch „IR-2026-04") → Audit `hervorhebung` → Kachel erscheint in Feld D; „Hervorhebung aufheben" mit Begründung. Weitere Aufgaben des Integritätsrats im selben Bereich: **Zurückweisung** eines Antrags (§ 5 Abs 2: schriftlich begründet, öffentlich, bekämpfbar), **Betroffenheits-Feststellung** (§ 5 Abs 6, erst mit F-… Betroffenheit), **Aussetzung** (§ 6 Abs 3 lit d, 7-Tage-Frist zum Schiedsgericht). Interne Abstimmung wie in FB-I4 (Quorum nach § 6 Abs 2 lit e).
- *Oberfläche Koordinationsrat:* Knopf „Hervorhebung beim Integritätsrat beantragen" an jedem Antrag im KoRat-Bereich, mit Begründung; Status des Antrags sichtbar (offen / beschlossen / abgelehnt).

**Ist:** ❌ kein UI — `Antrag.hervorgehoben` nur per `demo_seed` (`demo_seed.py:154-159`); Rolle Integritätsrat existiert ohne Funktion (`gremien/views.py:92-98`).

---

### Bereich E · Meine Region (Feld rechts unten)

#### FB-E1 · 3×3 Felder Gemeinde / Bezirk / Land — 🟡
**Quelle:** A0-05 — *„Meine Region ist ähnlich aufgebaut wie Wichtige Abstimmungen mit grafisch anregend und strukturiert in 3 x 3 rechteckige Felder in Gemeinde, Bezirks und Landesebene Abstimmungen oder Entscheide die direkt angezeigt werden und wo direkt drauf geklickt und abgestimmt werden kann."*

**Spezifikation**
- *Raster:* Drei Zeilen (Gemeinde · Bezirk · Land), jede Zeile ein **Band** mit Zeilenkopf links (vertikal: Ebene + Ortsname, z. B. „GEMEINDE · St. Marienkirchen", 11 px Kapitälchen, drehbar bei schmalen Feldern) und **drei gleich großen Kacheln** rechts daneben — das Feld ist also ein 3×3-Raster aus rechteckigen Kacheln (`grid-template-rows: repeat(3, 1fr)`), die das Feld ausfüllen. Hat eine Ebene mehr als drei laufende Verfahren, **wischt die Zeile horizontal** (Scroll-Snap je Kachel) und zeigt rechts eine Pille „› 2 weitere" (FB-A5, horizontal). Hat sie weniger, bleiben Plätze leer; hat sie keins, steht in der Zeile **eine** schmale Leerkachel „Noch nichts in deiner Gemeinde — Antrag einbringen ›".
- *„Grafisch anregend":* jede Ebene hat ein eigenes, dezentes Kachel-Wasserzeichen (Rathaus-, Bezirks-, Landes-Umriss als Linien-Icon, 10 % Deckung rechts unten) und einen farbigen Zeilenkopf-Balken (Gemeinde petrol, Bezirk gold, Land tinte). *(Ausarbeitung.)*
- *Kachel:* wie FB-D2 (Thema+Stern, Titel, Stand, Frist, Direkt-Handlung), ohne Hervorhebungsgrund, dafür mit Ortszeile nur bei Gästen/ohne Wohnsitz.
- *Direkt abstimmen:* Ja/Nein/Enthaltung in der Kachel; nach der Stimme bleibt die Kachel, die Wahl ist markiert, ein Gold-Haken „Erfasst" blendet 1,5 s ein; Personenwahl-Kacheln führen zur Wahl der Bewerbungen.
- *Ohne Wohnsitz (Mitglied):* Zeilen zeigen alle regionalen Verfahren mit Ort; Leerkachel „Wohnsitz hinterlegen ›" führt zum **Profil** (FB-K5 — heute gibt es keine Profilseite).
- *Gäste:* wie ohne Wohnsitz, ohne Stimmknöpfe.
- *Handy:* Zeilen untereinander, je Zeile horizontal wischbar (eine Kachel ≈ 78 % Feldbreite sichtbar, die nächste ragt an — der sichtbare Anschnitt ist der „mehr vorhanden"-Hinweis).

**Abnahme:** Auf 1440×900 sind drei Bänder mit je bis zu drei gleich großen Kacheln sichtbar, kein vertikaler Scroll nötig; die vierte Gemeinde-Kachel ist durch Wischen erreichbar und wird durch „› 1 weitere" angekündigt; Ja/Nein/Enthaltung funktioniert in der Kachel ohne Seitenwechsel.
**Ist (0.34.0):** 🟡 Drei **Bänder** Gemeinde · Bezirk · Land teilen sich die Feldhöhe (`.baender`, `repeat(3, minmax(0,1fr))`, Mindesthöhe 300 px), jedes mit senkrechtem Zeilenkopf (Ebene · Ort, farbiger Balken petrol/gold/tinte) und einer **waagrecht wischbaren Spur** mit drei gleich großen Kacheln (Scroll-Snap; Handy 78 % Breite, die nächste ragt an); ab der vierten Kachel die Pille „› n weitere" (Alpine `spur`, FB-A5). Kacheln wie FB-D2 in kompakter Form (Titel einzeilig, ohne Balken und Hervorhebungsgrund), Direktabstimmung ✅, Gold-Haken „Erfasst" ✅ (FB-A2). Leerkachel je Band mit Handlung (FB-E3). Auf 1440×900 sind alle drei Bänder ohne vertikalen Scroll sichtbar (`verfahren/test_region_baender.py`, `tests/e2e/test_mehr_vorhanden.py`). **Offen:** Wasserzeichen-Icons je Ebene ❌; Leerkachel „Wohnsitz hinterlegen ›" → Profil ❌ (FB-K5, es gibt keine Profilseite).
**Ist (0.33.0):** 🟡 drei Zeilen mit `.kacheln.dreier` (Zeilenumbruch statt Wischen, keine Höhenteilung).

#### FB-E2 · Gleicher Seitenaufbau wie Wichtige Abstimmungen (KI-Einschätzung, Chat) — ❌ (folgt aus FB-F)
**Quelle:** A0-05 — *„Ähnlich aufgebaut wie bei Wichtige Abstimmungen also mit KI Einschätzung und Chatbereich."* → Regionale Antragsseiten sind normale Antragsseiten (FB-F1–F3). Zusätzlich: die Zukunftswerkstatt kennt die Ebene (Gemeinde-Antrag → Gemeindeordnung, Landesgesetze; keine Bundes-Personalaggregate).

#### FB-E3 · Leerzustände — ✅
**Ausarbeitung:** kurz und mit einer Handlung (siehe FB-E1). **Ist (0.34.0):** ✅ je Band eine schmale Leerkachel „Noch nichts in Ihrer Gemeinde. Antrag einbringen →" (vier Wörter + Handlung; Bezirk/Land analog), `parlament.html`, getestet in `verfahren/test_region_baender.py`. Die anderen Felder: „Derzeit läuft kein Verfahren." / „Derzeit ist nichts hervorgehoben." (je vier Wörter).

---

### Bereich F · Die Antragsseite in drei Zonen

#### FB-F1 · Drei Zonen: Text · Einschätzung · Chat — ❌
**Quelle:** A0-05 — *„Diese Seiten haben immer den Bereich wo der Text steht um den es geht, einen wo die KI Einschätzungen (mit grafiken und animationen die die KI Einschätzungen leichter verständlich machen) für die User stehen und einen weiteren wo gechattet werden kann zu dem Thema."*

**Spezifikation**
- *Gilt für jede Antragsseite* — Sachantrag, Mandats-Kandidatur, regional oder bundesweit, in jeder Phase.
- *Kopf (über den Zonen):* Zurück-Pfeil „‹ Parlament", Titel (H1), Chip-Zeile (Phase, Ebene · Ort, Lebensbereiche als klickbare Chips), Meta in einer Zeile („eingebracht 02.09.2026 · Mitglied 4 · 3 Unterstützungen · Frist 29.09."), Stern. Bei Hervorhebung ein Gold-Band mit dem Beschluss.
- *Zonen-Leiste (klebt unter der App-Leiste):* drei Reiter **„Text" · „Einschätzung" · „Chat (12)"** + Reiter **„Archiv"** (FB-G7). Auf dem Desktop scrollen die Reiter zur Zone (Seite ist eine lange Fläche), auf dem Handy schalten sie die Zone um (nur eine Zone sichtbar, Wisch links/rechts wechselt, gerichtete Übergangsanimation). Aktiver Reiter gold unterstrichen; die Leiste zeigt beim Scrollen die aktuelle Zone (Scroll-Spy).
- *Layout Desktop ≥ 1100 px:* Zone 1 **links (58 %)** und Zone 2 **rechts (42 %, klebend beim Scrollen von Zone 1)** nebeneinander; Zone 3 darunter in voller Breite. So sind Text und Einschätzung gleichzeitig sichtbar — die Einschätzung ist die Lesehilfe zum Text. Zwischen 760 und 1099 px: Zonen untereinander in voller Breite.
- *Zone 1 „Text":* Wortlaut (aktuelle Fassung, gut lesbar: 17 px, Zeilenlänge ≤ 75 Zeichen), Begründung, darunter die **Handlungskarte** je Phase (Unterstützen / Bewerbungen / Abstimmen / Ergebnis / Umsetzung — Inhalte wie heute), darunter aufklappbar: „Alle Fassungen (3)", „Entwurfsschleife" (Stand und Vorschlag im Wortlaut, FB-I2), „Eingefrorene Regeln (§ 5 Abs 5)" als **lesbare Liste** („Unterstützungsschwelle 3 · Frist 60 Tage · Beratung 21 Tage · Abstimmung 28 Tage · Mindestbeteiligung 5 %") statt JSON; JSON als Link „Rohdaten".
- *Zone 2 „Einschätzung":* siehe FB-F2.
- *Zone 3 „Chat":* siehe FB-G1.
- *Ohne JavaScript:* alle Zonen untereinander, Reiter sind Anker-Links.
- *Barrierefreiheit:* Reiter als `role="tablist"` (Handy) bzw. Sprungnavigation (Desktop); Überschriften-Hierarchie H1 → H2 je Zone.

**Abnahme:** `/antrag/4/` auf 1440×900: Text links, Einschätzung rechts klebend, Chat unten; Reiterleiste bleibt beim Scrollen sichtbar und markiert die Zone; auf 390 px schalten die Reiter, Wischen wechselt; kein JSON-Block im Sichtbereich.
**Ist:** ❌ einspaltig, Reihenfolge Kopf → Wortlaut → Handlung → Ergebnis → Umsetzung → Schleife → Beratung → JSON (`antrag.html`); keine Zonen, keine Reiter.

#### FB-F2 · Zone „Einschätzung" der Zukunftswerkstatt mit Grafiken und Animationen — ❌
**Quelle:** A0-05 (oben) · A0-01 (Inhalte: Gesetze, Judikatur/Exekutive/Personal, Aufwand/Dauer, Ausschreibung, Firmen) · Satzung § 5 Abs 10 lit d, § 6 Abs 11 lit b.

**Spezifikation — die Zone ist ein Stapel von Karten, jede Karte = eine Einschätzungsart**
0. **Kopfkarte:** „Einschätzung der Zukunftswerkstatt" + Kennzeichnung in Gold-Rahmen: **„Modellrechnung — sie schlägt vor, sie entscheidet nie"**, darunter klein: Modell (z. B. mistral-small-latest), Kontextstand (Datum der Faktenbasis), Lauf-Nr. mit Link ins Lauf-Archiv, Knopf **„Beanstanden"** (öffnet Inline-Formular: Was ist falsch? → erzeugt öffentlichen Beanstandungsvermerk + Korrekturlauf-Anforderung, § 6 Abs 11 lit b).
1. **Ähnliche Anträge** (FB-H2): bis 3 Karten mit Übereinstimmung als Ring-Prozent, Phase, Beteiligung, Knopf „Unterstützen" — auf der Antragsseite als Rückblick („Beim Einbringen gefunden: …").
2. **Berührte Gesetze** (FB-H3): Liste der Normen mit RIS-Link, je Norm ein Chip „ändern" / „aufheben" / „neu"; darunter eine kleine **Graph-Grafik** (Kreise = Normen, Linien = Querverweise; berührte Normen gold, Nachbarn grau; beim Erscheinen wachsen die Kreise 400 ms gestaffelt). Tooltip je Kreis: Titel + § + Grund.
3. **Folgen für Judikatur und Exekutive** (FB-H3): zwei Spalten mit je 2–3 Sätzen; darunter die **Personal-Grafik**: horizontale Balken „Beamte" / „Vertragsbedienstete" mit Auf-/Abbau als ± Balken (Aufbau gold nach rechts, Abbau petrol nach links), Zahl mit Spanne („+120 bis +180 VBÄ"), Quelle. Balken wachsen beim Erscheinen.
4. **Aufwand, Last und Dauer** (FB-H4): **Lastampel** (drei Kreise grün/gelb/rot, der aktive leuchtet mit weichem Puls, `prefers-reduced-motion` = statisch) mit einem Satz „Vertretbar neben den 3 laufenden Umsetzungen" + Link zum Umsetzungsregister; **Zeitstrahl** „Inkrafttreten frühestens in ~14 Monaten" mit Etappen (Beschluss → Begutachtung → Gesetz → Verordnung → Vollzug), die sich beim Erscheinen von links füllen.
5. **Ausschreibung** (FB-H5): Ja/Nein-Plakette mit Begründung (Auftragsart, Schwellenwert nach BVergG), Link zur Vergabe-Kerndatenquelle; später (FB-H7) „Mögliche Bieter (Näherung)" als Liste mit Kapazitäts-Balken.
6. **Prognose-Abgleich** (nach Vollzug, FB-J7): Einschätzung vs. Wirklichkeit als Gegenüberstellung mit Abweichungs-Prozent.
- *Wenn kein Anbieter angeschlossen oder noch kein Lauf:* die Zone zeigt die Kopfkarte mit **ehrlichem Leerzustand** („Für diesen Antrag liegt noch keine Einschätzung vor — sie wird in der Beratungsphase erstellt" bzw. „Kein Anbieter angeschlossen") und die Karten als **Skelett-Umrisse** (graue Platzhalterformen), damit sichtbar ist, was kommen wird.
- *Wann gerechnet wird:* beim Eintritt in die Beratung automatisch (Warteschlange, FB-H6); auf der Antragsseite kein Knopf für Mitglieder (Kostenbudget); Rolleninhaber ER1 können einen Lauf anfordern.
- *Grafiken:* servergerendertes SVG aus `plattform_core/diagramme.py` (kein Chart-Framework), Farben aus den Tokens, Animation per CSS (`stroke-dashoffset`, `transform-origin`), alle Grafiken mit `role="img"` und Textalternative; Zahlen zusätzlich als Text.

**Abnahme:** `/antrag/2/` (Beratung) zeigt rechts die Kopfkarte mit Modell/Kontextstand/Beanstanden; bei angeschlossenem Anbieter mindestens die Karten 2, 4 und 5 mit animierten Grafiken; ohne Anbieter der Leerzustand mit Skeletten; Beanstanden legt einen öffentlichen Vermerk an.
**Ist:** ❌ keine Zone, keine Grafiken; die einzige KI-Nutzung ist die Werkstatt-Einschätzung im ER1-Fenster (`gremien/views.py:42-49,217-226`); Beanstandung ❌ (Lastenheft F-60 offen).

#### FB-F3 · Zone „Chat" — siehe Bereich G.

#### FB-F4 · Mandats-Kandidaturen auf der Antragsseite — ✅ (Politur)
**Ist:** Bewerbungen, Zustimmungswahl, Ergebnis ✅ (`antrag.html:43-111`). Delta: in Zone 1 als Handlungskarte; Bewerbungen als Karten mit Initialen-Avatar; Zone 2 zeigt für Kandidaturen nichts (Personenwahl: keine Modellrechnung) — Reiter „Einschätzung" entfällt dann.

---

### Bereich G · Das Chatsystem

#### FB-G1 · Der Chat unterhalb der Antragsseite — 🟡
**Quelle:** A0-05 — *„Ich kann mir vorstellen, dass Chats ein großes Thema auf der ganzen ParlamentPlattform sein werden. Deshalb sollten wir ein eigenes Chatsystem aufbauen. Einerseits unterhalb angezeigt zum runterscrollen…"*

**Spezifikation**
- *Datenmodell:* `Kommentar` erhält `antwort_auf` (FK auf Kommentar, null = Wurzelbeitrag), `phase` (Phase des Antrags beim Schreiben — Unterstützung / Beratung / Vorschlagsberatung Runde n / Abstimmung), `archiviert_am` (gesetzt bei Hochstufung, FB-G5), `bearbeitet_am` (Änderung nur binnen 5 Minuten, danach unveränderlich, Änderung sichtbar „bearbeitet"), `geloescht` (Soft-Delete durch Verfasser: Text wird „[vom Verfasser entfernt]", Struktur bleibt). Neues Modell `Reaktion` (kommentar, mitglied, art ∈ {zustimmung, ablehnung}, zeit; unique je Mitglied und Kommentar) — genutzt in FB-G6, in normalen Phasen als Zugabe („👍" ohne Wirkung auf Reihung — ❓ D-G1: Reaktionen außerhalb des Abstimmungs-Chats erlauben? Empfehlung: ja, aber nur Zustimmung, rein informativ, chronologische Reihung bleibt).
- *Aussehen:* Zone 3 „Chat (12)": Beiträge als **Sprechblasen-Karten** in einem Faden: Avatar-Kreis (Initiale des Anzeigenamens, Farbton aus Namens-Hash), Name, Zeit relativ („vor 2 Std.", Tooltip absolut), Text (Zeilenumbrüche, Links werden anklickbar, kein HTML), darunter Zeile: „Antworten" · Reaktion(en) · Beitragsnummer als Anker (#k-123). Antworten sind **eine Ebene eingerückt** (16 px, Linie links) unter ihrem Elternbeitrag; tiefere Antworten bleiben auf dieser Ebene (flach, wie bei Reddit-„max depth 1"), mit „↳ @Name" als Textpräfix (automatisch gesetzt, nicht nötig zu tippen). Eigene Beiträge mit Gold-Kante.
- *Eingabe:* unten eine **klebende Eingabezeile** (Textfeld wächst bis 6 Zeilen, Knopf „Senden", Zähler ab 3.500 von 4.000 Zeichen); „Antworten" unter einem Beitrag setzt die Eingabezeile in den Antwort-Modus (Chip „Antwort auf Mitglied 3 ×"). Senden per htmx: der neue Beitrag gleitet unten ein (Auftauchen 260 ms), Eingabe leert sich, Fokus bleibt. Ohne JavaScript: Formular, Seite lädt neu auf den Anker.
- *Reihung:* chronologisch aufsteigend (ältester oben) in Unterstützung, Beratung, Abstimmung; im Abstimmungs-Chat nach Engagement (FB-G6). Ein Umschalter „Neueste zuerst" (rein persönlich, `localStorage`).
- *Sperre:* Chat geschlossen (Eingabezeile ersetzt durch Hinweis) während „Expertenrat arbeitet" (FB-G6) und nach Verfahrensende (Archiv lesbar).
- *Leerzustand:* „Noch kein Beitrag — der erste kann deiner sein." + Eingabezeile. Gäste: „Mitlesen ist offen — zum Mitreden anmelden".
- *Neue Beiträge seit dem letzten Besuch:* Trennlinie „— 4 neue Beiträge —" an der Stelle, ab der die Beiträge neu sind (FB-G2), gold.
- *Moderation:* Meldeknopf „Melden" (Art 16 DSA, § 5 Abs 2) je Beitrag → Meldung an Verwaltung/Integritätsrat; Verwaltung kann Beiträge ausblenden (Grund öffentlich, Audit).

**Abnahme:** Antworten erscheinen eingerückt; Senden ohne Neuladen; Antwort-Modus per Chip abbrechbar; Zähler ab 3.500; Gast sieht Beiträge, aber keine Eingabe.
**Ist:** 🟡 flache Kommentarliste „Beratung (n)" mit Formular (`antrag.html:175-195`), kein Antworten, keine Reaktionen, keine Anker, keine Sperre nach Hochstufung (Formular nur in Unterstützung/Beratung), keine Moderation.

#### FB-G2 · Die Kommentarleiste merkt sich die Scrollposition — ❌
**Quelle:** A0-05 — *„(die kommentarleiste soll immer dort stehen wo ich zuletzt aufgehört habe zu scrollen auch wenn ich dazuwischen auf anderen seiten war)"*

**Spezifikation**
- Je Antrag und Gerät wird beim Verlassen der Seite (und alle 2 s beim Scrollen, `scroll`-Ereignis gedrosselt) gespeichert: `{antragId, letzterSichtbarerBeitragId, scrollOffsetImBeitrag, zeit}` in `localStorage` unter `ddoe.chat.<antragId>`. Beim erneuten Öffnen der Antragsseite (auch über den Reiter „Chat" oder das Panel) scrollt die Seite **ohne Animation** exakt dorthin (Beitrag-Anker + Offset), *bevor* die Seite sichtbar wird (Skript im `<head>`-Bereich der Zone bzw. `htmx:afterSettle`). Zusätzlich serverseitig beim Mitglied: `zuletzt_gelesen` (Kommentar-ID je Antrag) — daraus die Trennlinie „n neue Beiträge" (FB-G1), geräteübergreifend.
- Wenn der gemerkte Beitrag archiviert wurde (Hochstufung), landet man am Anfang des neuen Chats mit Hinweis „Der Chat wurde beim Wechsel in die Beratung archiviert — Archiv ansehen".
- Ohne JavaScript: Sprung zum ersten ungelesenen Beitrag über den Anker `#neu` (serverseitig aus `zuletzt_gelesen`).

**Abnahme:** In `/antrag/2/` zum 5. Beitrag scrollen, zu `/parlament/` wechseln, zurück: Der 5. Beitrag steht an derselben Stelle; nach Neustart des Browsers ebenso.
**Ist:** ❌ (Inventar Frage 11).

#### FB-G3 · Das Ausklapp-Panel links auf der Parlament-Seite — ❌
**Quelle:** A0-05 — *„…andererseits als eigenes menü zum ausklappen auf der linken Bildschirmseite der Parlament Seite worin eine chronologische Auflistung mit 3 Spalten ist. Thema, Name des Antrages und Chatpartner auf den du reagiert hast oder der auf dich reagiert hat wobei er nicht dich explizit benennen muss wie bei instagram sonder es reicht wenn er ein kommentar unter deinem postet oder du eines unter seinem. Falls die leiste zu lang wird kann man die leiste des Kommentarmenüs scrollen."*

**Spezifikation**
- *Griff:* Am **linken Bildschirmrand** von `/parlament/` (Ausarbeitung: auch auf jeder Antragsseite — ❓ D-G3) klebt vertikal mittig ein schmaler **Griff** (24 × 96 px, halbrund, Kartenfarbe, Sprechblasen-Symbol, Zähler-Punkt mit Zahl ungelesener Gespräche in Gold). Auf dem Handy liegt das Symbol in der Tableiste (fünftes Symbol „Chats") — kein Randgriff.
- *Panel:* Klick/Wisch von links öffnet ein **Panel** (Breite 380 px, Desktop; Handy: 92 % der Breite), das **von links hereingleitet** (280 ms), mit dunklem Schleier über dem Rest (`rgba(14,34,48,.35)`), Klick auf den Schleier, Escape oder der Griff schließen es. Kopf: „Meine Gespräche" + Filter-Chips „Alle · Ungelesen" + X.
- *Liste (chronologisch, neueste Aktivität zuerst), drei Spalten je Zeile:*
  1. **Thema** — Lebensbereich-Chip (kurz, Säulenfarbe),
  2. **Antrag** — Titel (max. 2 Zeilen), darunter klein die Phase,
  3. **Chatpartner** — Avatar + Anzeigename des Gegenübers, darunter der Anfang seines/meines letzten Beitrags (1 Zeile, kursiv), rechts die Zeit („vor 3 Std.") und ein Gold-Punkt, wenn ungelesen.
  Auf 380 px Breite sind die drei Spalten als Raster `56px 1fr 120px` gesetzt; unter 360 px Breite stapeln Thema und Antrag.
- *Was ein „Gespräch" ist (implizit, ohne Erwähnung):* ein Paar (ich, Gegenüber) an einem Antrag, sobald **eine Antwort** existiert: das Gegenüber hat mit „Antworten" unter meinem Beitrag geschrieben, oder ich unter seinem. *(Ausarbeitung:* zusätzlich zählt ein Wurzelbeitrag, der unmittelbar nach meinem Wurzelbeitrag geschrieben wurde, **nicht** — sonst wäre jeder Nachbar ein Gesprächspartner; die Antwortfunktion ist überall einen Klick entfernt, das genügt „unter deinem posten".) Mehrere Antworten desselben Paars am selben Antrag = ein Gespräch mit Zähler. Ein Gespräch ist „ungelesen", wenn der letzte Beitrag des Gegenübers jünger ist als mein `zuletzt_gelesen` am Antrag.
- *Klick auf eine Zeile:* führt **direkt zur Antragsseite an den Beitrag** (`/antrag/<id>/#k-<letzterBeitragDesGegenübers>`), der Beitrag wird 2 s gold hinterlegt; das Panel schließt sich.
- *Scrollen:* Die Liste scrollt innerhalb des Panels (Kopf bleibt), mit FB-A5-Hinweis; lädt in Blöcken à 30 (htmx „mehr laden" am Ende).
- *Räumung:* Gespräche eines Antrags verschwinden aus der Liste, sobald der Antrag hochgestuft wurde (FB-G5) — sie sind dann im Archiv.
- *Ohne JavaScript:* Der Griff ist ein Link auf `/gespraeche/` — dieselbe Liste als eigene Seite.
- *Barrierefreiheit:* Panel `role="dialog" aria-label="Meine Gespräche"`, Fokusfalle, Escape.

**Abnahme:** Mitglied 3 antwortet auf meinen Beitrag in Antrag 2 → Griff zeigt „1"; Panel öffnet von links; Zeile zeigt „Demokratie, Staat…" · „Testlauf: monatlicher…" · „Mitglied 3 · vor 1 Min."; Klick springt zum Beitrag und markiert ihn; nach Hochstufung von Antrag 2 ist die Zeile weg.
**Ist:** ❌ (Inventar Frage 11).

#### FB-G4 · Leiste scrollbar; Klick führt zur Antragsseite — ❌ (Teil von FB-G3)

#### FB-G5 · Chats werden bei jeder Hochstufung geräumt und archiviert — ❌
**Quelle:** A0-05 — *„Die Chats werden entfernt sobald der diskutierte Antrag durch also jedes mal wenn er hochgestuft wird."* · bestätigt 1.9. (Archiv, FB-G7).

**Spezifikation**
- *Hochstufung* = jeder Phasenwechsel nach vorn: Unterstützung → Beratung, Beratung → Expertenrat arbeitet (Fenster geöffnet und eingereicht — Ausarbeitung: Beginn der „Vorschlagsberatung"), Vorschlag → Endabstimmung, Endabstimmung → Ergebnis. Bei jedem dieser Wechsel werden alle Beiträge der vorigen Phase mit `archiviert_am` gestempelt; sie verschwinden aus Zone 3 und aus dem Panel und erscheinen im Archiv (FB-G7) unter der Phase. Zone 3 beginnt leer mit einem **Phasen-Band**: „Beratung begonnen am 12.09. — 14 Beiträge aus der Unterstützungsphase im Archiv ›".
- *Nichts wird gelöscht* — Archivierung ist Sichtbarkeit, nicht Entfernung (Audit-Kette, § 5 Abs 3 lit e).
- *Ausnahme (Ausarbeitung):* Beim Wechsel Beratung → Endabstimmung wird der Abstimmungs-Chat (FB-G6) mit dem Vorschlag **eingefroren** und in Zone 3 der Endabstimmung als aufklappbarer Block „So kam der Vorschlag zustande" angezeigt — die Abstimmenden sollen die Kritik sehen. ❓ D-G5.

**Abnahme:** Antrag 1 erreicht die Schwelle → seine 3 Beiträge sind in Zone 3 weg, im Archiv unter „Unterstützungsphase", das Panel zeigt das Gespräch nicht mehr; der Audit-Log hat keinen Löschvorgang.
**Ist:** ❌ Kommentare bleiben stehen, Formular schließt nur (`views_aktionen.py:257`).

#### FB-G6 · Der Abstimmungs-Chat zum Vorschlag des Expertenrats — ❌ (heute: Votum-Formular)
**Quelle:** A0-07 — *„P7 Bei Hochstufung zu Expertenrat kann erst wieder darunter gechattet werden wenn der Expertenrat eine Vorlage geliefert hat. In diesem Chat wird mit Zustimmungen zu Kommentaren gewählt. Wenn ein Kommentar etwas an dem Entwurf des Expertenrates auszusetzen (muss konkrete Kritik beinhalten) hat und diesem Kommentar sehr oft zugestimmt wird mittels klick auf ein passendes emoji oder zeichen neben dem Kommentar. Bei jedem Kommentar kann man zustimmen oder ablehnen. Die kommentare mit dem meisten engagement erscheinen dabei ganz oben. Das ist nur der erste Entwurf dieser abstimmungsfunktion. Wenn ein Kommentar mit passt alles ganz oben steht und die meiste zustimmung hat also mehr als 50% dann wird der entwurf nach ablauf der frist hochgestuft zur endgültigen abstimmung ob das gesetz so verabschiedet wird. Die Beratung ist ja der Vorschlag des Expertenrat."* · A0-03 — *„…wodurch der entwurf den unterstützern des antrages vorgelegt wird die dann abstimmen ob er nochmal zurück zu den experten muss mit verbesserungswünschen oder so zur endabstimmung kommt…"*

**Spezifikation**
- *Ruhephase:* Sobald der Expertenrat das Entwurfsfenster öffnet **und** einreicht — genauer: ab Hochstufung in die Beratung, sobald Gruppe 1 arbeitet (Ausarbeitung: die Sperre beginnt mit dem Öffnen des Entwurfsfensters; vorher ist die Beratung offener Chat) — ist Zone 3 gesperrt: Band „Der Expertenrat arbeitet am Vorschlag (Runde 1) — der Chat öffnet, sobald der Vorschlag vorliegt", mit Fristanzeige (FB-J1). Lesen bleibt möglich.
- *Öffnung als Abstimmungs-Chat:* Mit dem eingereichten (ggf. von Gruppe 2 validierten) Vorschlag öffnet Zone 3 neu, überschrieben mit **„Vorschlag des Expertenrats — Runde 1 · Beratung bis 26.09."**; der Vorschlag steht im Wortlaut als erste, gepinnte Karte (Gold-Rahmen), darunter Diff-Umschalter „Änderungen zum Antrag zeigen" (Wort-Diff, Einfügungen grün, Streichungen rot durchgestrichen).
- *Der „Passt alles"-Eintrag:* Die Plattform legt beim Öffnen automatisch **einen gepinnten Systembeitrag „✓ Passt alles — der Vorschlag kann so zur Endabstimmung"** an (kein Mitglied als Verfasser; deutlich als Systemeintrag gestaltet). Er ist der Kommentar, auf den sich die 50-%-Regel bezieht — so muss niemand raten, welcher Beitrag „passt alles" bedeutet. *(Ausarbeitung des Gründer-Satzes „Wenn ein Kommentar mit passt alles ganz oben steht".)*
- *Beiträge:* Jedes Mitglied kann Beiträge schreiben; Beiträge, die etwas am Vorschlag auszusetzen haben, werden als **Kritik** markiert (Umschalter „Das ist konkrete Kritik am Vorschlag" beim Schreiben; Pflicht: mindestens 80 Zeichen und **ein Bezug auf eine Textstelle** — Auswahl eines Absatzes des Vorschlags aus einer Liste oder Zitat per Markieren; ohne Bezug ist die Kritik-Markierung nicht setzbar). Kritik-Beiträge tragen ein rotes Eck-Etikett „Kritik · Absatz 3".
- *Reaktionen (das Wählen):* Neben **jedem** Beitrag zwei Zeichen: **👍 Zustimmen** und **👎 Ablehnen** (Ausarbeitung: als runde Knöpfe mit Zähler, ein Mitglied pro Beitrag genau eine Reaktion, umschaltbar bis Fristende; Tipp löst eine kurze Pop-Animation aus). **Nur Unterstützer des Antrags** können reagieren — das ist die Abstimmung der Unterstützer nach A0-03/§ 5 Abs 12; alle anderen sehen die Zähler und können schreiben, nicht reagieren (Tooltip „Reagieren können die Unterstützer dieses Antrags"). ❓ D-G6a: Sollen alle Mitglieder reagieren dürfen, die Reaktionen der Unterstützer aber gesondert gezählt werden?
- *Reihung:* nach **Engagement** = Zustimmungen + Ablehnungen (absteigend), bei Gleichstand nach Zustimmungsanteil, dann Zeit; der gepinnte „Passt alles"-Eintrag ordnet sich mit ein (steht also nur oben, wenn er das meiste Engagement hat) — ein Umschalter „chronologisch" für die eigene Ansicht. Die Reihungsregel steht als Parameter (`vorschlag-chat-reihung = engagement-v1`) im Register und ist im Zonenkopf verlinkt („Reihung: Engagement, Regel v1").
- *Auswertung nach Fristablauf (Unterstützer-Frist, FB-J1):*
  - Steht der **„Passt alles"-Eintrag an erster Stelle** und hat er **mehr als 50 % Zustimmung** (Zustimmungen ÷ (Zustimmungen + Ablehnungen) > 0,5; Schwelle als Parameter `vorschlag-annahme-anteil = 0.5`) → der Vorschlag wird zur **Endabstimmung hochgestuft** (neue Antragsfassung, wie heute in `Entwurf._endabstimmung_oeffnen`).
  - Sonst → der Vorschlag geht **mit den Kritik-Beiträgen als gesammelte Änderungswünsche** zurück an den Expertenrat (Runde + 1): Übergeben werden alle Kritik-Beiträge, gereiht nach Engagement, mit Textstellen-Bezug; sie erscheinen im Entwurfsfenster als Liste „Wünsche der Unterstützer (Runde 1)". Höchstrunden wie heute (Parameter). „Untätigkeit hemmt nie": bleibt der Chat still (keine einzige Reaktion), gilt der Vorschlag als angenommen (heutige Regel bleibt).
  - Sonderfall: „Passt alles" steht oben, aber ≤ 50 % — dann Rückgabe; steht ein Kritik-Beitrag oben, aber „Passt alles" hat > 50 % — dann **Rückgabe** (der Gründer verlangt beides: oben *und* > 50 %). ❓ D-G6b bestätigen.
- *Ablösung des heutigen Votum-Formulars:* Das Abstimmungs-Chat-Ergebnis ersetzt `UnterstuetzerVotum` (annehmen/zurückgeben). Migration: bestehende Voten werden als Reaktionen auf den „Passt alles"-Eintrag übernommen (annehmen → 👍, zurückgeben → 👎 + Wunsch als Kritik-Beitrag).
- *Anzeige im Entwurfsfenster (ER1):* Live-Stand „Passt alles: 7 👍 / 2 👎 (78 %) · 3 Kritik-Beiträge" + Link in den Chat.
- *Alle Zähler sind öffentlich und nachrechenbar* (Export im Archiv); Reaktionen tragen den Anzeigenamen (offen, wie das heutige Votum — § 5 Abs 12 kennt kein Geheimnis für dieses Votum). ❓ D-G6c: offen oder pseudonym?

**Abnahme:** Nach Einreichung erscheint der gepinnte Vorschlag + „Passt alles"; ein Nicht-Unterstützer sieht die Reaktionsknöpfe ausgegraut; 3 Unterstützer 👍 auf „Passt alles", 1 👎 → nach Fristablauf (Zeitraffer im Test) ist der Antrag in der Endabstimmung; umgekehrt (Kritik oben mit 4 Reaktionen, „Passt alles" 1 👍) → Runde 2 mit der Kritik im Entwurfsfenster.
**Ist:** ❌ `UnterstuetzerVotum` mit annehmen/zurückgeben + Wunsch (`_schleife.html`, `gremien/models.py:288-310`) — kein Chat, keine Reaktionen, keine Reihung; Sperre während der Werkstatt-Arbeit ❌.

#### FB-G7 · Die Archiv-Registerkarte mit Export — ❌
**Quelle:** A0-07 — *„Ein Archiv Registrierkarte mit den archivierten daten von allen chats von der Antragstellung bis hin zu den vorschlägen des expertenrats und allen vorherigen Vorgängen übersichtlich zum reinklicken dargestellt soll darin abrufbar und exportierbar sein."*

**Spezifikation**
- *Reiter „Archiv"* in der Zonen-Leiste (FB-F1). Inhalt: eine **Zeitleiste** von oben (Antragstellung) nach unten (heute), je Phase ein aufklappbarer Block mit Datum, Dauer, Kennzahlen („14 Beiträge · 3 Gespräche · 4 Unterstützungen") und Inhalt:
  - Unterstützungsphase: Chat (schreibgeschützt, Faden wie in Zone 3), Unterstützungsverlauf als kleine Kurve (Tage → Unterstützungen).
  - Beratung: Chat; Expertenrat-Block je Runde: Fassungen (append-only, mit Diff zur vorigen), interne Beratung des ER1 (öffentlich nach § 6 Abs 9), Einreich-Abstimmung, Prüfung Gruppe 2 mit Begründung, Abstimmungs-Chat mit Reaktionszählern und Auswertung („Passt alles 78 % → hochgestuft").
  - Endabstimmung: Beteiligungsverlauf, Ergebnis, Link zur Stimmliste.
  - Umsetzung: Vollzugseinträge.
  - Dazu die Audit-Ereignisse des Antrags als schmale Zeitleiste (Ereignis, Zeit, Hash-Kurzform).
- *Export:* Knopf „Archiv exportieren" → **JSON** (vollständig: Fassungen, Beiträge mit Antwortbezug, Reaktionen, Voten, Prüfungen, Audit-Auszug) und **Markdown** (lesbar, gleiche Gliederung); Dateiname `antrag-<id>-archiv.<ext>`; Personennamen wie öffentlich angezeigt (Anzeigename), keine E-Mails.
- *Zugriff:* öffentlich lesbar (wie die Antragsseite), Export für alle.

**Abnahme:** Reiter „Archiv" an Antrag 2 zeigt Blöcke „Unterstützung" und „Beratung — Runde 1"; Export-JSON enthält die Fassung 1 und alle Beiträge mit `antwort_auf`.
**Ist:** ❌ (Inventar Frage 11; `export.json` enthält nur Stimmen).

---

### Bereich H · Der Antragsweg mit der Zukunftswerkstatt (KI)

#### FB-H1 · Eine KI im Antragsweg — anbieterneutral, budgetiert — ✅ (Fundament) / ❌ (Nutzung)
**Quelle:** A0-01 — *„…dass wir eine (am besten kostenlos) ki (vielleicht mit einem api key) einsetzen…"*

**Spezifikation:** Der Modell-Steckplatz (App `ki`) bleibt die einzige Stelle, an der ein Modell aufgerufen wird; Anbieter per Umgebungsvariable (heute Mistral; Ollama/vLLM sprechen dasselbe Chat-Format); hartes Monatsbudget im Parameterregister; jeder Lauf archiviert (auch Fehlläufe); **Prompt-Versionierung** (jeder Auftragstext bekommt eine Versionsnummer und liegt als Datei `ki/auftraege/<zweck>-v<n>.md` im Repo, der Lauf speichert die Version); **Warteschlange** mit Tageskontingent (Läufe für die Beratungsphase werden eingereiht, nicht synchron im Request ausgeführt — Management-Command `ki_warteschlange` als Cron, oder Django-Q-freie Lösung: Verarbeitung beim nächsten Seitenaufruf mit Sperre, wie die Phasenautomatik). Zwecke: `aehnlichkeit`, `rechtsfolgen`, `vollzug_last`, `vergabe`, `einschaetzung` (Werkstatt), `muster` (Lernschleife).
**Ist:** ✅ Steckplatz, Archiv, Budget (`ki/`); ❌ Prompt-Versionierung, Warteschlange, alle Zwecke außer `einschaetzung`.

#### FB-H2 · Ähnlichkeitsprüfung mit Wahl: bestehenden unterstützen oder eigenen stellen — 🟡 (Stufe 1 lexikalisch)
**Quelle:** A0-01 — *„1. zu prüfen ob ein anderer antrag mit ähnlichem inhalt bereits eingegangen ist. (dann soll dieser oder diese dem user gezeigt werden und zur wahl gestellt werden ob er den bereits bestehenden antrag bzw. anträge unterstützt oder er seinen antrag für so unterschiedlich zum bestehenden einstuft, dass er ihn selbst stellen möchte)"* · Satzung § 5 Abs 10 lit d.

**Spezifikation**
- *Ablauf beim Einbringen (Zone „Ähnliche Anträge" auf `/einbringen/`):* Nach dem Ausfüllen von Titel und Wortlaut — **schon während des Tippens** (htmx, 800 ms nach der letzten Eingabe, ab 40 Zeichen) — erscheint rechts neben dem Formular (Desktop) bzw. unter dem Wortlaut (Handy) die Karte **„Gibt es das schon?"** mit bis zu 3 Treffern: Titel, Übereinstimmung als Ring („72 %"), Phase, Beteiligung („12 Unterstützungen · noch 40 Tage"), **Gegenüberstellung** (2 Sätze, vom Modell: „Beide fordern … Der bestehende Antrag beschränkt sich auf …; Ihr Text erweitert auf …" — gekennzeichnet als KI-Einschätzung, Stufe 2; ohne Anbieter nur der Wortvergleich).
- *Die Wahl:* je Treffer ein Knopf **„Diesen unterstützen"** (unterstützt sofort, verwirft den eigenen Entwurf — mit Rückfrage „Ihr Text wird verworfen") und darunter der Knopf **„Mein Antrag ist etwas anderes — einbringen"** (immer gleichwertig; § 2 Abs 6). Wer einbringt, obwohl es Treffer gab, bekommt seine Wahl dokumentiert: am neuen Antrag steht in Zone 2 „Beim Einbringen als eigenständig eingestuft gegenüber: …" (kein Malus, reine Transparenz).
- *Erbschaft:* Wer einen bestehenden unterstützt, sieht dessen Einschätzung (Zone 2) — „für diesen gibt es ja die simulationsergebnisse schon".
- *Stufe 2 (Embeddings):* lokales Embedding-Modell (z. B. `multilingual-e5-small` über `sentence-transformers`, CPU; **kein Text verlässt die Plattform**) oder Anbieter-Embedding über den Steckplatz; Vektor je Antrag bei Einbringung gespeichert (`AntragsEmbedding`, Modellname + Version); Ähnlichkeit = Kosinus; Schwelle als Parameter `aehnlichkeit-schwelle` (Start 0,78), Anzahl `aehnlichkeit-treffer` (3). Die lexikalische Stufe 1 bleibt als Rückfall und Zweitmeinung (beide Werte werden angezeigt: „Wortvergleich 31 % · Bedeutung 72 %").
- *Ohne JavaScript:* Prüfung beim Absenden (heutiger Weg).

**Abnahme:** Beim Tippen eines Titels, der Antrag 1 ähnelt, erscheint nach < 1 s die Karte mit Antrag 1; „Diesen unterstützen" fragt zurück und unterstützt; „einbringen" legt den Antrag an und vermerkt die Einstufung.
**Ist:** 🟡 Trigramm-Jaccard beim Absenden, Karte „Ähnliche Anträge gefunden" mit „Trotzdem einbringen" / „Lieber einen bestehenden unterstützen" (→ nur Link ins Parlament, unterstützt nicht direkt) (`views_aktionen.py:163-220`, `einbringen.html:11-41`); Stufe 2 ❌; Live-Prüfung ❌; Dokumentation der Wahl ❌.

#### FB-H3 · Rechtsfolgen: Welche Gesetze, was bedeutet es für Judikatur, Exekutive, Personal — ❌
**Quelle:** A0-01 — *„2. eine einschätzung darüber abzugeben, welche aller in österreich angewendeten gesetze bei tatsächlicher umsetzung dieses antrages dadurch geändert werden müssten und was das für die judikatur, die exekutive bedeutet inkl. dem wahrscheinlichen aufbau oder abbau von vertragsbediensteten bzw. beamten."*

**Spezifikation (Ring 1 + Ring 3 der Strategie, F-62/F-63)**
- *Faktenbasis (Schicht 1, deterministisch, keine KI schreibt):* Tabelle `Norm` (RIS-Kennung, Kurztitel, Typ Bundesgesetz/Landesgesetz/Verordnung, Bundesland, Stand, RIS-URL) und `NormVerweis` (von, nach, Art: verweist/ändert/ermächtigt) — befüllt per Management-Command `ris_import` aus der RIS-OGD-API (JSON), **nutzungsgetrieben**: zu jedem Antrag werden die vom Modell benannten Normen nachgezogen (Titel, Paragraphen, Querverweise 1 Stufe), nächtliches Delta für bekannte Normen. `PersonalAggregat` (Ressort/Bereich, Beamte, Vertragsbedienstete, VBÄ, Jahr, Quelle „Personaljahrbuch des Bundes") per Import-Command aus offenen Daten.
- *Aufbereitung (Schicht 2):* Zu einem Antrag stellt Code den Kontextausschnitt zusammen: Kandidaten-Normen per Schlagwort- und Embedding-Suche über die Normen-Kerntabelle (Kurztitel + Paragraphen-Überschriften), Ebene des Antrags (Bund/Land), Personal-Aggregate der betroffenen Ressorts, das aktuelle Lastbild (FB-H4).
- *Modell (Schicht 3), Auftrag `rechtsfolgen-v1`:* liefert **strukturiertes JSON** (Schema im Repo): `normen[] {ris_id, titel, aenderung: aendern|aufheben|neu, grund}`, `judikatur {text}`, `exekutive {text}`, `personal[] {bereich, beamte_delta_min, beamte_delta_max, vb_delta_min, vb_delta_max, grund}`, `unsicherheit`, `quellen[]`. Jede Norm ohne RIS-Treffer wird als „nicht verifiziert" markiert (Halluzinationsschutz: nur Normen, die in der Kerntabelle existieren oder per RIS nachgezogen werden konnten, bekommen einen Link).
- *Anzeige:* Zone 2, Karten 2 und 3 (FB-F2).
- *Rechtsrahmen:* „politische Bildung, keine Rechtsberatung" (Hinweis in der Kopfkarte).

**Abnahme:** Antrag 2 (Beratung) erhält nach dem Lauf eine Liste von ≥ 1 Norm mit funktionierendem RIS-Link und eine Personal-Grafik mit Spanne; eine erfundene Norm erscheint als „nicht verifiziert" ohne Link.
**Ist:** ❌ (nur Prosa „In Entwicklung", `einbringen.html:46-48`).

#### FB-H4 · Aufwand, Vertretbarkeit neben laufenden Umsetzungen, Dauer bis Inkrafttreten — ❌
**Quelle:** A0-01 — *„(Damit soll auch eingeschätzt werden wie hoch der aufwand für den staatsapparat ist und ob dieser im hinblick auf die aktuell umzusetzenden bereits durch abstimmung getroffenen entscheidungen vertretbar wäre und eine einschätzung getroffen werden wie lange es circa dauern würde bis diese neue regelung die der user vorschlägt in kraft treten könnte ohne dabei den staatsapparat und alle beteiligten zu überlasten)"* · § 5 Abs 11, § 6 Abs 10.

**Spezifikation (Ring 3, F-63)**
- *Lastbild:* Aus dem Umsetzungsregister wird je Ressort/Bereich die **laufende Last** berechnet: Summe der Aufwands-Schätzungen aller Beschlüsse mit Status offen/in Umsetzung (Aufwandsklasse je Beschluss aus dessen Einschätzung: S/M/L/XL mit VBÄ-Monaten). Parameter `last-kapazitaet-<bereich>` (Startwert: Näherung aus Personalaggregat × Anteil für Neuvorhaben, z. B. 5 %) — offen im Register.
- *Lastampel:* grün (neue Last + laufende Last ≤ 70 % Kapazität), gelb (≤ 100 %), rot (> 100 %) — Schwellen als Parameter. Rot bedeutet nicht „abgelehnt", sondern: Einschätzung sagt „Vertretbar erst nach Abschluss von …" und nennt die Warteliste (§ 5 Abs 11).
- *Dauer:* Modell-Auftrag `vollzug-v1` liefert Etappen mit Monatsspannen (Begutachtung, Gesetzesbeschluss, Verordnungen, Aufbau Vollzug) → Zeitstrahl (FB-F2 Karte 4); Kalibrierung später über das Prognose-Register (FB-J7).
- *Anzeige:* Zone 2 Karte 4; zusätzlich im Umsetzungsregister eine Seite „Lastbild" mit Balken je Bereich (öffentlich, F-63).

**Abnahme:** Mit zwei laufenden Umsetzungen der Klasse L im Bereich „Inneres" zeigt ein neuer Antrag der Klasse XL im selben Bereich eine rote Ampel mit Verweis auf die Warteliste; `/umsetzung/last/` zeigt die Balken.
**Ist:** ❌.

#### FB-H5 · Ausschreibungsprüfung — ❌
**Quelle:** A0-01 — *„3. zu prüfen ob eine ausschreibung zur vergabe von aufträgen gemacht werden müsste."*

**Spezifikation (Ring 4, F-64):** Auftrag `vergabe-v1` mit dem Kontext der BVergG-Schwellenwerte (Tabelle `VergabeSchwelle`: Auftragsart, Unter-/Oberschwelle, Verfahrensart, Stand, Quelle) → JSON `{ausschreibung: ja|nein|unklar, auftragsart, geschaetzter_wert_spanne, verfahren, begruendung}`; Anzeige als Plakette (Karte 5). Faktenbasis-Erweiterung: offene Vergabe-Kerndaten (data.gv.at Kerndaten-Bekanntmachungen) als Tabelle `Vergabe` (CPV-Code, Auftraggeber, Auftragnehmer, Wert, Jahr) für FB-H7.
**Ist:** ❌.

#### FB-H6 · Die Simulation als Kontext: neue Anträge durchlaufen sie automatisch — ❌
**Quelle:** A0-01 — *„Ich stelle mir vor, dass wir dazu einen oder mehrere spezielle kontexte aufbauen mit welchem die ki arbeitet, wie eine art simulation die neue anträge durchlaufen lässt insofern kein bereits bestehender antrag vom user gewählt wird…"*

**Spezifikation:** Ein **Simulationslauf** je Antrag = geordnete Kette der Zwecke (Ähnlichkeit → Rechtsfolgen → Vollzug/Last → Vergabe), ausgelöst (a) beim Einbringen: nur Ähnlichkeit (synchron, klein), (b) beim Eintritt in die Beratung: die volle Kette per Warteschlange, (c) bei jeder neuen Fassung (Vorschlag des Expertenrats): neuer Lauf mit Vermerk „Fassung 2" — der alte bleibt archiviert und in Zone 2 als „frühere Einschätzung (Fassung 1)" aufklappbar. Jeder Lauf speichert den **Kontextstand** (Datum/Version der Faktenbasis) und die **Prompt-Version**. Kostenkontrolle: Tageskontingent-Parameter `ki-tageslaeufe` (Start 20); Budget erschöpft → Lauf wartet, die Zone sagt „in der Warteschlange (Platz 3)".
**Ist:** ❌ (nur der manuelle Werkstatt-Lauf).

#### FB-H7 · Vertiefung bis „welche Firmen könnten sich bewerben" — ❌ (Ring 4, spät)
**Quelle:** A0-01 — *„…bis am Ende sogar dargestellt werden kann welche firmen konkret sich für ausschreibungen bewerben könnten weil sie die nötigen kapazitäten und die nötige erfahrung laut den die aktuell bestehenden ausschreibungsrichtlinien, erfüllen."*
**Spezifikation:** Näherung über die Vergabe-Historie (Tabelle `Vergabe`): Firmen, die in den letzten 5 Jahren Aufträge derselben CPV-Gruppe und Größenordnung erhalten haben, als Liste „Mögliche Bieter (Näherung aus der Vergabe-Historie — Kapazitäten sind nicht öffentlich)" mit Anzahl und Summe der Aufträge; **keine** Bonitäts- oder Kapazitätsbehauptung. Firmenbuch-Daten (kostenpflichtig) erst nach Beschluss. Ehrlicher Hinweis in der Karte.
**Ist:** ❌.

#### FB-H8 · Kontext aus geprüft korrekten Angaben — Datenbanken — ❌
**Quelle:** A0-01 — *„Der Kontext dazu sollte aus geprüft korrekten Angaben bestehen. Bspw. eine Datenbank aus allen Gesetzen in Österreich inkl. verlinkungen zueinander … Oder eine datenbank aller in österreich arbeitenden beamten und vertragsbediensteten insofern diese öffentlich verfügbar sind. Eine Datenbank aller Firmen in Österreich und deren Kapazitäten…"*
**Spezifikation:** siehe FB-H3/H4/H5/H7 (Tabellen `Norm`, `NormVerweis`, `PersonalAggregat`, `VergabeSchwelle`, `Vergabe`); Grundsätze: nur amtliche/offene Quellen, deterministische Importe, Stand je Datensatz, **keine personenbezogenen Beamtenlisten** (gibt es nicht und wollen wir nicht, L5), Firmenkapazitäten als ehrliche Näherung. Öffentliche Seite `/zukunftswerkstatt/faktenbasis/`: welche Quellen, wie viele Datensätze, Stand, letzter Import — Rechenschaft über den Kontext.
**Ist:** ❌.

#### FB-H9 · Das Hin und Her: die Plattform passt sich mit der Gesellschaft an — 🟡 (Satzung ✅, Software ❌)
**Quelle:** A0-01 — *„Damit soll eine Art hin und her etabliert werden bei der die Parlamentplattform sich selbst fortwährend den aktuellen gegebenheiten anpasst."* · A0-02 — *„es geht darum, dass wir ein System erschaffen, das mit der Gesellschaft die es verwendet zusammenspielt"*; *„wir können nicht alles jetzt bedenken was da kommt, weshalb es wichtig ist, dass wir diese tatsache … in das konzept … miteinfließen lassen."*
**Spezifikation:** Verankert in Satzung § 2 Abs 7, § 6 Abs 11 (Parameterverfahren, Kennzahlen, Lernschleife) und Strategie Kap. 2 („auf Unwissen gebaut"). Software: Parameterregister mit Tests/Experimenten (FB-J3), Kennzahlen (FB-J7), Prognose-Register (FB-J8), Muster-Berichte an den KoRat (FB-H11). **Ist:** Satzung ✅; Software nur Register-Grundstock.

#### FB-H10 · Unterbeteiligte, stabilisierende Anträge → Vorschlag an den Koordinationsrat → Hervorhebung — ❌
**Quelle:** A0-01 — *„…wenn Gesetzesanträge die wichtig im sinne von stabilisierend und vorteilhaft für alle beteiligten wären, aber diese zu wenig unerstützung erhalten … Dann könnte bspw. dieses gesetz auf die frontseite gestellt werden um die bevölkerung zur beteiligung anzuregen."* · A0-02: Adressat ist der **Koordinationsrat**.
**Spezifikation:** Wöchentlicher Lauf `muster-v1` (Warteschlange) über alle laufenden Anträge mit ihren Einschätzungen und Beteiligungskennzahlen → Liste „Kandidaten für Hervorhebung" mit Begründung (stabilisierend = geringe Last, breite Betroffenheit, niedrige Revisionswahrscheinlichkeit — Kriterien als versioniertes Regelwerk `hervorhebung-kandidaten-v1`, öffentlich) → **Posteingang des Koordinationsrats** (FB-I5): je Kandidat Knopf „Beim Integritätsrat beantragen" (mit Begründung) / „Verwerfen (Grund)"; alles öffentlich einsehbar unter `/zukunftswerkstatt/berichte/`. Der Integritätsrat entscheidet (FB-D4). **Nie** automatisch.
**Ist:** ❌ (Posteingang ist Platzhalter, `koordination.html:45-50`).

#### FB-H11 · Muster erkennen: schnell revidierte Gesetze, Korruptionsgefahr — ❌ (Ring 5)
**Quelle:** A0-01 — *„Oder wenn wir lernen, dass manche Getze nach einführung schnell wieder revidiert werden … Vielleicht entdecken wir muster … Vielleicht können wir damit frühzeitig eine korruptionsgefahr feststellen und dafür eigene regelungen treffen…"* · A0-02: Antwort auf Muster **im Verfahren** (längere Beratung, Zweitlesung, Anhörung), **nie im Stimmgewicht**.
**Spezifikation:** Muster-Berichte (quartalsweise) aus Prognose-Register + Umsetzungsregister + Kennzahlen: Revisionsrate je Lebensbereich, Beteiligung vs. Ergebnisstabilität, Auffälligkeiten bei Beschaffungsanträgen (Häufung gleicher Bieter, Prüfungen der Gruppe 2 mit Rückgaben) → Bericht an den KoRat mit **Verfahrensvorschlägen** (z. B. „Anträge im Lebensbereich X: Beratung 35 statt 21 Tage — als Test nach § 6 Abs 11 lit c") → KoRat beschließt Test → Parameterregister. Öffentlich unter `/zukunftswerkstatt/berichte/`.
**Ist:** ❌.

#### FB-H12 · Kontext-Updates regelmäßig und bei Änderungen sofort — ❌
**Quelle:** A0-01 — *„Wir brauchen regelmäßige kontext updates bzw. wenn sich was ändert an den gegebenheiten sollte das sofort auch im kontext aktualisiert werden."*
**Spezifikation:** Nächtlicher Delta-Import (RIS-Änderungen bekannter Normen, Personal-Aggregate jährlich, Vergabe-Kerndaten monatlich) per Cron auf Render; **Sofort-Update** durch Verwaltungsknopf „Faktenbasis jetzt aktualisieren (Quelle wählen)" und automatisch nach jedem Beschluss der Plattform (der eigene Beschluss ist Teil des Kontexts: Umsetzungsregister → Lastbild). Jede Änderung der Faktenbasis erhöht den **Kontextstand** (laufende Nummer + Datum); Einschätzungen tragen den Stand, mit dem sie gerechnet wurden; die Zone 2 zeigt „Kontextstand 2026-09-02 (aktuell)" oder „… (veraltet — Neuberechnung möglich)".
**Ist:** ❌.

---

### Bereich I · Gremien: Rollen, Expertenrat 1 und 2, Koordinationsrat, Integritätsrat

#### FB-I1 · Rollen auf Zeit: Zuweisung durch Admin, später automatisch; Sonderfunktionen nur während der Berufung — 🟡
**Quelle:** A0-03 — *„Du könntest zuerst noch die fähigkeiten zuweisung erweitern um als admin oder später automatisch den berufenen experten die expertenrolle zuzuteilen die einen eigenen Bereich für sie sichtbar macht…"* · A0-01 — *„Wir brauchen, auf den zeitraum der berufung zum expertenrat oder von anderen räten begrenzte sonderfunktionen bspw. für die abstimmung untereinander, für diese mitglieder."*

**Spezifikation**
- *Rollen (Gremium-Enum):* `expertenrat1`, `expertenrat2`, `koordinationsrat`, `integritaetsrat`, **neu:** `mandatar` (FB-L2), `partner` (FB-M4), `berichtswesenrat` (Umsetzungsregister-Pflege, § 6 Abs 5), `entwicklungsrat` (§ 6 Abs 4, Verwaltung der Plattform — löst langfristig `ist_admin` ab). Jede Rolle: befristet (Parameter `gremien-rollen-dauer-tage`), MV-Bestätigung, Beendigung mit Grund, Audit — wie heute.
- *Zuweisung heute:* Verwaltung `/verwaltung/rollen/` ✅. **Automatisch (später):** (a) aus dem Ergebnis eines Kandidatur-Antrags für eine Funktion (Antragsart „Funktions-Kandidatur", analog FB-L3) → Rolle wird mit dem Ergebnis angelegt (Bestätigung = das Wahlergebnis); (b) aus der **Ausschreibung** nach § 6 Abs 8: Ausschreibung als Antrag des KoRat, Bewerbungen, KoRat-Beschluss, MV-Bestätigung als Abstimmung → Rolle; (c) Expertenrat je Antrag: **Zufallsauswahl aus der öffentlichen Fachliste** (§ 6 Abs 7) — Modell `Fachliste` (Mitglied, Fachgebiete = Lebensbereiche, Interessenbindungen, seit), Command/Knopf „Expertenrat für Antrag X auslosen" mit veröffentlichtem Seed (nachrechenbar), Gruppe 1 und 2 disjunkt.
- *Sonderfunktionen nur während der Berufung:* alle Gremien-Bereiche prüfen `Rolle.hat()` bei **jedem** Aufruf (heute ✅); abgelaufene Rollen sehen den Bereich lesend mit Band „Ihre Rolle endete am …". Interne Abstimmungen (FB-I4) zählen nur Stimmen aktiver Rollen zum Zeitpunkt der Stimmabgabe.
- *„Mein Gremium"* führt in **alle** Bereiche, in denen das Mitglied eine Rolle hat (Auswahl, wenn mehrere), inkl. Integritätsrat (heute ins Leere).

**Ist:** 🟡 Rollen mit Frist/Bestätigung/Audit ✅ (`gremien/models.py:56-99`); Zuweisung nur manuell; Fachliste/Auslosung ❌; Rollen `mandatar`, `partner`, `berichtswesenrat`, `entwicklungsrat` ❌; Integritätsrat ohne Bereich ❌.

#### FB-I2 · Expertenrat 1: eigener Bereich, roher Antrag, Entwurfsfenster, gemeinsam entwerfen, abstimmen, einreichen — ✅ (Erstfassung) / 🟡 (Details)
**Quelle:** A0-03 — *„…die einen eigenen Bereich für sie sichtbar macht worin der rohe unterstützte antrag steht sowie ein entwurffenster wobei sich hier der expertenrat abstimmt und miteinander über den entwurf entwerfen kann und wenn er fertig ist kann er eingericht werden wodurch der entwurf den unterstützern des antrages vorgelegt wird…"*

**Spezifikation (Ergänzungen zur Erstfassung)**
- *Layout:* Entwurfsfenster als **Drei-Spalten-Arbeitsplatz** (Desktop): links der rohe Antrag (fest, mit Absatznummern), Mitte der Entwurf (Editor mit Fassungen; **Diff zur vorigen Fassung** ein/aus), rechts die Werkzeuge: Zone-2-Einschätzung des Antrags (FB-F2, als Arbeitsunterlage — *„die Simulationsergebnisse sind seine Arbeitsunterlage"*), Wünsche der Unterstützer aus der Vorrunde (FB-G6, mit Textstellen-Bezug, abhakbar „berücksichtigt"), interne Beratung, Einreich-Abstimmung. Handy: Reiter.
- *Gemeinsames Entwerfen:* Fassungen bleiben append-only (kein Echtzeit-Editor — bewusst: jede Fassung ist ein dokumentierter Schritt). Zugabe: „Absatz-Kommentar" (Beitrag, der an einen Absatz der Fassung gebunden ist, am Rand angezeigt).
- *Interessenbindungen (§ 6 Abs 7):* beim Einreichen Pflichtfeld je Rolleninhaber „Interessenbindungen zu diesem Antrag: keine / …" — steht öffentlich beim Vorschlag.
- *Fristen:* Erstvorschlag binnen **21 Tagen** ab Beratungsbeginn (Parameter `expertenrat-erstvorschlag-tage`, FB-J1) — Fristanzeige im Fenster („noch 12 Tage für den Erstvorschlag"); Ablauf ohne Einreichung: Antrag geht ohne Vorschlag weiter (heutige Regel „Untätigkeit hemmt nie" ✅).
- *Einreich-Abstimmung:* wie heute (Ja ≥ ⌈aktive/2⌉ ∧ Ja > Nein) — als Parameter `gremien-einreich-quorum`.
**Ist:** ✅ Kern (`gremien/views.py:160-276`, `fenster.html`); ❌ Drei-Spalten-Layout, Diff, Einschätzung als Arbeitsunterlage, Interessenbindungen, Erstvorschlags-Frist als eigener Parameter, Absatz-Kommentare.

#### FB-I3 · Expertenrat 2: eigene Oberfläche, Korruptionsprüfung, abstimmen, validieren / zurückgeben / Austausch — ✅ (Erstfassung) / 🟡 (Quorum)
**Quelle:** A0-03 — *„auch der expertenrat 2 braucht eine eigene oberfläche um die prüfung des vorschlages durch expertenrat 1 zu überprüfen, nicht wenn es um gesetze geht aber wenn es um direkte aufgaben geht wie bspw. die Beschaffung von Resourcen … Dann sollte schon ein expertenrat 2 deren vorschlag auf korruption überprüfen und sich dazu abstimmen und den vorschlag dann validieren oder mit begründung zurück geben und sogar um austausch von expertenrat 1 bitten können"* · A0-01: *„Der Expertenrat teilt sich ja in 2 gruppen auf wobei die zweite als redundanz und prüfung auf korruption des ersten dient."*

**Spezifikation (Ergänzungen):** Die Prüfung ist eine **interne Abstimmung der Gruppe 2** (FB-I4): jedes Mitglied gibt Votum (validieren / zurückgeben / Austausch) + Begründung; Ergebnis nach Mehrheit der aktiven Rollen (Parameter), Frist `gremien-pruefung-tage` (Start 7); alle Voten und Begründungen öffentlich (§ 6 Abs 9). Prüf-Checkliste im Bereich (Interessenkonflikte der Gruppe 1 laut Offenlegung, Bieterkreis, Schwellenwerte, Vergleichsangebote) als abhakbare Punkte, die in die Begründung übernommen werden. Bei Gesetzesvorschlägen ohne Vollzugsbezug: kein Gruppe-2-Schritt (heute ✅ per Häkchen; Ausarbeitung: das Häkchen setzt zusätzlich die Zukunftswerkstatt automatisch, wenn FB-H5 „Ausschreibung: ja" liefert).
**Ist:** ✅ Bereich mit drei Handlungen (`pruefung.html`, `gremien/views.py:430-462`); ❌ Einzelperson entscheidet sofort (kein Quorum, Inventar Auffälligkeit 17), keine Checkliste, keine Frist.

#### FB-I4 · Interne Abstimmungen in allen Räten (Sonderfunktion auf Zeit) — 🟡
**Quelle:** A0-01 (Sonderfunktionen „für die abstimmung untereinander"), A0-03 (ER2 „sich dazu abstimmen", KoRat „sich dort darüber abstimmen").
**Spezifikation:** Generisches Modell `GremienBeschluss` (gremium, gegenstand: Text + optionaler Bezug auf Antrag/Entwurf/Parameter/Prüfung, optionen: Liste, frist, quorum-Regel, status) und `GremienStimme` (beschluss, mitglied, option, begründung, zeit; nur aktive Rollen); Auswertung nach § 6 Abs 2 lit e bzw. Abs 8 (Hälfte anwesend = Hälfte hat abgestimmt, einfache Mehrheit); alles öffentlich mit Namen (§ 6 Abs 9), außer Passagen mit Datenschutz-/Sicherheitsbezug (Kennzeichnung + Integritätsrat-Prüfung). Oberfläche: in jedem Gremien-Bereich ein Block „Offene Beschlüsse" mit Stimmabgabe inline; Sitzungsprotokoll = die Liste der Beschlüsse und Beiträge, exportierbar. Die heutige Einreich-Abstimmung des ER1 wird auf dieses Modell umgestellt.
**Ist:** 🟡 nur `EinreichStimme` für ER1; ER2 und KoRat ohne Abstimmung.

#### FB-I5 · Der Koordinationsrat: eigene Oberfläche mit Aufgaben, Posteingang der Zukunftswerkstatt, Abstimmungen, Parameter — 🟡
**Quelle:** A0-03 — *„Auch der Koordinationsrat braucht eine eigene oberfläche in der ParlamentPlattform auf welcher er seinen Aufgaben nachgehen kann, diese vorschläge oder hinweise von der staatssimulation erhält und sich dort darüber abstimmen kann was wie umgesetzt werden soll."* · *„Vielleicht sollten wir gleich anfangen diese parameter zu sammeln und eine infrastruktur für den koordinationsrat dafür zur verfügung zu stellen."*

**Spezifikation — Aufbau von `/gremien/koordination/` (App-Look, vier Karten-Bereiche in einem 2×2-Raster wie das Parlament — Ausarbeitung)**
1. **Aufgaben:** offene Austauschanträge (heute ✅), Ausschreibungen (FB-I1), Überlastungsmeldungen (§ 6 Abs 10: binnen 30 Tagen Vorschlag an die MV — mit Fristzähler), Hervorhebungsanträge an den Integritätsrat (FB-D4), Vollzugsberichte zur Kenntnis.
2. **Posteingang der Zukunftswerkstatt:** Kandidaten für Hervorhebung (FB-H10), Muster-Berichte (FB-H11), Parametervorschläge (FB-J3), Lastwarnungen (FB-H4) — je Eintrag: Vorschlag, Begründung, Lauf-Nr., Knöpfe „Beschluss anlegen" (→ FB-I4) / „Verwerfen (Grund)" / „Zur Kenntnis". Nichts geschieht ohne Beschluss.
3. **Beschlüsse:** offene interne Abstimmungen (FB-I4) mit Stimmabgabe, danach Umsetzungsvermerk („was wie umgesetzt wird": Freitext + optionale Zuweisung an ein Ratsmitglied + Frist); Liste der entschiedenen.
4. **Parameter & Tests:** Übersicht des Parameterregisters mit laufenden Tests (FB-J3), Knopf „Test anordnen" (Parameter, Testwert, Hypothese, Messgröße, Probezeitraum, Rückweg) → interner Beschluss → Eintrag im Register (Status „Test bis …"); „Einführung freigeben" nach Test; jährlicher Parameterbericht als generierte Seite (§ 6 Abs 11 lit c).
- *Internationale Kooperation (§ 12 Abs 5, A0-03):* im Bereich ein Reiter „Partner" mit Export des Parameter-Schemas (FB-M5), Liste der Partnerorganisationen (FB-M4) und Austausch-Protokollen.
**Ist:** 🟡 Austauschanträge + Rollenübersicht + Posteingang-Platzhalter (`koordination.html`); alles andere ❌.

#### FB-I6 · Der Integritätsrat — ❌ (siehe FB-D4)
Bereich `/gremien/integritaet/` mit Hervorhebung, Zurückweisung (§ 5 Abs 2), Betroffenheit (§ 5 Abs 6), Aussetzung (§ 6 Abs 3 lit d), jährlicher Prüfbericht automatisierter Regeln (§ 2 Abs 6: Liste aller versionierten Regeln — WeicherFilter, Reihung Abstimmungs-Chat, Klassifikation, Ähnlichkeit — mit Datum, Version, Begründung; Knopf „Geprüft am … (Vermerk)"). Alles über FB-I4-Beschlüsse.

---

### Bereich J · Fristen, Parameter, Kennzahlen, Lernen

#### FB-J1 · Die Fristen: 2 Monate · 3 Wochen · 2 Wochen · 2 Wochen · 4 Wochen — 🟡
**Quelle:** A0-05 — *„Wir sollten die Fristen für Unterstützungsanträge auf 2 Monate setzen um die unterstützungsschwelle für die hochstufung des Antrages zum für die Endabstimmung vorgesehenen Antrag. Der Expertenrat wird berufen und hat 3 Wochen zeit um einen ersten Vorschlag auszuarbeiten. Um diesen Vorschlag anzunehmen oder nochmals zur Überarbeitung kommentiert zurück zu geben haben die ursprünglichen Unterstützer 2 Wochen woraufhin der Expertenrat wieder 2 Wochen bekommt um den Vorschlag entsprechend den Wünschen der User zu ändern. Für die Endabstimmung nach dem Durchwinken des Vorschlages des Expertenrates hat die gesamte Bevölkerung dann 4 Wochen Zeit."*

**Spezifikation — alle fünf Fristen als Parameter im Register, mit Schema-Kennung (FB-M5)**

| Schlüssel | Wert | Wirkung | Schema-Kennung |
|---|---|---|---|
| `verfahren-unterstuetzung-tage` | 60 | Unterstützungsfrist (Verfahrensordnung, eingefroren je Antrag) | `support.window_days` |
| `expertenrat-erstvorschlag-tage` | 21 | Frist des Expertenrats für den Erstvorschlag ab Beratungsbeginn; **zugleich** die Mindest-Beratungsdauer (§ 5 Abs 3 lit c ≥ 21) | `council.first_draft_days` |
| `gremien-review-tage` | 14 | Frist der Unterstützer (Abstimmungs-Chat) | `support.review_days` |
| `gremien-ueberarbeitung-tage` | 14 | Überarbeitung des Expertenrats je Runde | `council.rework_days` |
| `verfahren-abstimmung-tage` | 28 | Endabstimmung | `vote.window_days` |
| `gremien-hoechstrunden` | 3 | Runden der Entwurfsschleife | `council.max_rounds` |

- *Ablauf im Zeitbild:* Tag 0 Einbringen → bis Tag 60 Schwelle → Beratung beginnt (Tag B) → Expertenrat bis B+21 Erstvorschlag → Unterstützer bis +14 → (Rückgabe: Expertenrat +14 → Unterstützer +14 → …, max. 3 Runden) → Endabstimmung 28 Tage → Beschluss. Ohne Expertenrat-Vorschlag: Beratung endet B+21, Endabstimmung beginnt.
- *Technik:* Neue Verfahrensordnungs-Versionen werden **aus dem Register erzeugt** (Verwaltungsknopf „Verfahrensordnung v3 aus den aktuellen Parametern beschließen" → Snapshot; laufende Verfahren unberührt, § 5 Abs 5). Das Startseiten-Flussdiagramm liest die Zahlen aus dem Register (nicht hart).
- *Jede Frist sichtbar:* in Kacheln („noch 26 Tage"), im Antragskopf, im Entwurfsfenster, im Abstimmungs-Chat-Kopf — immer als Resttage **und** Datum.

**Ist:** 🟡 60/21/28 in der VO v2 (`demo_seed.py:36-53`, Migration 0008) ✅ als Wirkung; 14/14/3 im Register ✅; **`expertenrat-erstvorschlag-tage` fehlt** (die Beratungsfrist vertritt ihn); 60/28 **nicht im Register**; Diagramm hart (`index.html:118-126`); `grundordnung-v1.yaml` widerspricht (14/21/7) und wird nicht gelesen (Inventar Auffälligkeit 3).

#### FB-J2 · Alle Stellgrößen sind Parameter; Basisparameter für 2044 gemeinsam erarbeiten — 🟡
**Quelle:** A0-05 — *„Das sind alles Parameter die es zu untersuchen und halbautomatisch daraus zu lernen gilt…"* · A0-08 — *„…mit gemeinsamen erarbeiten der Basisparameter für den start 2044…"*
**Spezifikation:** Alle im Inventar als „harte Konstanten" gelisteten Werte (Auffälligkeit 4) wandern ins Register, gruppiert (Verfahren · Gremien · WeicherFilter · Fächer · KI · Schutz · Kacheln), je mit Schema-Kennung, Begründung, Historie, Status (gültig / im Test bis … / vorgeschlagen). Register-Seite `/parameter/` im App-Look: Gruppen als aufklappbare Karten, je Parameter Wert, Einheit, Herkunft, „Historie (3)", Test-Band. `/parameter.json` bekommt `schema_version`, `system_id` („ddoe-at"), `exported_at`.
**Ist:** 🟡 5 Einträge (`parameter/models.py:46-87`); Historie nur im Audit-Log; keine Gruppen, kein Schema, kein Status.

#### FB-J3 · Das Parameterverfahren: Test → Simulation → Vorschlag → Freigabe → Einführung — ❌ (Software) / ✅ (Satzung)
**Quelle:** A0-06 — *„Zuerst werden neue Parameter nach gutdüngen des Koordinationsrates getestet, die Testergebnisse fließen laufend in die Staatssimulation ein worauf hin diese beginnt Vorschläge zu liefern und nach Freigabe des Koordinationsrates einführt um weiter zu lernen."* · Satzung § 6 Abs 11 lit c ✅.
**Spezifikation:** Modell `ParameterTest` (parameter, testwert, hypothese, messgroesse (Kennzahl-Schlüssel), beginn, ende, rueckweg, beschluss (FB-I4), status: geplant/läuft/ausgewertet/eingeführt/verworfen, auswertung: Text + Kennzahlenwerte vorher/nachher). Ein laufender Test setzt den Wert **für neue Verfahren** (Snapshot) und zeigt überall ein Band „Testwert bis 30.11. — Hypothese: …". Auswertung: automatisch generierte Gegenüberstellung der Messgröße (vorher/während) als Karte im KoRat-Bereich und öffentlich unter `/parameter/<schluessel>/`; die Zukunftswerkstatt (Lauf `parameter-vorschlag-v1`) formuliert daraus einen **Vorschlag** (einführen / verwerfen / verlängern) → KoRat-Beschluss → „Einführung" mit Begründung ins Register (Audit). Jährlicher Parameterbericht = generierte Seite aller Änderungen des Jahres → MV-Abstimmung (Antrag).
**Ist:** ❌.

#### FB-J4 · Leichte Weichenstellungen des KoRat — nie im Stimmgewicht — ✅ (Grundsatz)
**Quelle:** A0-03 — *„(all diese regelungen kann der koordinationsrat nutzen um leichte weichenstellungen vorzunehmen ohne dabei Stimmdifferenzierung zuzulassen.)"* → Satzung § 6 Abs 11 lit c letzter Satz ✅; Software: die Parameter-Verwaltung erlaubt keine Änderung von Stimmgewichten (es gibt keinen solchen Parameter — Grundsatz im Code-Kommentar und Test „kein Parameter darf ein Stimmgewicht sein").

#### FB-J5 · Parameter und Lernerfahrungen mit Partnerparteien austauschen — 🟡
**Quelle:** A0-05 — *„…das macht der Koordinationsrat der eng mit den anderen Parteien weltweit zusammenarbeitet … um die Parameter und Lernerfahrungen auszutauschen … (Nicht so, dass alle systeme aller länder gleiche schwellen und parameter anwenden aber das alle systeme die selbe geniale Art haben um zu lernen und sich mit der bevölkerung co zu regulieren.)"* · Satzung § 12 Abs 5 ✅.
**Spezifikation:** siehe FB-M5 (Schema-Export/Import) und FB-I5 (Reiter Partner). **Ist:** Satzung ✅, Software ❌ (nur `/parameter.json` ohne Schema).

#### FB-J6 · Demos-Zuschnitt lernbar (Haupt-/Nebenwohnsitz) — 🟡
**Quelle:** A0-02 — *„…wobei auch nur die menschen mitstimmen - bestimmen die in dieser region den hauptwohnsitz oder vielleicht auch nebenwohnsitz (das wäre eventuell auch etwas das die parlamentplattform über die zeit lernen könnte…)"*
**Spezifikation:** Mitglied erhält optional `nebenwohnsitz` (Gemeinde, aus dem Verzeichnis); Parameter `region-nebenwohnsitz-stimmt-mit` (0/1, Start 0) je Ebene; Stimmberechtigung regional prüft Haupt- und ggf. Nebenwohnsitz; Kennzahl „Revisionsrate regionaler Beschlüsse" als Messgröße für einen späteren Test (FB-J3). Profilseite (FB-K5) für die Eingabe.
**Ist:** 🟡 Hauptwohnsitz ✅ (`Mitglied.wohnsitz`), Nebenwohnsitz ❌.

#### FB-J7 · Kennzahlen: Beteiligung nach Erstaufruf, Verweildauer, Themen-Attraktivität — aggregiert, ohne Profil — ❌
**Quelle:** A0-06 — *„Dabei werden Kennzahlen aus Parametern wie der Beteiliungsquote nach dem ersten Aufruf einer Antragsseite innerhalb welcher Zeit oder wie lange dass jemand auf einer Antragsseite verweilte, welche themen welche attraktivität haben herangezogen werden um Erkenntnisse über den Erfolg der Maßnahmen zu erhalten und damit kaskadierend die Lernschleifen zu verbessern bis sie bei einem optimum angelangt ist und sie dort halten zu können."* · Satzung § 6 Abs 11 lit d (aggregiert, ohne Profilbildung).

**Spezifikation**
- *Erhebung ohne Profil:* Ereignisse werden **nur als Tagessummen je Antrag/Lebensbereich** gespeichert (wie die heutige Besuchszählung): `antrag_aufrufe`, `antrag_verweildauer_summe` und `_anzahl` (Verweildauer per `visibilitychange`-Beacon in Sekunden-Klassen 0–10/10–60/60–300/300+, ohne Mitgliedsbezug), `beteiligung_binnen` (Unterstützungen/Stimmen binnen 24 h / 7 Tagen nach Erstveröffentlichung — als Zähler am Antrag, nicht je Person), `lebensbereich_aufrufe`. Kein Cookie, keine Kennung über den Tag hinaus (heutige Einweg-Tageskennung bleibt für „Besucher:innen heute").
- *Kennzahlen (versioniert, `plattform_core/kennzahlen.py`):* Beteiligungsquote binnen 24 h / 7 T (Beteiligte ÷ Stimmberechtigte), mittlere Verweildauer-Klasse je Antragsseite, Attraktivität je Lebensbereich (Aufrufe + Beteiligung je laufendem Antrag), Revisionsrate (FB-H11), Prognosefehler (FB-J8). Erhebungsregeln öffentlich unter `/zukunftswerkstatt/kennzahlen/` mit Grafiken (Zeitreihen) — die Seite ist zugleich der Datensatz für die Lernschleife.
- *Datenschutz:* Anhang-Prüfpunkt 8 der Satzung (DSFA) vor Produktivsetzung; Verweildauer-Beacon nur für Mitglieder, die in den Einstellungen „Kennzahlen mit meiner anonymen Nutzung verbessern" nicht abgewählt haben (Opt-out, Voreinstellung an — ❓ D-J7: Opt-in statt Opt-out?).
**Ist:** ❌ (nur Aufrufe/Besucher, `uebersicht/`).

#### FB-J8 · Prognose-Register und Lernschleife — ❌
**Quelle:** Strategie Kap. 6; Satzung § 6 Abs 11 lit e; A0-06 (kaskadierende Lernschleifen).
**Spezifikation:** Nach Vollzug (Umsetzungsregister „umgesetzt") wird je Einschätzung ein Eintrag `Prognose` erzeugt (Einschätzung: Dauer, Personal, Ausschreibung ja/nein; Wirklichkeit: aus dem Vollzugsbericht — Felder im Vollzugseintrag ergänzt: tatsächliche Dauer, tatsächlicher Personal-Delta, Ausschreibung durchgeführt); Prognosefehler berechnet; öffentlich `/zukunftswerkstatt/prognosen/` mit Trefferquote je Zweck und Modell; Muster-Lauf nutzt es (FB-H11).
**Ist:** ❌.

---

### Bereich K · Mitgliedschaft, Einstieg, Anstoß, Profil

#### FB-K1 · Mitgliedschaftsseite: Rechte plakativ, dann im Detail; Zukunftswerkstatt; Grafiken; Flowchart — ✅ / 🟡
**Quelle:** A0-04 — *„Um Nichtmitgliedern die MItgliedschaft korrekt anzubieten sollten die Funktionen und Rechte die ein Mitglied hat plackativ dargestellt werden und danach im detail erklärt werden. dort sollte auch die funktion der StaatsSimulation erklärt werden. alles mit grafiken die zur verständlichkeit beitragen, vielleicht einem flowchart zum ablauf der antragseinbringung bis zur gesetzesverabschiedung."*
**Spezifikation:** Bleibt wie umgesetzt, plus: (1) das **Flussdiagramm** von `/` erscheint **auch hier** (gemeinsames Include, mit Registerwerten), (2) die sechs Rechte-Karten erhalten je eine kleine Animation beim Erscheinen (Ikone zeichnet sich, 400 ms) und je einen Link „Wie das aussieht ›" auf die Live-Stelle (Parlament-Feld, Antragsseite), (3) Zukunftswerkstatt-Karte zeigt eine Miniatur der Zone-2-Karten (Skelett-Vorschau), (4) Wortlaut „StaatsSimulation" bleibt nur als „Rechenkern" erwähnt.
**Ist:** ✅ Rechte plakativ + Detail + Zukunftswerkstatt-Karte + Ikonen (`mitgliedschaft.html`); Flowchart nur als CSS-Stationen 🟡 (das SVG liegt auf `/`).

#### FB-K2 · Mitglied werden nur über die Plattform; Alpha-Phase — ✅
**Quelle:** A0-08 — *„mitglied werden geht ab jetzt nur noch über die parlamentsplattform. das ist ein funktionaler prototyp und kann insofern als vollwertig betrachtet werden weil die stätige verbesserung teil des projektes schon jetzt sein kann."* · *„…nicht mehr prototyp sondern alpha phase genannt werden."*
**Ist:** ✅ ddoe.at verlinkt `/mitgliedschaft/`; „Alpha" auf Plattform und Website. Rest: README sagt „Prototyp" (`README.md` Statuszeile), Demo-Antrag „Namenskonvention des Prototyps", `/uebersicht/` „Der Prototyp enthält Demo-Daten" — **drei Stellen ändern**.

#### FB-K3 · Das Anstoß-Widget auf jeder Seite; Speicherung zur späteren Auswertung — ✅ / ⚠️ (Speicherort)
**Quelle:** A0-08 — *„…über ein widges, dass den user auf allen seiten die auf der parlamentplattform besucht werden begleitet und dass er jederzeit für feedback und wünsche nützen kann. Dabei wird seine nachricht gespeichert um sie später mit deiner hilfe auszuwerten. nutze dafür einenen online webserver wo wir sowas speichern können. vielleicht den eigenen und ich gebe dir einen ftp zugriff…"*
**Spezifikation:** Umgesetzt mit Speicherung **in der eigenen Datenbank** der Plattform statt FTP (⚠️ Abweichung mit Grund: keine Fremdzugänge, Backup mit der Datenbank, DSGVO-Hoheit; Export CSV/JSON für die Auswertung mit Claude — ❓ D-K3 bestätigen). Ergänzungen: (1) Position: im Parlament liegt der Knopf **in der App-Leiste** (Sprechblasen-Symbol rechts neben „＋"), nicht schwebend über dem Raster (er verdeckt heute „Meine Region"); auf allen anderen Seiten bleibt die schwebende Pille rechts unten, aber 12 px kleiner. (2) Verwaltung: Eingabefeld „Vermerk" (heute fehlt es), Antwortmöglichkeit per Mail an Mitglieder („Rückfrage senden"), Verknüpfung „→ Fahrtenbuch-Nr." (Freitext). (3) Export enthält die Seite als Klartext-Titel, nicht nur den Pfad.
**Ist (0.33.0):** ✅ Widget, DB, Verwaltung, Export (`anstoss/`); **Position erledigt**: im Parlament in der App-Leiste mit Popover darunter, sonst schwebende Pille 12 px kleiner (`_widget.html`, `base.html:344-350`, `_leiste.html:23`) — „Meine Region" wird nicht mehr verdeckt. Rückmeldung per `HX-Trigger` statt Inline-Skript (`anstoss/views.py:63-69`). ❌ offen: Vermerk-Feld in der Verwaltung, Klartext-Titel im Export (Inventar 12).

#### FB-K4 · Einführung nach der Bestätigung — ✅ (Korrektur)
**Ist:** ✅ drei Schritte (`einfuehrung.html`); ❌ Schritt 1 verweist auf die abgeschaffte Seite `/kategorien/` („oben rechts") → Text auf die Suche im Favoriten-Feld umstellen; Schritt 2/3 nennen „mindestens sieben Tage" / „7 Tage Abstimmung" → Registerwerte (28) einsetzen.

#### FB-K5 · Profilseite für Mitglieder — ❌ (neu, nötig für Region, Nebenwohnsitz, Einstellungen)
**Ausarbeitung:** `/profil/`: Anzeigename (Pseudonym), Wohnsitz-Gemeinde (Datalist), Nebenwohnsitz (FB-J6), Sprache, E-Mail-Überblick (F-30: Digest an/aus, Takt), Kennzahlen-Opt-out (FB-J7), Sitzungen abmelden, Datenexport (Art 15/20 DSGVO: eigene Daten als JSON), Konto löschen (Austritt, § 4). Änderungen des Wohnsitzes werden auditiert (ohne Wert). **Ist:** ❌ (Parlament verweist auf ein nicht existierendes „Profil", Inventar 2.1).

---

### Bereich L · Die Mandatar-Steuerung

#### FB-L1 · Mandatare-Seite mit Foto, Aufgaben, Entscheidungsprozessen; Pflicht des Mandatars — ✅ (M1)
**Quelle:** A0-08 — *„Ich stelle mir das als Seite vor wo die Mandatare mit Foto sieht und ihre derzeitigen Aufgaben und Entscheidungsprozesse. Dazu verpflichtet sich der Mandatar die nötigen Informationen auf die Plattform zu stellen."*
**Ist:** ✅ `/mandatare/` (Foto in DB, Aufgaben mit Frist, verknüpfte Abstimmungen; § 7 Abs 3 lit b, Abs 9). Politur: Karten im App-Look (Foto 96 px rund, Ebene-Chip, nächste Frist als Zähler), Phase als Name statt Slug (`liste.html:53`), Leerzustand kürzer.

#### FB-L2 · Die Mandatar-Rolle: Instant-Reports mit Fristen, betreute Abstimmungen — ❌ (M2)
**Quelle:** A0-08 — *„Das bringt uns wieder zu einer neuen Roll die Funktionen für den Mandatar freischaltet wie bspw. instant Reports zu aktuellen Aufgaben oder Themen inkl. fristen und der dadurch entstehenden und von ihm betreuten Abstimmungen im Parlament."*

**Spezifikation**
- *Rolle `mandatar`* (FB-I1) — wird beim Anlegen eines Mandats automatisch vergeben und endet mit dem Mandat.
- *Bereich `/mandatare/mein/`* (nur Rolle): links die eigene Karte (Foto hochladen, Vorstellung), Mitte **„Instant-Report"**: ein Formular mit drei Feldern — Thema (≤ 120), Was steht an (≤ 1.000, Markdown light), Frist (Datum + Uhrzeit) — und einem Schalter **„Daraus eine Abstimmung im Parlament erzeugen"**: dann entsteht sofort ein Sachantrag (Antragsart `mandatsfrage`, Ausarbeitung: eigene Art, damit die Verfahrensordnung kürzere Fristen erlauben kann — Parameter `mandatsfrage-abstimmung-tage`, Start 7, Mindestbeteiligung wie Sachantrag), verknüpft mit der Aufgabe (`Aufgabe.antrag`), **ohne** Unterstützungsphase (die Mandatsfrage ist bereits durch das Mandat legitimiert — ❓ D-L2a) und mit Fristende ≤ Fristende der Aufgabe. Der Report erscheint sofort öffentlich auf der Mandatar-Karte und — bei Abstimmung — als Kachel in Feld D (❓ D-L2b: automatische Hervorhebung von Mandatsfragen? Empfehlung: nein, sie erscheinen im WeicherFilter und in der Region; die Hervorhebung bleibt beim Integritätsrat) und in Feld E (regionale Mandate).
- *Rechenschaft:* Nach der Abstimmung trägt der Mandatar das tatsächliche Stimmverhalten im Vertretungskörper und die Begründung ein (**Rechenschaftsregister** § 7 Abs 5: Beschluss der Plattform · Stimme im Parlament · Begründung, binnen 7 Tagen, Fristzähler, öffentlich auf `/mandatare/<id>/rechenschaft/` und gesamt `/rechenschaft/` — der Mock von ddoe.at wird echt).
- *Berichte:* monatlicher Bericht + Sammelbericht nach Sitzungstag (§ 7 Abs 3 lit b) als Formular mit Fristzähler; Versäumnisse werden öffentlich als „ausständig seit …" markiert (ohne Sanktion — die Vertragsstrafe regelt die Mandatsvereinbarung, nicht die Plattform).
**Ist:** ❌ (Pflege nur durch Verwaltung; `Mandat.kandidatur` nie gesetzt).

#### FB-L3 · Mandats-Kandidaturen als Anträge, Zustimmungswahl, meiste Zustimmung gewinnt — ✅ (M3)
**Quelle:** A0-08 — *„Abstimmungen zu Mandataren die sich zur Wahl stellen. Jedes Mitglied kann das machen indem es den entsprechenden Antrag stellt bzw. wenn bereits ein Antrag für dieses Mandat besteht sich daran beteiligen kann … Das Mitglied mit der meisten Zustimmung gewinnt die Wahl."*
**Ist:** ✅ (`Antragsart.MANDAT`, `Bewerbung`, `personenwahl_auszaehlen`). Delta: Beim Anlegen eines Mandats in der Verwaltung den Gewinner-Antrag verknüpfen (`Mandat.kandidatur`) und die Reihung als **Wahlvorschlag** exportieren (PDF/Markdown für die Wahlbehörde — Formvorschriften laut Anhang-Prüfpunkt 10 klären).

#### FB-L4 · Ab wann? — ✅ entschieden: von Anfang an (§ 7 Abs 1)
**Quelle:** A0-08 — *„Ich weiß aber nicht ab wann das geht … Dieser Vorgang gehört in die Satzung."* **Ist:** ✅ Satzung 2.5 § 7 Abs 1 („jederzeit, auch bevor die Partei ein Mandat der betreffenden Ebene innehat").

---

### Bereich M · Internationale Partner

#### FB-M1 · Die Partner-Seite: Strategie, Fahrplan, Kontakt — ✅ (Erststufe)
**Quelle:** A0-07 — *„Wir brauchen eine Unterseite für Menschen aus anderen Ländern die dort die selbe Partei gründen möchten … Auf dieser Seite soll eine gut verständliche Darstellung der Gesamtstrategie dieser Parte geschrieben stehen und veranschaulicht werden. Ein Fahrplan wie eine Zusammenarbeit konkret aussehen wird und ein Button zur Kontaktaufnahme."*
**Ist:** ✅ `/partner/` (DE/EN). Delta: **Veranschaulichung** fehlt — ein Schaubild „System und Parameter" (zwei Länder-Kästen mit eigenem System, dazwischen das gemeinsame Parameter-Schema als Brücke, animiert: Kennzahlen wandern als Punkte über die Brücke) als Inline-SVG; Kontakt-Knopf als Formular (FB-M3) statt `mailto:`.

#### FB-M2 · Verlinkung: Fußzeile der Plattform ✅ · Teaser auf ddoe.at ❌
**Quelle:** A0-07 — *„…aufrufbar unter den Links in der Fußzeile. Zusätzlich wird diese Funktionalität auf der ddoe.at homepage geteasert so, dass interessenten aus anderen ländern wenn sie darauf klicken zu der leicht versteckten Seite für internationale Partner gelangen…"*
**Spezifikation ddoe.at:** In der Sektion „International" ein zweiter Knopf **„Start a sister party — the partner page →"** auf `https://parlament.ddoe.at/partner/` (EN-Text, da Zielgruppe Ausland) und auf `/english/` unter „An invitation" derselbe Link vor dem Mail-Link. **Ist:** ❌ (Live-Prüfung 2.9.: nur `/english/` verlinkt).

#### FB-M3 · Konto anlegen, von uns bestätigt — ❌
**Quelle:** A0-07 — *„…wo sie sich einen account anlegen können der dann ebenfalls von uns bestätigt werden muss…"*
**Spezifikation:** Auf `/partner/` ein Formular **„Partner-Konto beantragen"** (Organisation, Land, Website, Name, E-Mail, Sprache, „Was baut ihr?" ≤ 1.000 Zeichen, Botschutz wie Registrierung) → Modell `PartnerAntrag` (Status: beantragt / bestätigt / abgelehnt, Vermerk) → Double-Opt-in-Mail → Verwaltung/KoRat-Bereich „Partner-Anträge" mit Bestätigen (Grund) / Ablehnen (Grund, Audit) → bei Bestätigung: Konto (`Mitglied` mit `status = partner`, **keine** Mitgliedsrechte: kein Stimmrecht, kein Antragsrecht, kein Chat-Schreiben — ❓ D-M3: Chat lesen ja; schreiben nur im Partner-Bereich) + Rolle `partner` (FB-I1) + Willkommensmail (EN/DE).
**Ist:** ❌.

#### FB-M4 · Rolle „Internationaler Partner" mit eigener Oberfläche — ❌
**Quelle:** A0-07 — *„…eine eigene Rolle als internationaler Partner zugewiesen bekommt mit der widerum eigene Funktionalitäten auf der ParlamentPlattform und eine eigene Oberfläche freigeschaltet wird. Wie die genau aussieht besprechen wir dann später."*
**Spezifikation (Vorschlag für „später", zur Besprechung):** `/partner/bereich/` (EN-first): (1) **Software-Start**: Anleitung + Knopf „Instanz-Vorlage herunterladen" (Docker-Compose, `.env`-Vorlage, Erstbestand der Parameter als JSON, Kategorienbaum als YAML — die Lebensbereiche sind länderneutral gedacht), Checkliste „Einrichtung", Link zum Repo; (2) **Parameter-Austausch**: eigenes Schema-Profil hochladen (`parameter.json` ihrer Instanz), Gegenüberstellung mit unserem (Tabelle je Schema-Kennung: ihr Wert / unser Wert / Kennzahl); (3) **Lernfortschritt**: geteilte Kennzahlen (aggregiert), Muster-Berichte beider Seiten, Kommentare (Partner-Chat, getrennt vom Mitglieder-Chat); (4) **Kontakt & Termine** (Netzwerk-Calls, siehe `ddoe_outreach`). ❓ D-M4: Umfang der Erststufe.
**Ist:** ❌.

#### FB-M5 · Die Schnittstelle: sprachneutrales Parameter-Schema, Export/Import — ❌
**Quelle:** A0-07 — *„Sie soll in weiterer Folge als Schnittstelle zwischen den verschiedenen Ländern dienen wobei zuerst die Software für diese Parteigründer von uns zur Verfügung gestellt und eingerichtet wird und später der Lernfortschritt und parameter erarbeitet und ausgetauscht werden können."* · Satzung § 12 Abs 5.
**Spezifikation:** Jeder Parameter trägt `schema_key` (englisch, stabil, z. B. `support.window_days`), `schema_version`; `/parameter.json` und neu `/kennzahlen.json` (aggregiert) sind das Austauschformat (dokumentiert in `docs/SCHEMA.md`, versioniert); Import-Command `partner_import <url>` liest fremde Exporte in `PartnerParameter` (system_id, schema_key, wert, stand) für die Gegenüberstellung. Keine personenbezogenen Daten, je.
**Ist:** ❌ (`/parameter.json` ohne Schema).

---

### Bereich N · Menü, Navigation, Namen

#### FB-N1 · „Umsetzungsregister" statt „Umsetzung" — ✅
**Quelle:** A0-03. **Ist:** ✅ Nav (`base.html:336`).

#### FB-N2 · Hauptfenster heißt „Parlament" und ist Menüpunkt — ✅
**Quelle:** A0-04 — *„Das Hauptfenster heißt nun Parlament als Menüeintrag und ist darüber erreichbar."* **Ist:** ✅ (`base.html:333`, Test `test_nav_heisst_parlament`).

#### FB-N3 · „Antrag einbringen" prominenter und hervorgehoben; kein Button im Bereich — ✅ (0.33.0, S1)
**Quelle:** A0-05 — *„Der „Eigenen Antrag einbringen" Button kann dort weg weil es ein Menüeintrag ist. Der könnte etwas Prominenter positioniert sein und hervorgehoben werden."*
**Spezifikation:** In der App-Leiste ganz rechts vor dem Konto: **gefüllter Gold-Knopf „＋ Antrag einbringen"** (Desktop), auf dem Handy als Gold-„＋" in der Mitte der Tableiste (FB-A1). Kein weiterer Einbring-Knopf in den Feldern (außer in Leerzuständen als Textlink). **Ist (0.33.0):** ✅ gefüllte Goldpille „＋ Antrag einbringen" (36 px) rechts in der einen App-Leiste (`_leiste.html:19`, `base.html:84-85`); am Handy als 48-px-Goldkreis in der Mitte der Tableiste (`_tabs.html:11`, `base.html:259-260`). In den Feldern steht kein Einbring-Knopf außer im Leerzustand.

#### FB-N4 · Seite „Lebensbereiche" aus dem Menü — ✅
**Quelle:** A0-05 — *„Die Seite Lebensbereiche können wir aus dem Menü entfernen weil der Favoritenbereich auf der Parlament Seite absolut reicht."* **Ist:** ✅ (`/kategorien/` → Redirect in den Fächer; Fußzeilenlink bleibt — zulässig).

#### FB-N5 · Zukunftswerkstatt (statt StaatsSimulation) — überall; StaatsSimulation nur als Rechenkern — ✅
**Quelle:** A0-07 — *„Die Entscheidung ist auf Zukunftswerkstatt anstatt StaatsSimulation gefallen…"* **Ist:** ✅ Route, Nav, Satzung, Website; „StaatsSimulation" verbleibt an 4 Stellen als Rechenkern-Begriff (Satzung § 6 Abs 11 lit a definiert ihn so) — konsistent. Zu prüfen: `einbringen.html:48` („berechnet mit der StaatsSimulation") → „in der Zukunftswerkstatt".

#### FB-N6 · Der Feed heißt WeicherFilter — ✅
**Quelle:** A0-06/A0-07. **Ist:** ✅ Feldtitel, Satzung § 5 Abs 10 lit d, Website.

#### FB-N7 · „Vorschlag" statt „Vorlage" — ✅
**Quelle:** A0-07 — *„Die Beratung ist ja der Vorschlag des Expertenrat. Ich schlage vor du bleibst bei dem Terminus. Dieser Vorschlag ist der Text der aus dem Antrag entstanden ist und hochgestuft wird zur endwahl."* **Ist:** ✅ Plattform und Satzung § 5 Abs 12; das Strategie-Papier (Kap. 4/5) sagt noch „Vorlage" → mit Fassung 4 ändern (D-Z2).

#### FB-N8 · Menüstruktur der App-Leiste (Ausarbeitung, aus FB-A1)
**Desktop:** [Wortmarke] Parlament · Mandatare · Gremien · Umsetzungsregister · Zukunftswerkstatt · Übersicht | **＋ Antrag einbringen** | [Anstoß-Symbol] [Konto-Avatar ▾: Mein Gremium · Profil · Beitrag · Verwaltung · Sprache · Abmelden] — Gäste: … | Anmelden · **Mitglied werden** · EN. Gremien wandert ins Hauptmenü (öffentliche Besetzung), Übersicht nach hinten. **Handy:** Wortmarke + Burger (Menü gleitet von rechts) + Tableiste im Parlament. ❓ D-N8.

**Ist (0.33.0):** ✅ so gebaut (`_leiste.html`), D-N8 nach Empfehlung angewendet; der aktive Punkt folgt dem Bereich statt dem genauen Pfad (`templatetags/leiste.py:11-35`). **Abweichung:** „Profil" fehlt bewusst, weil `/profil/` erst mit S10 entsteht (FB-K5) — kein toter Link; das Konto-Menü führt stattdessen den Abschnitt „Mehr" mit den Fußzeilen-Links, Gäste haben dafür ein eigenes ⋯-Menü (`_mehr_links.html`). Tests: `verfahren/test_app_rahmen.py:40-125`.

---

### Bereich O · Die Homepage ddoe.at (WordPress)

#### FB-O1 · Mitmachen-Seite → Spenden — ✅ (bestätigt durch A0-08 selbst)
**Quelle:** A0-08 — *„die mitmachen seite auf der ddoe.at homepage kann also weg bzw. muss auf die mitgliederanmeldung auf der parlamentplattform führen"* + *„Insofern fällt auch der Menüeintrag Mitmachen bzw. ändert sich zu Spenden denn das ist das einzige was auf dieser seite übrig bleibt."* **Ist (Live 2.9.):** ✅ Menü „Spenden" → `/mitmachen/` als Spenden-Seite mit Verweis auf `/mitgliedschaft/`. Delta (Ausarbeitung): Slug `/spenden/` mit 301 von `/mitmachen/`; QR-Code prüfen (Live-Prüfung konnte kein Bild-Element nachweisen — im Browser kontrollieren).

#### FB-O2 · „So funktioniert's" neu — systemisch, 18 Jahre, 2044 — ✅ (Live: Sektion „Die systemische Herangehensweise")
#### FB-O3 · „Distanz zwischen Wissen und Macht" — Betroffene statt Minderheiten — ✅ (Live; das Wort „Minderheiten" kommt noch 3× vor — ddoe_konzept-Regel „Betroffene und Fachkundige" → 🟡 Wortwahl nachziehen ❓ D-O3)
#### FB-O4 · Plattform im Menü, Alpha-Phase — ✅
#### FB-O5 · „Dieses Werkzeug baut sich nicht von selbst" → neue Sektion; Buttons → Plattform; Spenden mit QR; Menü Spenden — ✅ (QR 🟡 s. O1)
#### FB-O6 · „Minderheiten mit Sachkunde": Zukunftswerkstatt — ✅
#### FB-O7 · Partner-Teaser → `/partner/` — ❌ (siehe FB-M2)
#### FB-O8 · Weitere Live-Befunde (Ausarbeitung): Footer-Satz „Österreich ist das erste Land welches die logisch nächste Regierungsform etabliert" widerspricht der Sprachregel („Form der gesamtgesellschaftlichen Selbstorganisation") → ändern; Blog-Post-Slug „satzung-der-didide-1-1" trägt Titel „Satzung der DDÖ 1.3" → ok; Satzungsseite ohne Änderungsprotokoll → Link auf `Aenderungsuebersicht` ergänzen (❓ D-O8).

---

### Bereich P · Look & Feel — App-Anmutung (Querschnitt; Details in der Design-Spezifikation)

#### FB-P1 · Hochglanz und Politur als laufender Maßstab — 🟡
**Quelle:** Auftrag 1.9. abends (Fahrplan E2): *Animationen, App-Gefühl, nicht Homepage; der Fächer slidet hinein statt zu springen; Leisten fahren ein; moderne Schrift, wo die Serif zu behäbig wirkt.* · A0-05: *„mehr nach app aussieht als nach homepage"*.
**Spezifikation:** verbindlich in `DDOE_Design_Spezifikation_App-Look.md`: Tokens, Typografie (FB-P2), Bewegungssystem (Dauern 160/260/320/420 ms, eine Easing-Familie, gerichtete Übergänge: Feldtausch gleitet in Wischrichtung, Overlays von ihrem Rand, Fächer-Zoom vom Klickpunkt, Zahlen zählen hoch, Balken wachsen, Skelette beim Laden), Zustände (Laden/Leer/Fehler/Erfolg), Komponentenkatalog (App-Leiste, Feld, Kachel, Zeile, Chip, Regler, Overlay, Panel, Reiter, Sprechblase, Plakette, Ampel, Zeitstrahl, Ring), Responsive-Raster, Dark Mode ohne Lücken, Reduced Motion, Fokus.
**Ist:** 🟡 Erststand 0.31/0.32.

#### FB-P2 · Schrift: Sans für alles Bedienbare — ✅ (0.33.0, D-P2 angewendet)
**Ausarbeitung:** Serif (Georgia) in H1–H3 wirkt auf Parlament, Antragsseite und Gremien wie Zeitung, nicht wie App. Vorschlag: **Sans überall auf der Plattform** (System-Stack, kein Webfont — Datenschutz), Serif nur in der Wortmarke „Parlament*Plattform*" und optional auf `/` und `/zukunftswerkstatt/` als Erzähl-Akzent. ❓ D-P2.

**Ist (0.33.0):** ✅ Sans für alles Bedienbare mit der Skala aus 2.2 (`base.html:65-70`); Serif nur in der Wortmarke (Leiste und Fuß) und im Bühnen-H1 der drei Erklärseiten (`base.html:77`, `:112`, `:277`). Serif-Reste auf der Startseite und in den Mandatar-Platzhaltern entfernt; ein statischer Test hält die Ausnahmeliste fest (`verfahren/test_design_system.py:103-121`).

#### FB-P3 · Dark Mode vollständig, manueller Schalter — ✅ (0.33.0, S1)
**Ausarbeitung:** heute nur `prefers-color-scheme`; Lücken (hart kodierte Badge-/Ikonenfarben, QR-Kasten). Ziel: alle Farben über Tokens; Schalter im Konto-Menü (System / Hell / Dunkel), `localStorage`, `data-theme`-Attribut.

**Ist (0.33.0):** ✅ Tokens mit den Spezifikationsnamen, dunkel doppelt hinterlegt (Systemeinstellung und `data-theme="dark"`, `base.html:14-61`); Schalter System/Hell/Dunkel im Konto- und ⋯-Menü (`_thema.html`), gemerkt in `localStorage`, vor dem ersten Zeichnen gesetzt (`static/verfahren/js/thema.js`). Vollzugsampel, Status-Badges, Ergebnislegende und QR-Kasten laufen über Token-Klassen (`templatetags/phasen.py:38-50`, `uebersicht.html:39-46`, `verwaltung_mitglied.html:8-11`, `_beitrag_kasten.html:4`). Statische Tests: `verfahren/test_design_system.py:52-101`; im Browser geprüft (`tests/e2e/test_app_rahmen.py`). 🟡 Rest: Inline-SVG-Grafiken der Erklärseiten und das Captcha bleiben hell — als „Grafiken mit eigenem Papier" zulässig (Spezifikation 8.8).

#### FB-P4 · Technik für das App-Gefühl: htmx + Alpine.js, eingecheckt — ✅ (0.33.0, S1)
**Quelle:** A0-05 — *„Nütze Skills die ich bereits installiert habe oder sag mir welche skills oder plug ins ich dir installieren soll … such mir ein github repository raus das ich installieren soll."* → Entscheidung (Fahrplan E): htmx 2 + Alpine.js 3 als statische Dateien. **Ist (0.33.0):** ✅ htmx 2.0.10 genutzt (Feldtausch jetzt mit `transition:true` und `hx-indicator`); **Alpine 3.17.1 wird verwendet**: Komponenten `klappmenue`, `anstoss`, `thema`, `tabs`, `meldung` in `static/verfahren/js/app.js`, dazu das kleine `thema.js` im Kopf. **Kein Inline-Handler und kein Inline-Skript mehr** in irgendeinem Template (Test `verfahren/test_design_system.py:141-148`), damit ist eine strikte CSP möglich. Playwright liegt als eigene Abhängigkeitsgruppe `e2e` im `pyproject.toml`; die Bildschirmtests überspringen sich ohne Browser.

#### FB-P5 · Sichtprüfung des Gründers je Politur-Schritt — Prozessregel
Jeder Bauschritt aus Teil C endet mit Screenshots (Desktop 1440×900, Handy 390×844, hell und dunkel) und einem kurzen Bewegungs-Video/GIF, abgelegt unter `docs/sichtpruefung/<version>/`; der Gründer bestätigt oder korrigiert im Fahrtenbuch (Eintrag → Status).

---

## Teil C · Die Bauschritte in Reihenfolge (für Claude Code)

Jeder Schritt ist in sich abnehmbar, hat Tests und endet mit einer Sichtprüfung (FB-P5) und einem CHANGELOG-Eintrag. Reihenfolge: zuerst das, was der Gründer täglich sieht (Parlament, Antragsseite, Chat), dann die Gremien-Tiefe, dann die Zukunftswerkstatt-Ringe. Versionsnummern sind Vorschläge (SemVer-Minor je Schritt).

| Schritt | Version | Inhalt | FB-Einträge | Abnahme (Kurz) |
|---|---|---|---|---|
| **S1 · App-Rahmen** ✅ 2.9.2026 | 0.33.0 | Eine App-Leiste (Konto-Menü), gefüllter „＋ Antrag"-Knopf, Parlament ohne Fußzeile, Raster auf `100dvh`, Handy-Snap + Tableiste, Anstoß in die Leiste, Gastband, Sans-Typografie (nach D-P2), Alpine aktivieren, Skelett-Zustände, Dark-Mode-Lücken | A1, A2, A6, N3, N8, K3(Position), P2, P3, P4 | Screenshots 1440/390, kein Seiten-Scroll im Parlament |
| **S2 · „Mehr vorhanden" + Kachel-Raster** | 0.34 | Scroll-Hinweis an allen Feldern; Wichtige Abstimmungen 2×2/3×2 gleich groß; Meine Region 3×3-Bänder mit horizontalem Wischen; Kachel-Inhalt (Thema-Chip + Themen-Stern, Frist-Ring, „Mitreden"); Rückmeldung in der Kachel statt Flash; Leerzustände kurz | A5, D1, D2, D3, E1, E3, A2 | 7 hervorgehobene → 6 sichtbar + „↓ 1 weitere"; Region wischt |
| **S3 · WeicherFilter komplett** | 0.35 | Neun Regler (zwei Richtungen), Favoriten-zuerst-Schalter, Live-Vorschau, einfahrbare Profil-Leiste mit Pfeil, Overlay mit Speichern/Neu/Umbenennen/Löschen/Zurücksetzen, „Warum hier?"-Aufklapp, Direkt-Handlung in der Zeile, Regel v2 dokumentiert + Parameter | B1–B6 | Abnahmen B2, B4, B5 |
| **S4 · Der Fächer mit fünf Ebenen** | 0.36 | Neuer Layout-Algorithmus (keine Überlappung, Tests über alle 312 Anker), Auffächer-Regel (Ebene 5 entfaltet), Säulenfarben, Faden-Hover, Zoom-Animation vom Klickpunkt, Mitte-Modus mit vollem Rückweg, Brotkrume, Handy-Variante, Stern-Tausch ohne Feldflackern, laufende Verfahren je Ast (nach D-C5) | C1–C5 | Abnahmen C1, C2, C3 |
| **S5 · Antragsseite in drei Zonen** | 0.37 | Zonen-Leiste (Desktop-Scroll-Spy, Handy-Reiter mit Wisch), Zone 1 (Text + Handlungskarten + lesbare Regeln), Zone 2 als Skelett/Leerzustand mit Kopfkarte + Beanstanden, Zone 3 = neuer Chat (S6) | F1, F2 (Rahmen), F4 | Abnahme F1 |
| **S6 · Chatsystem** | 0.38 | Datenmodell (antwort_auf, phase, archiviert_am, Reaktion), Sprechblasen-Faden mit Antworten, Eingabezeile, Anker, Scroll-Gedächtnis + „n neue", Sperre/Phasenband, Räumung bei Hochstufung, Panel links mit Griff und drei Spalten, `/gespraeche/`, Melden/Ausblenden | G1, G2, G3, G4, G5 | Abnahmen G1–G3, G5 |
| **S7 · Abstimmungs-Chat + Archiv** | 0.39 | Gepinnter Vorschlag + Diff, „Passt alles"-Systemeintrag, Kritik mit Textstellenbezug, Reaktionen (nur Unterstützer, nach D-G6), Engagement-Reihung (Parameter), Auswertung 50 %/oben, Übergabe der Kritik ins Entwurfsfenster, Migration der Voten; Archiv-Reiter mit Zeitleiste + Export JSON/Markdown | G6, G7, I2(Wünsche-Liste) | Abnahmen G6, G7 |
| **S8 · Fristen + Parameterregister v2** | 0.40 | Fünf Fristen + Schema-Kennungen im Register, Erstvorschlags-Frist im Fenster, VO aus dem Register erzeugen, Diagramm liest Register, alle harten Konstanten ins Register, Register-Seite im App-Look, JSON mit Schema/system_id, `grundordnung-v1.yaml` entfernen oder importieren | J1, J2, J4, M5(Schema) | Abnahme J1; `/parameter/` zeigt Gruppen |
| **S9 · Gremien vervollständigen** | 0.41 | Generische interne Beschlüsse (GremienBeschluss), ER2-Quorum + Checkliste + Frist, KoRat-Bereich 2×2 (Aufgaben, Posteingang, Beschlüsse, Parameter & Tests mit ParameterTest), Integritätsrat-Bereich (Hervorhebung mit Beschlussnummer, Zurückweisung, Aussetzung, Regelprüfung), „Mein Gremium" für alle, ER1-Dreispalter mit Diff + Interessenbindungen, Fachliste + Auslosung | I1–I6, D4, J3 | Hervorhebung nur noch per Integritätsrat-UI; KoRat-Beschluss braucht Mehrheit |
| **S10 · Mandatar-Rolle + Profil** | 0.42 | Rolle `mandatar`, `/mandatare/mein/`, Instant-Report, Mandatsfrage-Antrag (nach D-L2), Rechenschaftsregister echt, Berichte mit Fristzähler; Profilseite (Wohnsitz, Nebenwohnsitz, Digest, Opt-out, Export, Löschen); Mandat ↔ Kandidatur | L1–L3, K5, J6 | Abnahme L2; Profil ändert Region-Feld |
| **S11 · Zukunftswerkstatt Ring 1–2** | 0.43 | Prompt-Versionierung, Warteschlange, Simulationslauf-Kette, Faktenbasis `Norm`/`NormVerweis` + `ris_import`, Rechtsfolgen-Lauf mit JSON-Schema und Verifikation, Ähnlichkeit Stufe 2 (Embeddings, Live-Karte beim Tippen, direktes Unterstützen, Dokumentation der Wahl), Zone 2 Karten 1–3 mit Grafiken, Beanstandung/Korrekturlauf, `/zukunftswerkstatt/faktenbasis/` | H1, H2, H3, H6, H8, H12, F2 | Abnahmen H2, H3, F2 |
| **S12 · Ring 3–4: Last, Dauer, Vergabe** | 0.44 | `PersonalAggregat`, Lastbild + Lastampel + `/umsetzung/last/`, Dauer-Zeitstrahl, `VergabeSchwelle` + Vergabe-Lauf, Vergabe-Kerndaten-Import, „Mögliche Bieter (Näherung)" | H4, H5, H7 | Abnahme H4 |
| **S13 · Ring 5: Kennzahlen, Prognosen, Muster** | 0.45 | Kennzahlen-Erhebung ohne Profil (+ DSFA-Vermerk), `/zukunftswerkstatt/kennzahlen/`, Prognose-Register, Muster-Lauf + Berichte, Hervorhebungs-Kandidaten → KoRat-Posteingang, Parameter-Vorschläge → KoRat | J7, J8, H10, H11 | Bericht erscheint im Posteingang, nie automatisch im Feld D |
| **S14 · Internationale Partner** | 0.46 | Partner-Konto mit Bestätigung, Rolle `partner`, Bereich (Software-Start, Parameter-Gegenüberstellung, Lernfortschritt, Kontakt), Schaubild auf `/partner/`, Kontaktformular, `docs/SCHEMA.md`, `partner_import`; ddoe.at-Teaser (WordPress, getrennt) | M1–M5, O7 | Abnahme M3 |
| **laufend** | — | Website-Punkte (O1 Slug/QR, O3 Wortwahl, O8 Footer-Satz), README/Übersicht „Prototyp" → „Alpha", Einführungstexte (K4), Mitgliedschafts-Flowchart (K1), i18n der Verwaltung, `pyproject`-Version = CHANGELOG-Version, Inventar-Auffälligkeiten 5–22 | K1, K2, K4, O* | — |

**Parallelität:** S1–S4 sind Oberfläche und unabhängig von S8–S9; S6 vor S7; S5 vor S11 (Zone 2 braucht den Rahmen); S8 vor S9 (Parameter für Quoren/Fristen); S11 vor S12/S13.

---

## Teil D · Offene Entscheidungen des Gründers (❓)

Bitte je Zeile: **Ja / Nein / anders (Text)**. Ohne Antwort gilt die Empfehlung.

| Nr. | Frage | Empfehlung |
|---|---|---|
| D-B2 | WeicherFilter: „wofür / wogegen gestimmt" als **zwei** Regler (statt einem richtungslosen)? | Ja, zwei |
| D-C5 | Favoriten-Feld zeigt je Ast eine Zahl-Pille „3 laufend", die eine kompakte Liste laufender Verfahren im Feld einblendet (§ 5 Abs 10 lit a)? | Ja |
| D-D2 | Kachel „wieviel % und wofür": (a) Tendenz verdeckt bis Fristende (heute), (b) Tendenz ab erreichter Mindestbeteiligung, (c) immer sichtbar? | (a) jetzt, (b) als Parameter vorbereiten |
| D-D4 | Hervorhebung bleibt beim **Integritätsrat** (Satzung), der Koordinationsrat **beantragt**; oder Satzung auf KoRat ändern? | Satzung belassen |
| D-G1 | Reaktionen (👍) auch außerhalb des Abstimmungs-Chats, rein informativ? | Ja, nur Zustimmung |
| D-G3 | Chat-Panel (Griff links) nur im Parlament oder auf jeder Seite? | Auf jeder Seite der Plattform; die Handy-Tableiste hat in S1 vier Ziele + ＋, „Chats" kommt als fünftes mit S6 |
| D-G5 | Der eingefrorene Abstimmungs-Chat wird in der Endabstimmung als aufklappbarer Block „So kam der Vorschlag zustande" gezeigt? | Ja |
| D-G6a | Reagieren im Abstimmungs-Chat: nur Unterstützer (= das Votum) — oder alle Mitglieder, Unterstützer gesondert gezählt? | Nur Unterstützer |
| D-G6b | Hochstufung nur, wenn „Passt alles" **oben steht und** > 50 % hat (beides), sonst Rückgabe? | Ja, beides |
| D-G6c | Reaktionen im Abstimmungs-Chat offen mit Namen (wie heute das Votum) oder pseudonym? | Offen (§ 6 Abs 9-Logik, Unterstützung ist ohnehin öffentlich) |
| D-J7 | Verweildauer-Kennzahl: Opt-out (Voreinstellung an) oder Opt-in? | Opt-out, vor Produktivsetzung DSFA |
| D-K3 | Anstoß-Speicherung in der eigenen Datenbank (statt FTP-Webserver) bleibt? | Ja — **angewendet in S1 (0.33.0)**, S1 änderte nur die Position |
| D-L2a | Mandatsfrage (Instant-Report → Abstimmung) **ohne** Unterstützungsphase, eigene Antragsart mit kürzerer Frist (Parameter, Start 7 Tage)? | Ja |
| D-L2b | Mandatsfragen automatisch in „Wichtige Abstimmungen"? | Nein (bleibt beim Integritätsrat) |
| D-M3 | Partner-Konto: lesen überall, schreiben nur im Partner-Bereich; keine Mitgliedsrechte? | Ja |
| D-M4 | Umfang der Partner-Oberfläche in der Erststufe: (1) Software-Start + (4) Kontakt zuerst, (2)/(3) später? | Ja |
| D-N8 | Neue Menüreihenfolge (Gremien ins Hauptmenü, Übersicht nach hinten, Konto-Menü)? | Ja — **angewendet in S1 (0.33.0)**; „Profil" erst mit S10 |
| D-O3 | ddoe.at: Wort „Minderheiten" (3×) durch „Betroffene und Fachkundige" ersetzen (Regel aus ddoe_konzept)? | Ja |
| D-O8 | Satzungsseite ddoe.at: Link auf die Änderungsübersicht 1.3 → 2.x? | Ja |
| D-P2 | Sans-Schrift überall auf der Plattform, Serif nur Wortmarke (+ optional Erklärseiten)? | Ja — **angewendet in S1 (0.33.0)**, Serif auf den drei Bühnen-H1 |
| D-Z1 | Satzung-Anhang: doppelte Nummerierung (zweimal 9 und 10) bereinigen → 11, 12 | Ja |
| D-Z2 | Strategie-Papier Fassung 4: „Vorlage" → „Vorschlag", Zukunftswerkstatt-Name durchziehen, Ringe mit Stand 0.32 | Ja |

---

## Teil E · Was am alten Fahrplan fehlte oder zu dünn war (Analyse vom 2.9.2026)

Der alte Fahrplan (`DDOE_Fahrplan_Oberflaeche_2026-09-01.md`) war ein guter Statusbericht, aber kein Bauplan. Konkret:

1. **Verdichtung statt Zerlegung.** Jede Nachricht wurde zu einem Absatz („P5 · Der WeicherFilter") — wer baute, las den Absatz, nicht das Original. Folge: 3 statt 5 Fächer-Ebenen (FB-C2), feste Chip-Leiste statt Pfeil-Leiste (FB-B4), richtungsloser Regler (FB-B2), Antragsseite ohne Zonen (FB-F1), Chat gar nicht (FB-G). → Jetzt: eine FB-Kennung je Einzelforderung mit Zitat.
2. **Kein Aussehen.** Nirgends standen Maße, Anordnung, Zustände, Bewegung (Dauer, Richtung), Handy-Verhalten, Leerzustände. → Jetzt in jedem Eintrag; Design-Spezifikation als eigenes Dokument.
3. **Keine Abnahmekriterien.** „Erledigt" wurde aus dem CHANGELOG übernommen, nicht gegen die Anweisung geprüft (z. B. „P2 erledigt", obwohl fünf Ebenen fehlten; „Bildschirmfüllend", obwohl die Seite scrollt). → Jetzt: Abnahme je Eintrag, Ist mit Datei:Zeile.
4. **Status-Vermischung.** Satzungslage, Zielbild und Code standen in einem Satz („Zielwerte → F-68"). → Jetzt getrennt: Satzung ✅ / Software ❌ (z. B. FB-J3).
5. **Fehlende Themen:** Chat-Datenmodell, Archiv-Inhalt und Export, Integritätsrat-Oberfläche, Kennzahlen-Erhebung ohne Profil, Prognose-Register, Faktenbasis-Tabellen, Warteschlange, Prompt-Versionierung, Profilseite, Nebenwohnsitz, Fachliste/Auslosung, Partner-Konto-Ablauf, Mandatsfrage, Rechenschaftsregister echt, Scroll-Gedächtnis, Handy-Tableiste.
6. **Widersprüche unbemerkt:** „Tendenz verdeckt" auf Kacheln, aber `/uebersicht/` zeigt laufende Ergebnisse (Inventar 5); Fristen 60/21/28 nicht im Register, aber Register „führt"; `grundordnung-v1.yaml` mit alten Werten im Repo.
7. **Reihenfolge ohne Abhängigkeiten.** → Teil C mit Abhängigkeiten und Abnahmen.
8. **Offene Fragen nicht gesammelt.** → Teil D.

Was **gut** war und übernommen wurde: die Namensentscheidungen (Abschnitt C), die Fristen-Tabelle (D), die Technik-Entscheidung htmx/Alpine (E), die Look-Grundsätze (E2), die Mandatar-Abschnitte (F), die A0-Abgleich-Punkte vom 2.9. (drei Nachbau-Punkte — sie sind jetzt FB-C2, FB-B4, FB-A5).

---

*Fahrtenbuch Detailfassung 1.0 · 2.9.2026 · S1 (0.33.0) gebaut und fortgeschrieben am 2.9.2026 — Bilder unter `docs/sichtpruefung/0.33.0/`. Nächste Fortschreibung: nach der Sichtprüfung des Gründers und nach den Antworten zu Teil D.*
