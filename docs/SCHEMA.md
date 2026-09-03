# SCHEMA.md — Die Schnittstelle zwischen den Landesinstanzen

*Satzung § 12 Abs 5 · Fahrtenbuch FB-M5/M6 · ADR-009 · Schema-Version **1.0** (3.9.2026)*

Die ParlamentPlattform wird je Land als **eigene Instanz** betrieben (eigene Datenbank, eigenes
Parameterregister, eigener Kategorienbaum, eigene Satzung). Der **Kern** — Quellcode, Freigaben,
dieses Schema — ist gemeinsam. Getauscht wird ausschließlich, was überall dasselbe bedeutet:
Stellgrößen mit **sprachneutralen Kennungen** und **aggregierte Kennzahlen**. Personenbezogene Daten
verlassen eine Instanz nie.

Maßgeblich ist `plattform_core/schema.py` (rein, getestet); diese Datei ist die lesbare Fassung.

## 1. Grundsätze

| Regel | Bedeutung |
|---|---|
| **Eine Instanz je Land** | `system_id` = `<ländercode>-<kurzname>` (ISO 3166-1 alpha-2, klein), z. B. `at-ddoe`, `se-ddk`. Gesetzt über `DDOE_SYSTEM_ID`. |
| **Kennung statt Sprache** | Jede Stellgröße trägt eine `schema_key` (englisch, stabil, Punkt-gegliedert: `bereich.name`). Lokale Schlüssel und Beschreibungen dürfen in jeder Sprache stehen. |
| **Werte bleiben eigen** | Das Schema sagt, *was* eine Stellgröße bedeutet — nie, *wie hoch* sie sein muss. Jede Instanz lernt ihren Wert selbst (Parameterregister, F-68). |
| **Nie personenbezogen** | Exporte enthalten keine Namen, E-Mails, Pseudonyme, Stimmen einzelner Menschen. Die Prüfung (`pruefe_export`) beanstandet solche Felder. |
| **Versioniert** | `schema_version` nach SemVer: neue Kennungen → Nebenversion (1.1), umgedeutete Kennungen → Hauptversion (2.0). Leser verarbeiten unbekannte Kennungen tolerant. |
| **Offen** | Alle Exporte sind öffentlich, ohne Anmeldung, mit `Access-Control-Allow-Origin: *`. |

## 2. Der Kopf jedes Exports

```json
{
  "schema_version": "1.0",
  "system_id": "at-ddoe",
  "system_name": "Direkte Demokratie Österreich",
  "software": {"name": "ParlamentPlattform", "version": "0.36.0",
               "quelle": "https://github.com/parlamentplattform/parlamentplattform", "lizenz": "AGPL-3.0-or-later"},
  "exportiert_am": "2026-09-03T08:00:00+00:00"
}
```

## 3. `/parameter.json` — Stellgrößen und Verfahrensordnung

```json
{
  "…Kopf…",
  "parameter": [
    {"schema_key": "draft_loop.review_days", "schluessel": "gremien-review-tage", "wert": "14",
     "einheit": "Tage", "beschreibung": "…", "quelle": "§ 5 Abs 12 · F-67", "geaendert_am": "…"}
  ],
  "verfahrensordnung": [
    {"id": "sachantrag-standard", "version": 1, "werte": [
      {"schema_key": "support.threshold", "einheit": "supporters", "wert": 3},
      {"schema_key": "support.window_days", "einheit": "days", "wert": 14},
      {"schema_key": "deliberation.window_days", "einheit": "days", "wert": 21},
      {"schema_key": "vote.window_days", "einheit": "days", "wert": 7},
      {"schema_key": "vote.min_turnout", "einheit": "share", "wert": 0.05},
      {"schema_key": "vote.majority_basis", "einheit": "enum", "wert": "ja_nein"},
      {"schema_key": "motion.resubmission_block_months", "einheit": "months", "wert": 6}
    ]}
  ]
}
```

Ein Registereintrag ohne `schema_key` ist eine **lokale** Stellgröße (nur für diese Instanz bedeutsam).

### Kennungen der Stellgrößen (Schema 1.0)

| Kennung | Einheit | Bedeutung |
|---|---|---|
| `draft_loop.review_days` | days | Frist der Unterstützer, einen Vorschlag anzunehmen oder mit konkretem Wunsch zurückzugeben |
| `draft_loop.revision_days` | days | Überarbeitungsfrist des Expertenrats je Rückgabe-Runde |
| `draft_loop.max_rounds` | rounds | Höchstzahl der Runden der Entwurfsschleife |
| `bodies.role_term_days` | days | Regeldauer einer Gremien-Rolle |
| `ai.monthly_token_budget` | tokens/month | Monatsbudget des Modell-Steckplatzes |
| `support.threshold` | supporters | Unterstützungen bis zur Beratung |
| `support.window_days` | days | Frist der Unterstützungsphase |
| `deliberation.window_days` | days | Dauer der Beratung |
| `vote.window_days` | days | Dauer der Abstimmung |
| `vote.min_turnout` | share | Mindestbeteiligung (Anteil der Stimmberechtigten) |
| `vote.majority_basis` | enum | `ja_nein` (Ja > Nein) oder `abgegeben` (Enthaltung wirkt wie Nein) |
| `motion.resubmission_block_months` | months | Sperre für die Wiedereinbringung abgelehnter Anträge |

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

Alle Werte sind Zählungen oder Anteile über die ganze Instanz — nichts davon lässt sich auf einen Menschen zurückführen.

## 5. Weitere offene Formate

| Adresse | Inhalt | Personenbezug |
|---|---|---|
| `/antrag/<id>/export.json` | Nachrechenbare Auszählung einer Abstimmung: Policy-Kopie, Stimmberechtigte, Stimmen je Pseudonym, Prüfsumme — mit `verify/nachrechnen.py` unabhängig nachrechenbar | Pseudonyme (nur der Mensch selbst kennt seines) |
| `/umsetzung.json` | Umsetzungsregister mit voller Historie | Anzeigenamen der Vollzugsmeldenden (Gremien-Rollen, öffentlich) |
| `policies/kategorien-v2.yaml` | Kategorienbaum der Lebensbereiche (312 Knoten, sprachneutrale Slugs) | — |
| `policies/grundordnung-v1.yaml` | Verfahrensordnung als Daten (ADR-004) | — |

## 6. Wie eine andere Instanz die Daten liest

1. `GET https://<instanz>/parameter.json` und `/kennzahlen.json` holen (öffentlich).
2. `schema_version` prüfen: gleiche Hauptversion → verarbeiten; unbekannte Kennungen überspringen.
3. Werte je `schema_key` gegenüberstellen — nie „übernehmen": Der Vergleich ist Lernstoff, die Entscheidung bleibt bei der eigenen Mitgliederversammlung.
4. Der Import-Befehl `partner_import <url>` (S14b) liest fremde Exporte in eine Gegenüberstellung; bis dahin genügt `python -c "import json,urllib.request; …"` oder jedes Tabellenwerkzeug.

## 7. Änderungsverlauf

| Version | Datum | Änderung |
|---|---|---|
| 1.0 | 3.9.2026 | Erste Fassung: Kopf, 12 Stellgrößen-Kennungen, 7 Kennzahlen, Prüfregeln |
