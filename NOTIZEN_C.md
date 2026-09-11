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
