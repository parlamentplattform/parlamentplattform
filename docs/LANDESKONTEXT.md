# Quellenherkunft in neuen Modellaufträgen (0.70, Schema1.25)

Neue öffentliche Rechtsbezug-Aufträge halten Quellenrahmen2 fest. Der vorhandene Bestand
umfasst Bundes- und ausdrücklich bezeichnete Landesquellen. Das ist kein vollständiger
Rechtsbestand und keine rechtliche Zuständigkeitsprüfung. Das freie Feld `Antrag.gebiet`
ist kein geprüfter Gebietsschlüssel und wird für keinen versteckten Landesfilter verwendet.
Örtliche Wahlberechtigung und der offene Punkt FB-L8 bleiben davon unabhängig.

## Herkunft, Auswahl und Zeit

Die reine verzeichnete Regel `plattform_core/quellenumfang.py`, Fassung1, trennt gespeicherte
Ebene, amtlichen Bundeslandnamen und Dokumentkennung. Ihre Umfangskennung lautet
`bund_land_ohne_gebietspruefung`. Das Format einer Landeskennung allein beweist kein Bundesland.
Bei der neuen Kontexterfassung müssen die zusätzlichen Herkunftsfelder zu den erhaltenen
Originalmetadaten passen: Dokument-ID, BrKons/LrKons, Gesetzesnummer und bei Land Bundesland.
Der Metadatenhash wird vorher erneut geprüft. Es werden Datenbankwerte verwendet, keine
nachträglich veränderten Eigenschaften eines übergebenen Python-Objekts.

Der begrenzte vorhandene Bestand bleibt neutral nach Dokumentkennung gereiht. Wortanfangsregel1,
Mindestwortlänge, Bestands-, Quellen- und Textgrenzen bleiben im Register und Rahmen nachlesbar.
Später importierte Daten, fehlgeschlagene Importe, zukünftige Stichtage und spätere Textstände
werden nicht in einen früheren Rahmen eingeschoben. Keine Netz- oder Anbieteranfrage bei der
Erfassung, Anzeige oder Nachlese; keine Änderung des Tages-/Monatsbudgets oder zusätzliche Aufgabe.

Jede Quelle in Fassung2 nennt `ebene` und `bundesland`. Der Root ergänzt den versionierten
`umfang`. Bundes- und Landes-XML-Pfad sind getrennt. Bereits festgehaltene Originalbytes,
Textprojektionen und Hashes bleiben unangetastet. Eine leere oder gekürzte Auswahl bestätigt
weder fehlende Rechtsfolgen noch die Vollständigkeit der Quellen.

## Alte Eingaben bleiben alte Eingaben

Der Quellenvertrag1 wurde vor dem Umbau als synthetischer unabhängiger Beleg festgehalten,
einschließlich Auswahlregel1, Textparser1, fester Prüfsumme und exakter alter Eingabe.
Fassung1 akzeptiert weiter ausschließlich Bundesrecht. Alte Frames werden nicht auf2 umgestellt.

`ki.eingabevertrag` wählt ausschließlich bekannte zusammengehörige Fassungen:

| Erhaltener Quellenrahmen | Rechtsbezug | Korrektur |
|---|---|---|
| Alter leerer Rahmen `{}` | v1 | v1 |
| Fassung1 | v2 | v1 |
| Fassung2 | v3 | v2 |

Die tatsächliche damalige Eingabe und das öffentliche Antwortschema bleiben erhalten.
Alte wartende Aufgaben werden weiterhin mit ihrem bisherigen Prompt ausgeführt. Korrekturen
verwenden ausschließlich den belegten öffentlichen Ursprungstext, die alte Antwort und
Beanstandung. Ein Kontexthash allein beweist nicht, dass ein anderer Wortlaut öffentlich war.
Einwilligung für Verfahrensnachrichten und alle bisherigen Rechte bleiben unverändert.

## Getrennte heutige Nachlese

Kennungsregel2 vergleicht dieselbe Ebene Bund/Land und dieselbe vollständige Dokumentnummer
mit genau einer damaligen Quelle. Keine Titelsuche, Abkürzung, URL-Normalisierung oder Auflösung
von Mehrdeutigkeit. Bei neuer Quelle steht der damalige amtliche Landesname getrennt neben
der ungeprüften Modellbehauptung. Bei alten Quellen werden fehlende Felder nicht erfunden.

Antragskarte, Historie und Brief erklären den Umfang und seine Grenze; der Export erhält
die unveränderten Originalframes und die ausdrücklich heutige Kennungsnachlese. Die Herkunft
einer Quelle ist keine Bestätigung von Modelltitel, Geltung, Betroffenheit oder Änderungsbedarf.
`rechtlich_verifiziert` bleibtfalse. Normgraph, juristische Verifikation, automatische
Aktualisierung sowie weitere Folgenketten und die vollständige S11-Abnahme bleiben offen.
