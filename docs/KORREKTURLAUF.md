# Erste öffentliche Nachrechnung (0.65.0)

Ein bestätigtes aktives Mitglied kann eine gelesene Einschätzung öffentlich
beanstanden. Der Vermerk bleibt unverändert. Ein neues Formular hält die Nummer
des gelesenen Laufs fest; eine inzwischen neue Antwort ändert das Ziel nicht.

Die für diesen Antrag zuständige aktive Gruppe1 kann ausdrücklich eine
Nachrechnung des **öffentlichen Rechtsbezugs** anfordern. Das ist die bestehende
Werkstattrolle, keine zusätzliche Verwaltungsbefugnis. Die öffentliche Eingabe,
Antwort und Beanstandung werden dabei an den vorhandenen Anbieter übergeben.
Es werden keine Namensdaten aus dem Konto der beanstandenden Person ergänzt.

## Tatsächlicher alter Stand

Der Ursprung muss ein erfolgreicher öffentlicher Rechtsbezug-Lauf mit eindeutigem
öffentlichen Ursprungsauftrag und prüfbarem archiviertem Textkontext sein.
Interne Werkstatttexte, Textvektoren, fehlende oder beschädigte Altstände können
nicht mit diesem Weg nachgerechnet werden. Es wird kein älterer Stand aus der
heutigen Antragsfassung rekonstruiert. Personenwahlen werden nicht neu analysiert.

Der neue Auftrag hält Ursprung und Beanstandung, tatsächliche ursprüngliche
Eingabe/Antwort samt SHA256, Text-/Quellenrahmen und eine Gesamtprüfsumme fest.
Die gleiche Beanstandung erhält auch bei wiederholtem POST nur einen Auftrag.
Neue Python-Objekte, QuerySet-/Mengenänderung, Konflikt-Upsert und gewöhnliche
Löschwege dürfen den Vermerk oder seine Eingabebeziehungen nicht ersetzen.
Das ist Anwendungsschutz und kein Schutz gegen privilegierte Datenbankeingriffe.

## Vorhandene Warteschlange und Budgets

Seit0.70 bestimmt der erhaltene Quellenrahmen den Prompt: alte Rahmen ohne Quellen
oder in Fassung1 weiterhin `korrektur-v1`, neue Herkunftsfassung2 `korrektur-v2`.
Der genaue öffentliche Ursprung und sein bekannter Rechtsbezug-Prompt müssen belegt
sein; Quellenhashes allein ersetzen nicht den tatsächlich gesendeten Wortlaut.
Die neue Fassung ist in `LANDESKONTEXT.md` beschrieben, alte Dateien bleiben erhalten.

Der Zweck `korrektur` und der Auftragstext `korrektur-v1.md` verwenden denselben
Steckplatz, die atomare Reservierung, Fehlerwiederholung sowie Tages-/Monatsbudget.
Jeder tatsächlich archivierte Korrekturaufruf zählt im Tageskontingent mit, auch
ein Anbieterfehler. Ein leerer Steckplatz oder erschöpftes Kontingent wartet.
GET, Beanstandung und Anfordern selbst lösen keinen Anbieteraufruf aus.
Es gibt keinen neuen Anbieter, Tarif, bezahlten Dienst oder neuen Budgetrahmen.

Original und Beanstandung werden nicht als sachlich erledigt markiert. Die neue
Antwort steht getrennt daneben: Modell, Auftragstextfassung, Zeitpunkt, Formprüfung
und ursprünglicher Kontext sind nachlesbar. Eine neue Antwort kann ebenfalls falsch
sein; Formprüfung und amtliche Quellen sind keine juristische Bestätigung.

## Export und Grenzen

Schema1.20 ergänzt `rechtsbezug.korrekturen` außerhalb der ursprünglichen
Auftrags-/Lauflisten. Der unveränderte Korrekturrahmen und die zugehörigen Versuche,
auch frühere Fehlversuche, bleiben nachlesbar. Fremde/interne Laufzuordnungen werden
nicht veröffentlicht. Der eigene Datenexport ergänzt die neuen Auftragsbeziehungen.

Verbrauchsfassung2 zählt fünf bekannte Zwecke plus Sonstige vollständig und
neutral nach Zweckkennung. Eurokosten bleiben ohne damaligen Abrechnungsnachweis
unbekannt; Tokenzahlen werden nicht in erfundene Preise umgerechnet.

Offen bleiben Korrekturen interner Werkstatt-Einschätzungen, juristische
Verifikation, amtlicher Normgraph, automatische Quellenaktualisierung und weitere
Folgenketten. Kein Korrekturlauf ändert Stimmen, Phasen, Fristen oder die
festgeschriebenen Regeln laufender Verfahren. FB-L8 bleibt gesondert offen.
