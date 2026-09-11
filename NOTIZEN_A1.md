# NOTIZEN Cluster A1 — Antragsseite, Chat, Parlament, Design-System

Branch `befunde/a1`, Worktree `C:/Users/plav/DDOE-code/wt/a1`, abgezweigt von c5a0902.
Alle Änderungen liegen in A1-Dateien; was andere Cluster brauchen, steht hier als konkreter Vorschlag.

## Für Cluster C (Kern)

### Befund #22 — Auswertung der Vorschlagsrunde am Audit-Ereignis festschreiben
`verfahren/archiv.py` (`schwelle_der_runde`) liest jetzt die Schwelle einer abgeschlossenen Runde aus dem
Audit-Ereignis, das sie beendet hat — bevorzugt aus einem strukturierten Feld `auswertung`, sonst aus dem
Wortlaut „(Schwelle NN %)“ der Rechnung. Das Feld schreibt noch niemand. Vorschlag für
`gremien/models.py`, `Entwurf.fortschreiben`, Zweig `EntwurfsStatus.UNTERSTUETZER` (Zeilen ~470–490):

```python
festgehalten = {k: stand[k] for k in ("ja", "nein", "prozent", "schwelle", "oben", "angenommen", "grund", "reihung")}
festgehalten["runde"] = self.runde
```
und dieses Dict als `"auswertung": festgehalten` in beide Ereignisse aufnehmen:
- in `zurueck_an_gruppe_1(...)` → das `vorschlag_zurueckgegeben`-Ereignis (Zeile ~373; dort zusätzlich
  `"auswertung"` als Parameter durchreichen — Achtung: `self.runde` ist dort schon hochgezählt, im Dict steht
  die entschiedene Runde),
- in `_endabstimmung_oeffnen(...)` → das `phasenwechsel`-Ereignis (Zeile ~400).
Sobald das Feld da ist, braucht archiv.py keinen Wortlaut mehr zu lesen (der Rückfall bleibt für Altdaten).
Kommt mit Befund 0 eine eingefrorene Schwelle in die Policy, kann `_auswertung` sie zusätzlich aus
`antrag.policy()` nehmen — den Schlüsselnamen bitte mitteilen.

### Befund #39 — Pfad am Lebensbereich speichern
A1 lädt die Elternkette jetzt per `Prefetch("kategorien", queryset=Kategorie.objects.select_related(
"eltern__eltern__eltern__eltern__eltern"))` (`verfahren/views.py::_mit_pfad`) — sechs Ebenen, mehr hat der
Baum nicht. Dauerhaft besser (Vorschlag des Nachprüfers): Feld `pfad = models.CharField(max_length=400,
blank=True)` an `Kategorie` (`verfahren/models.py`), beim Import in `kategorien_laden` gesetzt (der Befehl
kennt den ganzen Baum, Slugs sind stabil), `pfad`/`pfad_kurz`/`tiefe` lesen daraus ohne Abfrage. Migration:
Feld + Datenmigration (idempotent, RunPython.noop rückwärts). Danach kann `_mit_pfad` auf ein schlichtes
`prefetch_related("kategorien")` zurück.

### Befund #41 — Index für die Audit-Spur je Antrag
`archiv.audit_spur` filtert jetzt `AuditEintrag.objects.filter(ereignis__antrag=antrag.pk)` in der Datenbank.
Ohne Index bleibt das auf PostgreSQL ein Seq-Scan über das ganze Log. Vorschlag `verfahren/models.py`,
`AuditEintrag.Meta`:

```python
from django.db.models.fields.json import KeyTransform

indexes = [models.Index(KeyTransform("antrag", "ereignis"), name="audit_antrag_idx")]
```
Wichtig (Nachprüfer): `ereignis__antrag=pk` kompiliert auf PostgreSQL zu `("ereignis" -> 'antrag')` (jsonb),
also `KeyTransform`, **nicht** `KeyTextTransform` (`->>`, text) — ein Text-Index läge brach. Alternative:
`GinIndex(fields=["ereignis"])` (django.contrib.postgres) plus Filter `ereignis__contains={"antrag": pk}`;
dann müsste archiv.py den Filter umstellen. Eigene Migration, nur Index (Grundregel 7).

## Für Cluster A2 (Handlungen)

### Befund #30 — eigene Meldung beim Abstimmen während einer Aussetzung
`verfahren/views_aktionen.py::abstimmen` (vor `stimme_abgeben`, Zeile ~427):

```python
if antrag.aussetzung_laeuft():
    messages.error(request, _("Die Abstimmung ist durch den Integritätsrat ausgesetzt (§ 6 Abs 3 lit d) — "
                              "solange sie ruht, werden keine Stimmen angenommen; die Frist läuft danach weiter."))
    return _zurueck_zum_antrag(request, antrag)
```
Die Antragsseite zeigt die laufende Aussetzung schon als Band mit Beschlussnummer (A1, antrag.html).
Neuer Nutzertext → NEUE_TEXTE_A2.

## Für Cluster D (Betrieb, Register, Sprache)

### Befund #42 — neuer Registerschlüssel `chat-faden-wurzeln`
`verfahren/chat.py` liest `zahl("chat-faden-wurzeln", 50)`: wie viele Wurzelbeiträge (samt Antworten) der
Faden auf einmal zeigt; ältere über `?ab=<pk>`. Bitte in `parameter/models.py` ERSTBESTAND und
`plattform_core/schema.py` aufnehmen, Vorschlag:

```python
{
    "schluessel": "chat-faden-wurzeln",
    "wert": "50",
    "einheit": "Beiträge",
    "gruppe": "kacheln",
    "beschreibung": "Wie viele Wurzelbeiträge (mit ihren Antworten) der Chat eines Antrags auf einmal zeigt. "
    "Ältere Beiträge kommen auf Wunsch nach — gelöscht oder verborgen wird nichts; im Abstimmungs-Chat "
    "sind es die vordersten der offengelegten Reihung.",
    "quelle": "§ 5 Abs 3 lit c",
},
```

### Befund #45 — `faecher-kinder-hoechstzahl`
`plattform_core/faecher.py` trägt `KINDER_HOECHSTZAHL = 3` fest; `faecher_layout(zeilen, fokus_slug, abos)`
hat keinen Parameter dafür. Sobald D die Übergabe baut (z. B. `faecher_layout(..., kinder_hoechstzahl=3)`),
ergänzt A1 in `verfahren/views.py::parlament` den Aufruf um
`kinder_hoechstzahl=zahl("faecher-kinder-hoechstzahl", 3)` — eine Zeile, in den Aufruf bei
`faecher = faecher_layout(zeilen, fokus_slug=..., abos=abo_slugs)`. Die übrigen A1-Schlüssel sind gelesen:
`kacheln-hervorgehoben` (Parlament und Startseite), `kacheln-abgeschlossen`, `suche-treffer-hoechstzahl`;
`gespraeche-liste-hoechstzahl` (chat.py, jetzt auch in der Gesprächsseite) und `archiv-audit-anzeige`
(archiv.py) waren es schon.

### Übersetzungen
Neue und geänderte Texte in `NEUE_TEXTE_A1.md`.

## Für die Hauptarbeit

### Befund #40 — Deckelung der neutralen Gruppen (nicht gebaut)
Wie vom Nachprüfer verlangt: Bereich d ist nach FB-B1 DIE Liste aller laufenden Verfahren; eine Deckelung
mit `?mehr=`-Seite ist eine Produktentscheidung → ❓-Eintrag in Fahrtenbuch Teil D vorlegen, erst nach
Entscheidung des Gründers bauen. Der Leistungsteil ist erledigt: Zähler in je einer Abfrage, eine Liste für
alle Bereiche, Gäste ohne Stimmregister-Abfrage; der Abfragezähl-Test in `verfahren/test_views.py` nagelt
fest, dass die Abfragezahl von der Zahl der Anträge unabhängig ist.

### Befund #79 — Zähler langfristig in SQL
Erledigt ist: einmal laden, Zähler daraus, je Anfrage gepuffert (`request._gespraeche_ungelesen`). Der
Kontextprozessor zählt auf allen **anderen** Seiten weiter über `gespraeche(nutzer, grenze=None)` in Python.
Der SQL-Zähler (Gruppierung nach antrag/mitglied/antwort_auf__mitglied mit Lesestand-Join) ist ein eigener
Schritt — nicht angefasst.

### Befund #48 — Datei `_leiste.html`
`verfahren/templates/verfahren/_leiste.html` steht in keiner Cluster-Zuordnung; A1 hat sie für die Kurzformen
(`<span class="lang">`/`<span class="kurz">`) und die Klasse `leiste gast` angefasst (zwei Zeilen + Header).
Der Test `verfahren/test_app_rahmen.py::_leiste` sucht jetzt nach `<header class="leiste` (Präfix).

### Große Umbauten (Zusammenführung)
- `verfahren/views.py`: der Helferblock `_beteiligung` … `_meine_stimmen` (Zähler, Pfad-Prefetch, wirksame
  Beginne, neutraler Schlüssel, `_als_liste`) ist neu geschrieben; `parlament()` lädt `laufende` einmal;
  `antrag_detail` liest `?antwort_auf=`, `?ab=`, `?archiv=`. `_weicherfilter_feed` nimmt weiter ein QuerySet
  (views_aktionen.filter_vorschau) oder eine Liste; neue optionale Parameter `zaehler`, `beginne`.
- `verfahren/chat.py`: `faden()` → `faden_fenster()` + dünnes `faden()`; neue Helfer `mit_zaehlern`, `leicht`,
  `faden_wurzeln`.
- `verfahren/archiv.py`: `zeitleiste(antrag, geoeffnet=None, alles=False)`, `_chat_je_phase(antrag, phasen)`,
  `_anzahl_je_phase`, `schwelle_der_runde`, `_auswertung(antrag, phase, ereignisse)`.
- `base.html`: Medienblöcke der Leiste umgebaut (1279 / 1179 gast / 1023 / 759), Panel-Regeln außerhalb der
  Medienblöcke, Token `--on-deep`, `--stern-aus` neu, `.faden-fenster`, `.faden-mehr`, `.archiv-laden`.
- Neue Vorlage `_chat_mehr.html`; neue Testdatei `verfahren/test_views.py`.
- Bildschirmtests laufen hier nur mit `C:/Users/plav/DDOE-code/venv/Scripts/python` (Playwright); die
  Haupt-`.venv` hat kein Playwright. `tests/e2e/test_chat.py::test_ohne_javascript…` wartet nach Ankersprüngen
  600 ms (scroll-behavior: smooth ließ Klicks als „not stable“ scheitern).
- Dateien, die per Python umgeschrieben wurden, liegen im Worktree mit CRLF; `.gitattributes` normalisiert beim
  Commit auf LF (git status ist sauber).
