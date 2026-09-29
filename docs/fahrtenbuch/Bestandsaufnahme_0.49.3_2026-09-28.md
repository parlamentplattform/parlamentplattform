# Bestandsaufnahme ParlamentPlattform 0.49.3 — 28.9.2026

Stand: `main` 9bf9ec0, Version 0.49.3, live auf parlament.ddoe.at. Grundlage: CLAUDE.md, CHANGELOG, CONCEPT, ADR-001…010, das eingeklebte Fahrtenbuch (Detailfassung 1.0 mit Nachträgen bis A0-19), der Code, eigene Läufe (SQLite und PostgreSQL 16, Bildschirmsonde mit Chromium) und eine gegnerische Prüfung in acht Richtungen mit je einem Widerleger.

## 0. Was hier selbst gemessen wurde

| Prüfung | Ergebnis |
|---|---|
| `ruff check .` (0.16.9) | grün |
| `python manage.py makemigrations --check` | keine Änderungen |
| `check` / `check --deploy --fail-level WARNING` (Produktionsumgebung nachgestellt) | grün (W021 begründet gestillt) |
| `tools/po_pruefen.py` | 2 142 Einträge, 0 offen, 0 unsicher, 0 doppelt |
| Tests auf SQLite (Python 3.11) | 1 464 bestanden, 1 übersprungen; Kern 97 % Zweigabdeckung |
| Tests auf PostgreSQL 16 (eigener Cluster, gleiche Suite) | 1 463 bestanden, **1 rot** — zeitabhängig, nicht Postgres-bedingt (siehe B-…) |
| Bildschirmtests `tests/e2e` (Chromium 1194 über Symlink) | 69 grün (durch den Prüfagenten Bedienbarkeit) |
| GitHub: Pull Requests seit 3.9. | **keine** — alles direkt auf `main`; 2 der letzten 6 CI-Läufe auf `main` rot |
| GitHub: offene Issues | 0 |
| Repository | `.git` 38 MB, `docs/sichtpruefung/` **85 MB / 609 Bilder** in 22 Fassungen |

## 1. Selbst belegte Befunde (vor der Agentenprüfung)

### S-1 · Direkt-Handlung aus Kachel/Feed-Zeile löscht das Feld — hoch
`verfahren/views_aktionen.py:331` (`unterstuetzen`) endet auch bei Erfolg mit `redirect("verfahren:antrag", pk=pk)` und ignoriert das mitgeschickte `weiter`; `abstimmen` folgt `weiter` bei Erfolg (Zeilen 534–537), beide leiten aber in jedem Fehlerfall (Phase vorbei, Aussetzung, offener Adresswechsel) auf die Antragsseite. Die Kachel/Feed-Zeile (`_kachel.html:57-76`) ruft mit `hx-target="#feld-x" hx-select="#feld-x" hx-swap="outerHTML"`. htmx folgt dem 302 auf die Antragsseite, die kein `#feld-x` enthält, das Fragment ist leer, das ganze Feld verschwindet. Browser-Sonde: Klick „Unterstützen“ in der Feed-Zeile als demo1 → Unterstützung in der DB gespeichert, `#feld-filter` danach nicht mehr im DOM, kein `htmx:afterSwap`, kein Gold-Haken. CHANGELOG 0.24.0 versprach „ohne JavaScript kehrt man aufs Parlament zurück, mit htmx wechselt nur das Feld“. Kein Test deckt den HX-Pfad von `unterstuetzen`/`abstimmen` ab (grep `HX_REQUEST` in verfahren: nur Filter-Vorschau). Folge: FB-A2/FB-B1/FB-D3 (Gold-Haken „Erfasst“, Direkt-Handlung) sind im Fahrtenbuch ✅, wirken aber nicht. Behebung: bei HX-Request `_zurueck_zum_parlament` (bzw. `weiter`) statt Antragsseite, Rückmeldung per `HX-Trigger`; ein Unit-Test je View mit `HTTP_HX_REQUEST` und ein Bildschirmtest, der nach dem Klick das Feld und den Haken prüft.

### S-2 · Testkonten zählen im Nenner der Stimmberechtigten — hoch (für den Alpha-Betrieb)
`mitglieder/models.py:299-306` `stimmberechtigte_zaehlen` filtert `is_active, status=AKTIV, geprüft, beitritt`, nicht `testkonto`. `demo_seed` legt demo1…demo5 aktiv, geprüft, mit 200 Tagen Anwartschaft an und läuft bei jedem Deploy (`render.yaml`). Migration `0020_nummern_bestand` hat in Produktion alle Konten vor dem Gründer als Testkonten markiert — genau diese fünf. Folge: Jede Abstimmung veröffentlicht „Stimmberechtigte: 10“ statt 5; die Mindestbeteiligung rechnet gegen die doppelte Grundgesamtheit; Nachrechnende bekommen eine falsche Zahl. A0-15 des Gründers: „Alle Mitglieder vor mir waren nur Testmitgliedschaften.“ Behebung: `testkonto=True` aus Zählung und `ist_stimmberechtigt` ausschließen; `demo_seed` legt Demo-Konten als Testkonten an; Bestand nicht rückwirkend ändern (eingefrorene Zahlen bleiben, Grundregel 7), aber ab dem nächsten Abstimmungsbeginn richtig zählen.

### S-3 · Kein Fristen-Wächter im Betrieb (D-J1a) — hoch
`render.yaml` kennt keinen Cron; `verfahren_fortschreiben` läuft nirgends von selbst. `gunicorn.conf.py` startet seit 0.49 je Worker einen Hintergrundfaden für den Postausgang (alle 30 s) — der Fristenlauf könnte denselben Faden nutzen, ohne zusätzliche Kosten (D-J1a nannte nur den bezahlten Render-Cron). Folge heute: Ein Antrag, den niemand öffnet, wechselt seine Phasen nur rückwirkend beim nächsten Aufruf; Anfechtungsfrist der Vertrauensfrage (§ 7 Abs 10 lit h) kann verstreichen, bevor das Ergebnis je sichtbar war. `docs/BETRIEB-RENDER.md:84` empfiehlt außerdem einen Cron-Einzeiler, der weniger tut als der Befehl.

### S-4 · Zeitabhängiger Test — niedrig
`mandatare/test_vertrauensfrage_ansichten.py:685` rechnet `beginn` mit `strftime` auf dem UTC-Zeitpunkt, die Seite zeigt Wiener Zeit; zwischen 22:00 und 24:00 UTC (Sommerzeit) ist der Test rot (hier reproduziert um 00:10 Wien, auf SQLite wie Postgres). Der Nachbar auf Zeile 706 rechnet richtig (`timezone.localtime`). Einzeiler.

### S-5 · UTC-Datum als Stichtag beim Bewerben — niedrig
`verfahren/views_aktionen.py:740` prüft die Wählbarkeit gegen `timezone.now().date()` statt `timezone.localdate()` (Fehlerklasse Befund #32, Wirkung 0–2 Uhr Wien).

### S-6 · Prozess: keine Pull Requests, kein Schutz auf `main` — mittel
CLAUDE.md § 5.6 verlangt Zweig `schritt/…` → PR gegen `main` mit grünem `pruefen`; seit dem 3.9. gab es keinen PR mehr (die beiden einzigen wurden geschlossen, nicht gemerged). Zwei der letzten sechs Läufe auf `main` waren rot (3878d90, c885e14). Der Deploy-Job schützt die Live-Fassung, aber `main` ist als Referenzstand nicht verlässlich. Empfehlung: Branch-Schutz auf `main` (Pflicht-Check `pruefen`, optional `sichtpruefung`), PR-Pflicht auch für den Gründer-Arbeitsplatz.

### S-7 · Bilder im Repository — niedrig
`docs/sichtpruefung/` trägt 85 MB in 609 Dateien; jede Fassung addiert rund 50 Bilder. Empfehlung: nur die jeweils letzte Fassung im Repo halten (oder Bilder als CI-Artefakt/Release-Anhang), die Historie liegt ohnehin am Arbeitsplatz.


## 2. Verdichtete Befundliste nach Gegenprüfung

Acht Prüfrichtungen lieferten 97 Rohbefunde; je Richtung hat ein Widerleger jeden Befund am Code nachgelesen (Scratch-Tests, Browser-Sonden, Abfragezählung). Widerlegt: 4. Abgeschwächt: rund 20. Die Gegenprüfer nannten 25 zusätzliche Punkte, die Vollständigkeitskritik 11 weitere (die schweren davon sind unten eingearbeitet; alles Übrige steht im Anhang `Bestandsaufnahme_Anhang_Rohbefunde.md`). 17 Agenten, 675 Werkzeugaufrufe, 91 Minuten. Hier stehen die Befunde zusammengezogen (Doppelnennungen vereint), geordnet nach dem, was sie für den Alpha-Betrieb bedeuten. Kennungen: **H** = hoch, **M** = mittel, **N** = niedrig. Aufwand je Zeile.

### A · Verfahren und Betrieb (was falsch rechnet oder still liegen bleibt)

| Nr. | Befund | Beleg | Aufwand |
|---|---|---|---|
| A1 **H** | **Testkonten zählen im Nenner der Stimmberechtigten.** `stimmberechtigte_zaehlen` und `ist_stimmberechtigt` kennen `testkonto` nicht; `demo_seed` legt demo1…5 aktiv, geprüft, 200 Tage Anwartschaft an und läuft bei jedem Deploy; kein Codepfad setzt `testkonto=True` (nur Migration 0020 für den Bestand). Auch die Startseiten-Bühne und `/uebersicht/` zählen Test- und ungeprüfte Konten als „Mitglieder“. Folge: jede Abstimmung veröffentlicht einen zu hohen Nenner; Mindestbeteiligung und 5-%-Schwelle der Vertrauensfrage sind für echte Mitglieder schwerer zu erreichen. | `mitglieder/models.py:299`, `demo_seed.py:126`, `verfahren/views.py:570`, `uebersicht/views.py:180` | halber Tag |
| A2 **H** | **Kein Fristen-Wächter im Betrieb (D-J1a).** Phasen, Beschlussfristen, Aussetzungen, Parametertests und Stufe 2 der Vertrauensfrage laufen nur beim Seitenaufruf; die Antragsseite wendet je Aufruf nur *einen* Übergang an. Nachgestellt: 120 Tage liegengebliebener Antrag → Aufruf 1 „Abstimmung“ (Frist längst um, Stimme abgewiesen), Aufruf 2 „abgelehnt 0/5“. Das Fahrtenbuch duldet den Zustand bis zur Kostenfreigabe eines Render-Crons; seit 0.49 gibt es aber den kostenlosen Hintergrundfaden in `gunicorn.conf.py`, der dieselbe Arbeit tun kann. Die Betriebsdoku empfiehlt zudem einen Cron-Einzeiler, der weniger tut als `verfahren_fortschreiben`. | `render.yaml:31`, `gunicorn.conf.py:11`, `verfahren/views.py:1177`, `docs/BETRIEB-RENDER.md:84` | halber Tag |
| A3 **H** | **Mitgliedsstatus und Gremien sind entkoppelt.** `Rolle.hat`/`hat_fuer` prüfen nur die Rolle; ein pausiertes Mitglied stimmt und beschließt weiter (Scratch-Test bestätigt). Der Ausschluss beendet keine Rollen (der Austritt schon) — die Person bleibt im Quorum-Nenner; der Lostopf der Fachliste zieht auch ausgeschlossene und pausierte Einträge in den Expertenrat. | `gremien/models.py:145`, `:1769`, `mitglieder/verwaltung.py:308` | halber Tag |
| A4 **M** | Globale Nachläufe (Aussetzungen, Beschlüsse, Parametertests, Vertrauensfrage-Stufe 2) laufen aus jedem Seitenaufruf ohne Sperre; bei zwei Workern doppelte Audit-/Register-Einträge möglich. Lazy geschlossene Beschlüsse tragen den Auswertungs- statt den Fristzeitpunkt als `entschieden_am`/Aussetzungsbeginn. Die Antragsseite sperrt bei jedem GET die Zeile und zählt in der Abstimmungsphase alle Stimmen aus. | `gremien/models.py:1097`, `:1129`, `:1620`, `:2317`, `verfahren/models.py:343` | halber Tag |
| A5 **M** | Übergangsregel `DDOE_UEBERGANGSREGEL` wird live gelesen, nicht mit dem Antrag eingefroren (§ 5 Abs 5); Umschalten während einer Abstimmung macht Nenner und Einzelprüfung uneins. | `config/settings.py:131`, `verfahren/views_aktionen.py:509` | halber Tag |
| A6 **M** | Anzeige des Abstimmungs-Chats fällt auf den Registerwert der Annahme-Schwelle zurück, die Entscheidung liest die eingefrorene Ordnung (Live-Anzeige zeigt die Schwelle heute nicht, das Archiv der laufenden Runde schon). Snapshots vor Ordnungs-Fassung 2 tragen kein `vorschlag_annahme_anteil` (Standard 0,5 statt Registerwert beim Einbringen). | `verfahren/chat.py:416`, `verfahren/archiv.py:189`, `plattform_core/policy.py:167` | Stunde |
| A7 **M** | Audit-Kette wird geschrieben, aber nirgends geprüft: kein Kommando, keine Seite, `nachrechnen.py` kennt sie nicht; der Export trägt nur `hash[:12]` ohne `vorgaenger`. Verwaltungs-Einträge erscheinen nirgends („öffentliches Audit-Log“ ist versprochen, es gibt nur die Spur je Antrag). | `plattform_core/hashchain.py:74`, `verfahren/archiv.py:275`, `mitglieder/verwaltung.py:15` | halber Tag |
| A8 **M** | Reaktionen im Abstimmungs-Chat (das Votum) werden beim Zurücknehmen hart gelöscht und nicht auditiert (Auswertung zum Fristzeitpunkt ist festgehalten). D-L6e nicht umgesetzt: Sperrfeststellung des Integritätsrats nur bei Software-Hinweis erreichbar. | `verfahren/chat.py:307`, `gremien/views.py:1112` | je halber Tag |
| A9 **M** | `Unterstuetzung.mitglied`, `StimmRegister.mitglied`, `Reaktion.mitglied` hängen per CASCADE am Konto (alle anderen Verfahrensbezüge PROTECT). Freitext-Begründungen zu Personen (Pause/Ausschluss) landen unveränderlich in der Kette. | `verfahren/models.py:576`, `:622`, `mitglieder/verwaltung.py:346` | Stunde |
| A10 **M** | Sicherung nur über Render-Snapshots, kein Export außerhalb des Anbieters, keine geprobte Wiederherstellung (die Partner-Checkliste verlangt beides). Kein Alarm bei 500/503. | `docs/BETRIEB-RENDER.md:81`, `config/settings.py:184` | halber Tag |
| A11 **N** | Postaufträge ohne Endzustand (stündlich ewig); Beitragserinnerung als synchrone Schleife mit hartem Text ohne Stempel; KI-Monatsbudget mit UTC-Monatsgrenze; `bewerben` und `demo_seed` mit UTC-Datum; Bestätigungslink reaktiviert ein ausgeschlossenes Konto; Anmeldelinks per GET verbraucht (Mail-Scanner); `art` statt `typ` in zwei Audit-Ereignissen; Prüfcode 40 Bit ohne Drossel. | `mitglieder/postausgang.py:74`, `beitraege_views.py:160`, `ki/models.py:59`, `views_aktionen.py:740`, `mitglieder/views.py:211`, `:326`, `views_aktionen.py:478` | je Stunde |

| A12 **H** | **Beitragsreferenz wechselt mit der Anmeldeadresse.** `beitragsreferenz` hasht `mitglied.username`; der Vier-Augen-Adresswechsel setzt `username = neue_email`. Willkommensbrief, Beitragsseite und QR tragen die alte Referenz; nichts hält sie fest. Daueraufträge und gedruckte Vorlagen laufen nach einem Adresswechsel ins Leere. | `mitglieder/auth_flows.py:85`, `mitglieder/models.py:453` | halber Tag |
| A13 **H** | **Frische Instanz ohne Gemeindeverzeichnis.** Die Registrierung verlangt eine Gemeinde aus dem Verzeichnis; `gemeinden_laden` steht in keinem Startbefehl (`render.yaml`, Dockerfile, Partner-Vorlagen) und in keiner Anleitung außer als „aktualisieren“. Ein Render-Neuaufbau oder eine Partner-Instanz kann niemanden registrieren (FB-M7 „in unter einer Stunde“ nicht einlösbar). | `mitglieder/views.py:61`, `render.yaml:31`, `docs/partner/EINRICHTUNG.md` | Stunde |
| A14 **M** | Bank: der Meldeknopf steht jedem Konto offen und teilt sich nur eine globale Drossel — ein ungeduldiges Konto verbraucht das PSD2-Tageskontingent für alle; Ablauf der Bankzustimmung (180 Tage) wird nicht geprüft; Beitragserinnerung geht an Testkonten und an frisch Registrierte ohne Eingang. Berichtswesenrat existiert seit 0.45, darf das Umsetzungsregister aber nicht fortschreiben (nur Admin; Texte sagen „bis es ihn gibt“). Austritt lässt Anstöße mit Kontoverweis und Freitext stehen. | `beitraege_views.py:79`, `:151`, `mitglieder/models.py:584`, `views_aktionen.py:943`, `profil.py:797` | je Stunde bis halber Tag |

### B · Oberfläche (was der Gründer täglich sieht)

| Nr. | Befund | Beleg | Aufwand |
|---|---|---|---|
| B1 **H** | **Direkt-Handlung aus Kachel/Feed-Zeile löscht das Feld.** `unterstuetzen` leitet auch bei Erfolg auf die Antragsseite (ignoriert `weiter`); `abstimmen` und `unterstuetzen` tun es in jedem Fehlerfall; die Antragsseite hat kein `#feld-x`, `hx-select` liefert nichts, `outerHTML` entfernt das Feld. Browser-Sonde: Unterstützung gespeichert, `#feld-filter` weg. Dazu: 403 (nicht stimmberechtigt, Mitwirkung ruht) bleibt mit htmx ohne jede Rückmeldung, weil die Kachel Knöpfe jedem Angemeldeten zeigt und `htmx:responseError` nicht behandelt wird; Chat-Fehler leeren das Textfeld und zeigen die Meldung erst auf der nächsten Seite. Kein Unit-Test fährt den HX-Pfad, kein Bildschirmtest klickt eine Kachel-Handlung. | `verfahren/views_aktionen.py:331`, `:290-306`, `:500-528`, `:352`, `_kachel.html:57`, `_chat.html:69`, `app.js:413` | Tag |
| B2 **M** | Gold-Haken „Erfasst“ (FB-A2 ✅) erscheint nie: `app.js` wertet `detail.elt` (das getauschte Feld) statt `requestConfig.elt` aus. Fokus geht nach jedem Feldtausch verloren (Knöpfe ohne `id`); gewählter Zustand und Fokusring sind identisch gestylt; Fokusring Gold auf Hell 2,25:1 (WCAG 3:1). Flash-Meldungen bei htmx-Aktionen bleiben liegen oder werden verworfen (Vorbild für richtig: `kategorie_abonnieren`). | `app.js:128`, `base.html:523`, `:357`, `views_aktionen.py:913` | Tag |
| B3 **M** | 459 Inline-Styles in 65 Templates gegen die Template-Regel; 69 KB Design-CSS in `base.html` wird je Seite ausgeliefert statt als gehashte statische Datei. | `gremien/fenster.html`, `base.html:9` | Tage (schrittweise) |
| B4 **N** | Kein `h1` im Parlament; vier stumme Tab-Stopps; Skelett-Schimmer flackert bei reduzierter Bewegung; harte rgba-Schatten; Erklärsätze auf Antragsseite/Chat/Archiv/Gremien-Beschlüsse (FB-N5 „StaatsSimulation … in Entwicklung“ beim Einbringen). | `parlament.html:16`, `base.html:535`, `einbringen.html:46`, `antrag.html:335` | je Stunde |

### C · Ehrlichkeit der Texte und Dokumente

| Nr. | Befund | Beleg | Aufwand |
|---|---|---|---|
| C1 **H** | **Startseite: „geheim … keinem Menschen zuzuordnen“** — ADR-003, README und die eigene Seite „Meine Stimme“ sagen das Gegenteil (Betreiber kann zuordnen). „Meine Stimme“ verspricht zudem eine Löschung der Zuordnung nach der satzungsmäßigen Frist, die es nicht gibt (D-K5b offen). ADR-003/README sagen „Personenwahlen nicht online“, Kandidatur und Vertrauensfrage laufen online. | `index.html:76`, `:132`, `:187`, `eigene_stimme.html:15`, `ADR-003:18`, `README.md:19` | Stunde |
| C2 **H** | **Willkommensseite nennt feste 3/12-Monats-Fristen**, die mit der Übergangsregel nicht gelten; Mail und /mitgliedschaft/ sagen das Gegenteil; die Seite wird auch pausierten Bestandsmitgliedern gezeigt. | `willkommen.html:6`, `mitglieder/views.py:268` | Stunde |
| C3 **H** | **Keine Datenschutzinformation** (kein Impressum/Datenschutz-Link, keine Seite); Registrierung verspricht „Keine Weitergabe“, während Art-9-Daten bei Render (US-Anbieter) liegen, Beratungstexte an Mistral gehen und die in `render.yaml` vorausgesetzte Einwilligung der Testmitglieder nirgends eingeholt wird. | `registrieren.html:37`, `render.yaml:15` | Tag (Text vom Gründer/Rechtsberatung, Einbau Stunde) |
| C4 **M** | Beitragsseite verspricht „wir prüfen automatisch weiter“, es läuft kein Zeitplan (CONCEPT F-59 sagt „anlassbezogen“). „Mitglied n“/„Ehemaliges Mitglied n“ tragen die technische ID, Profil/Austritt versprechen die Mitgliedsnummer. 18 Verwaltungs-/Gremien-Meldungen nicht übersetzbar (po_pruefen sieht sie nicht). Rollenmatrix verspricht „mit S9/S11“ für Gebautes; Regelverzeichnis-Wächter kennt keine Liste erledigter Schritte. | `beitraege_views.py:98`, `mitglieder/models.py:246`, `parameter/views.py:375`, `gremien/views.py:633`, `plattform_core/rollen.py:551` | je Stunde |
| C5 **M** | Dokumente hinken: CONTRIBUTING (Conventional Commits, DCO, „drei Anträge“), README-Landkarte ohne gremien/mandatare, BETRIEB-RENDER „Stand 20.08.“ (Python- vs. Docker-Runtime, demo_seed-Satz, Cron-Einzeiler), Partner-EINRICHTUNG (Tags, die es nicht gibt; Schema 1.5 statt 1.6; createsuperuser), CONCEPT Anhang A/„Dependency-Scans“, GOVERNANCE-Handle, CLAUDE.md (Version 0.40.0, „nächste ADR 010“), CHANGELOG 0.49.0 mit „-“. | je Datei | halber Tag gesamt |
| C7 **❓** | „Meistgelesene Anträge“ auf `/uebersicht/` ist eine Aufmerksamkeitsreihung von Anträgen außerhalb des Abstimmungs-Chats — von F-50 gefordert, von CLAUDE.md § 6 verboten, nicht versioniert. Entscheidung des Gründers: streichen, als Zahl je Antrag, oder als versionierte Kernregel offenlegen. | `uebersicht/views.py:168`, `uebersicht.html:111` | Stunde |
| C6 **N** | Rollenseite „keine Cookies außer Session/CSRF“ (Sprachcookie); Profil zählt Postarten unvollständig; „Danke für die Meldung“ ohne Speicherung. | `rollen.py:130`, `profil.html:73`, `beitraege_views.py:72` | je Stunde |

### D · Code, Tests, CI, Prozess

| Nr. | Befund | Beleg | Aufwand |
|---|---|---|---|
| D1 **H** | **Zeitabhängiger Test** (UTC-`strftime`) — rot zwischen 22 und 24 Uhr UTC; hier reproduziert; blockiert in dem Fenster den Deploy. | `mandatare/test_vertrauensfrage_ansichten.py:685` | Minuten |
| D2 **M** | **CI prüft nur SQLite**, Produktion ist PostgreSQL 16; Migrationen laufen erstmals live (je Migration atomar, Gesundheitscheck fängt einen scheiternden Start); `select_for_update` ist auf SQLite wirkungslos; das Extra `postgres` wird in keinem CI-Lauf aufgelöst. Der Postgres-Lauf hier war bis auf D1 grün — die Lücke ist heute ohne Schaden, aber ohne Netz. Dazu: kein `makemigrations --check`, nur Python 3.12, kein Dependabot, Dockerfile-Build ungeprüft. | `.github/workflows/ci.yml:9` | halber Tag |
| D3 **M** | **Prozess:** keine PRs seit 3.9., kein Branch-Schutz, zwei rote Läufe auf `main` in den letzten sechs; `docs/sichtpruefung` 85 MB im Repo. | GitHub | Stunde |
| D4 **M** | FB-B3-Höchstzahl in Overlay/Meldung als Konstante, Test zementiert „5 von 5“ (bestätigt). Nachrangig (Gegenprüfung: niedrig): Sperren der Vertrauensfrage als Klartext in `mandatare/models.py` statt im Kern; drei Ein-Zeilen-Regeln doppelt zwischen mandatare und verfahren; `hashchain`/`bankauszug` ohne VERSION (Regelverzeichnis führt sie bewusst mit `fassung=None`); Schonfrist/Wiederholungssperre der Vertrauensfrage als Konstante ohne Satzungsvermerk. | `mandatare/models.py:918`, `verfahren/views.py:375` | Tag |
| D5 **M** | App-Abdeckung wird nicht gemessen (hier einmalig: 90 % gesamt; `bank.py` 57 %, `beitraege_views.py` 62 %, `ausweis.py` 76 %, `gremien/views.py` 85 %); Sperrtests fehlen für Parameterregister-Aktionen und einige Gremien-Views; e2e ohne Browser ergibt Errors statt Skips. | `pyproject.toml:59`, `parameter/test_register.py` | Tag |
| D6 **N** | Toter `verfahren.views.gesund` (überdeckt), hartkodierte Pfade, Denglisch (`review_frist`, `policy_snapshot`), Großmodule (gremien/views 1 914, gremien/models 2 470, mandatare/views 1 708 Zeilen) — Abschnittsmarken zeichnen die Schnitte vor. | `verfahren/views.py:1391`, `gremien/views.py:408` | Tage (gelegentlich) |

### Widerlegt (nicht übernommen)
- Parlament-Reihung „nach Phase und Frist“ stimmt (gruppiert nach `PHASEN_RANG`, dann Fristende).
- Startseiten-Flussdiagramm liest laut FB-J1 bewusst das Register.
- Betriebs-Stellgrößen des Postausgangs/Tokens sind nach FB-J2 „Grenzen der Maschine“, keine Registerwerte.
- Deckelung von Bereich d (D-B1a) ist ausdrücklich Gründerentscheidung, kein Codefehler.

Abgeschwächt auf niedrig, weil abgesichert: Bankabruf blockiert den Worker nicht (Mindestabstand 180 s, Zeitlimit); toter `gesund`-Pfad ist durch `tests/test_betrieb.py` gegen Rückfall gesichert; Großmodule verletzen keine aufgestellte Regel.

## 3. Wie weiter — Vorschlag

Grundsatz: zuerst das, was falsch rechnet oder still liegen bleibt (A1–A3, D1), dann das, was der Gründer täglich sieht (B1–B2), dann Ehrlichkeit (C1–C3), dann Netz und Struktur (D2–D5), dann die Fachschritte nach Teil C. Jede Fassung ein Zweig `schritt/…`, PR gegen `main`, Sichtprüfung.

| Fassung | Inhalt | Aufwand | Braucht vom Gründer |
|---|---|---|---|
| **0.50.0 · Betrieb richtig rechnen** | A1 Testkonten aus allen Nennern und Zählungen; `demo_seed` legt Testkonten an; Live-Bestand per idempotenter Migration/Verwaltungsaktion markieren (eingefrorene Zahlen bleiben). A2 Fristen-Wächter im vorhandenen Hintergrundfaden (alle 10 Min. `alles_fortschreiben()` unter DB-Sperre, ein Worker) + Seiten schreiben „bis zum Stand“ fort; Betriebsdoku-Cron-Zeile korrigieren. A3 Status koppeln: `Rolle.hat` verlangt `darf_mitwirken`, Ausschluss beendet Rollen und streicht die Fachliste, Lostopf filtert. D1 Test lokalisiert. A4 Nachläufe unter Sperre und mit Fristzeitpunkt. A12 Referenz aus Mitgliedsnummer/festem Salz mit Einfrieren des Bestands. A13 `gemeinden_laden` in alle Startbefehle und Anleitungen. | 2,5 Tage | Kenntnisnahme A2 (kostenfreie Alternative zu D-J1a); ob Pause = Unterbrechung der Anwartschaft (❓ neu) |
| **0.50.1 · Ehrliche Texte** | C1 Startseite/„Meine Stimme“/ADR-003-Nachtrag; C2 Willkommensseite aus `stimmrechts_satz`; C4 Beitragsmeldungen, „Mitglied n“ auf Mitgliedsnummer, 18 Meldungen übersetzbar, Rollenmatrix Fassung 6 mit Wächter; C6. | 1 Tag | Wortlaut C1 zur Kenntnis |
| **0.51.0 · Direkt-Handlung repariert** | B1 HX-Weiche in `unterstuetzen`/`abstimmen`/Chat (Rückmeldung per `HX-Trigger`, Fehler im Feld, nie Antragsseite bei HX); Kachel zeigt Knöpfe nur, wer darf; `htmx:responseError` behandelt; B2 Gold-Haken, Fokus-Rückgabe, Fokusring-Token, Flash nur im Nicht-HX-Zweig; Unit-Tests je HX-Pfad, ein Bildschirmtest je Direkt-Handlung. | 2 Tage | Sichtprüfung |
| **0.51.1 · Datenschutz und Sicherung** | C3 Datenschutzseite (Verantwortlicher, Auftragsverarbeiter, Fristen, KI-Hinweis) + Link in Fußzeile/Registrierung/Anstoß; Registrierungstext; A10 täglicher externer `pg_dump` (GitHub-Action, verschlüsselt) und Wiederherstellungsprobe mit Kettenprüfung; A7 `audit_pruefen`-Kommando + Export mit `vorgaenger`/vollem Hash + globale Audit-Seite; A9 PROTECT. | 2 Tage | **Text der Datenschutzinformation (rechtlich), Speicherort der Sicherung** |
| **0.52.0 · Netz** | D2 Postgres-Job in CI (Migrationen, demo_seed zweimal, Suite), `makemigrations --check`, Python 3.11/3.12, Dependabot, Docker-Build; D3 Branch-Schutz `main` (Pflicht `pruefen`), Sichtprüfungsbilder auf die letzte Fassung reduzieren; D5 App-Abdeckung ausweisen, Sperrtests Register/Gremien; C5 Dokumente nachziehen. | 1,5 Tage | Branch-Schutz einschalten (GitHub-Einstellung), Entscheidung zu den Bildern |
| **0.53.0 · Teil-D-Empfehlungen** | D-L6e Sperr-Knopf ohne Hinweis; D-L6d MV-Bestätigung; D-K5b Stellgröße 90 Tage + Kappung im Wächter (löst auch C1-Löschversprechen ein); D-G5 Block „So kam der Vorschlag zustande“; D-D2 (b) als schlafender Parameter; A5 Übergangsregel einfrieren; A6 Schwelle aus Snapshot; A8 Reaktionen append-only. | 2 Tage | keine (Empfehlungsregel), Kenntnisnahme |
| **0.54.0 · S10b Sitzungsmodus** (FB-L5 B+C, D-L6g) | Modelle Sitzung/Livemeldung append-only, Karte in /mandatare/mein/, öffentliche Live-Seite, Rechenschaft aus dem Ticker. | 2–3 Tage | Gastzugang fremder Abgeordneter (D-L5a) ausdrücklich ausgeklammert |
| danach | FB-I1 Bestellweg § 6 Abs 8 (+ FB-K1 Flowchart-Include) · S14b Partner-Konto/Kontaktformular (D-M3/M4 gelten) · FB-L7 Gliederungen · S11 Zukunftswerkstatt Ring 1–2 (ADR sentence-transformers, Budget, RIS-Daten) · S12/S13 · D4/D6 Kernmodul `vertrauensfrage.py`, Schnitte der Großmodule | Wochen | D-B1a, D-C5, D-L5a, D-M8, Kosten S11 |

## 4. Fragen an den Gründer (vor dem Bauen)

1. **A2:** Darf der Fristen-Wächter im bestehenden Gunicorn-Hintergrundfaden laufen (kostenfrei, alle 10 Minuten), statt auf den bezahlten Render-Cron zu warten? D-J1a kannte diese Möglichkeit noch nicht.
2. **A1:** Sollen die fünf Demo-Konten der Live-Datenbank pausiert werden (dann verschwinden sie aus jedem Nenner ab dem nächsten Abstimmungsbeginn), oder nur als Testkonten aus der Zählung fallen? Bereits veröffentlichte Nenner bleiben unverändert (Grundregel 7).
3. **A3 / ❓ neu:** Gilt eine Pause wegen Beitragsrückstand als Unterbrechung der Anwartschaft (§ 4 Abs 4)? Der Code sagt nein; das Fahrtenbuch schweigt.
4. **C3:** Wer liefert den Datenschutztext (Verantwortlicher, Auftragsverarbeiter, Fristen)? Ich kann einen Entwurf vorlegen, freigeben muss ihn der Gründer bzw. Rechtsberatung.
5. **D3:** Branch-Schutz auf `main` mit Pflicht-Check `pruefen` (und `sichtpruefung`) einschalten? Das erzwingt den PR-Weg aus CLAUDE.md § 5.6 auch am Arbeitsplatz.
6. **C7:** „Meistgelesene Anträge“ auf der Übersicht behalten (dann als offengelegte, versionierte Regel), auf eine Zahl je Antrag reduzieren oder streichen? F-50 und CLAUDE.md § 6 widersprechen sich hier.
7. **D3:** Sichtprüfungsbilder: nur die letzte Fassung im Repo behalten (Historie am Arbeitsplatz), oder als CI-Artefakt?

## 5. Am Arbeitsplatz nachzutragen

- Fahrtenbuch: Kopf „Stand 28.9.2026“; FB-K8 ✅ (0.49.3, K8b–f erledigt); laufend-Zeile (K7, K8) durchstreichen; Teil C: Versionen S11–S13/S14b auf „0.5x (Vorschlag)“, S10b-Zeile mit Sollversion 0.54; A0-11 Nr. 2 Nachtrag „0.49 = FB-K8“; FB-K4, FB-P1 auf 🟡; FB-K3 Ist auf 0.49; FB-A2 auf 🟡 (Gold-Haken wirkt nicht, Direkt-Handlung löscht Feld); FB-B3 🟡 (Höchstzahl in Anzeige/Meldung als Konstante); FB-J2 Testverfahren ✅ seit 0.45; D-J1a um die kostenfreie Variante ergänzen; neuer ❓ „Pause = Unterbrechung der Anwartschaft?“; D-K5b mit dem Löschversprechen auf „Meine Stimme“ verknüpfen.
- Teil E/Prüfprotokoll: diese Bestandsaufnahme (8 Richtungen, 97 Rohbefunde, 5 widerlegt) mit Datum eintragen.
- CLAUDE.md: Version ohne feste Zahl, „nächste ADR-Nummer: 011“, § 6 Cookie-Satz um die Sprachwahl ergänzen.
- Memory: Postgres-Lauf hier grün bis auf den Zeit-Test; e2e hier 69 grün mit Chromium-1194-Symlink; Umgebung braucht `pip install cffi` wegen kaputter System-`cryptography`.
