# Änderungsprotokoll

Format nach [Keep a Changelog](https://keepachangelog.com/de/), Versionierung nach [SemVer](https://semver.org/lang/de/).

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
