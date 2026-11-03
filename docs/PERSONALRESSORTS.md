# Amtliche Personalstände nach Ressort

Der Baustein0.71 übernimmt ausschließlich Tabelle7 des schon bekannten amtlichen
Berichts **Das Personal des Bundes2026 – Daten und Fakten**, gedruckteSeite30.
Stichtag31.12.2025, vierzehn Ressort-/Organezeilen plus getrennte Gesamtzeile.
Die Spalten sind Gesamt, Zentralstelle und nachgeordnete Dienststellen. Diese
Tabelle enthält keine Aufteilung nach Beamten und Vertragsbediensteten je Ressort.
Sie wird deshalb getrennt vom bisherigen PersonalAggregat gespeichert.

## Quelle und überprüfbare Grenzen

Quelle: [Bundeskanzleramt, Personalbericht2026](https://oeffentlicherdienst.gv.at/wp-content/uploads/2026/03/Das-Personal-des-Bundes-2026-1.pdf).
Der bekannte Original-SHA256 lautet
`40e720bb4aee9ae26df87452498c9e1021966d4b9a54288c46ccafa7b06ffd63`.
Unbekannte Bytes und zu große Dateien werden vor dem PDF-Parser abgewiesen.
Gelesen werden nur die beiden bekannten Seiten mit Tabelle und Methodik, keine
frei ausgewählte PDF-Seite oder Modelltranskription. Es wird keine öffentliche
Vollkopie der Publikation angelegt; der Link führt zum Herausgeber.

Die Methodik auf gedruckterSeite175 (PDFindex176) belegt Stichtag, Abgrenzung,
VBÄ als grundsätzliche Messgröße sowie mögliche Rundungsunterschiede. Die dortige
Originalfußzeile nennt2025, obwohl der Bericht2026 heißt; das Original wird nicht
nachträglich korrigiert. Die Verweise geben die tatsächlich benutzten Seiten an.
VBÄ bezeichnet Vollbeschäftigtenäquivalente, keine Anzahl einzelner Menschen und
keine freie Kapazität für neue Vorhaben. Datenjahr, Publikationsjahr und Stichtag
werden getrennt gezeigt. Die Ressortabgrenzung ist die des angegebenen Stands.

Die reine Regel `plattform_core/personalressorts.py`, Fassung1, prüft Tabellenkopf,
Spaltenfolge, alle vierzehn amtlichen Bezeichnungen in ihrer ursprünglichen Folge,
Gesamtzeile und Methodik. Sie korrigiert nur zwei nachgewiesene Wortumbrüche der
Textauswertung. Leere Originalteilfelder bleibennull, nicht0. Unterschiedliche
gerundete Summen werden weder ausgeglichen noch durch berechnete Zahlen ersetzt.

## Übernahme und Archiv

```text
python manage.py personal_ressorts_import --datei <bekannte-originaldatei.pdf>
python manage.py personal_ressorts_import --amtliche-quelle
```

Der amtliche Einzelbezug verwendet denselben festen Download, die bestehenden
Netzgrenzen und das gemeinsame Stundenkontingent/Mindestintervall der Faktenbasis.
Keine automatische Produktionsbefüllung, kein Sammelabruf, kein neuer Dienst oder
Kostenrahmen. Ein Dateibezug geht nicht ins Netz. Ein GET übernimmt keine Daten.

Die additive Migration0006 legt nur getrennte Ressorttabellen und Abrufnachweise
an. Vorhandene Aggregate, Metadaten, Texte und Modelleingaben werden nicht geändert.
Originalhash und Parserfassung identifizieren den Tabelleninhalt. Eine Wiederholung
behält alle Daten und den ersten Zeitpunkt; jeder Versuch bleibt separat dokumentiert.
Fehler entfernen keine früheren Zahlen. Der gewöhnliche ORM darf weder Inhalt noch
Abruf nachträglich ersetzen oder löschen; privilegiertes SQL ist dadurch nicht gesperrt.

## Öffentliche Nachlese und Export

`/zukunftswerkstatt/faktenbasis/personal/ressorts/` zeigt die übernommenen Tabellen
nach jüngstem Stichtag und Erfassungszeitpunkt. Die Detailansicht behält die amtliche
Zeilenfolge; die Gesamtzeile wird nicht als weiteres Ressort mitgezählt. Leere Felder
heißen ausdrücklich nicht angegeben. Deutsch/Englisch sowie Bedienung ohne JavaScript.

`.../ressorts/<id>/nachweis.json` enthält Stichtag, Datenjahr, Einheit, alle Originalwerte,
Publikation, Quelle, Tabellen-/Methodikseite, Originalhash, Parserfassung und Erfassungszeit.
Keine Einzelpersonen oder lokale Dateipfade. Der bisherige Personal-Aggregatexport bleibt
unverändert. Ressorttabellen gelangen nicht automatisch in Modellaufträge oder alte Eingaben.
Rechtsfolgen, Stellenbedarf, freie Kapazität, Prognosespannen und S11-Gesamtabnahme bleiben offen.
