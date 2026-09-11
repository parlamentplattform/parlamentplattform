# NOTIZEN Cluster C (Kern des Verfahrens) — Behebung 0.45.0

Änderungsvorschläge für Dateien anderer Cluster und Punkte, die der Nachprüfer als eigenen
Bauschritt bezeichnet hat. Jeder Eintrag nennt Datei, Stelle und den konkreten Code.

## Befund #3 / #16 — Entwurfsschleife liest aus der eingefrorenen Ordnung

Umgesetzt in `plattform_core/policy.py` (fünf neue Felder `vorschlag_annahme_anteil`,
`hoechstrunden`, `review_tage`, `ueberarbeitung_tage`, `pruefung_tage` mit Vorgaben 0.5/3/14/14/7,
Satzungsgrenze `review_tage`/`ueberarbeitung_tage` ≤ 14, `REGISTER_ZUORDNUNG` erweitert) und
`gremien/models.py` (alle Lesestellen über `antrag.policy()`). Keine Datenmigration nötig:
`Policy.aus_dict` ergänzt fehlende Felder mit den Vorgaben, die den bisherigen Registerwerten
entsprechen.

**Für die Zusammenführung (Cluster D, zwei Zeilen zusammen ändern):**

1. `plattform_core/regelwerk.py`, Regel `modul="policy.py"`: `fassung=1` → `fassung=2`, und im
   `zweck` ergänzen: „Seit Fassung 2 gehören auch die Fristen, Runden und die Annahme-Schwelle
   der Entwurfsschleife (§ 5 Abs 12) zur Ordnung; die Fristen der Unterstützer und des
   Expertenrats dürfen 14 Tage nicht überschreiten.“
2. `plattform_core/policy.py`: `VERSION = 1` → `VERSION = 2` (der Kommentar darüber sagt schon,
   dass beide zusammen angehoben werden). Ich habe die Nummer auf 1 gelassen, weil
   `parameter/test_regelwerk.py::test_die_genannte_fassung_steht_wirklich_im_modul` sonst rot
   wäre — die Prüfung ist richtig, sie verlangt nur, dass beide Dateien in einem Zug geändert
   werden.

**Cluster D, `parameter/views.py` `FELD_NAMEN`:** fünf Einträge ergänzen, damit der Abgleich
„Register ↔ geltende Fassung“ und `_lesbare_ordnung` die neuen Felder benennen:

```python
    "vorschlag_annahme_anteil": "Annahme-Schwelle „Passt alles“ (Anteil)",
    "hoechstrunden": "Höchstzahl der Runden der Entwurfsschleife",
    "review_tage": "Frist der Unterstützer je Runde (Tage)",
    "ueberarbeitung_tage": "Überarbeitungsfrist des Expertenrats je Rückgabe (Tage)",
    "pruefung_tage": "Prüffrist der Gruppe 2 (Tage)",
```

**Cluster D, `parameter/models.py` ERSTBESTAND:** Die beiden Schlüssel, die weiterhin sofort
wirken, weil sie kein Antragsverfahren betreffen, brauchen den Zusatz in der Beschreibung:
`gremien-rollen-dauer-tage` und `gremien-beschluss-tage` → „… Wirkt sofort — auch auf
laufende Rollen bzw. neu angelegte Beschlüsse; kein Teil der Verfahrensordnung.“ Der
`help_text` von `Parameter.status` („Ein Wert „im Test“ gilt nur für neu beginnende
Verfahren“) stimmt jetzt für alle Schlüssel in `REGISTER_ZUORDNUNG`; für die übrigen
(Kacheln, KI, Schutz, Rollen-Dauer, Beschluss-Frist) wirkt ein Testwert sofort — Vorschlag:
„Ein Wert „im Test“ gilt für Verfahrensordnungs-Werte nur für neu beginnende Verfahren
(§ 5 Abs 5); alle anderen Stellgrößen wirken sofort.“ Ebenso der Satz in
`parameter/templates/parameter/liste.html` („Ein geänderter Wert wirkt deshalb nie auf ein
laufendes Verfahren“): nur bei `p.speist_ordnung` zeigen oder auf „Werte der
Verfahrensordnung“ einschränken.

## Befund #5 — eingereichte Fassung

Umgesetzt: `Entwurf.eingereichte_fassung` (Migration `gremien/0014`, Nachtrag für bestehende
Entwürfe aus der höchsten Fassung zum Einreichzeitpunkt), `Entwurf.vorgelegte_fassung()`,
`_endabstimmung_oeffnen` nimmt nur noch diese. Kein Cluster-fremder Bedarf.

## Befund #8 — Fristen im PRUEFUNG-Zweig

Umgesetzt in `Entwurf.fortschreiben`: (a) keine Gruppe 2 → nach `pruefung_tage` ab
`eingereicht_am` Vermerk VALIDIERT ohne Beschluss und weiter an die Unterstützer; (b) offener
Austauschantrag → nach `pruefung_tage` ab `Pruefung.erstellt_am` weiter an die Unterstützer.
Beide mit Audit `pruefung_frist_verstrichen` und `wirksam_ab` = Fristzeitpunkt.

**Abweichungen vom Vorschlag, mit Grund:**
- Statt eines neuen Registerschlüssels `gremien-austausch-tage` nimmt (b) die Prüffrist
  `pruefung_tage` der **eingefrorenen Ordnung**. Ein neuer Schlüssel bräuchte einen
  ERSTBESTAND-Eintrag (`parameter/models.py`, Cluster D); ohne ihn würde `aus_register` jede
  neue Fassung mit „fehlender Wert“ abweisen. Wer eine eigene Frist will: Feld
  `austausch_tage: int = 7` in `Policy` + `REGISTER_ZUORDNUNG["austausch_tage"] =
  ("gremien-austausch-tage", int)` + ERSTBESTAND-Eintrag (Quelle § 6 Abs 7 · § 5 Abs 12) in
  einem Zug.
- Statt `korat_entscheid` leer zu lassen, trägt die Prüfung den neuen Wert `verfristet`
  (`Pruefung.KoratEntscheid`, Migration `gremien/0015`). Ein leerer Entscheid hätte den Antrag
  bei einer späteren zweiten Prüfungsrunde erneut blockiert (der Filter `korat_entscheid=""`
  fände den alten Austauschantrag wieder); mit dem eigenen Wert stimmen alle vier
  Filterstellen in `gremien/views.py` ohne Änderung, und `koordination.html` zeigt die
  Beschriftung über `get_korat_entscheid_display`.
- „Den KoRat-Entscheid mittelfristig als GremienBeschluss mit Anlass AUSTAUSCH und Frist
  führen“ — das ist seit 0.45 schon so (`koordination_beschluss`, Anlass AUSTAUSCH); nur die
  **Anlage** des Beschlusses ist eine unbefristete Einzelhandlung. Genau diese Lücke schließt (b).

## Befund #14 / #37 — Gruppe 2 wird nachgezogen

Umgesetzt: `auslosen(antrag, runde, jetzt, gruppen=(1,))` mit Rückführung der Losregel-Indizes
auf die tatsächlichen Gruppennummern; `gruppe_2_nachziehen(antrag)` (einmal je Antrag, eigene
Runde, eigener Anker, Gruppe 1 und frühere Geloste ausgeschlossen) — aufgerufen beim Setzen des
Vollzugsbezugs im Fenster und spätestens in `Entwurf.einreichen`. `austausch_wirkung` zieht
damit automatisch nur noch Gruppe 1 nach (bisher hätte es bei Vollzugsbezug eine zweite
Gruppe 1 UND eine Gruppe 2 gezogen). Die Prüffrist ohne Gruppe 2 ist Teil von Befund #8.
Kein „◐ bis dahin“ nötig — der Weg ist jetzt erreichbar:

- `plattform_core/rollen.py:459` (Cluster D): Der Eintrag „Vollzugs- oder Beschaffungsbezug
  setzen — dann prueft Gruppe 2 vorab“ stimmt jetzt; Vorschlag für die Beschreibung: „… dann
  wird Gruppe 2 aus der Fachliste nachgelost und prüft vorab (§ 6 Abs 7).“ Bitte „prueft“ →
  „prüft“ (Ersatzschreibung im Nutzertext).
- `verfahren/templates/verfahren/antrag.html:224` (Cluster A1): Der Satz „Der Expertenrat zu
  diesem Antrag wurde aus der öffentlichen Fachliste gelost“ stimmt weiterhin (er steht nur,
  wenn eine Auslosung existiert; Gruppe 2 kommt jetzt aus derselben Liste). Keine Änderung nötig.

## Befund #18 / #65 — demo_seed

Umgesetzt in `verfahren/management/commands/demo_seed.py`: Hervorhebungs-Beschluss nur, wenn
ausschließlich Demo-Mitglieder im Integritätsrat sitzen; Wächter des Abstimmungs-Chat-Blocks am
Titel (`TESTLAUF_TITEL`). Tests in `verfahren/test_demo_seed.py` (lassen den Befehl zweimal
laufen). Kein Cluster-fremder Bedarf.

## Befund #31 — Aussetzung nur bei Abstimmung oder Vollzug

Umgesetzt: `aussetzungs_gegenstand(antrag)` (gremien/models.py), `aussetzung_wirkung` vermerkt
„Ohne Wirkung“ in anderen Phasen, `integritaet_beschluss` weist das Anlegen ab,
`vollzug_fortschreiben` wirft `VollzugAusgesetzt(ValueError)` bei laufender Vollzugs-Aussetzung.

**Cluster A2, `verfahren/views_aktionen.py` (Umsetzungsstand, ca. Zeile 785-791):** Der
`except ValueError` zeigt heute für jeden Fehler „Das Umsetzungsregister führt nur angenommene
Anträge.“ — für die neue Sperre wäre das falsch. Vorschlag:

```python
    except VollzugAusgesetzt:
        messages.error(request, _("Der Vollzug ist durch den Integritätsrat ausgesetzt — solange die Aussetzung läuft, wird das Register nicht fortgeschrieben (§ 6 Abs 3 lit d)."))
    except ValueError:
        messages.error(request, _("Das Umsetzungsregister führt nur angenommene Anträge."))
```
(`VollzugAusgesetzt` aus `verfahren.models` importieren; neue msgid → .po.)

## Befund #32 — Stichtag der Stimmberechtigung

Umgesetzt: `Antrag.stimmberechtigung_stichtag` (Migration `verfahren/0017`, Nachtrag für
laufende Abstimmungen mit dem damals verwendeten UTC-Datum), gesetzt in `Antrag.fortschreiben`
und `Entwurf._endabstimmung_oeffnen` mit `timezone.localdate(...)`; Lesehilfe
`Antrag.stichtag_der_stimmberechtigung()` (gespeicherter Tag, sonst Wiener Tag des Phasenbeginns).

**Cluster A2, `verfahren/views_aktionen.py`:** die beiden Stellen `stichtag = antrag.phase_beginn.date()`
(`abstimmen`, ca. Zeile 420; `kandidatur_zustimmen`, ca. Zeile 674) ersetzen durch
`stichtag = antrag.stichtag_der_stimmberechtigung()`. Bis dahin prüfen Zählung und
Einzelprüfung zwischen 0 und 2 Uhr verschiedene Tage.

## Befund #33 — Fristzeitpunkt statt Aufrufzeitpunkt

Umgesetzt in `Entwurf.fortschreiben` (`wirksam = review_frist` bzw. `ueberarbeitung_frist`,
auch im Audit). Neuer Management-Befehl `verfahren_fortschreiben` (verfahren/management/commands)
für einen Cron; idempotent.

**Cluster D, `render.yaml`:** einen Cron-Dienst ergänzen, z. B.

```yaml
  - type: cron
    name: plattform-fortschreiben
    runtime: python
    schedule: "0 */6 * * *"
    buildCommand: pip install -e .
    startCommand: python manage.py verfahren_fortschreiben
    envVars: (wie der Web-Dienst; POSTGRES_* fromDatabase plattform-db)
```
Und der Kommentar in `verfahren/views.py:695` („Produktion: zusätzlich Cron“, Cluster A1) stimmt
erst, wenn der Cron eingerichtet ist — bis dahin ehrlicher: „Produktion: `verfahren_fortschreiben`
per Cron, sobald eingerichtet“.

## Befund #34 — Werkstatt nach Beratungsende

Umgesetzt (gremien/views.py `fenster_aktion`, `Entwurf.einreichen`, fenster.html). Beim Prüfen
aufgefallen, **Cluster A1, `verfahren/chat.py` `ruht_wegen_werkstatt`:** Die Sperre gilt für
jeden Entwurf im Status IN_ARBEIT/PRUEFUNG — auch nach dem Beratungsende. Endet die Beratung
mit einem nie eingereichten Fenster (Runde 1), geht der Antrag in die Abstimmung, und
`chat_offen` bleibt für die ganze Abstimmung False („Der Expertenrat arbeitet am Vorschlag“).
Vorschlag:

```python
def ruht_wegen_werkstatt(antrag) -> bool:
    from plattform_core import Phase
    if antrag.phase != Phase.BERATUNG.value:
        return False  # nach der Beratung arbeitet die Werkstatt nicht mehr (Befund #34)
    ...
```

## Befund #38 — Rollen zählen Menschen

Umgesetzt: `Rolle.personen(rollen)`, Nenner in `aktive_rollen`, `_integritaetsrat_beschlussfaehig`,
Anzeige „besetzt“ (integritaet/koordination), Abweisung einer zweiten parteiweiten Rolle in
`rollen_aktion`. Kein Cluster-fremder Bedarf.

## Befund #44 / #77 / #80 — Abfragen je Zeile

Umgesetzt (`unvereinbarkeiten_laden`/`unvereinbar_fuer`, `quoren_fuer`, `auslosung`-Ansicht).
Nebenbefund des Nachprüfers zu #77: Der Schlüssel `gremien-beschluesse-seite` (gremien/views.py
`_register(..., 50)`) steht nicht im ERSTBESTAND — **Cluster D** möge ihn ergänzen (Gruppe
„gremien“, Wert 50, Einheit „Beschlüsse“, Quelle „§ 6 Abs 9 (Anzeige)“), sonst zeigt das
Register eine Stellgröße nicht, die der Code liest.

## Befund #57 — Kettenkopf

Umgesetzt als Ist-Stand in der Docstring von `plattform_core/hashchain.py` (Weg 1 des
Nachprüfers). Der kleine Bau (Kopf auf /uebersicht/ und in kennzahlen.json, Cron in eine Datei)
liegt bei A2 (`uebersicht/**`, `parameter/kennzahlen.py`) und D (Cron) — `AuditEintrag.objects
.order_by("-lfd").values("lfd", "hash").first()` liefert den Kopf.

## Befund #69 — Bearbeitungsfenster

Umgesetzt in `Kommentar.bearbeitungsfenster_minuten()` / `darf_bearbeiten`. **Cluster A1,
`verfahren/templates/verfahren/_chat_beitrag.html:46`:** „Ändern geht in den ersten fünf
Minuten.“ ist hart. Vorschlag: in `verfahren/views.py` `_chat_lage` die Kontextvariable
`"bearbeitungsfenster": Kommentar.bearbeitungsfenster_minuten()` ergänzen und in der Vorlage
`{% blocktranslate count n=chat.bearbeitungsfenster %}Ändern geht in der ersten Minute.{% plural %}Ändern geht in den ersten {{ n }} Minuten.{% endblocktranslate %}`.
Der Filter `darf_bearbeiten` in `verfahren/templatetags/chat.py` (A1) ruft nur die Methode und
stimmt; seine Docstring („von fünf Minuten“) bitte auf „aus dem Register“ ändern.

## Befund #72 / #73 / #76 — Beschlussnummer

Umgesetzt in `GremienBeschluss.save` (`_naechste_nummer`: höchste vergebene + 1, Wiederholung
bei IntegrityError außerhalb des Savepoints; Jahr aus `timezone.localtime`). Vergebene Nummern
bleiben. Kein Cluster-fremder Bedarf.

## Befund #74 — Migration 0003 rückwärts

Umgesetzt (`RunPython.noop`, Wächter `gremien/test_migrationen.py`).

## Befund #81 — Indizes

Umgesetzt (`Antrag.Meta.indexes`, `GremienBeschluss.Meta.indexes`, `Fachliste.Meta.indexes`,
Migrationen `verfahren/0019`, `gremien/0016`). Der Ausdrucksindex auf `ereignis->>'antrag'`
gehört zu Befund #2 (nicht in meiner Liste).

## Befund #27 — Rücknahmen dokumentiert (teilweise)

Umgesetzt in `verfahren/models.py`: `BewerbungsZustimmung.zurueckgenommen_am` + `gueltige()`,
`bewerbung_zustimmen` stempelt statt zu löschen (Audit `personenwahl_stimme` /
`personenwahl_stimme_zurueckgenommen`), `kandidatur_auszaehlen` zählt nur gültige;
`Unterstuetzung.zurueckgezogen_am` + `gueltige()`, die Zählstellen in meinen Dateien
(`Antrag.fortschreiben`, `Entwurf.votum_stand`) filtern schon. Migration `verfahren/0018`.

**Zusammenführung — dieselbe Auslieferung, sonst zählen zurückgenommene Zustimmungen mit:**
- **A1, `verfahren/views.py`:** `_beteiligung` →
  `BewerbungsZustimmung.gueltige().filter(bewerbung__antrag=antrag).values("pseudonym").distinct().count()`;
  `antrag_detail` (meine_zustimmungen) → `BewerbungsZustimmung.gueltige().filter(bewerbung__antrag=antrag, pseudonym=reg.pseudonym)`.
- **A2, `verfahren/views_aktionen.py` `export_json` (Zeile ~726):**
  `for z in BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag).order_by(...)` mit
  `{"pseudonym": ..., "bewerbung": ..., "zurueckgenommen_am": z.zurueckgenommen_am.isoformat() if z.zurueckgenommen_am else None}`
  — so bleibt der Export vollständig UND nachrechenbar (die Auszählung zählt `gueltige()`).
- **Unterstützungen (A2, `verfahren/views_aktionen.py` `unterstuetzen`, Zeile ~239-245):**
  statt `.delete()`:
  ```python
  eintrag, neu = antrag.unterstuetzungen.get_or_create(mitglied=request.user)
  if not neu and eintrag.zurueckgezogen_am is None:
      eintrag.zurueckgezogen_am = timezone.now(); eintrag.save(update_fields=["zurueckgezogen_am"]); typ = "unterstuetzung_zurueckgezogen"
  else:
      eintrag.zurueckgezogen_am = None; eintrag.save(update_fields=["zurueckgezogen_am"]); typ = "unterstuetzung"
  AuditEintrag.anhaengen({"typ": typ, "antrag": antrag.pk})  # ohne Mitglieds-ID
  ```
  **Nur zusammen mit** den Filtern `zurueckgezogen_am__isnull=True` an allen Zählstellen:
  A1 `verfahren/views.py` (Zeilen ~142, 161, 275, 487, 658, 755, 801), A1 `verfahren/chat.py:337`
  (`darf_reagieren`), A1 `verfahren/archiv.py:206`, A2 `views_aktionen.py:185, 555`,
  A2 `parameter/kennzahlen.py` (falls Unterstützungen gezählt werden), B `mitglieder/**` (falls).
  Bis A2 umstellt, bleibt das Feld ohne Wirkung (keine Zeile trägt den Stempel) — nichts bricht.

## Befund #64 — Beschriftungen übersetzbar (teilweise)

Umgesetzt mit `gettext_lazy`: gremien (Gremium, Anlass, BeschlussStatus, Aussetzung.Gegenstand,
Regelpruefung.Ergebnis, HinweisQuelle, HinweisStatus, Pruefung.KoratEntscheid), verfahren
(Meldung.Grund, Vollzugsstatus, Reaktionsart), ki.Zweck, parameter.Status,
mandatare.Aufgabenstatus; `integritaet.html` übersetzt die IR_ANLAESSE-Namen mit
`{% translate name %}`, die Namen selbst bleiben deutsch (der gespeicherte `gegenstand` hängt
nicht von der Oberflächensprache ab). Keine Migration nötig (`makemigrations --check` leer).

**Bewusst NICHT umhüllt** — `Ebene`, `Antragsart` (verfahren/models.py) sowie `EntwurfsStatus`
und `Pruefung.Ergebnis` (gremien/models.py): Ihre `get_…_display()`-Werte fließen in
`verfahren/archiv.py` (Zeilen 90, 100, 201, 202, **Cluster A1**) in ein Wörterbuch, das
`archiv_json` (archiv.py:216) mit dem Standard-`json.dumps` ausgibt — ein lazy-Objekt wirft
dort `TypeError: Object of type __proxy__ is not JSON serializable`, und der Archiv-Export
fiele aus. Vorschlag für A1 (eine Zeile): `json.dumps(archiv(antrag), ensure_ascii=False,
indent=2, cls=DjangoJSONEncoder)` (`from django.core.serializers.json import DjangoJSONEncoder`;
er gibt lazy-Strings als Text aus). **Danach** in C-Dateien die vier Klassen umhüllen — je
Zeile `"Bund"` → `_("Bund")` usw. (verfahren/models.py `Ebene`, `Antragsart`; gremien/models.py
`EntwurfsStatus`, `Pruefung.Ergebnis`); `_` ist in beiden Modulen importiert. Neue msgids dafür
stehen schon in NEUE_TEXTE_C.md („Bund“, „Sachantrag“, „Mandats-Kandidatur“, „in Arbeit
(Expertenrat)“, …); „Land“, „Bezirk“, „Gemeinde“ sind im Katalog.
