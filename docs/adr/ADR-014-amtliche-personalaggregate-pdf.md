# ADR-014: Bekannten amtlichen Personalbeleg deterministisch lesen

Status: technische Implementierungsentscheidung im freigegebenen Faktenbasis-Ausbau.
Datum: 3. November 2026. Keine neue Gründerentscheidung oder Freigabe eines Dienstes.

## Problem

Die Rechtsfolgen-Aufbereitung braucht eine amtliche aggregierte Personalgrundlage.
Der aktuelle Personalbericht2026 des Bundeskanzleramts enthält auf gedruckter
Seite75, Tabelle20, eine eindeutig gegengeprüfte Zeile zum Datenjahr2025. Die
Einheit ist VBÄ und nicht die Anzahl einzelner Beschäftigter. Ein passendes
maschinenlesbares CSV-Original wurde in der Quellenprüfung nicht nachgewiesen.
Eine Modellantwort oder eine freie JSON-Transkription darf keinen Fakt erzeugen.

## Entscheidung

`pypdf>=5,<7` wird aus der bereits vorhandenen Entwicklungsabhängigkeit in die
Laufzeitabhängigkeiten übernommen. Es kommt kein zusätzlicher Dienst hinzu.
Die gelesenen Originalbytes müssen vor dem PDF-Parser genau den bekannten
SHA-256 des visuell geprüften amtlichen Belegs haben und innerhalb der technischen
Größengrenze liegen. Unbekannte oder veränderte PDFs werden nicht verarbeitet.

Der Parser liest nur die bekannte Seite, prüft Publikation, Seitenzahl,
Tabellenüberschrift, Spaltenfolge, Datenjahr und Fußnote zur Einheit. Er nimmt
die drei Zahlen aus der passenden Tabellenzeile und prüft deren Summe. Neue
Publikationen und andere Jahrgänge brauchen eine neue, belegte Quellenfassung.
Es gibt keine OCR, Titelsuche oder Modellkorrektur bei unpassenden Daten.

Das Original-PDF wird nicht in das öffentliche Repository eingecheckt oder als
neue öffentliche Kopie angeboten. Ein späterer Datenimport muss Zahlen, Einheit,
Abgrenzung, Quelle, Seite, Originalhash und Parserfassung nennen. Quelle:
[Bundeskanzleramt, Personalbericht2026](https://oeffentlicherdienst.gv.at/wp-content/uploads/2026/03/Das-Personal-des-Bundes-2026-1.pdf).

## Grenzen und weitere Schritte

Dieses Fundament führt keinen Netz- oder Datenbankaufruf aus. Ein späterer
ausdrücklicher Einzelimport und seine öffentliche Nachlese sind eigene Schritte.
Keine automatische Produktionsbefüllung und keine nachträglichen Werte für
laufende Modellaufträge. Bestandszahlen sind keine freie Personalkapazität,
Personalbedarfsprognose oder Belastungsampel. Personenbezogene Listen bleiben
ausgeschlossen. Keine Satzung, feste Verfahrensregel, Budgetgrenze oder Stimme
wird geändert.
