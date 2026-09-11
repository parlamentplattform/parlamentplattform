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
