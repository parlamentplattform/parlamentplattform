# Spätere lokale Quellenstände neben dem alten Modellkontext

Seit0.64.0 wird ausschließlich beim aktuell angezeigten Rechtsbezug-Auftrag oder
Lauf ein gesonderter heutiger Vergleich angeboten. Ein neuer lokaler Import ist
kein Beleg für eine Änderung des geltenden Rechts. Auch das Ausbleiben späterer
Funde bestätigt weder einen vollständigen Rechtsbestand noch rechtliche Aktualität.

Der damalige Rahmen bleibt genau gleich: Quellen-IDs, Ausschnitt, Hash,
Erfassungszeit, Quellenwahl und ursprüngliche Modellantwort werden weder
ersetzt noch neu berechnet. Der Vergleich schreibt nichts und löst keinen
Anbieter-, Netz- oder Warteschlangenaufruf aus. Es gibt keinen neuen Kostenrahmen.

## Vergleichsfassung1

- Dieselbe amtliche Kennung und kein älterer historischer Stichtag. Nur eine
  Erfassung nach dem damaligen Quellenrahmen kann einen späteren Stand ergeben.
- Metadaten: späterer Stichtag oder anderer gespeicherter Metadatenhash.
- Dokumenttext: später erfasst, neuer XML-Hash oder neue Parserfassung;
  ein vorher nicht vorhandener Text wird ebenfalls gezeigt. Eine neue ID allein
  ist kein Inhaltsunterschied.
- Auch spätere Texte zum ursprünglichen Metadatenstand zählen. Eine zusätzliche
  Metadatenübernahme darf sie nicht verdecken. Texte mit älterem historischen
  Stichtag und künftig datierte Erfassungen werden nicht vorzeitig herangezogen.
- Neutrale Ausgabe nach amtlicher Kennung. Fehlende Vergleichsdaten, alte
  Rahmen ohne Quellen, leere Auswahl und nicht prüfbare Rahmen bleiben getrennt.
  Ein mehrdeutiger Rahmen mit mehreren Versionen derselben Kennung wird nicht
  stillschweigend auf eine Version verkürzt.
- Für die Gegenüberstellung wird je Kennung der letzte lokale Metadatenstand
  nach Stichtag, bei Gleichstand höherer ID, gelesen. Dokumenttexte werden nach
  Erfassungszeit, dann höherer ID ausgewählt. Nur bis zum Vergleichszeitpunkt
  erfasste Daten und Stichtage bis zum Vergleichstag in der Instanzzeitzone
  zählen. Texte mit älterem Stichtag als der Ausgangsquelle zählen nicht.

`plattform_core/quellenfortschritt.py` enthält die reine Vergleichsregel;
`faktenbasis/nachlese.py` prüft zuerst den Quellenrahmen und liest höchstens
zwei gebündelte Abfragen. Die vorhandene Rahmenprüfung begrenzt die Quellenzahl.
Es wird kein Dokumenttextinhalt für den Vergleich geladen. Nur Metadaten, IDs,
Hashes, Parserfassungen und Zeitpunkte sind erforderlich.

Die historische Seitenliste erzeugt keinen Vergleich je Lauf. Auch der
öffentliche Archivexport ergänzt einmal `rechtsbezug.quellenabgleich` außerhalb
der Originalkontexte (Schema1.19): Regel-Fassung, Ermittlungszeitpunkt,
Ausgangs-Prüfsumme, Auftrags-/Lauf-ID sowie Befunde je Kennung. Dieser heutige
Lesebefund gehört ausdrücklich nicht zur damaligen Modelleingabe.

`gegenuebergestellte_quellen` enthält nach Kennung gereiht die tatsächlichen
heutigen Vergleichswerte: Norm-ID, Stichtag, Metadatenhash und Importzeit sowie
Text-ID, zugehörige Norm-ID, XML-Hash, Parserfassung und Erfassungszeit. Zusammen
mit dem unveränderten Originalrahmen sind die Befunde ohne Datenbank nachrechenbar.

Nicht abgeschlossen: automatisches Aktualisieren des gesamten Bestands,
rechtliche Verifikation, amtlicher Normverweis-Graph, neue Rechtsfolgenketten
und Korrekturläufe. Ein Modell erhält keine nachträglich ausgetauschten Quellen.
