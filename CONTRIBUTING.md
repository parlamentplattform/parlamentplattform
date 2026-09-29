# Mitarbeiten

Danke, dass du hier bist. Dieses Projekt wird öffentlich entwickelt — jede Änderung, auch die des Kernteams, läuft als Pull Request mit Review.

## Einstieg in 10 Minuten
1. Repository klonen, `make dev`, `make test` — alles muss grün sein, bevor du beginnst.
2. `make run` und `make seed` — dann siehst du unter http://localhost:8000 Demo-Anträge in allen Phasen (Unterstützung, Beratung, Abstimmung, Beschluss, Kandidatur), fünf Demo-Konten `demo1…demo5` (Anmeldung per Link im Serverlog) und besetzte Gremien. `make seed` legt nur mit `DDOE_DEBUG=1`/`DDOE_DEMO=1` an; in Produktion tut es nichts.
3. Lies `docs/CONCEPT.md` (Was bauen wir und warum) und `docs/adr/` (Warum so).

## Regeln
- **Verhalten ändern heißt Test ändern.** Kein PR ohne Test, der das neue Verhalten festschreibt. Der Verfahrenskern (`plattform_core/`) hält ≥ 90 % Zweigabdeckung — die CI blockiert sonst.
- **Architekturentscheidungen sind Dokumente.** Wer etwas Grundsätzliches ändern will, schreibt zuerst einen ADR-Entwurf und stellt ihn zur Diskussion.
- **Deutsch im Fachcode, Englisch willkommen.** Fachbegriffe folgen der Satzung (Antrag, Unterstützung, Beratung …), damit Satzung und Code dieselbe Sprache sprechen. Issues und PRs gern auch auf Englisch.
- **Sicherheitsrelevantes** bitte nie als öffentliches Issue — siehe `SECURITY.md`.
- **Commits auf Deutsch, im Imperativ, mit der FB-Kennung aus dem Fahrtenbuch** — „Fächer auf fünf Ebenen ausbauen (FB-C2)“; ein Commit je logischem Teilschritt. Kein Conventional-Commits-Präfix, kein Sign-off, kein CLA (AGPL genügt).
- **Zweig und Pull Request:** Arbeit auf einem Zweig `schritt/<kennung>` (z. B. `schritt/s3-weicherfilter`), PR gegen `main`. Gemerged wird nur mit grünen Status-Checks `pruefen (3.11)` und `pruefen (3.12)` (SQLite) sowie `pruefen_postgres` (PostgreSQL 16 mit Startkette und `demo_seed`); `sichtpruefung` (Bildschirmtests) soll ebenfalls grün sein. Einen Check, der nur `pruefen` heißt, gibt es nicht — ein Branch-Schutz nennt die Namen mit Python-Fassung. Der Gründer merged.
- **Fahrtenbuch pflegen:** Jeder Bauschritt aktualisiert den Status seiner FB-Einträge in `docs/fahrtenbuch/DDOE_Fahrtenbuch_Detail_v1_2026-09-02.md` (✅/🟡 mit Datei:Zeile) und schreibt einen CHANGELOG-Abschnitt.

## Was wir gerade brauchen
Siehe die Issues mit dem Etikett `hilfe-gesucht` — von Code über Textkritik an Verfahrensbeschreibungen bis zu Tests der Barrierefreiheit. Auch Kritik am Konzept ist ein Beitrag: `didide@ddoe.at`.
