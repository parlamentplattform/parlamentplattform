# Änderungsprotokoll

Format nach [Keep a Changelog](https://keepachangelog.com/de/), Versionierung nach [SemVer](https://semver.org/lang/de/).

## [0.1.0] — 2026-08-19 · Phase 0: Fundament

### Hinzugefügt
- Verfahrenskern `plattform_core`: Phasenautomat (§ 5 Abs 3), Policy-Modell mit satzungsfesten Untergrenzen und Einfrier-Mechanik (§ 5 Abs 5), ganzzahlig exakte Auszählung (§ 5 Abs 4), Stimmberechtigung mit Anwartschaftslogik (§ 4 Abs 4), Audit-Hash-Kette (§ 5 Abs 8)
- Eigenschaftstests (Hypothesis) für Reihenfolgeunabhängigkeit, Monotonie, Determinismus, Endgültigkeit von Endphasen und Manipulationserkennung; Kern-Zweigabdeckung ≥ 90 % als CI-Pflicht
- Django-Anwendung: Mitglieder mit Identitätsstufen, Anträge mit Fassungshistorie und Policy-Snapshot, getrenntes Stimmregister (Pseudonym ↔ Person, zugriffsbeschränkt), read-only-Audit-Admin
- Unabhängiges Nachrechen-Skript `verify/nachrechnen.py` (nur Standardbibliothek)
- Verfahrensordnung als versionierte YAML (`policies/`), Demo-Seed, Docker-Compose-Setup, CI (ruff, pytest, Coverage-Gate), ADR-001 bis ADR-005, Konzeptdokument mit Satzungs-Traceability
