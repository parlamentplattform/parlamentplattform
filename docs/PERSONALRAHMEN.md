# Personal-Bestandsrahmen

`faktenbasis.personalrahmen` Fassung1 hält vorhandene Personalbelege für den
getrennten Rechtsfolgenauftrag fest. Die Erfassung selbst löst keinen Anbieter-
aufruf oder Import aus. Quelle und damaliger Leer-/Teil-/Fehlerstand sind in der
Berichtsanzeige gesondert nachlesbar. Keine Kapazitäts- oder Folgenprognose.

Der Rahmen umfasst ausdrücklich nur die bekannte Publikation „Das Personal des
Bundes 2026 – Daten und Fakten“: Gesamtzeile 2025 nach Dienstverhältnis und
Tabelle 7 mit Ressortbeständen zum 31.12.2025. Quelle, Originalhash, Parserfassung,
Publikation, Tabellen-/Methodikseite und Einheit werden geprüft. Höchstens zwei
lokale, auf jeweils zwei Ergebnisse begrenzte Abfragen; mehrdeutige Datensätze
führen zu einem Fehlerstand. Keine Suche nach vermeintlich betroffenen Ressorts,
keine Gemeinde-/Landeszuständigkeit aus einem Ortsnamen.

`leer`, `teilweise`, `vorhanden` und `fehler` unterscheiden fehlende und tatsächlich
vorhandene bekannte Belege. „Vorhanden“ bedeutet beide Teile dieser Publikation,
keinen vollständigen oder aktuellen österreichweiten Personalbestand. Nach dem
Erfassungszeitpunkt gespeicherte Belege werden nicht rückwirkend eingefügt.
Ein fehlerhafter Teil wird nicht durch den anderen als vollständiger Rahmen
ausgegeben. Frühere Daten und Kontexte werden nicht verändert.

VBÄ sind Bestände, keine Kopfzahlen, frei verfügbare Kapazitäten oder geschätzten
Personalfolgen. Leere Teilspalten bleiben null; Originalrundungen bleiben
unverändert. Der globale Beamten-/Vertrags-Split wird keinem Ressort zugeordnet.
Es werden keine Deltas, Stellenprognosen oder Bedarfsspannen erzeugt.

Der gesamte Rahmen ist an die Textprüfsumme und Erfassungszeit gebunden. Seine
spätere Prüfung liest keine neueren Daten nach. Der Hash weist einen gespeicherten
Stand nach; er bietet keinen Schutz gegen privilegiertes SQL oder eine
kompromittierte Originalquelle. Die vorhandenen Faktenmodelle bleiben über
gewöhnliche ORM-Wege unveränderlich.
