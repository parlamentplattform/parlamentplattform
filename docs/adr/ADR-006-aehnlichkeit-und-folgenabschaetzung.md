# ADR-006: Ähnlichkeitshinweis und Folgenabschätzung — assistierend, gestuft, nie blockierend

Status: angenommen · Datum: 2026-08-19

## Kontext
Beim Einbringen eines Antrags soll das System erkennen, ob ein inhaltlich
ähnlicher Antrag bereits existiert, und ihn zur Unterstützung vorschlagen —
statt dass dieselbe Idee in zehn Varianten zersplittert. Später soll eine
Analyse zeigen, welche bestehenden Normen ein Antrag berührt und welche
Auswirkungen die StaatsSimulation berechnet. § 2 Abs 6 der Satzung setzt die
Grenze: Automatisierte Systeme dürfen zusammenfassen, übersetzen, Dubletten
erkennen und nach offengelegten, nachrechenbaren Regeln kategorisieren — sie
dürfen Anträge niemals bewerten, priorisieren, zurückweisen oder ausschließen.

## Entscheidung
Drei Stufen, jede einzeln abschaltbar, jede mit demselben Grundsatz:
**Der Hinweis ist ein Angebot. Die Entscheidung trifft der Mensch.**
„Trotzdem einbringen" ist in jeder Stufe ein gleichwertiger, nie versteckter Weg.

1. **Stufe 1 (jetzt): lexikalische Ähnlichkeit, vollständig nachrechenbar.**
   Trigramm-Überlappung über Titel und Wortlaut (normalisiert: Kleinschreibung,
   Satzzeichen entfernt). Der Algorithmus steht in
   `plattform_core/similarity.py`, ist deterministisch, benötigt kein Modell
   und keine externen Dienste; der angezeigte Score ist von jedem Mitglied
   von Hand nachprüfbar. Angezeigt werden die drei ähnlichsten offenen
   Anträge oberhalb einer offengelegten Schwelle.
2. **Stufe 2 (später): semantische Suche.** Lokal betriebene Embeddings
   (kein Datenabfluss an Dritte), Modellname und -version werden am Hinweis
   angezeigt; Stufe 1 bleibt als nachrechenbare Zweitmeinung daneben bestehen.
3. **Stufe 3 (später): Normbezüge und Folgenabschätzung.** Erkennung, welche
   Gesetze/Normen ein Antrag berührt (Abgleich mit dem Rechtsinformationssystem
   des Bundes), und Durchrechnung von Auswirkungen in der StaatsSimulation —
   angezeigt als gekennzeichnete Modellrechnung mit Annahmen und
   Unsicherheiten (§ 6 Abs 4), die keine Abstimmung bindet.

## Konsequenzen
+ Stufe 1 ist sofort einsatzfähig, kostenlos, offline und erfüllt die
  Nachrechenbarkeits-Anforderung wörtlich.
+ Die Stufen-Architektur verhindert, dass eine KI-Abhängigkeit in den
  Kern einzieht: Jede Stufe ist ein Zusatz, kein Torwächter.
− Lexikalische Ähnlichkeit übersieht Umformulierungen — bewusst in Kauf
  genommen, bis Stufe 2 lokal und geprüft betrieben werden kann.
− Forschungsbefund als ständige Mahnung: Sprachmodelle unterrepräsentieren
  Minderheitenpositionen systematisch. Deshalb entscheidet auch in Stufe 2/3
  nie das Modell, und der Integritätsrat prüft die Hinweise jährlich (§ 2 Abs 6).
