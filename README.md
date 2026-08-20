# ParlamentPlattform

**Die offene Beteiligungs- und Entscheidungsinfrastruktur der Direkte Demokratie Österreich (DDÖ).**

Eine Partei ohne inhaltliches Programm braucht ein Verfahren, dem man nicht glauben muss, weil man es nachrechnen kann. Dieses Repository ist dieses Verfahren: Anträge einbringen → unterstützen → beraten → abstimmen → dauerhaft veröffentlichen — mit Regeln, die beim Einbringen eingefroren werden, einem Audit-Log, das Manipulation erkennbar macht, und einer Auszählung, die jede und jeder unabhängig überprüfen kann.

**Status: Phase 1 — der Prototyp ist öffentlich:** **[parlament.ddoe.at](https://parlament.ddoe.at)**. Der Verfahrenskern steht und ist getestet; Registrierung, Verfahrensweg, Kategorienbaum, öffentliche Übersicht und Mitgliederverwaltung laufen. Fahrplan und vollständiges Lastenheft: [`docs/CONCEPT.md`](docs/CONCEPT.md), Betrieb: [`docs/BETRIEB-RENDER.md`](docs/BETRIEB-RENDER.md). *English summary below.*

---

## Warum dieses Projekt anders gebaut ist

1. **Nachrechenbar ohne Spezialkenntnisse** (Satzung § 5 Abs 8). Die gesamte Verfahrenslogik liegt in [`plattform_core/`](plattform_core/) — wenige hundert Zeilen frameworkfreies Python, geschrieben zum Lesen. Zu jedem Ergebnis gehört eine unabhängige Zweitimplementierung: [`verify/nachrechnen.py`](verify/nachrechnen.py), nur Standardbibliothek.
2. **Die Regeln frieren ein** (§ 5 Abs 5). Beim Einbringen wird die gültige Verfahrensordnung als unveränderliche Kopie am Antrag gespeichert. Keine Mehrheit, kein Admin, kein Deployment kann ein laufendes Verfahren umkonfigurieren — der Code hat dafür schlicht keinen Pfad.
3. **Niemand kuratiert im Verborgenen.** Anträge sortieren sich nach Phase und Frist, nie nach Beliebtheit. Es gibt keinen Feed und keinen Algorithmus mit Meinung.
4. **Offen, ohne kaperbar zu sein** (§ 4 Abs 4). Ein Konto je Mensch, geprüfte Identität, Anwartschaftsfristen — im Code, nicht im Kleingedruckten.
5. **Ehrlich über Grenzen.** Sachabstimmungen sind pseudonym-offen und verifizierbar — nicht kryptografisch geheim, weil geheime Online-Abstimmung und Laien-Überprüfbarkeit einander nach heutigem Stand ausschließen. Warum wir so entschieden haben: [ADR-003](docs/adr/ADR-003-offene-verifizierbare-abstimmung.md). Geheime Personenwahlen laufen per Präsenz und Brief.

## Schnellstart

Mit Docker (PostgreSQL wie in Produktion):

```bash
docker compose up --build
# → http://localhost:8000  ·  Übersicht: /uebersicht/  ·  Verwaltung (Admins): /verwaltung/
```

Ohne Docker (SQLite, Python ≥ 3.11):

```bash
make dev        # virtuelle Umgebung + Abhängigkeiten
make run        # Migrationen + Entwicklungsserver
make seed       # Demo-Daten: drei Anträge in drei Phasen
make test       # Tests inkl. Property-based Tests, Kernabdeckung ≥ 90 %
```

Ein Ergebnis unabhängig nachrechnen:

```bash
python3 verify/nachrechnen.py export.json
```

## Aufbau des Repositories

| Pfad | Inhalt |
|---|---|
| `plattform_core/` | Der Verfahrenskern: Phasenautomat, Fristen, Stimmberechtigung, Auszählung, Audit-Hash-Kette, SVG-Diagramme. Frameworkfrei, vollständig getestet. |
| `verfahren/`, `mitglieder/` | Django-Anwendung: Datenmodelle, Ansichten, Mitgliederverwaltung (F-51). Speichert Zustand, ruft den Kern. |
| `uebersicht/` | Öffentliche Übersichtsseite und datensparsame Besuchszählung — Tages-Summen, keine IP-Adressen, keine Cookies ([ADR-008](docs/adr/ADR-008-uebersicht-und-zaehlung.md)). |
| `policies/` | Die Verfahrensordnung als versionierte, maschinenlesbare Daten ([ADR-004](docs/adr/ADR-004-policies-als-daten.md)). |
| `verify/` | Unabhängiges Nachrechen-Skript, nur Standardbibliothek. |
| `docs/CONCEPT.md` | Lastenheft und technisches Konzept mit Satzungs-Traceability. |
| `docs/adr/` | Alle Architekturentscheidungen mit Begründung. |
| `tests/` | Beispiel- und Eigenschaftstests (Hypothesis) des Kerns. |

## Mitmachen

Beiträge sind ausdrücklich willkommen — von Code über Textkritik bis Barrierefreiheits-Tests. Der Einstieg steht in [`CONTRIBUTING.md`](CONTRIBUTING.md), Sicherheitsmeldungen in [`SECURITY.md`](SECURITY.md), Projektsteuerung in [`GOVERNANCE.md`](GOVERNANCE.md). Kontakt: [didide@ddoe.at](mailto:didide@ddoe.at) · [ddoe.at](https://www.ddoe.at)

Lizenz: [AGPL-3.0-or-later](LICENSE) — wer diese Software betreibt, auch verändert als Netzwerkdienst, muss den Quellcode offenlegen. Für ein demokratisches Werkzeug ist das keine Einschränkung, sondern der Punkt.

---

## English summary

**ParlamentPlattform** is the open deliberation and decision infrastructure of Direct Democracy Austria (DDÖ): propose → support → deliberate (≥ 21 days) → vote (≥ 7 days) → publish permanently. A public prototype is live at [parlament.ddoe.at](https://parlament.ddoe.at). Its distinguishing properties: procedural rules are **frozen per motion at submission** (no majority can change a running game), every tally is **independently recomputable by laypeople** (a stdlib-only second implementation lives in `verify/`), an **append-only hash-chained audit log** with externally published anchors makes tampering detectable, and votes are **pseudonymous-verifiable rather than cryptographically secret** — a deliberate, documented choice ([ADR-003](docs/adr/ADR-003-offene-verifizierbare-abstimmung.md)). Core logic is a small framework-free Python package; the web layer is boring-by-design Django. We welcome international collaboration: didide@ddoe.at.
