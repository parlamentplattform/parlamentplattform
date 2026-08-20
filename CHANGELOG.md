# Änderungsprotokoll

Format nach [Keep a Changelog](https://keepachangelog.com/de/), Versionierung nach [SemVer](https://semver.org/lang/de/).

## [0.9.0] — 2026-08-20 · Eine Wurzel, vier Säulen — und die Einführung

### Hinzugefügt
- **Kategorienbaum v2** (F-45): Alles führt jetzt auf **„Das gesellschaftliche Zusammenleben"** zurück — darunter vier Säulen (Sicherheit & Soziales Fundament · Wirtschaft, Arbeit & Finanzen · Lebensraum & Infrastruktur · Bildung, Entwicklung & Gesellschaft) und zwölf Bereiche mit den Beschreibungen des Parteigründers; darunter unverändert die bisherigen 295 Kategorien (312 Knoten, 6 Ebenen). Alle Slugs sind stabil geblieben — bestehende Favoriten und Zuordnungen überleben den Umbau
- **Fokus-Ansicht** (F-45): Jede Kategorie ist eine eigene Seite — oben der Stamm als klickbare Brotkrume bis zur Wurzel, in der Mitte der aktuelle Bereich mit Stern und laufenden Anträgen des Astes, darunter die Unterbereiche als Karten zum Hineinklicken. Dazu eine **Suche** über Namen, Beschreibungen und Schlagworte. Ohne JavaScript; die Ast-Zählung läuft jetzt mit zwei Datenbankabfragen statt einer je Knoten
- **Einführung nach der Bestätigung** (F-53): drei geführte, bebilderte Schritte — Lebensbereiche finden, die erste Abstimmung verstehen, einen Antrag einbringen lernen — mit Fortschrittsleiste, jederzeit überspringbar; Abschluss ist der Beitrags-QR. Der Bestätigungslink führt jetzt hierher
- Kategorie-Chips bei Anträgen sind verlinkt und zeigen den kurzen Pfad (letzte drei Ebenen)

### Geändert
- Alte Gesamtbaum-Seite durch die Fokus-Ansicht ersetzt; neue Texte vollständig übersetzt (Deutsch/Englisch)
- 8 neue Tests (120 gesamt)

## [0.8.0] — 2026-08-20 · Zweisprachig: Deutsch und Englisch

### Hinzugefügt
- **Vollständige englische Oberfläche** (F-33, vorgezogen): alle mitgliederseitigen Seiten, Formulare, Meldungen, Diagrammbeschriftungen und System-E-Mails; 232 übersetzte Texte. Umschalter **DE/EN** in der Kopfzeile (ohne JavaScript, per Django-`set_language`); ohne Wahl entscheidet die Browsersprache. Übersetzte, menschliche Phasennamen (Filter `phase_name`) statt technischer Werte — auch auf Deutsch eine Verbesserung („Unterstützung" statt „unterstuetzung")
- Kompilierter Sprachkatalog (`locale/en/…/django.mo`) ist eingecheckt — der Betrieb braucht kein gettext

### Geändert
- Inhalte (Anträge, Beratungen, Kategorienamen) bleiben bewusst in ihrer Originalsprache; mehrsprachige Kategorienamen folgen mit dem EuroVoc-Anschluss (ADR-007). Die Mitgliederverwaltung bleibt vorerst deutsch (internes Werkzeug)
- 5 neue Tests (112 gesamt)

## [0.7.0] — 2026-08-20 · Öffentliche Übersicht und Mitgliederverwaltung

### Hinzugefügt
- **Öffentliche Übersichtsseite** `/uebersicht/` (F-50): Mitglieder mit Verlauf, Anträge je Phase, neue Anträge je Woche, Besuche je Tag, meistgelesene Anträge — und je Abstimmung Ergebnis (Ja/Nein/Enthaltung) samt Beteiligung als 100-%-Balken. Abstimmungsverhalten ausschließlich als Summe; Einzelstimmen bleiben pseudonym. In Navigation und Fußzeile verlinkt
- **Servergerenderte SVG-Diagramme** (`plattform_core/diagramme.py`): Linie, Säulen, Anteilsbalken — ohne JavaScript, ohne Diagramm-Bibliothek; Farbpalette auf Farbfehlsichtigkeit geprüft, native Tooltips, Werte immer auch als Text (ADR-008)
- **Datensparsame Besuchszählung** (F-52): Tages-Summen je Plattform und je Antrag — keine Cookies, keine IP-Speicherung; anonyme Tageskennung, die um Mitternacht wertlos wird; Maschinen ausgefiltert; Zählweise öffentlich erklärt
- **Mitgliederverwaltung** `/verwaltung/` (F-51, ersetzt den Django-Admin): Suche und Filter, Stammdaten korrigieren (Gemeinde stets gegen das amtliche Verzeichnis), Identitätsstufe setzen, Beitragseingang vermerken, **pausieren** (Mitwirkungsrechte ruhen bis zum Beitragseingang), **ausschließen** (vollzieht den Beschluss nach § 4 Abs 6, umkehrbar), Admins ernennen und entziehen. Fixer Erstzugang per `DDOE_FIX_ADMIN` (Standard didide@ddoe.at) — immer Admin, unantastbar; niemand wirkt auf das eigene Konto. Jede Handlung im öffentlichen Audit-Log, ohne personenbezogene Werte
- Mitglied: Felder `status`, `status_grund`, `beitrag_zuletzt_am`, `ist_admin`; pausierte Mitglieder sehen einen Hinweis mit Beitrags-QR-Link, Mitwirkungs-Sperren greifen in allen handelnden Ansichten und in der Stimmberechtigung

### Geändert
- Django-Admin aus den URLs entfernt — `/verwaltung/` ist jetzt die eigene, auditierte Verwaltung
- Dokumentation auf den echten Stand gebracht: README (Phase 1, Live-Adresse), `docs/BETRIEB-RENDER.md` (Starter-Instanz, SMTP-Sperre auf Free-Instanzen, manueller Deploy nach Push, Postgres, `DDOE_FIX_ADMIN`), CONCEPT (F-50–F-52, Phasenstand), `render.yaml` (parlament.ddoe.at, vollständiger Startbefehl), neue ADR-008
- 18 neue Tests (107 gesamt)

## [0.6.1] — 2026-08-19 · Robuster Mailversand

### Behoben
- **Versandstörungen hinterlassen kein „halbes" Konto mehr:** Konto-Anlage und Bestätigungs-Mail laufen in einer Transaktion — scheitert der Versand (z. B. SMTP nicht erreichbar), wird alles zurückgerollt, die Adresse bleibt frei, und das Formular meldet die Störung ehrlich statt einer „E-Mail unterwegs"-Seite ohne E-Mail. Gleiches offenes Verhalten beim Anmeldelink
- **SMTP-Timeout** (`DDOE_SMTP_TIMEOUT`, Standard 20 s): Ein hängender Mailserver hält den Web-Worker nicht mehr bis zum Gunicorn-Timeout fest (vorher: 60 s Blockade + Fehler 500)

### Geändert
- 2 neue Tests (96 gesamt)

## [0.6.0] — 2026-08-19 · Captcha-Bild und amtliches Gemeindeverzeichnis

### Hinzugefügt
- **Sichtbares Captcha** (F-49): Die Sicherheits-Rechenfrage steht jetzt als verzerrtes Bild im Formular (selbst erzeugtes SVG mit Störlinien — kein Drittanbieter, keine Datenweitergabe); die Aufgabe erscheint nicht mehr im Seitentext. Temporär bis zur ID-Austria-Anbindung; Barrierefreiheits-Ausweich per E-Mail-Hinweis
- **Amtliches Gemeindeverzeichnis** (F-43): 2.092 Gemeinden (Statistik Austria, Gebietsstand 2026, CC BY 4.0) als `daten/gemeinden.csv` + `manage.py gemeinden_laden`. Die Wohnsitz-Gemeinde wird beim Registrieren live vorgeschlagen (natives Auswahlfeld, ohne JavaScript-Pflicht) und gegen das Verzeichnis geprüft: Tippfehler werden abgewiesen (mit Vorschlägen), mehrdeutige Namen wie „Krumbach" verlangen die Präzisierung „Name (Bezirk)", „Sankt"/„St." wird toleriert
- Bezirk und **Bundesland werden automatisch zugeordnet** (Feld entfällt im Formular); neuer Verweis `Mitglied.wohnsitz` ins Verzeichnis — Grundlage für die spätere Bezirks-Ebene regionaler Anträge

### Geändert
- Demo-Daten und Tests auf amtliche Gemeindenamen umgestellt; 2 neue Tests (94 gesamt)

## [0.5.0] — 2026-08-19 · Menschlichkeitsprüfung, Beitrags-QR, voller Kategorienbaum

### Hinzugefügt
- **Menschlichkeitsprüfung** (F-49) bei Registrierung und Anmeldelink — vier Lagen, ohne Drittanbieter, ohne JavaScript-Pflicht: Honigtopf-Feld, signierte Mindestzeit, Rechenfrage, IP-Drossel (5 Registrierungen bzw. 10 Anmeldelinks je Stunde und IP)
- **Zahlen mit Code** (F-38): EPC-QR-Code auf der Willkommensseite — Banking-App scannt, Empfänger/IBAN/persönliche Referenz sind vorausgefüllt; Überweisung direkt von Konto zu Konto, ohne Zahlungsdienstleister, ohne Prozentgebühren (neue Abhängigkeit: segno)
- **Kategorienbaum voll ausgebaut:** 295 Knoten — 24 Hauptkategorien, 96 Unterkategorien, 175 Detailkategorien über alle Lebensbereiche; die automatische Zuordnung trifft die Detailebene (z. B. „Tempo 30 vor Schulen" → Verkehr › Straßen › Tempolimits & Verkehrsberuhigung)
- Konzept: F-48 (spätere App mit klar getrenntem, opt-in „Für dich"-Bereich — beeinflusst nie die gemeinsame Reihung), F-49 dokumentiert

### Geändert
- Einheitliches **Favoriten**-Wording für Lebensbereiche (statt „Abo"): „Favorisieren Sie, was Sie betrifft: Neues daraus erscheint in Ihrem Hauptfenster unter Favoriten. Favoriten sind rein persönlich und beeinflussen nie ein Ergebnis." — Detailkategorien sind einzeln favorisierbar
- 5 neue Tests (92 gesamt)

## [0.4.0] — 2026-08-19 · Kategorienbaum, automatische Zuordnung, Regionalbindung

### Hinzugefügt
- **Kategorienbaum** (F-45, ADR-007): 24 Hauptkategorien (Lebensbereiche) mit ~100 Unter- und Detailkategorien in `policies/kategorien-v1.yaml` (z. B. Wirtschaft › Bauwirtschaft › Installateur) — versioniert, stabile Slugs, Deaktivieren statt Löschen, kein „Sonstiges"; EuroVoc-Domänen als Anschluss-Ebene für RIS/EUR-Lex; Import per `manage.py kategorien_laden` (rekursiv, idempotent)
- **Automatische Zuordnung** (F-47, Stufe 1): Beim Einbringen ordnet die Plattform den Antrag selbst in den Baum ein — niemand kreuzt Kategorien an. Deterministische, nachrechenbare Schlagwort-Klassifikation (`plattform_core/klassifikation.py`), tiefste passende Ebene gewinnt, Vorfahren werden nicht doppelt vergeben; jede Zuordnung wird auditiert; Stufe 2 ersetzt die Schlagworte durch lokale Embeddings bei gleicher Schnittstelle
- **Kategorie-Abos mit Ast-Wirkung** (F-46): Ein Abo (z. B. „Energie") umfasst alle Unterkategorien; Bereich a zeigt „Neu in Ihren Lebensbereichen"; Baum-Seite mit Aufklapp-Unterkategorien und Abo je Knoten
- **Regionalbindung** (F-43): Regionale Anträge nur in der ansässigen Region — Mitglieder erfassen Gemeinde und Bundesland bei der Registrierung, das Gebiet eines Antrags kommt zwingend aus dem Wohnsitzprofil (keine freie Eingabe, Manipulationsversuche laufen ins Leere); Ebenen-Auswahl zeigt „Meine Gemeinde (…)" / „Mein Bundesland (…)"

### Geändert
- Einbringen-Formular ohne Kategorien- und Gebietsfelder (automatisch bzw. profilgebunden); Erfolgsmeldung nennt die automatisch zugeordneten Lebensbereiche; Antrags-Chips zeigen den vollen Pfad

## [0.3.0] — 2026-08-19 · Das Hauptfenster in vier Bereichen

### Hinzugefügt
- Startseite als **Hauptfenster nach § 5 Abs 10 des Satzungsentwurfs 2.2** (Leitgestalt aus Satzung 1.3): a) persönliche Favoriten, b) hervorgehobene Abstimmungen, c) regionaler Bereich, d) Anträge & Gesetzesvorschläge (F-40)
- **Favoriten** (F-41): Stern an jedem Antrag; laufende Abstimmungen der eigenen Favoriten stehen im Hauptfenster zuerst. Favoriten sind rein persönlich und wirken nie auf Reihung oder Ergebnis
- **Hervorhebung wichtiger Abstimmungen** (F-42): Felder `hervorgehoben` + öffentliche Begründung am Antrag; Entscheidung des Integritätsrats (im Prototyp über die Verwaltung), niemals eines Algorithmus — die Begründung wird im Hauptfenster und am Antrag angezeigt
- **Regionale Ebenen** (F-43): Anträge tragen Ebene (Bund/Land/Bezirk/Gemeinde) und Gebiet; das Einbringen-Formular fragt beides ab (Gebiet ist bei regionalen Anträgen Pflicht), regionale Anträge erscheinen im Bereich c
- **Ähnlichkeitsübersicht mit Beteiligung** (F-44): Die Treffer beim Einbringen zeigen jetzt die Zahl der Unterstützungen; Hinweis auf die kommende Folgenabschätzung per StaatsSimulation (F-36) direkt im Formular
- Acht neue Ansichts-Tests (77 gesamt); Demo-Daten decken alle vier Bereiche ab; F-40 bis F-44 im Konzept dokumentiert

## [0.2.0] — 2026-08-19 · Phase 1: Benutzbare Plattform

### Hinzugefügt
- Selbstregistrierung mit Double-Opt-in (F-37): Konto wird erst mit bestätigter E-Mail aktiv; Anwartschaft (§ 4 Abs 4) beginnt mit der Bestätigung; Willkommensseite mit persönlicher Beitragsreferenz und IBAN (F-38)
- Passwortloser Login per E-Mail-Einmallink (30 min gültig, nur als SHA-256-Hash gespeichert); Architektur vorbereitet für den späteren Umstieg auf ID Austria (F-39, ADR-002)
- Antrag einbringen im Browser (F-10) mit Ähnlichkeitshinweis (F-35, ADR-006): rein lexikalischer Trigramm-Jaccard-Vergleich, deterministisch und von Hand nachrechenbar; der Hinweis schlägt vor und blockiert nie (§ 2 Abs 6) — „Trotzdem einbringen“ ist immer gleichwertig möglich
- Unterstützen (umschaltbar), Beratungsbeiträge (nur in offenen Phasen) und Abstimmen (Ja/Nein/Enthaltung, änderbar bis Fristende) direkt auf der Antragsseite
- Feststellung der Stimmberechtigtenzahl automatisch bei Abstimmungsbeginn — festgeschrieben und danach unveränderlich (§ 4 Abs 4 lit a); Übergangsregel § 4 Abs 4 lit d über `DDOE_UEBERGANGSREGEL` konfigurierbar
- Stimmlisten-Export als JSON je Antrag (erst nach Abstimmungsende, § 5 Abs 3 lit d), kompatibel mit `verify/nachrechnen.py`; Seite „Meine Stimme prüfen“ zeigt das eigene Pseudonym (F-21)
- Ansichts-Tests für alle Flüsse (Registrierung, Login, Einbringen inkl. Ähnlichkeit, Schwellen-Übergang, Anwartschafts-Prüfung, Export-Sperre, unabhängiges Nachrechnen im Test)
- ADR-006 (Ähnlichkeitshinweis und Folgenabschätzung in drei Stufen), Konzept-Kapitel 3.4 (F-35 bis F-39)

### Geändert
- Basis-Layout mit Anmelde-Navigation, Statusmeldungen und Formular-Stilen; Antragsseite zeigt Fristen, Beratung und Handlungs-Schaltflächen je nach Phase und Berechtigung
- `ruff format` einheitlich über die gesamte Codebasis angewendet (reine Formatierung, keine Verhaltensänderung)

## [0.1.0] — 2026-08-19 · Phase 0: Fundament

### Hinzugefügt
- Verfahrenskern `plattform_core`: Phasenautomat (§ 5 Abs 3), Policy-Modell mit satzungsfesten Untergrenzen und Einfrier-Mechanik (§ 5 Abs 5), ganzzahlig exakte Auszählung (§ 5 Abs 4), Stimmberechtigung mit Anwartschaftslogik (§ 4 Abs 4), Audit-Hash-Kette (§ 5 Abs 8)
- Eigenschaftstests (Hypothesis) für Reihenfolgeunabhängigkeit, Monotonie, Determinismus, Endgültigkeit von Endphasen und Manipulationserkennung; Kern-Zweigabdeckung ≥ 90 % als CI-Pflicht
- Django-Anwendung: Mitglieder mit Identitätsstufen, Anträge mit Fassungshistorie und Policy-Snapshot, getrenntes Stimmregister (Pseudonym ↔ Person, zugriffsbeschränkt), read-only-Audit-Admin
- Unabhängiges Nachrechen-Skript `verify/nachrechnen.py` (nur Standardbibliothek)
- Verfahrensordnung als versionierte YAML (`policies/`), Demo-Seed, Docker-Compose-Setup, CI (ruff, pytest, Coverage-Gate), ADR-001 bis ADR-005, Konzeptdokument mit Satzungs-Traceability
