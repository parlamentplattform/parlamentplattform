# NOTIZEN_A2 — Änderungsvorschläge für Dateien anderer Cluster und offene Teile

Branch `befunde/a2`, Worktree `C:/Users/plav/DDOE-code/wt/a2`. Alles Folgende konnte Cluster A2
nicht selbst umsetzen, weil die Datei einem anderen Cluster gehört oder der Nachprüfer den Teil als
eigenen Bauschritt bezeichnet hat.

## 1. `parameter/models.py` — ERSTBESTAND-Eintrag `uebersicht-abstimmungen` (Befund #43)

`uebersicht/views.py:_abstimmungen()` liest die Grenze der gezeigten Entscheidungen über
`zahl("uebersicht-abstimmungen", 20)`. Ohne Eintrag greift ehrlich der Standard 20 (Tests grün),
aber CLAUDE.md § 4 verlangt zu jeder Stellgröße einen Erstbestand. Bitte in `ERSTBESTAND`
hinter `kacheln-abgeschlossen` einfügen:

```python
    {
        "schluessel": "uebersicht-abstimmungen",
        "wert": "20",
        "einheit": "Einträge",
        "gruppe": "kacheln",
        "beschreibung": "Wie viele entschiedene Abstimmungen die öffentliche Übersicht zeigt, bevor sie auf "
        "Umsetzungsregister und Parlament verweist. Laufende Abstimmungen erscheinen immer — nur mit "
        "Beteiligung, die Tendenz bleibt bis zum Fristende verdeckt.",
        "quelle": "§ 5 Abs 10 lit d · § 5 Abs 3 lit e (F-15)",
    },
```

Falls `erstbestand_sicherstellen()` in einer bestehenden Datenbank nachzieht (idempotent), braucht es
keine Datenmigration. `uebersicht/test_uebersicht.py:145` legt den Parameter im Test selbst an.

## 2. `verfahren/views.py` — `_beteiligung()` mit Filter auf nicht zurückgezogene Bewerbungen (Befund #26)

Der Nachprüfer verlangt, dass Kachel-Beteiligung und Auszählung dieselbe Zahl liefern.
`_beteiligung()` (verfahren/views.py:110-119) zählt Pseudonyme über alle Zustimmungen, auch zu
zurückgezogenen Bewerbungen; `kandidatur_auszaehlen` (verfahren/models.py:405-415) filtert
`bewerbung__zurueckgezogen=False`. Seit A2 den Rückzug ab Abstimmungsbeginn sperrt, kann der
Unterschied im Regelbetrieb nicht mehr entstehen — er bleibt aber für Altdaten und für Rückzüge in
Unterstützung/Beratung, bei denen schon Zustimmungen vorliegen könnten (heute nicht möglich, da
Zustimmen erst in der Abstimmung geht). A2 hat den gemeinsamen Helfer `parameter/kennzahlen.py:
abgegeben_je_antrag()` bereits mit dem Filter gebaut. Vorschlag für A1, Zeile 114-116:

```python
        abgegeben = (
            BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag, bewerbung__zurueckgezogen=False)
            .values("pseudonym")
            .distinct()
            .count()
        )
```

Docstring ergänzen: „… mit mindestens einer Zustimmung zu einer nicht zurückgezogenen Bewerbung —
dieselbe Regel wie `kandidatur_auszaehlen`, damit Kachel und Ergebnis nicht auseinanderlaufen."
Alternativ `_beteiligung` durch `parameter.kennzahlen.abgegeben_je_antrag([antrag])[antrag.pk]` ersetzen.

## 3. `config/settings.py` — LOGGING für `django.request` (Befund #17 / #52)

A2 hat seinen Teil erledigt: Die 500-Seite verspricht nicht mehr „Er ist protokolliert und wird
angesehen" (`verfahren/templates/500.html`, Test `test_die_fuenfhunderter_seite_verspricht_nichts_unwahres`).
Die LOGGING-Einstellung baut Cluster D (laut Regeln). Sobald sie steht, kann der Satz zurückkehren —
dann bitte in 500.html wieder aufnehmen und den Test umdrehen. Schlankste Fassung nach Nachprüfer:

```python
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"stderr": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["stderr"], "level": "WARNING"},
    "loggers": {"django.request": {"handlers": ["stderr"], "level": "ERROR", "propagate": False}},
}
```

## 4. Befund #53 — Korrekturlauf selbst (Zukunftswerkstatt) ist ein eigener Bauschritt (S11)

Texte in Flash (`views_aktionen.py`), Hilfetext (`_zone_einschaetzung.html`) und
`zukunftswerkstatt.html` sagen jetzt, dass der Korrekturlauf noch nicht gebaut ist. Den Lauf selbst
(Zweck KORREKTUR in `ki/models.py`, Posteingang des Koordinationsrats, Schreiben von
`Beanstandung.erledigt_am`/`erledigt_vermerk`) hat der Nachprüfer als eigenen Bauschritt
bezeichnet — nicht Teil dieser Behebung. Sobald er existiert: die drei Texte zurückdrehen.

## 5. Befund #4/#13 — Alternativzweig (Entscheidung des Gründers) bewusst weggelassen

Umgesetzt ist D-D2 (a): überall verdeckt bis Fristende. Ein Wechsel auf (b)/(c) wäre ein Eintrag in
Teil D des Fahrtenbuchs, kein Bauschritt (so der Nachprüfer). Die Hauptarbeit möge den Widerspruch in
Fahrtenbuch Detail:1136 und SollIst:43 als erledigt markieren.

## 6. Befund #71 — kein Badge nach `gewonnen_id`

Der Nachprüfer hat den Vorschlagsteil „Badge nach gewonnen_id statt Phase" als überflüssig
bezeichnet; die Übersicht führt das Badge weiter nach Phase (`fortschreiben` setzt ANGENOMMEN
nur bei gewählter Bewerbung). Zusätzlich zeigt sie bei Personenwahlen „Gewählt: Name mit n
Zustimmungen" bzw. „Keine Bewerbung gilt als gewählt."

## 7. Hinweise für die Zusammenführung

- `uebersicht/views.py` ist stark umgebaut (`_abstimmungen()` neu: eine Stimmenabfrage, Grenze aus
  dem Register, Personenwahlen, laufende nur mit Beteiligung); `uebersicht/templates/uebersicht/uebersicht.html`
  entsprechend. `parameter/kennzahlen.py` hat den neuen Helfer `abgegeben_je_antrag()`, den
  `werte()` (votes.turnout_mean) und die Übersicht teilen.
- `verify/nachrechnen.py` ist um `personenwahl_nachrechnen()` gewachsen; `nachrechnen()` verzweigt
  nach `art`. Wer das Skript aus Doku zitiert (`docs/SCHEMA.md:104`, `partner.html:114`,
  `regelwerk.py:172`), braucht nichts zu ändern — Aufruf und Sachfragen-Ausgabe sind gleich,
  nur das Feld `art: sache` kommt hinzu.
- Neue Vorlage `verfahren/templates/403_csrf.html` (Django findet sie über den festen Namen
  `CSRF_FAILURE_TEMPLATE_NAME`; keine Einstellung nötig).
- Tests ergänzt in `verfahren/test_kandidatur.py` (Cluster C, nur Ergänzungen) und
  `verfahren/test_oeffentliche_texte.py`.
