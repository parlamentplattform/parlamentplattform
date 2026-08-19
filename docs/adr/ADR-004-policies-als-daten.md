# ADR-004: Verfahrensregeln als versionierte Daten mit Einfrier-Snapshot

Status: angenommen · Datum: 2026-08-19

## Kontext
§ 5 Abs 5 der Satzung: Die Regeln eines Antrags werden bei Einbringung
festgeschrieben; keine Mehrheit kann ein laufendes Verfahren kippen. § 5 Abs 7:
Die Verfahrensordnung entwickelt sich durch Mitgliederbeschluss weiter.

## Entscheidung
Policies sind deklarative Daten (policies/*.yaml → Tabelle Verfahrensordnung),
nicht Code. Beim Einbringen wird die aktive Policy als JSON-Snapshot am Antrag
gespeichert; Phasenautomat und Auszählung lesen ausschließlich den Snapshot.
Die satzungsfesten Untergrenzen (21 Tage Beratung, 7 Tage Abstimmung, 5 %
Mindestbeteiligung) validiert der Konstruktor der Policy-Klasse — eine
satzungswidrige Policy ist technisch nicht ladbar.

## Konsequenzen
+ Neue Verfahrensordnung = neue Datenversion, kein Deployment.
+ Historische Verfahren bleiben exakt reproduzierbar.
− Redundante Speicherung des Snapshots je Antrag — gewollt und billig.
