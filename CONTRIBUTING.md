# Mitarbeiten

Danke, dass du hier bist. Dieses Projekt wird öffentlich entwickelt — jede Änderung, auch die des Kernteams, läuft als Pull Request mit Review.

## Einstieg in 10 Minuten
1. Repository klonen, `make dev`, `make test` — alles muss grün sein, bevor du beginnst.
2. `make run` und `make seed` — dann siehst du unter http://localhost:8000 drei Anträge in drei Phasen.
3. Lies `docs/CONCEPT.md` (Was bauen wir und warum) und `docs/adr/` (Warum so).

## Regeln
- **Verhalten ändern heißt Test ändern.** Kein PR ohne Test, der das neue Verhalten festschreibt. Der Verfahrenskern (`plattform_core/`) hält ≥ 90 % Zweigabdeckung — die CI blockiert sonst.
- **Architekturentscheidungen sind Dokumente.** Wer etwas Grundsätzliches ändern will, schreibt zuerst einen ADR-Entwurf und stellt ihn zur Diskussion.
- **Deutsch im Fachcode, Englisch willkommen.** Fachbegriffe folgen der Satzung (Antrag, Unterstützung, Beratung …), damit Satzung und Code dieselbe Sprache sprechen. Issues und PRs gern auch auf Englisch.
- **Sicherheitsrelevantes** bitte nie als öffentliches Issue — siehe `SECURITY.md`.
- Commits nach [Conventional Commits](https://www.conventionalcommits.org/); Sign-off nach [DCO](https://developercertificate.org/) (`git commit -s`), kein CLA.

## Was wir gerade brauchen
Siehe die Issues mit dem Etikett `hilfe-gesucht` — von Code über Textkritik an Verfahrensbeschreibungen bis zu Tests der Barrierefreiheit. Auch Kritik am Konzept ist ein Beitrag: `didide@ddoe.at`.
