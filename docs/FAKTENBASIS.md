# Amtliche Quellen der Zukunftswerkstatt

Die erste Stufe sammelt gezielt amtliche Metadaten zu Dokumenten des konsolidierten Bundesrechts. Öffentlich nachlesbar unter /zukunftswerkstatt/faktenbasis/. Sie enthält noch keine vollständigen Normtexte, NormVerweis-Kanten oder Personalangaben. Modelle können diese Sammlung nicht befüllen; ihre rechtlichen Zuordnungen bleiben Vorschläge.

Ein Betreiber kann einen kleinen Einzelbezug auslösen:

    python manage.py ris_import --gesetzesnummer <achtstellige-amtliche-Kennung> --stand YYYY-MM-DD

Der Befehl macht genau eine Anfrage an die feste amtliche Bundesrecht-API und liest ausschließlich die erste Seite mit höchstens zehn Dokumenten. Er sucht nicht nach einem Titel und übernimmt keine Modell-URLs. Stimmen Kennung, Quelle oder Antwortformat nicht, wird keine Norm der Seite übernommen. Ein Fehler ist ein fehlgeschlagener Import, keine leere Faktenbasis. Unveränderte Inhalte bleiben einmal gespeichert; geänderte Inhalte erhalten einen zusätzlichen Schnappschuss. Ein Datenbankfehler rollt die gesamte Übernahme zurück.

Jeder erfolgreiche Import bewahrt die vollständige JSON-Antwort auf. Die Download-Adresse steht am Norm-Schnappschuss. Beide SHA-256-Prüfsummen werden aus kanonischem JSON gebildet: Schlüssel sortiert, keine zusätzlichen Leerzeichen, UTF-8 und unmaskierte Unicode-Zeichen. Der Inhalts-Hash bezieht sich auf das Data-Objekt des Dokuments; der Antwort-Hash auf das gesamte JSON.

Es gibt keinen automatischen oder periodischen Abruf und keine automatische Zuordnung zu Anträgen. Größere Abfragen verlangen vor ihrer Aktivierung eine BKA-Meldung, serielle Abrufe mit mindestens zwei Sekunden Abstand und die vorgegebenen Zeitfenster. Die Meldung wurde noch nicht gesendet. Diesen Einzelimport deshalb nicht als Massendownload-Schleife oder Cron betreiben. Bei einer solchen Erweiterung sind zudem konkurrierende Abrufe und Wiederholungen über mehrere Prozesse zu koordinieren.

Die öffentlichen Norm-Schnappschüsse stammen aus den amtlichen Metadaten; die Frage, ob eine Norm für einen Antrag relevant ist oder geändert werden müsste, wird dadurch nicht verifiziert. Konsolidiertes Recht dient der Information; rechtlich verbindlich ist die authentische Kundmachung.

Quelle und Bedingungen: [RIS / Bundeskanzleramt, OGD-FAQ](https://data.bka.gv.at/ris/api/v2.6/), [API-Handbuch V2.6, Juli 2025](https://www.data.gv.at/katalog/dataset/0fb9ae1a-92cb-4ab8-a589-470c16d4fe21/resource/42070d46-01fe-4b36-803f-4af925290f59/download/dokumentation_ogd-ris_api.pdf), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Die Metadaten werden vor der Anzeige von HTML-Markierungen befreit; die unveränderten Daten bleiben im Download.
