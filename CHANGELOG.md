# Änderungsprotokoll

Format nach [Keep a Changelog](https://keepachangelog.com/de/), Versionierung nach [SemVer](https://semver.org/lang/de/).

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
