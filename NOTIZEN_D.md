# NOTIZEN Cluster D (Betrieb, Sprache, Offenlegung) — Gesamtprüfung 0.45

Branch `befunde/d`, Worktree `C:/Users/plav/DDOE-code/wt/d`, abgezweigt von c5a0902.

## Änderungsvorschläge für Dateien anderer Cluster

### Befund #45 — elf Stellgrößen, deren lesende Stelle in fremden Dateien liegt

Cluster D hat `ki-antwort-hoechsttokens` (ki/anbieter.py) angebunden, den Satz auf /parameter/ auf
Stellgrößen eingeschränkt und in `parameter/test_register.py` den Wächter
`test_jede_stellgroesse_wird_vom_code_gelesen` geschrieben. Er kennt die Menge `NOCH_NICHT_ANGEBUNDEN`;
**sobald eine der folgenden Stellen liest, ihren Schlüssel dort streichen** (der Test bleibt sonst
grün, wird für den Schlüssel aber erst danach scharf). Muster überall: `from parameter.models import zahl`
(in verfahren/ und anstoss/ lazy im Funktionsrumpf, wenn Importzyklen drohen).

**Cluster A1 — `verfahren/views.py`:**
- Z. 218 `…order_by("-phase_beginn")[:20]` → `[: zahl("kacheln-abgeschlossen", 20)]`
- Z. 349 `wichtige = laufend.filter(hervorgehoben=True).order_by("phase_beginn")[:3]` →
  `[: zahl("kacheln-hervorgehoben", 3)]`; im Parlament (Z. 467–469, unbegrenzte `wichtige`) dieselbe Grenze anwenden
- Z. 423 `return treffer[:24]` → `return treffer[: zahl("suche-treffer-hoechstzahl", 24)]`
- Z. 441 Aufruf des Fächers (`plattform_core/faecher.py`, `KINDER_HOECHSTZAHL = 3`): die Funktion nimmt
  (bzw. bekommt) einen Parameter `kinder_hoechstzahl`; Aufruf mit `zahl("faecher-kinder-hoechstzahl", 3)`.
  faecher.py selbst ist Django-frei — der Wert wird durchgereicht, die Konstante bleibt Rückfall.

**Cluster A2 — `verfahren/views_aktionen.py`:**
- Z. 177 `treffer = aehnlichste(f"{d['titel']} {d['wortlaut']}", kandidaten)` →
  ```python
  treffer = aehnlichste(
      f"{d['titel']} {d['wortlaut']}",
      kandidaten,
      schwelle=zahl("aehnlichkeit-schwelle-prozent", 18) / 100,
      limit=zahl("aehnlichkeit-treffer", 3),
  )
  ```
  (`plattform_core/similarity.py` nimmt beides schon als Parameter; Docstring dort ist angepasst.)
- Z. 466/475 `FilterProfil.HOECHSTZAHL` → `zahl("weicherfilter-profile-hoechstzahl", FilterProfil.HOECHSTZAHL)`
  (die Klassenkonstante in verfahren/models.py:661 bleibt als Rückfall, Cluster C).

**Cluster C — `verfahren/models.py`:**
- Z. 833/898 `BEARBEITUNGSFENSTER = timedelta(minutes=5)`: in der Prüfung (Z. 898)
  `timedelta(minutes=zahl("chat-bearbeitungsfenster-minuten", 5))` statt der Konstante — der Kommentar
  in Z. 832 sagt selbst, dass der gültige Wert im Register steht.
- Z. 1018 `treffer = zuordnen(text, aktive)` → `zuordnen(text, aktive, limit=zahl("kategorien-je-antrag", 3))`.
- Nebenfund (C): `gremien/views.py:750` liest `_register("gremien-beschluesse-seite", 50)` — ein Schlüssel,
  der **nicht** im ERSTBESTAND steht, also nie auf /parameter/ erscheint. Entweder Eintrag in
  `parameter/models.py` ERSTBESTAND (Gruppe „kacheln", Einheit „Einträge", Quelle § 6 Abs 9) samt Schema-Kennung
  in `plattform_core/schema.py`, oder die Konstante offen benennen. Cluster D hat den Eintrag nicht angelegt,
  weil die Schema-Zuordnung (docs/SCHEMA.md, Fassung 1.0) davon berührt wäre.

**Cluster B — `anstoss/views.py`:**
- Z. 18–19 `MIN_ABSTAND_SEKUNDEN = 60`, `TAGESGRENZE = 20` bleiben Rückfall; an den Verwendungsstellen
  `zahl("anstoss-mindestabstand-sekunden", MIN_ABSTAND_SEKUNDEN)` und `zahl("anstoss-tagesgrenze", TAGESGRENZE)`.

### Befund #17 — Text der 500-Seite (Cluster A2)
`verfahren/templates/500.html:39` „Er ist protokolliert und wird angesehen." ist mit dem LOGGING aus
`config/settings.py` (Commit 7e222f8) jetzt wahr — der Traceback steht auf stderr, Render zeigt ihn im Log.
Cluster A2 kann den Satz so lassen; wenn er ihn fasst, bitte „protokolliert" beibehalten.

### Befund #0 — CSP
Nicht als Middleware im selben Schritt (Nachprüfer): base.html trägt einen Inline-`<style>`-Block, Vorlagen
nutzen `style=`-Attribute, Alpine braucht `unsafe-eval` oder den CSP-Build. Eigener Bauschritt mit ADR
(Nonce für `<style>`, Alpine-CSP-Build, Inline-Styles abbauen).

## Bewusst nicht oder nur teilweise umgesetzt

- **#90 (teilweise):** Die 326 Texte der Rollenmatrix, 88 des Regelverzeichnisses und 72 des Erstbestands sind
  markiert (`_` No-op in plattform_core, `gettext_noop` in parameter/models.py) und laufen in den Vorlagen
  durch `{% translate variable %}`; übersetzt sind davon bisher die kurzen (Stand, Wirkung, Einheiten).
  Die langen Texte zu übersetzen ist Datenpflege (≈ 480 Einträge) und war in diesem Lauf nicht zu leisten;
  `tests/test_katalog.py` führt sie als „vorgemerkt", nicht als Fehlbestand. Solange sie deutsch sind, steht
  auf /rollen/, /regeln/ und /parameter/ bei nicht-deutscher Sprache der Hinweis „Die Einträge dieser Seite
  liegen derzeit nur auf Deutsch vor …" — **den Hinweis entfernen, wenn die Einträge übersetzt sind.**
  Kategorienamen aus `policies/kategorien-v*.yaml` (Fächer, Chips) bleiben deutsch — nicht angefasst.
- **#54:** `VERSION` von rollen.py bleibt 2 — sie stand seit c5a0902 (0.45-Arbeitsstand) schon auf 2, und
  regelwerk.py führt die Rollenmatrix bereits als „Fassung 2 … seit 2026-09-11" ohne Zahlen in der Prosa;
  meine Änderungen sind Textkorrekturen innerhalb derselben, noch nicht veröffentlichten Fassung. Der Test
  `test_die_genannte_fassung_steht_wirklich_im_modul` hält beide Zahlen zusammen.
- **#92:** Entfernt wurden 84 (nicht „rund 60") tote Einträge — der Abgleich lief gegen den 0.45-Stand und
  fand auch Texte der ersten Koordinationsrat-Fassung. Jeder Eintrag wurde vor dem Entfernen per Suche über
  Vorlagen, Python, .txt, .js und .yaml gegengeprüft; Treffer gab es nur in CHANGELOG, Docstrings/Kommentaren
  und Tests. `test_kein_katalogeintrag_ohne_fundstelle` hält das künftig.
- **#96:** Obergrenzen gesetzt (ruff `<0.17`, gunicorn `<27`, whitenoise `<7`, psycopg `<4`, requests `<3`,
  PyYAML `<7`, segno `<2`). Die vom Nachprüfer als stärker bezeichnete Constraints-/Lockdatei, die CI und
  Docker gleichermaßen installieren, ist nicht angelegt (eigener Schritt: Erzeugung, Pflegeweg, ADR).
- **#95:** Live-Dienst `autoDeployTrigger: "off"` (der CI-Hook bleibt der Weg), Partner-Muster `checksPass`;
  docs/BETRIEB-RENDER.md ergänzt.

## Hinweise für die Zusammenführung

- `locale/en/LC_MESSAGES/django.po` (+ `.mo`): 14 Blöcke umgeschrieben, 3 Schlüssel korrigiert, 84 Einträge
  entfernt, 5 Einträge zu Pluralpaaren zusammengezogen, 228 Einträge angehängt (zwei Nachtragsabschnitte am
  Dateiende). **Nach dem Zusammenführen aller Cluster:** die `NEUE_TEXTE_<Cluster>.md` in die .po eintragen,
  `python tools/po_pruefen.py --mo` laufen lassen und `pytest tests/test_katalog.py` — der Test nennt jeden
  markierten Text ohne Eintrag und jeden Eintrag ohne Fundstelle mit Datei.
- `plattform_core/rollen.py`, `plattform_core/regelwerk.py`: fast jede Textzeile geändert (`_()`-Markierung).
  Konflikte nur, falls ein anderer Cluster dort Texte anfasst (Zuordnung: Cluster D).
- `parameter/models.py`: ERSTBESTAND-Zeilen mit `gettext_noop(...)` und `erstbestand_sicherstellen()` umgebaut;
  Cluster C ändert in derselben Datei nur die TextChoices-Beschriftungen (Befund #64) — andere Hunks.
- `tools/po_pruefen.py`: `lesen(pfad=PO)` wirft jetzt `KatalogFehler`; wer `lesen()` importiert
  (`verfahren/test_design_system.py`, `verfahren/test_vorlagen.py`, `tests/test_katalog.py`), ist angepasst.
- `parameter/test_register.py`: `NOCH_NICHT_ANGEBUNDEN` nach dem Zusammenführen um die Schlüssel kürzen,
  die A1/A2/B/C angebunden haben.
- Keine Migrationen. `makemigrations --check --dry-run`: No changes detected.
