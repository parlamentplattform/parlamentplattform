# ADR-005: Audit-Log als Hash-Kette mit veröffentlichtem Tagesanker — keine Blockchain

Status: angenommen · Datum: 2026-08-19

## Kontext
Verfahrensereignisse müssen nachträglich unverfälschbar dokumentiert sein
(§ 5 Abs 8). Eine Blockchain löst dieses Problem nicht besser, kostet aber
Verständlichkeit, Betriebskomplexität und Erklärbarkeit.

## Entscheidung
Append-only-Tabelle; jeder Eintrag speichert SHA-256(vorgänger_hash +
kanonisches_ereignis). Der jeweils aktuelle Kettenkopf wird täglich außerhalb
des Systems veröffentlicht (Website, Repository). Implementierung in
plattform_core/hashchain.py (~60 Zeilen), erklärbar in einem Satz: "Jeder
Eintrag versiegelt alle vorherigen."

## Konsequenzen
+ Manipulation erfordert Fälschung aller Folgeeinträge UND aller extern
  veröffentlichten Anker — praktisch erkennbar.
+ Für Laien erklärbar; keine neue Infrastruktur.
− Kein Schutz gegen das Weglassen der jüngsten, noch nicht verankerten
  Einträge — der Anker-Rhythmus (täglich) begrenzt dieses Fenster und ist
  bewusst dokumentiert.
