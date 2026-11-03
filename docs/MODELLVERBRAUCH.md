# Modellverbrauch und Kostenstand je Antrag

Seit0.62.0 ist an der Antragsseite eine lesende Übersicht der archivierten
Verbrauchsangaben aufklappbar, auch ohne JavaScript. Sie löst keinen Anbieter-
oder Modellaufruf aus. Ein Antrag erhält durch diese Zahlen weder Vorrang noch
eine Hürde. Das Monatsbudget, die Tagesgrenze und die vorhandene Auftragszahl
werden nicht geändert.

Die Übersicht gruppiert in **einer** SQL-Abfrage alle dem Antrag zugeordneten
Läufe nach den sieben bekannten Zwecken; unbekannte Zwecke werden vollständig in
„Weitere Zwecke“ zusammengefasst. Es gibt daher höchstens acht Gruppen und keine
versteckte Auswahlgrenze. Reihenfolge: Zweckkennung aufsteigend. Interne Gremien-
Läufe tragen nur zur aggregierten Metadatenzählung bei, ihre Eingaben, Antworten
und Urheber erscheinen hier nicht. Ein anderer Antrag oder ein Vergleich vor
Einbringung ohne Antrags-ID zählt nicht mit.

Die reine Regel `plattform_core/modellverbrauch.py`, VERSION4, summiert genau
diese Gruppen. Regelverzeichnis19 nennt Fassung, Datum und Begründung. Gezählt
werden Läufe, fehlgeschlagene Läufe, gespeicherte Eingabe-/Ausgabetokens und
gespeicherte Dauer in Millisekunden. Die Anzeige nennt Tokenangaben, keine
Textlängen und keinen Eurobetrag. Auch eine positive Tokenangabe ist keine
Abrechnung und erlaubt ohne damaligen Tarif keinen belastbaren Kostenbetrag.

**Keine erfundenen Preise und keine Kostenfreiheitsbehauptung:** Im bisherigen
Archiv fehlen Tarif und Währung. Anbieterfehler erhalten häufig keine
Verbrauchsmeldung; der Adapter hat auch fehlende Usage-Felder als0 gespeichert.
Diese historischen Werte werden nicht nachträglich zu angeblichen echten
Nullkosten oder vollständigen Abrechnungsdaten umgedeutet. Eine leere Übersicht
kann außerdem bedeuten, dass Aufträge noch warten. Der Kostenstand bleibt
ausdrücklich `{betrag: null, waehrung: null, nachweis: nicht_erfasst}`.

Schema1.18 ergänzt denselben aktuellen Summenstand im öffentlichen Antragsarchiv
unter `rechtsbezug.verbrauch` (Formatversion1). Nur die ohnehin öffentlichen
Rechtsbezug-Läufe erhalten im vollständigen Export ihre eigenen gespeicherten
Felder `tokens_ein`, `tokens_aus` und `dauer_ms`; interne Texte bleiben außerhalb
des öffentlichen Exports. Der persönliche Datenexport ergänzt diese drei
Metadaten der eigenen Läufe. Die Laufaufzeichnungen selbst bleiben unverändert.

Formatfassung2 ergänzte den Korrekturzweck; Fassung3 ergänzt den privaten
Textvergleich. Er hat vor dem Einbringen keine Antrags-ID und zählt daher nicht
zur Antragssumme. Er bleibt Teil des tatsächlichen Monatsverbrauchs. Sein
persönlicher Nachweis enthält die private Anforderung und unveränderte Antwort;
öffentliche Antragsarchive oder die Werkstatt-Laufliste enthalten diese Texte nicht.

Ein tatsächlicher Kostenbetrag aus belegten Tarifen oder Abrechnungen und eine
ausdrückliche Erfassung, ob ein Anbieter seinen Verbrauch gemeldet hat, sind
separate offene Ergänzungen. Diese Übersicht schafft keine Tarife, Verpflichtung
oder neue Ausgabe. Die örtliche Wahlberechtigung bleibt davon unberührt.

Fassung4 führt zusätzlich `rechtsfolgen` als eigenen Zweck, auch im Tageskontingent
der Warteschlange. Neue0.73-Aufträge ersetzen beim Einbringen den alten
Rechtsbezug durch den kombinierten Bericht; keine zweite automatische Rechnung.
Bereits gespeicherte Aufträge und deren damalige Kontexte bleiben unverändert.
