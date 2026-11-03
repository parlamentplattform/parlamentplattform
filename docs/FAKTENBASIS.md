# Amtliche Quellen der Zukunftswerkstatt

Die Sammlung bewahrt gezielt amtliche Metadaten und einzeln abgerufene Dokumenttexte des konsolidierten Bundesrechts. Öffentlich nachlesbar unter /zukunftswerkstatt/faktenbasis/. Sie ist keine vollständige Gesetzesdatenbank und enthält noch keine geprüften NormVerweis-Kanten oder Personalangaben. Modelle können diese Sammlung nicht befüllen; ihre rechtlichen Zuordnungen bleiben Vorschläge.

Ein Betreiber kann einen kleinen Einzelbezug auslösen:

    python manage.py ris_import --gesetzesnummer <achtstellige-amtliche-Kennung> --stand YYYY-MM-DD

Der Befehl macht genau eine Anfrage an die feste amtliche Bundesrecht-API und liest ausschließlich die erste Seite mit höchstens zehn Dokumenten. Er sucht nicht nach einem Titel und übernimmt keine Modell-URLs. Stimmen Kennung, Quelle oder Antwortformat nicht, wird keine Norm der Seite übernommen. Ein Fehler ist ein fehlgeschlagener Import, keine leere Faktenbasis. Unveränderte Inhalte bleiben einmal gespeichert; geänderte Inhalte erhalten einen zusätzlichen Schnappschuss. Ein Datenbankfehler rollt die gesamte Übernahme zurück.

Jeder erfolgreiche Import bewahrt die vollständige JSON-Antwort auf. Die Download-Adresse steht am Norm-Schnappschuss. Beide SHA-256-Prüfsummen werden aus kanonischem JSON gebildet: Schlüssel sortiert, keine zusätzlichen Leerzeichen, UTF-8 und unmaskierte Unicode-Zeichen. Der Inhalts-Hash bezieht sich auf das Data-Objekt des Dokuments; der Antwort-Hash auf das gesamte JSON.

Es gibt keinen automatischen oder periodischen Abruf und keine automatische Zuordnung zu Anträgen. Größere Abfragen verlangen vor ihrer Aktivierung eine BKA-Meldung, serielle Abrufe mit mindestens zwei Sekunden Abstand und die vorgegebenen Zeitfenster. Die Meldung wurde noch nicht gesendet. Diesen Einzelimport deshalb nicht als Massendownload-Schleife oder Cron betreiben.

Seit0.59.0 gibt es denselben ausdrücklichen Einzelbezug unter /verwaltung/faktenbasis/: exakte achtstellige Gesetzesnummer und Stichtag, keine freie URL oder Titelsuche. Ein einzelner XML-Dokumenttext wird auf der Seite seines gespeicherten Norm-Schnappschusses angefordert. Vor GET und POST werden bestehende Verwaltungsrechte, aktive echte Mitgliedschaft, geprüfter Nachweis und das Fehlen eines offenen Anmeldeadresswechsels geprüft. CSRF schützt beide Aktionen; GET löst keinen Abruf aus. Administrative Anforderungen werden mit Konto-ID und Ziel, ohne Profilwerte oder Schutzcodes, auditiert; die öffentliche Audit-Fassung schwärzt die Konto-ID nach den bestehenden Regeln.

Beide Fachoperationen und damit beide CLI-Befehle sowie Webaktionen teilen den betrieblichen Datensatz AbrufSperre. Eine kurze atomare Reservierung mit zufälligem Eigentumscode verhindert Parallelabrufe; es wird keine eigene Transaktion über den Netzaufruf gehalten. Nach Abschluss gelten mindestens zwei Sekunden Abstand. Nach Prozessabbruch läuft die technische Reservierung nach60 Sekunden aus; nur der eigene Code darf sie freigeben. Empfangene Daten werden in Blöcken mit Gesamtzeitprüfung gelesen; jeder Socket-Read hat zusätzlich15 Sekunden Zeitgrenze. Die Übertragung wird spätestens nach Ablauf dieser Zeit plus einem laufenden Socket-Read abgebrochen. Weiterleitungen und mehr als2MiB bleiben unzulässig.

Der Registerwert faktenbasis-manuelle-abrufe-je-stunde (Schema sources.manual_requests_per_hour) begrenzt beide Bezugstypen gemeinsam, anfangs auf10 je UTC-Kalenderstunde. Null sperrt weitere Anforderungen. Eine Reservierung verbraucht einen Platz, auch bei anschließendem Quellenfehler. Stundenwechsel setzt den Zähler zurück, hebt aber keine aktive Sperre auf. Abgewiesene Reservierungen erhalten keinen falschen Quellen-Fehlernachweis; der Verwaltungsversuch bleibt auditiert. Der Textabruf liest ausschließlich den tatsächlich erhaltenen Metadatenstand aus der Datenbank.

Die öffentlichen Norm-Schnappschüsse stammen aus den amtlichen Metadaten; die Frage, ob eine Norm für einen Antrag relevant ist oder geändert werden müsste, wird dadurch nicht verifiziert. Konsolidiertes Recht dient der Information; rechtlich verbindlich ist die authentische Kundmachung.

Einzelne Originaltexte ab Version 0.57.0:

    python manage.py ris_volltext --norm <ID-des-Metadaten-Schnappschusses>

Nur die ausdrücklich als MainDocument/XML in den gespeicherten Metadaten benannte Adresse ist zulässig; Host, Pfad und NOR-Kennung müssen exakt passen. Ein Request ohne Weiterleitung, höchstens 2 MiB und 15 Sekunden; danach UTF-8/XML und die enthaltene Dokument-/Gesetzesnummer prüfen. DTD, Entitätendeklarationen und externe Verarbeitungsanweisungen sind unzulässig. Der Parser extrahiert ausschließlich als Text markierte Nutzdaten, keine Kopf-/Fußzeilen oder bibliografischen Metadaten. Die ursprünglichen XML-Bytes bleiben unverändert als Anlage verfügbar; der SHA-256-Hash bezieht sich auf genau diese Bytes, nicht auf den abgeleiteten Text oder kanonisiertes XML. Die Fassung der Textauswertung bleibt gespeichert.

NormText und NormTextAbruf sind eigenständige unveränderliche Schnappschüsse. Gleiche Bytes zur gleichen Norm und Parserfassung bleiben einmal gespeichert; jeder Versuch erhält dennoch seinen eigenen Beginn/Abschluss/Erfolgs- oder Fehlernachweis. Die erste Erfassung eines Inhalts wird nicht als jüngster Abruf ausgegeben. Bei Fehler bleibt der vorherige Text lesbar, bei geändertem Inhalt entsteht ein zusätzlicher Schnappschuss. Inhalt, Erfolgsnachweis und Audit werden atomar übernommen. Es existiert keine öffentliche Importschnittstelle und kein automatisches Nachziehen. Metadaten und Text können zu verschiedenen Zeitpunkten abgerufen sein; ihre Quellenstände und Abrufzeiten bleiben getrennt nachlesbar. Einzeldokumente ergeben noch keine vollständige Rechtsvorschrift, Querverweisprüfung oder Modellkontextintegration.

Quelle und Bedingungen: [RIS / Bundeskanzleramt, OGD-FAQ](https://data.bka.gv.at/ris/api/v2.6/), [API-Handbuch V2.6, Juli 2025](https://www.data.gv.at/katalog/dataset/0fb9ae1a-92cb-4ab8-a589-470c16d4fe21/resource/42070d46-01fe-4b36-803f-4af925290f59/download/dokumentation_ogd-ris_api.pdf), [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Die Metadaten werden vor der Anzeige von HTML-Markierungen befreit; die unveränderten Daten bleiben im Download.


Seit0.63.1 gilt der gewöhnliche ORM-Schreibschutz auch für neue Python-Objekte
mit einer bereits belegten ID und für Konflikt-Upserts. Neue Einfügungen erzwingen
INSERT auch dann, wenn eine parallele Anlage die Existenzprüfung überholt.
Mengenänderungen scheitern vor Djangos innerer Transaktion; ein abgefangener
Schutzfehler beschädigt keine äußere Verfahrens- oder Importtransaktion.
Die gleichen vorhandenen Stände werden weder umgeschrieben noch nachträglich
neu importiert. Neue/idempotente Einzelimporte bleiben möglich. Dieser
Anwendungsschutz ersetzt keine Datenbankrechte, Sicherungen oder Signatur.
