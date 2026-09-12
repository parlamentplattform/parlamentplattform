# SCHEMA.md — Die Schnittstelle zwischen den Landesinstanzen

*Satzung § 12 Abs 5 · Fahrtenbuch FB-M5/M6 · ADR-009 · Schema-Version **1.5** (12.9.2026)*

Die ParlamentPlattform wird je Land als **eigene Instanz** betrieben (eigene Datenbank, eigenes
Parameterregister, eigener Kategorienbaum, eigene Satzung). Der **Kern** — Quellcode, Freigaben,
dieses Schema — ist gemeinsam. Getauscht wird ausschließlich, was überall dasselbe bedeutet:
Stellgrößen mit **sprachneutralen Kennungen** und **aggregierte Kennzahlen**. Personenbezogene Daten
verlassen eine Instanz nie.

Maßgeblich ist `plattform_core/schema.py` (rein, getestet); diese Datei ist die lesbare Fassung.
Die Tabellen in Abschnitt 3 und 4 sind aus dem Code erzeugt (Stand 0.46.0) — weicht die Datei
vom Code ab, gilt der Code, und die Datei ist nachzuziehen.

## 1. Grundsätze

| Regel | Bedeutung |
|---|---|
| **Eine Instanz je Land** | `system_id` = `<ländercode>-<kurzname>` (ISO 3166-1 alpha-2, klein), z. B. `at-ddoe`, `se-ddk`. Gesetzt über `DDOE_SYSTEM_ID`. |
| **Kennung statt Sprache** | Jede Stellgröße trägt eine `schema_key` (englisch, stabil, Punkt-gegliedert: `bereich.name`, Muster `^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*)+$`). Lokale Schlüssel und Beschreibungen dürfen in jeder Sprache stehen. |
| **Werte bleiben eigen** | Das Schema sagt, *was* eine Stellgröße bedeutet — nie, *wie hoch* sie sein muss. Jede Instanz lernt ihren Wert selbst (Parameterregister, F-68). |
| **Nie personenbezogen** | Exporte enthalten keine Namen, E-Mails, Pseudonyme, Stimmen einzelner Menschen. Die Prüfung (`pruefe_export`) beanstandet solche Felder. |
| **Versioniert** | `schema_version` nach SemVer: neue Kennungen → Nebenversion (1.1), umgedeutete Kennungen → Hauptversion (2.0). Leser verarbeiten unbekannte Kennungen tolerant; `pruefe_export` verlangt nur dieselbe Hauptversion. |
| **Offen** | Alle Exporte sind öffentlich, ohne Anmeldung, mit `Access-Control-Allow-Origin: *`. |

## 2. Der Kopf jedes Exports

```json
{
  "schema_version": "1.5",
  "system_id": "at-ddoe",
  "system_name": "Direkte Demokratie Österreich",
  "software": {"name": "ParlamentPlattform", "version": "0.46.0",
               "quelle": "https://github.com/parlamentplattform/parlamentplattform", "lizenz": "AGPL-3.0-or-later"},
  "exportiert_am": "2026-09-12T08:00:00+00:00"
}
```

## 3. `/parameter.json` — Stellgrößen und Verfahrensordnung

```json
{
  "…Kopf…",
  "parameter": [
    {"schema_key": "support.review_days", "schluessel": "gremien-review-tage", "wert": "14",
     "einheit": "Tage", "beschreibung": "…", "quelle": "§ 5 Abs 12", "geaendert_am": "…"}
  ],
  "verfahrensordnung": [
    {"id": "sachantrag-standard", "version": 1, "werte": [
      {"schema_key": "support.threshold", "einheit": "supporters", "wert": 3},
      {"schema_key": "support.window_days", "einheit": "days", "wert": 14},
      {"schema_key": "deliberation.window_days", "einheit": "days", "wert": 21},
      {"schema_key": "vote.window_days", "einheit": "days", "wert": 7},
      {"schema_key": "vote.min_turnout", "einheit": "share", "wert": 0.05},
      {"schema_key": "vote.majority_basis", "einheit": "enum", "wert": "ja_nein"},
      {"schema_key": "council.group1_size", "einheit": "people", "wert": 3},
      {"schema_key": "council.group2_size", "einheit": "people", "wert": 3},
      {"schema_key": "motion.resubmission_block_months", "einheit": "months", "wert": 6}
    ]}
  ]
}
```

Unter `verfahrensordnung` steht die **wirksame** Ordnung jeder Fassung: Felder, die eine ältere
Fassung noch nicht kannte, erscheinen mit dem eingebauten Vorgabewert (seit 0.44.0).

Ein Registereintrag ohne `schema_key` wäre eine **lokale** Stellgröße (nur für diese Instanz
bedeutsam). In der Instanz `at-ddoe` gibt es keine: Ein Wächter (`verfahren/test_partner.py`)
verlangt für jeden Erstbestandsschlüssel eine Kennung.

### 3.1 Kennungen der Stellgrößen (Schema 1.5, 43 Kennungen)

Die Spalte „Registerschlüssel“ nennt den deutschen Schlüssel der Instanz `at-ddoe`; andere
Instanzen wählen ihre eigenen Schlüssel und tragen dieselbe Kennung.

| Kennung | Registerschlüssel (at-ddoe) | Einheit | Bedeutung |
|---|---|---|---|
| `account.email_change_waiting_hours` | `adresswechsel-wartefrist-stunden` | hours | Waiting time before an administrative change of a login address takes effect |
| `ai.max_response_tokens` | `ki-antwort-hoechsttokens` | tokens | Maximum length of a model response |
| `ai.monthly_token_budget` | `ki-monatstokens` | tokens/month | Hard monthly token budget of the model slot (cost cap of the future workshop) |
| `archive.audit_display_limit` | `archiv-audit-anzeige` | events | How many audit events the archive timeline shows; the export always contains all |
| `areas_fan.max_children` | `faecher-kinder-hoechstzahl` | branches | How many sub-branches a branch shows before it must be fanned out |
| `areas_fan.max_search_hits` | `suche-treffer-hoechstzahl` | hits | Maximum number of hits shown by the search in the areas-of-life fan |
| `areas_fan.rule_version` | `faecher-regel` | rule version | Version of the layout algorithm for the areas-of-life fan |
| `areas_of_life.per_motion` | `kategorien-je-antrag` | areas | How many areas of life a motion is assigned to automatically |
| `areas_of_life.rule_version` | `kategorien-regel` | rule version | Version of the assignment rule for areas of life (keyword lists, no AI) |
| `bodies.role_term_days` | `gremien-rollen-dauer-tage` | days | Regular term of a body role (public call, confirmation by the assembly, automatic expiry) |
| `chat.thread_roots` | `chat-faden-wurzeln` | posts | How many root posts (with replies) a motion's chat shows at once |
| `conversations.list_limit` | `gespraeche-liste-hoechstzahl` | conversations | How many conversations the panel shows at once; the counter covers all of them |
| `council.decision_days` | `gremien-beschluss-tage` | days | Default deadline for an internal decision in a council body |
| `council.decisions_per_page` | `gremien-beschluesse-seite` | decisions | How many council decisions the public list shows at once |
| `council.first_draft_days` | `expertenrat-erstvorschlag-tage` | days | Days the expert council has for its first proposal; also the minimum deliberation period |
| `council.group1_size` | `expertenrat-gruppe1-groesse` | people | Size of the first expert group drawn for a motion |
| `council.group2_size` | `expertenrat-gruppe2-groesse` | people | Size of the second expert group, which checks proposals with procurement relevance |
| `council.max_rounds` | `gremien-hoechstrunden` | rounds | Maximum number of draft-loop rounds before the proposal goes to the final vote |
| `council.review_days` | `gremien-pruefung-tage` | days | How long the second expert group has to check a proposal with implementation or procurement relevance |
| `council.rework_days` | `gremien-ueberarbeitung-tage` | days | Days the expert council has to revise a draft after it was returned |
| `deliberation.edit_window_minutes` | `chat-bearbeitungsfenster-minuten` | minutes | How long an author may still edit their own post |
| `deliberation.post_max_chars` | `chat-zeichen-hoechstzahl` | characters | Maximum length of a post in the deliberation chat |
| `draft_loop.acceptance_percent` | `vorschlag-annahme-prozent` | percent | Approval share the „fine as it is" post must exceed in the proposal chat so the draft goes to the final vote (it must also rank first) |
| `draft_loop.chat_ordering_version` | `vorschlag-chat-reihung` | rule version | Version of the proposal-chat ordering rule (engagement-v1: engagement desc, then approval share, then time) |
| `draft_loop.criticism_min_chars` | `kritik-mindestzeichen` | characters | Minimum length of a criticism so it counts as a change request to the expert council |
| `feedback.daily_limit` | `anstoss-tagesgrenze` | messages | How many feedback messages a person may send per day |
| `feedback.min_interval_seconds` | `anstoss-mindestabstand-sekunden` | seconds | Waiting time between two feedback messages from the same person |
| `mandate.monthly_report_grace_days` | `mandatar-monatsbericht-frist-tage` | days | Day of the following month until which an office holder's monthly report counts as on time |
| `mandate.question_vote_window_days` | `mandatsfrage-abstimmung-tage` | days | Duration of the vote on a mandate question opened by an office holder (never below the statutory minimum; frozen into the motion when it is opened) |
| `motion.resubmission_block_months` | `verfahren-wiedereinbringung-monate` | months | Months before a rejected or lapsed motion may be resubmitted verbatim |
| `overview.decided_votes` | `uebersicht-abstimmungen` | entries | How many decided votes the public overview lists before pointing to the registers |
| `region.secondary_residence_counts` | `region-nebenwohnsitz-zaehlt` | flag | Whether a registered secondary residence also assigns a member to that region for regional motions (0 or 1; never affects voting rights) |
| `similarity.max_hits` | `aehnlichkeit-treffer` | motions | How many similar motions are shown when submitting |
| `similarity.threshold_percent` | `aehnlichkeit-schwelle-prozent` | percent | Similarity above which the platform points to an existing motion when submitting a new one |
| `soft_filter.max_profiles` | `weicherfilter-profile-hoechstzahl` | profiles | How many personal filter profiles a member may store |
| `soft_filter.rule_version` | `weicherfilter-regel` | rule version | Version of the member-controlled ordering rule (nine sliders, neutral by default) |
| `support.review_days` | `gremien-review-tage` | days | Days the supporters have to accept a draft or return it with a concrete wish (draft loop) |
| `support.threshold` | `verfahren-unterstuetzung-schwelle` | supporters | Number of supporters a motion needs to enter deliberation |
| `support.window_days` | `verfahren-unterstuetzung-tage` | days | Days a motion has to reach the support threshold |
| `tiles.completed` | `kacheln-abgeschlossen` | entries | How many completed procedures appear in the feed |
| `tiles.highlighted` | `kacheln-hervorgehoben` | tiles | How many highlighted votes the important-votes field shows |
| `vote.min_turnout_percent` | `verfahren-mindestbeteiligung-prozent` | percent | Share of eligible members that must take part for a result to stand |
| `vote.window_days` | `verfahren-abstimmung-tage` | days | Duration of the final vote |

Einheiten sind freier Text; `flag` steht seit 1.5 für einen Schalter mit den Werten 0 und 1,
`rule version` für die Fassung einer offengelegten Regel (kein Testwert, kein Vergleichswert).

### 3.2 Kennungen der Verfahrensordnung (je Fassung im Export)

| Kennung | Policy-Feld | Einheit |
|---|---|---|
| `support.threshold` | `unterstuetzung_schwelle` | supporters |
| `support.window_days` | `unterstuetzung_frist_tage` | days |
| `deliberation.window_days` | `beratung_tage` | days |
| `vote.window_days` | `abstimmung_tage` | days |
| `vote.min_turnout` | `mindestbeteiligung` | share |
| `vote.majority_basis` | `mehrheitsbasis` | enum (`ja_nein`: Ja > Nein · `abgegeben`: Enthaltung wirkt wie Nein) |
| `council.group1_size` | `expertenrat_gruppe1` | people |
| `council.group2_size` | `expertenrat_gruppe2` | people |
| `motion.resubmission_block_months` | `wiedereinbringung_sperre_monate` | months |

Wo ein Feld der Ordnung aus einer Stellgröße des Registers gespeist wird, tragen beide dieselbe
Kennung — mit zwei begründeten Ausnahmen (`plattform_core/test_schema.py`, `ABWEICHENDE_KENNUNG`):

| Register | Ordnung | Warum verschieden |
|---|---|---|
| `council.first_draft_days` (`expertenrat-erstvorschlag-tage`) | `deliberation.window_days` (`beratung_tage`) | Der Registerwert ist die Frist des Expertenrats für den ersten Vorschlag; in der Ordnung ist er zugleich die Mindestdauer der Beratung — zwei Bedeutungen, die eine Partnerinstanz getrennt halten muss. |
| `vote.min_turnout_percent` (`verfahren-mindestbeteiligung-prozent`) | `vote.min_turnout` (`mindestbeteiligung`) | Im Register steht ein Prozentwert (5), in der Ordnung ein Anteil (0.05). |

Die weiteren Felder der eingefrorenen Ordnung (Annahmeanteil, Höchstrunden, Unterstützer-,
Überarbeitungs- und Prüffrist der Entwurfsschleife, Losregel-Fassung) stehen **nicht** im Export
je Fassung; ihre Registerwerte sind über die Kennungen `draft_loop.*` und `council.*` in 3.1 lesbar.

## 4. `/kennzahlen.json` — aggregierter Lernfortschritt

```json
{
  "…Kopf…",
  "kennzahlen": [
    {"schema_key": "members.active", "einheit": "count", "wert": 128},
    {"schema_key": "motions.total", "einheit": "count", "wert": 41},
    {"schema_key": "motions.by_phase", "einheit": "map",
     "wert": {"unterstuetzung": 5, "beratung": 2, "abstimmung": 3, "angenommen": 24, "abgelehnt": 6, "verfallen": 1}},
    {"schema_key": "votes.completed", "einheit": "count", "wert": 30},
    {"schema_key": "votes.turnout_mean", "einheit": "share", "wert": 0.37},
    {"schema_key": "implementation.by_status", "einheit": "map",
     "wert": {"offen": 4, "in_umsetzung": 9, "blockiert": 1, "umgesetzt": 10, "zurueckgestellt": 0}},
    {"schema_key": "areas_of_life.active", "einheit": "count", "wert": 312}
  ]
}
```

### 4.1 Kennungen der Kennzahlen (Schema 1.5, 7 Kennungen)

| Kennung | Einheit | Bedeutung |
|---|---|---|
| `members.active` | count | Active member accounts |
| `motions.total` | count | Motions submitted (without formally rejected ones) |
| `motions.by_phase` | map | Motions per phase: support, deliberation, vote, adopted, rejected, lapsed |
| `votes.completed` | count | Completed votes (adopted or rejected after a vote) |
| `votes.turnout_mean` | share | Mean turnout of completed votes: ballots cast / eligible members |
| `implementation.by_status` | map | Adopted motions per implementation status |
| `areas_of_life.active` | count | Active areas of life (nodes of the category tree) |

Alle Werte sind Zählungen oder Anteile über die ganze Instanz — nichts davon lässt sich auf einen
Menschen zurückführen. Dieselben Kennungen sind die Messgrößen der Parametertests des
Koordinationsrats (§ 6 Abs 11 lit c): Eine zweite Zählung nur für Tests wäre nicht nachrechenbar.
Mandatsfragen (Antragsart `mandatsfrage`, seit 0.46.0) zählen in `motions.*` und `votes.*` wie
Sachanträge; eine eigene Kennung haben sie nicht.

## 5. Weitere offene Formate

| Adresse | Inhalt | Personenbezug |
|---|---|---|
| `/antrag/<id>/export.json` | Nachrechenbare Auszählung einer Abstimmung: Policy-Kopie, Stimmberechtigte, Stimmen je Pseudonym, Prüfsumme — mit `verify/nachrechnen.py` unabhängig nachrechenbar (Sachfragen, Kandidaturen und Mandatsfragen) | Pseudonyme (nur der Mensch selbst kennt seines) |
| `/umsetzung.json` | Umsetzungsregister mit voller Historie | Anzeigenamen der Vollzugsmeldenden (Gremien-Rollen, öffentlich) |
| `/gremien/protokoll/<gremium>/<jahr>.json` | Sitzungsprotokoll eines Rates: die Beschlüsse des Jahres mit Stimmen, Begründungen und Umsetzungsvermerken (§ 6 Abs 9) | Anzeigenamen der Ratsmitglieder (öffentliche Besetzung) |
| `/rechenschaft.json` | Rechenschaftsregister der Mandatare (§ 7 Abs 5): Gegenstand, Sitzungstag, Beschluss der Plattform, Stimme im Vertretungskörper, Begründung — seit 0.46.0 | Anzeigenamen der Mandatare (öffentliches Amt) |
| `/mandatare/wahlvorschlag/<antrag>.md` | Reihung einer beendeten Kandidatur nach Zustimmungen (§ 7 Abs 1) als Markdown — seit 0.46.0 | Anzeigenamen der Bewerberinnen und Bewerber (öffentliche Kandidatur) |
| `policies/kategorien-v2.yaml` | Kategorienbaum der Lebensbereiche (312 Knoten, sprachneutrale Slugs) | — |
| `policies/grundordnung-v1.yaml` | Verfahrensordnung als Daten (ADR-004) | — |

## 6. Wie eine andere Instanz die Daten liest

1. `GET https://<instanz>/parameter.json` und `/kennzahlen.json` holen (öffentlich).
2. `schema_version` prüfen: gleiche Hauptversion → verarbeiten; unbekannte Kennungen überspringen.
3. Werte je `schema_key` gegenüberstellen — nie „übernehmen": Der Vergleich ist Lernstoff, die Entscheidung bleibt bei der eigenen Mitgliederversammlung.
4. Der Import-Befehl `partner_import <url>` (S14b) liest fremde Exporte in eine Gegenüberstellung; bis dahin genügt `python -c "import json,urllib.request; …"` oder jedes Tabellenwerkzeug.

## 7. Änderungsverlauf

| Version | Datum | Plattform | Änderung |
|---|---|---|---|
| 1.0 | 3.9.2026 | 0.36.0 | Erste Fassung: Kopf, 5 Register-Kennungen (`draft_loop.review_days`, `draft_loop.revision_days`, `draft_loop.max_rounds`, `bodies.role_term_days`, `ai.monthly_token_budget`), 7 Kennungen der Verfahrensordnung, 7 Kennzahlen, Prüfregeln. Mit 0.39.0 (4.9.2026) kamen `draft_loop.acceptance_percent` und `draft_loop.chat_ordering_version` hinzu, ohne dass die Version stieg |
| 1.1 | 5.9.2026 | 0.41.0 | 25 Register-Kennungen: die Stellgrößen des Verfahrens (`support.threshold`, `support.window_days`, `vote.window_days`, `vote.min_turnout_percent`, `motion.resubmission_block_months`, `council.first_draft_days`), der Lebensbereiche und Fächer (`areas_of_life.*`, `areas_fan.*`), der Beratung und des Chats (`deliberation.*`, `chat.*`-Vorläufer, `conversations.list_limit`, `draft_loop.criticism_min_chars`), der Ähnlichkeitsprüfung (`similarity.*`), des WeicherFilters (`soft_filter.*`), der Kacheln und des Archivs (`tiles.*`, `archive.audit_display_limit`), des Anstoß-Widgets (`feedback.*`) und des Modell-Steckplatzes (`ai.max_response_tokens`). **Zugleich wurden drei Kennungen aus 1.0 umbenannt** — `draft_loop.review_days` → `support.review_days`, `draft_loop.revision_days` → `council.rework_days`, `draft_loop.max_rounds` → `council.max_rounds` —, ohne dass das damals hier oder im Änderungsprotokoll stand. Nach der eigenen Regel wäre das eine Hauptversion gewesen; es blieb bei der Nebenversion, weil noch keine Partnerinstanz Exporte las. Die alten Namen gelten nicht mehr |
| 1.2 | 8.9.2026 | 0.43.0 | Nachgeholte Erhöhung für `council.review_days` und `council.decision_days`, die mit 0.42.0 (5.9.2026) ohne Versionssprung hinzugekommen waren |
| 1.3 | 8.9.2026 | 0.44.0 | `council.group1_size`, `council.group2_size` — im Register und in der Verfahrensordnung (die Gruppengrößen des Expertenrats stehen in der eingefrorenen Ordnung, § 5 Abs 5) |
| 1.4 | 11.9.2026 | 0.45.0 | `overview.decided_votes`, `chat.thread_roots`, `council.decisions_per_page`, `account.email_change_waiting_hours` |
| 1.5 | 12.9.2026 | 0.46.0 | `mandate.question_vote_window_days` (Dauer der Abstimmung über eine Mandatsfrage, § 7 Abs 9), `mandate.monthly_report_grace_days` (Karenz des Monatsberichts, § 7 Abs 3 lit b), `region.secondary_residence_counts` (Schalter 0/1, § 5 Abs 6 — nie Stimmrecht). Diese Datei vollständig auf den Code gebracht: Die Tabelle stand seit 1.0 unverändert bei 12 Kennungen und trug die drei in 1.1 umbenannten noch unter ihren alten Namen; der Verlauf nannte 1.1 bis 1.3 nicht |
