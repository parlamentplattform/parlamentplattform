# Soll/Ist-Abgleich — Fahrtenbuch Detailfassung 1.0 gegen den Code (v0.32.0)

Stand 2.9.2026 · Grundlage: `DDOE_Fahrtenbuch_Detail_v1_2026-09-02.md` (Soll), `Funktionsinventar_Ist_2026-09-02.md` (Ist aus dem Code), `Website_Ist_Live_2026-09-02.md` (Ist ddoe.at/parlament.ddoe.at), lokaler Lauf des Repos (265 Tests grün, Screenshots Desktop/Handy)

## 1. Das Bild in Zahlen

96 Einzelforderungen aus den acht Original-Nachrichten. Davon:

| Status | Anzahl | Bedeutung |
|---|---|---|
| ✅ umgesetzt | 34 | gegen die Anweisung geprüft — meist Satzung, Namen, Menü, Mandatare, Gremien-Kern, Anstoß, Website |
| 🟡 teilweise | 24 | vorhanden, aber vom Original abweichend oder unvollständig — vor allem die Oberfläche (Raster, Fächer, WeicherFilter, Kacheln) |
| ❌ fehlt | 31 | nicht gebaut — Antragsseite in Zonen, gesamtes Chatsystem, Abstimmungs-Chat, Archiv, Integritätsrat-Oberfläche, Zukunftswerkstatt-Ringe 1–5, Kennzahlen, Partner-Konto, Mandatar-Rolle, Profil |
| ❓ / — | 7 | Entscheidung nötig bzw. Grundsatz/Prozessregel ohne Code |

**Die ehrliche Zusammenfassung:** Fundament, Verfahrenskern, Gremien-Kern, Satzung und Website stehen. **Was der Gründer täglich sieht — das Parlament als App, die Antragsseite mit Einschätzung und Chat — ist zum größten Teil noch nicht so gebaut, wie es beschrieben wurde.** Die Zukunftswerkstatt existiert als Steckplatz und Erklärseite, aber noch nicht als Rechenwerk.

## 2. Die zehn größten Lücken (nach Sichtbarkeit für den Gründer)

1. **Antragsseite ohne die drei Zonen** — keine Einschätzung, keine Grafiken, kein Chat (FB-F1, F2).
2. **Kein Chatsystem** — weder Antworten, noch Scroll-Gedächtnis, noch das linke Panel, noch Räumung/Archiv (FB-G1–G7).
3. **Fächer mit drei statt fünf Ebenen; Beschriftungen überlappen; kein Zoom auf den Klickpunkt** (FB-C1–C3).
4. **Parlament ist nicht bildschirmfüllend** (Fußzeile, zwei Nav-Zeilen, Anstoß-Knopf über dem Feld; kein Handy-Snap) (FB-A1).
5. **WeicherFilter: feste Chip-Leiste statt einfahrbarer Leiste mit Pfeil; 8 statt 9 Regler, einer richtungslos; keine Live-Vorschau** (FB-B2, B4, B5).
6. **Kein „mehr vorhanden"-Hinweis** an keinem Feld (FB-A5); Wichtige Abstimmungen ohne 4/6-Raster, Meine Region ohne 3×3-Bänder (FB-D1, E1).
7. **Abstimmungs-Chat zum Vorschlag fehlt** — stattdessen Votum-Formular (FB-G6).
8. **Integritätsrat hat keine Oberfläche; Hervorheben ist nur per Demo-Seed möglich** (FB-D4, I6).
9. **Zukunftswerkstatt rechnet nicht:** keine Rechtsfolgen, kein Aufwand, keine Ausschreibungsprüfung, keine Faktenbasis, keine Warteschlange (FB-H3–H8, H12).
10. **Fristen nur teilweise im Register** (60/28 fehlen, Expertenrat-21-Tage-Frist fehlt als Parameter), Register ohne Schema (FB-J1, J2, M5).

## 3. Was bewusst anders gebaut wurde (⚠️ — braucht Bestätigung oder Rückbau)

| Punkt | Anweisung | Umsetzung | Grund | Entscheidung |
|---|---|---|---|---|
| Anstoß-Speicherung | Webserver/FTP | eigene Datenbank + CSV/JSON-Export | keine Fremdzugänge, Backup, DSGVO | D-K3 |
| Kachel „wofür" | Tendenz zeigen | Tendenz verdeckt bis Fristende | F-15 (kein Mitläufer-Effekt) | D-D2 |
| Hervorhebung | KoRat (Erinnerung) | Integritätsrat (Satzung), KoRat beantragt | § 5 Abs 10 lit b | D-D4 |
| „Lebensbereiche" | aus dem Menü | aus dem Menü; Fußzeilenlink bleibt | Erreichbarkeit | — |
| Mitmachen-Seite | weg / umleiten | bleibt als „Spenden" | A0-08 selbst („das einzige, was übrig bleibt") | — |

## 4. Widersprüche im Code, die vor dem Weiterbau zu klären sind

1. `/uebersicht/` zeigt Zwischenstände laufender Abstimmungen (Ja/Nein/Enthaltung) — die Kacheln verbergen sie. Entweder überall verdeckt (Empfehlung) oder D-D2 anders entscheiden.
2. `policies/grundordnung-v1.yaml` (14/21/7 Tage) widerspricht der aktiven Ordnung v2 (60/21/28) und wird von keinem Code gelesen → entfernen oder zum Import-Format machen.
3. `pyproject.toml` Version 0.1.0 vs. CHANGELOG 0.32.0; `plattform_core.__version__` ebenso.
4. `demo_seed` läuft bei jedem Produktiv-Deploy (Demo-Konten `@example.org`, Demo-Rollen) → nur bei `DDOE_DEMO=1`.
5. `DDOE_DEBUG` Default „1" → Default „0", Entwicklung setzt explizit.
6. Alpine.js wird geladen, aber nicht benutzt; Inline-`onclick`/`oninput` verhindern eine strikte CSP.
7. Flash-Meldungen gehen bei htmx-Feldtausch verloren.
8. Prüfcode (`StimmRegister.pruefcode`) wird erzeugt, aber nie angezeigt — Texte versprechen ihn.
9. Geburtsjahr wird abgefragt, aber nicht gespeichert (Altersprüfung nur einmalig) — ok, aber im Datenschutztext so sagen.
10. Verwaltung (8 Templates) nicht übersetzbar; Mails hart kodiert; `beitrag_verbuchen` verlinkt hart `parlament.ddoe.at`.
11. Bot-Drossel im prozesslokalen Cache (2 Worker) → Datenbank-Cache oder Redis.
12. Koordinationsrat und Gruppe 2 entscheiden als Einzelperson ohne Quorum (§ 6 Abs 2 lit e, Abs 8).
13. Rolle Integritätsrat: „Mein Gremium" führt ins Leere.
14. Einführung Schritt 1 verweist auf die abgeschaffte Seite `/kategorien/`; Schritt 2/3 nennen 7 Tage Abstimmung (aktiv sind 28).
15. Mandatare-Liste gibt die Phase als rohen Slug aus (`liste.html:53`).
16. Anstoß-Verwaltung: `vermerk` ohne Eingabefeld; Parameter-Verwaltung nicht aus `/verwaltung/` verlinkt.
17. Dark Mode: hart kodierte Badge-/Ikonenfarben, QR-Kasten hell.
18. Zwei `prefers-reduced-motion`-Blöcke, doppelte Fokus-/Hover-Regeln, CSS-Leichen (`.mini-kacheln`, `.brotkrume`, `blase-auf`, `.feld::after`).
19. Unterstützungen und Kommentare ohne Audit-Eintrag (Stimmen, Bewerbungen haben einen).
20. `Gemeinde.finden` lädt bei jedem Aufruf alle 2 092 Gemeinden; Registrierungsseite rendert 2 092 `<option>`.
21. README: „Status: Phase 1 — der Prototyp ist öffentlich" → „Alpha-Phase".
22. Satzung 2.5 Anhang: doppelte Nummern 9 und 10.

## 5. Vollständige Tabelle (alle 96 Forderungen)

| FB | Forderung | Status | Ist (Kurz) | Delta / Nächster Schritt |
|---|---|---|---|---|
| FB-A1 | Vier gleich große Bereiche über den ganzen Bildschirm | 🟡 | `.parlament{grid 1fr 1fr; gap:16px}`, `.feld{height:calc(50vh − 66px); min-height:360px}` (`base.html:137-138`) — Raster füllt nur näherungsweise; darunter … | Rasterhöhe an `100dvh` binden, Fußzeile auf `/parlament/` entfernen, App-Leiste auf eine Zeile bringen (Konto-Menü), mobile Snap-Ansicht + Tableiste, … |
| FB-A2 | Die vier Bereiche: direkt bedienbar, selbsterklärend | 🟡 | Direktbedienung in Kacheln ✅ (`_kachel.html:25-36`); Flash-Meldungen gehen bei htmx-Tausch verloren (Inventar Auffälligkeit 6); Feldfüße mit Erklärsätzen … | Kachel-Rückmeldung statt Flash; Leerzustände kürzen (siehe FB-E3). |
| FB-A3 | App-Anmutung als Qualitätsmaßstab | 🟡 | Erststand Politur 0.31/0.32 (Auftauchen, Hover-Lift, View Transitions) — aber Serif-Überschriften, zwei Nav-Zeilen, Fußzeile, keine Skeletons, keine … | Design-Spezifikation umsetzen, Feld für Feld, mit Sichtprüfung des Gründers. |
| FB-A4 | Willkommensseite und Parlament getrennt | ✅ | ✅ (`index.html`, `parlament.html`). |  |
| FB-A5 | „Mehr vorhanden"-Hinweis an scrollenden Feldern | ❌ | ❌ — `.feld::after` ist ein leerer Stummel (`base.html:159`). |  |
| FB-A6 | Gäste im Parlament | ✅ (Politur) | Hinweis als `.meldung.info` über dem Raster (`parlament.html:5-9`) — verschiebt das Raster. |  |
| FB-B1 | Der selbstgesteuerte Feed | 🟡 | Regel v1 mit 8 Reglern ✅ (`plattform_core/weicherfilter.py`); Favoriten-Bevorzugung in der Voreinstellung ❌ (Voreinstellung ist rein Phase/Frist, … |  |
| FB-B2 | Die Regler | 🟡 (7 von 9 vorhanden, einer falsch) | 8 Regler (`views.py:31-40`); „gestimmt" richtungslos (`views.py:62-64,80`); `ablaufend` pauschal /60 (`views.py:77`); keine Live-Vorschau (Formular „Anwenden & … |  |
| FB-B3 | Bis zu fünf gespeicherte Konfigurationen | ✅ (Feinschliff) | ✅ `FilterProfil` (max. 5, `verfahren/models.py:580-606`, `views_aktionen.py:321-336`); Umbenennen ❌, Löschen ohne Rückfrage 🟡. |  |
| FB-B4 | Das Umschaltmenü am oberen Rand mit Pfeil (Slide) | ❌ | ❌ feste Chip-Leiste (`parlament.html:20-56`), nur Lade-Animation `einfahren-oben` (`base.html:283`). |  |
| FB-B5 | Der Reglerbereich als halbtransparentes Overlay rechts | 🟡 | 🟡 `<details>`-Overlay mit `einfahren-rechts` (`base.html:146,284`); Aktionen „Anwenden & speichern" + „Als neues Profil" (`parlament.html:31-55`); keine … |  |
| FB-B6 | Voreinstellung neutral, Regel offen | ✅ | ✅ neutral; Regeltext heute als Satz im Overlay (`parlament.html`) — wird zum Link. |  |
| FB-C1 | Der grafische Themenbaum mit Fäden | 🟡 | 🟡 Fächer direkt im Feld ✅ (0.31.0), Wurzel „Lebensbereiche" ✅, Fäden ✅, Schriftgrößen 24/22/20 ✅ — aber **Beschriftungen überlappen und sind abgeschnitten** … |  |
| FB-C2 | Fünf Ebenen im Fächer | ❌ (heute drei) | ❌ maximal drei Ebenen über dem Anker (`faecher.py:111-135`), Enkel-Deckel 12 (`ENKEL_HOECHSTZAHL`), ab Tiefe 5 Lücken (Inventar Frage 2). |  |
| FB-C3 | Hineinbewegen beim Klick; ab der dritten Ebene sitzt der Anker in der Mitte | 🟡 | 🟡 Mitte-Modus ab Tiefe 3 ✅ (`faecher.py:67,84-89`), Rückweg auf 2 Vorfahren + Wurzel begrenzt (Lücke ab Tiefe 5) 🟡; Bewegung = pauschales `hineingleiten` von … |  |
| FB-C4 | Stern an jedem Element | ✅ | ✅ Stern je Knoten (`_faecher.html`), htmx tauscht das ganze Feld 🟡 (→ nur Stern tauschen), `aria-pressed` ❌. |  |
| FB-C5 | Was das Favoriten-Feld sonst noch zeigt | ❓ | ❌ (Ast-Zähler nur in der Suche). |  |
| FB-D1 | 4 oder 6 Kacheln, gleichmäßig | 🟡 | 🟡 `.kacheln` 2 Spalten, kein Zeilenmaß, kein Limit, Kacheln wachsen mit Inhalt (`base.html:167-169`, `views.py:266`). |  |
| FB-D2 | Inhalt einer Kachel | 🟡 | 🟡 Kachel mit Titel, Stern (Antrag), Phase, Balken, Beteiligung, Resttage, Begründung, Direktabstimmung ✅ (`_kachel.html`); Thema-Chip mit Themen-Stern ❌; … |  |
| FB-D3 | Klick öffnet Antrag oder Unterstützungserklärung | ✅ | ✅ Titel-Link (`_kachel.html`). Delta: ganze Kachel klickbar (Ausarbeitung). |  |
| FB-D4 | Wer hebt hervor | Integritätsrat mit Oberfläche, Koordinationsrat beantragt — ❌ (Oberfläche fehlt ganz) | ❌ kein UI — `Antrag.hervorgehoben` nur per `demo_seed` (`demo_seed.py:154-159`); Rolle Integritätsrat existiert ohne Funktion (`gremien/views.py:92-98`). |  |
| FB-E1 | 3×3 Felder Gemeinde / Bezirk / Land | 🟡 | 🟡 drei Zeilen ✅ mit `.kacheln.dreier` (3 Spalten, aber Zeilenumbruch statt Wischen, keine Höhenteilung) — auf 1440×900 ist nur die Gemeinde-Zeile sichtbar … |  |
| FB-E2 | Gleicher Seitenaufbau wie Wichtige Abstimmungen (KI-Einschätzung, Chat) | ❌ (folgt aus FB-F) |  |  |
| FB-E3 | Leerzustände | 🟡 | drei Sätze mit Link (`parlament.html:145-166`) — kürzen. |  |
| FB-F1 | Drei Zonen: Text · Einschätzung · Chat | ❌ | ❌ einspaltig, Reihenfolge Kopf → Wortlaut → Handlung → Ergebnis → Umsetzung → Schleife → Beratung → JSON (`antrag.html`); keine Zonen, keine Reiter. |  |
| FB-F2 | Zone „Einschätzung" der Zukunftswerkstatt mit Grafiken und Animationen | ❌ | ❌ keine Zone, keine Grafiken; die einzige KI-Nutzung ist die Werkstatt-Einschätzung im ER1-Fenster (`gremien/views.py:42-49,217-226`); Beanstandung ❌ … |  |
| FB-F3 | Zone „Chat" | siehe Bereich G. |  |  |
| FB-F4 | Mandats-Kandidaturen auf der Antragsseite | ✅ (Politur) | Bewerbungen, Zustimmungswahl, Ergebnis ✅ (`antrag.html:43-111`). Delta: in Zone 1 als Handlungskarte; Bewerbungen als Karten mit Initialen-Avatar; Zone 2 zeigt … |  |
| FB-G1 | Der Chat unterhalb der Antragsseite | 🟡 | 🟡 flache Kommentarliste „Beratung (n)" mit Formular (`antrag.html:175-195`), kein Antworten, keine Reaktionen, keine Anker, keine Sperre nach Hochstufung … |  |
| FB-G2 | Die Kommentarleiste merkt sich die Scrollposition | ❌ | ❌ (Inventar Frage 11). |  |
| FB-G3 | Das Ausklapp-Panel links auf der Parlament-Seite | ❌ | ❌ (Inventar Frage 11). |  |
| FB-G4 | Leiste scrollbar; Klick führt zur Antragsseite | ❌ (Teil von FB-G3) |  |  |
| FB-G5 | Chats werden bei jeder Hochstufung geräumt und archiviert | ❌ | ❌ Kommentare bleiben stehen, Formular schließt nur (`views_aktionen.py:257`). |  |
| FB-G6 | Der Abstimmungs-Chat zum Vorschlag des Expertenrats | ❌ (heute: Votum-Formular) | ❌ `UnterstuetzerVotum` mit annehmen/zurückgeben + Wunsch (`_schleife.html`, `gremien/models.py:288-310`) — kein Chat, keine Reaktionen, keine Reihung; Sperre … |  |
| FB-G7 | Die Archiv-Registerkarte mit Export | ❌ | ❌ (Inventar Frage 11; `export.json` enthält nur Stimmen). |  |
| FB-H1 | Eine KI im Antragsweg | anbieterneutral, budgetiert — ✅ (Fundament) / ❌ (Nutzung) | ✅ Steckplatz, Archiv, Budget (`ki/`); ❌ Prompt-Versionierung, Warteschlange, alle Zwecke außer `einschaetzung`. |  |
| FB-H2 | Ähnlichkeitsprüfung mit Wahl: bestehenden unterstützen oder eigenen stellen | 🟡 (Stufe 1 lexikalisch) | 🟡 Trigramm-Jaccard beim Absenden, Karte „Ähnliche Anträge gefunden" mit „Trotzdem einbringen" / „Lieber einen bestehenden unterstützen" (→ nur Link ins … |  |
| FB-H3 | Rechtsfolgen: Welche Gesetze, was bedeutet es für Judikatur, Exekutive, Personal | ❌ | ❌ (nur Prosa „In Entwicklung", `einbringen.html:46-48`). |  |
| FB-H4 | Aufwand, Vertretbarkeit neben laufenden Umsetzungen, Dauer bis Inkrafttreten | ❌ | ❌. |  |
| FB-H5 | Ausschreibungsprüfung | ❌ | ❌. |  |
| FB-H6 | Die Simulation als Kontext: neue Anträge durchlaufen sie automatisch | ❌ | ❌ (nur der manuelle Werkstatt-Lauf). |  |
| FB-H7 | Vertiefung bis „welche Firmen könnten sich bewerben" | ❌ (Ring 4, spät) | ❌. |  |
| FB-H8 | Kontext aus geprüft korrekten Angaben | Datenbanken — ❌ | ❌. |  |
| FB-H9 | Das Hin und Her: die Plattform passt sich mit der Gesellschaft an | 🟡 (Satzung ✅, Software ❌) | Satzung ✅; Software nur Register-Grundstock. |  |
| FB-H10 | Unterbeteiligte, stabilisierende Anträge → Vorschlag an den Koordinationsrat → Hervorhebung | ❌ | ❌ (Posteingang ist Platzhalter, `koordination.html:45-50`). |  |
| FB-H11 | Muster erkennen: schnell revidierte Gesetze, Korruptionsgefahr | ❌ (Ring 5) | ❌. |  |
| FB-H12 | Kontext-Updates regelmäßig und bei Änderungen sofort | ❌ | ❌. |  |
| FB-I1 | Rollen auf Zeit: Zuweisung durch Admin, später automatisch; Sonderfunktionen nur während der Berufung | 🟡 | 🟡 Rollen mit Frist/Bestätigung/Audit ✅ (`gremien/models.py:56-99`); Zuweisung nur manuell; Fachliste/Auslosung ❌; Rollen `mandatar`, `partner`, … |  |
| FB-I2 | Expertenrat 1: eigener Bereich, roher Antrag, Entwurfsfenster, gemeinsam entwerfen, abstimmen, einreichen | ✅ (Erstfassung) / 🟡 (Details) | ✅ Kern (`gremien/views.py:160-276`, `fenster.html`); ❌ Drei-Spalten-Layout, Diff, Einschätzung als Arbeitsunterlage, Interessenbindungen, Erstvorschlags-Frist … |  |
| FB-I3 | Expertenrat 2: eigene Oberfläche, Korruptionsprüfung, abstimmen, validieren / zurückgeben / Austausch | ✅ (Erstfassung) / 🟡 (Quorum) | ✅ Bereich mit drei Handlungen (`pruefung.html`, `gremien/views.py:430-462`); ❌ Einzelperson entscheidet sofort (kein Quorum, Inventar Auffälligkeit 17), keine … |  |
| FB-I4 | Interne Abstimmungen in allen Räten (Sonderfunktion auf Zeit) | 🟡 | 🟡 nur `EinreichStimme` für ER1; ER2 und KoRat ohne Abstimmung. |  |
| FB-I5 | Der Koordinationsrat: eigene Oberfläche mit Aufgaben, Posteingang der Zukunftswerkstatt, Abstimmungen, Parameter | 🟡 | 🟡 Austauschanträge + Rollenübersicht + Posteingang-Platzhalter (`koordination.html`); alles andere ❌. |  |
| FB-I6 | Der Integritätsrat | ❌ (siehe FB-D4) |  |  |
| FB-J1 | Die Fristen: 2 Monate · 3 Wochen · 2 Wochen · 2 Wochen · 4 Wochen | 🟡 | 🟡 60/21/28 in der VO v2 (`demo_seed.py:36-53`, Migration 0008) ✅ als Wirkung; 14/14/3 im Register ✅; **`expertenrat-erstvorschlag-tage` fehlt** (die … |  |
| FB-J2 | Alle Stellgrößen sind Parameter; Basisparameter für 2044 gemeinsam erarbeiten | 🟡 | 🟡 5 Einträge (`parameter/models.py:46-87`); Historie nur im Audit-Log; keine Gruppen, kein Schema, kein Status. |  |
| FB-J3 | Das Parameterverfahren: Test → Simulation → Vorschlag → Freigabe → Einführung | ❌ (Software) / ✅ (Satzung) | ❌. |  |
| FB-J4 | Leichte Weichenstellungen des KoRat | nie im Stimmgewicht — ✅ (Grundsatz) |  |  |
| FB-J5 | Parameter und Lernerfahrungen mit Partnerparteien austauschen | 🟡 | Satzung ✅, Software ❌ (nur `/parameter.json` ohne Schema). |  |
| FB-J6 | Demos-Zuschnitt lernbar (Haupt-/Nebenwohnsitz) | 🟡 | 🟡 Hauptwohnsitz ✅ (`Mitglied.wohnsitz`), Nebenwohnsitz ❌. |  |
| FB-J7 | Kennzahlen: Beteiligung nach Erstaufruf, Verweildauer, Themen-Attraktivität | aggregiert, ohne Profil — ❌ | ❌ (nur Aufrufe/Besucher, `uebersicht/`). |  |
| FB-J8 | Prognose-Register und Lernschleife | ❌ | ❌. |  |
| FB-K1 | Mitgliedschaftsseite: Rechte plakativ, dann im Detail; Zukunftswerkstatt; Grafiken; Flowchart | ✅ / 🟡 | ✅ Rechte plakativ + Detail + Zukunftswerkstatt-Karte + Ikonen (`mitgliedschaft.html`); Flowchart nur als CSS-Stationen 🟡 (das SVG liegt auf `/`). |  |
| FB-K2 | Mitglied werden nur über die Plattform; Alpha-Phase | ✅ | ✅ ddoe.at verlinkt `/mitgliedschaft/`; „Alpha" auf Plattform und Website. Rest: README sagt „Prototyp" (`README.md` Statuszeile), Demo-Antrag „Namenskonvention … |  |
| FB-K3 | Das Anstoß-Widget auf jeder Seite; Speicherung zur späteren Auswertung | ✅ / ⚠️ (Speicherort) | ✅ Widget, DB, Verwaltung, Export, X, Auto-Schließen (`anstoss/`); ❌ Vermerk-Feld (Inventar 12), Position im Parlament (Inventar 3.7). |  |
| FB-K4 | Einführung nach der Bestätigung | ✅ (Korrektur) | ✅ drei Schritte (`einfuehrung.html`); ❌ Schritt 1 verweist auf die abgeschaffte Seite `/kategorien/` („oben rechts") → Text auf die Suche im Favoriten-Feld … |  |
| FB-K5 | Profilseite für Mitglieder | ❌ (neu, nötig für Region, Nebenwohnsitz, Einstellungen) | ❌ (Parlament verweist auf ein nicht existierendes „Profil", Inventar 2.1). |  |
| FB-L1 | Mandatare-Seite mit Foto, Aufgaben, Entscheidungsprozessen; Pflicht des Mandatars | ✅ (M1) | ✅ `/mandatare/` (Foto in DB, Aufgaben mit Frist, verknüpfte Abstimmungen; § 7 Abs 3 lit b, Abs 9). Politur: Karten im App-Look (Foto 96 px rund, Ebene-Chip, … |  |
| FB-L2 | Die Mandatar-Rolle: Instant-Reports mit Fristen, betreute Abstimmungen | ❌ (M2) | ❌ (Pflege nur durch Verwaltung; `Mandat.kandidatur` nie gesetzt). |  |
| FB-L3 | Mandats-Kandidaturen als Anträge, Zustimmungswahl, meiste Zustimmung gewinnt | ✅ (M3) | ✅ (`Antragsart.MANDAT`, `Bewerbung`, `personenwahl_auszaehlen`). Delta: Beim Anlegen eines Mandats in der Verwaltung den Gewinner-Antrag verknüpfen … |  |
| FB-L4 | Ab wann? | ✅ entschieden: von Anfang an (§ 7 Abs 1) | ✅ Satzung 2.5 § 7 Abs 1 („jederzeit, auch bevor die Partei ein Mandat der betreffenden Ebene innehat"). |  |
| FB-M1 | Die Partner-Seite: Strategie, Fahrplan, Kontakt | ✅ (Erststufe) | ✅ `/partner/` (DE/EN). Delta: **Veranschaulichung** fehlt — ein Schaubild „System und Parameter" (zwei Länder-Kästen mit eigenem System, dazwischen das … |  |
| FB-M2 | Verlinkung: Fußzeile der Plattform ✅ · Teaser auf ddoe.at ❌ |  | ❌ (Live-Prüfung 2.9.: nur `/english/` verlinkt). |  |
| FB-M3 | Konto anlegen, von uns bestätigt | ❌ | ❌. |  |
| FB-M4 | Rolle „Internationaler Partner" mit eigener Oberfläche | ❌ | ❌. |  |
| FB-M5 | Die Schnittstelle: sprachneutrales Parameter-Schema, Export/Import | ❌ | ❌ (`/parameter.json` ohne Schema). |  |
| FB-N1 | „Umsetzungsregister" statt „Umsetzung" | ✅ | ✅ Nav (`base.html:336`). |  |
| FB-N2 | Hauptfenster heißt „Parlament" und ist Menüpunkt | ✅ | ✅ (`base.html:333`, Test `test_nav_heisst_parlament`). |  |
| FB-N3 | „Antrag einbringen" prominenter und hervorgehoben; kein Button im Bereich | 🟡 | 🟡 Umriss-Pille im Header (`.nav-cta`), zweite Nav-Zeile drückt sie optisch nach oben; im Bereich entfernt ✅. |  |
| FB-N4 | Seite „Lebensbereiche" aus dem Menü | ✅ | ✅ (`/kategorien/` → Redirect in den Fächer; Fußzeilenlink bleibt — zulässig). |  |
| FB-N5 | Zukunftswerkstatt (statt StaatsSimulation) | überall; StaatsSimulation nur als Rechenkern — ✅ | ✅ Route, Nav, Satzung, Website; „StaatsSimulation" verbleibt an 4 Stellen als Rechenkern-Begriff (Satzung § 6 Abs 11 lit a definiert ihn so) — konsistent. Zu … |  |
| FB-N6 | Der Feed heißt WeicherFilter | ✅ | ✅ Feldtitel, Satzung § 5 Abs 10 lit d, Website. |  |
| FB-N7 | „Vorschlag" statt „Vorlage" | ✅ | ✅ Plattform und Satzung § 5 Abs 12; das Strategie-Papier (Kap. 4/5) sagt noch „Vorlage" → mit Fassung 4 ändern (D-Z2). |  |
| FB-N8 | Menüstruktur der App-Leiste (Ausarbeitung, aus FB-A1) |  |  |  |
| FB-O1 | Mitmachen-Seite → Spenden | ✅ (bestätigt durch A0-08 selbst) | ✅ Menü „Spenden" → `/mitmachen/` als Spenden-Seite mit Verweis auf `/mitgliedschaft/`. Delta (Ausarbeitung): Slug `/spenden/` mit 301 von `/mitmachen/`; … |  |
| FB-O2 | „So funktioniert's" neu | systemisch, 18 Jahre, 2044 — ✅ (Live: Sektion „Die systemische Herangehensweise") |  |  |
| FB-O3 | „Distanz zwischen Wissen und Macht" | Betroffene statt Minderheiten — ✅ (Live; das Wort „Minderheiten" kommt noch 3× vor — ddoe_konzept-Regel „Betroffene und Fachkundige" → 🟡 Wortwahl nachziehen ❓ D-O3) |  |  |
| FB-O4 | Plattform im Menü, Alpha-Phase | ✅ |  |  |
| FB-O5 | „Dieses Werkzeug baut sich nicht von selbst" → neue Sektion; Buttons → Plattform; Spenden mit QR; Menü Spenden | ✅ (QR 🟡 s. O1) |  |  |
| FB-O6 | „Minderheiten mit Sachkunde": Zukunftswerkstatt | ✅ |  |  |
| FB-O7 | Partner-Teaser → `/partner/` | ❌ (siehe FB-M2) |  |  |
| FB-O8 | Weitere Live-Befunde (Ausarbeitung): Footer-Satz „Österreich ist das erste Land welches die logisch nächste Regierungsform etabliert" widerspricht der Sprachregel („Form der gesamtgesellschaftlichen Selbstorganisation") → ändern; Blog-Post-Slug „satzung-der-didide-1-1" trägt Titel „Satzung der DDÖ 1.3" → ok; Satzungsseite ohne Änderungsprotokoll → Link auf `Aenderungsuebersicht` ergänzen (❓ D-O8). |  |  |  |
| FB-P1 | Hochglanz und Politur als laufender Maßstab | 🟡 | 🟡 Erststand 0.31/0.32. |  |
| FB-P2 | Schrift: Sans für alles Bedienbare | ❓ |  |  |
| FB-P3 | Dark Mode vollständig, manueller Schalter | 🟡 | 🟡. |  |
| FB-P4 | Technik für das App-Gefühl: htmx + Alpine.js, eingecheckt | ✅ / 🟡 | htmx 2.0.10 ✅ genutzt; **Alpine 3.17.1 geladen, aber nirgends benutzt** → die Overlays, Leisten, Panels, Reiter, Regler-Livevorschau, Scroll-Hinweise, Zähler … |  |
| FB-P5 | Sichtprüfung des Gründers je Politur-Schritt | Prozessregel |  |  |

*Legende: ✅ umgesetzt · 🟡 teilweise · ❌ fehlt · ⚠️ bewusst anders · ❓ Entscheidung nötig. Details, Zitate und Abnahmekriterien je Kennung im Fahrtenbuch.*
