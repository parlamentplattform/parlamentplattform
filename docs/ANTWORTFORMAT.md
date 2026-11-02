# Formale Nachlese von Rechtsbezug-Antworten

Seit 0.60.0 prüft die Leseschicht die Form jeder erfolgreichen Rechtsbezug-Antwort.
Das ist eine aktuelle Darstellungsprüfung, kein nachträglich behaupteter Nachweis vom
Zeitpunkt des ursprünglichen Modelllaufs. Originalantwort, Eingabe, Kontext, Zeitpunkt
und Auftragsfassung bleiben unverändert. Ein Formatfehler ändert keinen Auftrag,
kein Budget, kein Stimmrecht und keinen Verfahrensschritt. Er löst keinen Modellaufruf aus.

## Schema und unabhängige Prüfung

`GET /zukunftswerkstatt/antwortformat.json` liefert das vollständige JSON-Schema
(2020-12, Formfassung 1). Die reine Funktion `plattform_core.modellantwort.pruefen`
prüft dessen verwendete Teilmenge ohne Bibliotheksabruf, Datenbank oder Netzwerk.
Das Schema beschreibt Pflichtfelder, Zeichenketten, Listen und bekannte Werte des
bestehenden Rechtsbezug-Auftrags. Es ergänzt ausdrücklich veröffentlichte technische
Darstellungsgrenzen; historische Antworten werden daran gemessen, nicht umgeschrieben.
Es wird kein fremdes Schema und keine modellgelieferte Adresse aufgerufen.

Die Schema-Prüfsumme ist SHA-256 über UTF-8 des Objekts mit `ensure_ascii=False`,
`sort_keys=True`, `separators=(',', ':')`. Die Antwort-Prüfsumme bezieht sich auf die
unveränderte UTF-8-Zeichenkette, einschließlich Leerraum. Außerhalb der technischen
Größengrenze oder bei nicht kodierbarem Rohtext wird kein Antwort-Hash behauptet.

Der Formbefund enthält `fassung`, `zeitbezug: "darstellung"`, `schema_sha256`,
`antwort_sha256`, `gueltig` und eine begrenzte Liste `fehler` mit `pfad` und `code`.
Die Antragsseite zeigt den Befund auch bei älteren Antworten. Ihr JSON-Archivexport
enthält ihn unter `rechtsbezug.laeufe[].antwortformat` (Schema1.16). Fehlgeschlagene Anbieteraufrufe
tragen dort `null`; sie sind keine erfolgreich gelieferten Antworten.

## Grenzen und Diagnosecodes

- Höchstens 100.000 Zeichen vor dem JSON-Parser, Verschachtelungstiefe 32 und 20
  Diagnoseeinträge. Klammern innerhalb von JSON-Zeichenketten zählen nicht als Tiefe.
- Höchstens acht Normen im formalen Schema. Historische tolerant gelesene Antworten
  behalten die bisherige Anzeigegrenze zwölf, erscheinen bei Abweichung aber gewarnt.
- Titel: 1 bis 200 Zeichen, mindestens ein Nicht-Leerzeichen; Kennung höchstens 120,
  Begründung 600, Hinweis 2.000. Nur EU/Bund/Land und die veröffentlichten Änderungstypen.
- Keine zusätzlichen Felder, doppelten Schlüssel, NaN/Infinity oder unpaarigen Unicode-
  Surrogate. Feldnamen aus ungeprüften Zusatzfeldern werden nicht in Diagnosepfade kopiert.

Die Codes `typ`, `pflichtfeld`, `zusatzfelder`, `anzahl`, `laenge`, `muster`, `wert`,
`json`, `doppelte_schluessel`, `kodierung`, `groesse` und `tiefe` benennen ausschließlich
Formabweichungen. Ein Auszug alter eingerahmter Antworten kann weiterhin lesbar sein,
bleibt aber formal abweichend. Mehrdeutige doppelte Schlüssel und technische Grenzen
werden auch beim toleranten Lesen nicht durch eine andere Interpretation umgangen.

## Keine juristische Verifikation

Ein eingehaltenes Schema bestätigt weder Existenz, Inhalt oder Aktualität einer Norm
noch ihre Relevanz für den Antrag. Eine gültige leere Normenliste ist kein Nachweis,
dass kein Gesetz betroffen wäre. Unbekannte Änderungsarten heißen „unklar“, fehlende
oder unbekannte Unsicherheitsangaben „nicht angegeben“. Jede Norm bleibt ausdrücklich
„nicht verifiziert“. Amtliche Quellenprüfung und Rechtsfolgenkette bleiben gesonderte
Bausteine; die Formatprüfung schreibt niemals Modellangaben in die Faktenbasis.
