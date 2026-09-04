# CLAUDE.md — ParlamentPlattform (Direkte Demokratie Österreich)

Diese Datei steuert Claude Code in diesem Repository. Sie ist knapp; die Tiefe steht in den verlinkten Dokumenten. **Lies vor jeder Arbeit zuerst das Fahrtenbuch.**

## 1. Was das hier ist

Die **ParlamentPlattform** ist die Mitgliederversammlung der Partei DDÖ als Software (Satzungsentwurf 2.5 § 5): Anträge einbringen → unterstützen → beraten (Expertenrat, Zukunftswerkstatt) → geheim abstimmen → nachrechenbar auszählen → Umsetzungsregister. Django 5 / PostgreSQL 16 (SQLite in Entwicklung), server-gerendert, htmx 2 + Alpine.js 3 als eingecheckte Dateien, kein SPA, kein CDN, kein Tracking. Lizenz AGPL-3.0-or-later. Version laut CHANGELOG (0.39.3 am 4.9.2026). Produktion: https://parlament.ddoe.at (Render, Auto-Deploy nach grüner CI auf `main`).

## 2. Die maßgeblichen Dokumente (in dieser Reihenfolge lesen)

> **Der Ordner `docs/fahrtenbuch/` ist intern und liegt nicht im Repository** (`.gitignore`, seit 3.9.2026): Er trägt die wörtlichen Anweisungen des Gründers, Bauplan, Soll/Ist, Inventar, Website-Prüfung und den Satzungsentwurf. Auf dem Arbeitsplatz des Gründers liegt er unter `parlamentplattform-phase0/docs/fahrtenbuch/`, Kopien im Arbeitsordner (`DDOE-code/claude-code-uebergabe/`). Wer ohne diesen Ordner arbeitet (CI, fremder Klon), findet die öffentliche Fassung der Zusammenarbeit in `docs/partner/` und `docs/SCHEMA.md`.

1. `docs/fahrtenbuch/DDOE_Fahrtenbuch_Detail_v1_2026-09-02.md` — **der Bauplan.** Jede Forderung des Gründers als FB-Kennung mit Zitat, Spezifikation, Abnahme, Ist, Delta. Teil C = Reihenfolge der Bauschritte S1–S14. Teil D = offene Entscheidungen (ohne Antwort gilt die Empfehlung).
2. `docs/fahrtenbuch/DDOE_Design_Spezifikation_App-Look.md` — Tokens, Layouts, Komponenten, Bewegung, Zustände, Barrierefreiheit, Bildschirmtests.
3. `docs/fahrtenbuch/DDOE_SollIst_Abgleich_2026-09-02.md` — was fehlt, was anders ist, Widersprüche im Code.
4. `docs/fahrtenbuch/Funktionsinventar_Ist_2026-09-02.md` — der Code, Seite für Seite, mit Datei:Zeile (Stand 0.32.0).
5. `docs/CONCEPT.md` — Lastenheft (F-01…F-71, Leitplanken L1–L7), `docs/adr/` — Architekturentscheidungen (nächste Nummer: 010).
   Öffentlich für Schwesterparteien: `docs/SCHEMA.md` (Austauschformate, § 12 Abs 5) und `docs/partner/` (Vision, Einstieg, Einrichtung, Satzungs-Baukasten — Erzeugnis von `tools/satzung_baukasten.py`).
6. `docs/fahrtenbuch/Satzung_DDOE_2.5_Entwurf.md` — die Regeln, auf die sich alles bezieht (§ 2 Abs 6, § 5, § 6, § 7, § 12).

Wenn Fahrtenbuch und Code sich widersprechen, gilt das Fahrtenbuch. Wenn Fahrtenbuch und Satzung sich widersprechen, gilt die Satzung — und das Fahrtenbuch bekommt einen ❓-Eintrag.

## 3. Die sieben Grundregeln (verletze keine davon — auch nicht „nur kurz")

1. **Werkzeug, keine Werbefläche:** kein Erklär-/Werbesatz im Parlament, auf Antragsseiten, in Gremien-Bereichen.
2. **App, nicht Homepage:** bildschirmfüllend, direkt bedienbar, gerichtete kurze Bewegung (Design-Spezifikation).
3. **Ohne JavaScript bleibt alles bedienbar.** htmx/Alpine/CSS sind Zugabe. `prefers-reduced-motion` respektieren.
4. **Keine Stimmgewichtung, nie.** Kein Parameter, kein Code-Pfad darf eine Stimme mehr wiegen lassen als eine andere. (Betroffenheitsregeln nach § 5 Abs 6 sind ein eigener, noch nicht gebauter Baustein und brauchen einen Satzungsbeschluss.)
5. **Die KI schlägt vor, sie entscheidet nie.** Jeder Modell-Aufruf läuft über `ki.lauf_ausfuehren` (Steckplatz, Archiv, Budget, Kennzeichnung). Keine KI schreibt in die Faktenbasis. Keine automatische Priorisierung, Zurückweisung, Hervorhebung.
6. **Keine verdeckte Reihung.** Jede Sortierung ist offengelegt, versioniert, nachrechenbar (`plattform_core`, Parameterregister). Voreinstellungen neutral.
7. **Nichts wird gelöscht, was Verfahren betrifft:** Audit-Kette (`AuditEintrag.anhaengen`), append-only-Fassungen, eingefrorene Policy je Antrag (§ 5 Abs 5). Archivieren = Sichtbarkeit ändern, nicht entfernen.

## 4. Arbeiten im Repo

```bash
make dev        # venv + pip install -e ".[dev]"
make test       # coverage run -m pytest -q  (plattform_core ≥ 90 % Zweigabdeckung ist Pflicht)
make lint       # ruff check .
make run        # migrate + runserver
make seed       # demo_seed (Demo-Mitglieder demo1…demo5, Anträge je Phase, Gremien-Rollen)
python manage.py makemessages -l en --no-location && python manage.py compilemessages  # nach jedem neuen Text
python tools/po_pruefen.py --mo   # Ersatz ohne gettext: Katalog prüfen und .mo schreiben
python -m pytest tests/e2e -q     # Bildschirmtests (Playwright); DDOE_SICHTPRUEFUNG=1 legt die Bilder ab
```
- Python ≥ 3.11, Django 5.x; **keine neuen Abhängigkeiten ohne ADR** (Ausnahme: `playwright` als dev-Abhängigkeit für `tests/e2e/`, `sentence-transformers` für Ähnlichkeit Stufe 2 mit ADR).
- Sprache im Code: **Deutsch** für Fachbegriffe (Antrag, Unterstuetzung, Entwurf, Fassung, Rolle, Gremium, Kachel, Feld), englische Framework-Begriffe bleiben englisch. Kein Denglisch in Nutzer-Texten.
- Fachlogik ohne Django in `plattform_core/` (rein, getestet, mit Hypothesis wo sinnvoll); Django-Apps rufen sie auf. Neue Regeln (Reihung, Auswertung, Layout) gehören dorthin, versioniert (`VERSION = n`).
- Jede schreibende Verwaltungs-/Gremien-Handlung → `AuditEintrag.anhaengen({...})` ohne personenbezogene Werte.
- Jede Stellgröße → `parameter.zahl(schluessel, standard)` mit Erstbestand in `parameter/models.py` (ERSTBESTAND) und Schema-Kennung; **keine neuen harten Konstanten**.
- Jeder Nutzer-Text übersetzbar (`{% trans %}`/`gettext`), Verwaltungs-Templates eingeschlossen; `.po` pflegen, `.mo` kompilieren.
- Templates: `verfahren/templates/verfahren/base.html` ist das Design-System (Tokens oben). Keine Inline-Handler (`onclick`, `oninput`), keine Inline-Styles außer berechneten Positionen (Fächer). Alpine-Direktiven + htmx-Attribute.
- htmx-Feldtausch: `hx-target="#feld-x" hx-select="#feld-x" hx-swap="outerHTML transition:true"`; Rückmeldung per `HX-Trigger`-Header, nicht per Flash.
- Migrationen: eine je Schritt, benannt nach Inhalt; Datenmigrationen idempotent.
- Tests: je App `test_*.py`; neue Funktion = neuer Test; Sperren/Rechte (Gast, Mitglied, bestätigt, Rolle, Admin) immer testen; „Untätigkeit hemmt nie" bleibt getestet.
- Bildschirmtests (`tests/e2e/`, Playwright, Chromium): Desktop 1440×900, Handy 390×844, hell/dunkel, mit und ohne JavaScript; Screenshots nach `docs/sichtpruefung/<version>/`.

## 5. Definition of Done je Bauschritt (Teil C des Fahrtenbuchs)

1. Alle FB-Abnahmekriterien des Schritts erfüllt und **im Fahrtenbuch der Status aktualisiert** (✅/🟡 mit Datei:Zeile).
2. `make lint` und `make test` grün; plattform_core-Abdeckung ≥ 90 %; `python manage.py check --deploy` ohne neue Warnung.
3. Übersetzungen vollständig (`makemessages` zeigt 0 fuzzy/leer).
4. CHANGELOG.md: neuer Abschnitt `## [0.xx.0] — Datum · Titel` (Keep a Changelog, Deutsch); `pyproject.toml` + `plattform_core.__version__` auf dieselbe Nummer.
5. Screenshots/GIF unter `docs/sichtpruefung/<version>/` (der Gründer prüft von Hand).
6. Ein Commit je logischem Teilschritt, deutsche Commit-Nachricht im Imperativ („Fächer auf fünf Ebenen ausbauen (FB-C2)"), FB-Kennungen in der Nachricht; Branch `schritt/s3-weicherfilter` → PR gegen `main` (Status-Check `pruefen` muss grün sein); der Gründer merged.
7. Nichts deployen, was den Demo-Betrieb bricht: `demo_seed` muss auf leerer und auf bestehender Datenbank durchlaufen.

## 6. Nicht tun

- Keine Stimmgewichte, keine algorithmische Priorisierung, kein Engagement-Ranking außerhalb des ausdrücklich beschriebenen Abstimmungs-Chats (FB-G6, dort offen und als Parameter).
- Keine Webfonts, kein CDN, keine Analytics, keine Cookies außer Session/CSRF.
- Keine Löschung/Änderung von Audit-, Stimm-, Fassungs- oder Archivdaten; keine `--fake`-Migrationen in Produktion.
- Keine Änderung der Satzungstexte im Repo (nur der Gründer); Satzungsbezüge (§) korrekt zitieren.
- Keine Erklärtexte in Arbeitsbereiche; keine englischen UI-Texte ohne deutsche Quelle.
- Keine Secrets in Code oder Doku (`DDOE_KI_SCHLUESSEL`, SMTP, Bank).
- Keine Force-Pushes auf `main`.

## 7. Fallstricke

- Windows: `git status` zeigt 40 „geänderte" Dateien durch CRLF → `.gitattributes` mit `* text=auto eol=lf` anlegen und `git add --renormalize .` (einmalig, eigener Commit).
- `demo_seed` läuft in Produktion bei jedem Deploy (`render.yaml`) — beim Umbau auf `DDOE_DEMO=1` achten, dass die Demo-Daten des Alpha-Betriebs erhalten bleiben (Wächter idempotent).
- `antrag_detail` schreibt bei jedem GET (`fortschreiben`) — Phasenautomatik ist lazy; Tests, die Zeit brauchen, nutzen Zeitraffer über `phase_beginn`.
- Die Website ddoe.at (WordPress) ist **nicht** in diesem Repo; Änderungen dort laufen über die REST-API (siehe `docs/fahrtenbuch/Website_Ist_Live_2026-09-02.md`, Bereich O des Fahrtenbuchs) und nicht über Claude Code, sofern der Gründer nichts anderes sagt.
- E-Mails: ohne `DDOE_SMTP_HOST` Konsolen-Backend (Login-Links stehen im Serverlog).

## 8. Wer entscheidet

Der Gründer (Michael Hackl, didide@ddoe.at / oisxeng auf GitHub). Bei ❓-Punkten (Fahrtenbuch Teil D) gilt die Empfehlung, bis er anders entscheidet — die Entscheidung wird dann im Fahrtenbuch eingetragen. Claude Code fragt bei Unklarheit **vor** dem Bauen, nicht danach; es baut nie über eine Grundregel hinweg.
