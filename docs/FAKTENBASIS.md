# Amtliche Quellen der Zukunftswerkstatt

Seit0.77.0 zeigt `/zukunftswerkstatt/faktenbasis/bestand/` einen nachrechenbaren
Nachweis aller lokal gespeicherten Norm-, Dokumenttext- und Personalstände.
Der Download ist an den angezeigten Hash gebunden. Keine erneute Originalprüfung,
keine Aussage zur vollständigen/aktuellen Rechtsordnung und keine Kontextänderung.
Aufbau, Hashbezüge, Grenzen und Nachrechnung stehen in `docs/SCHEMA.md`
(Bestandsnachweis Fassung1). Nur eine konsistente Datenbank-Leseabfrage, keine
Netz- oder Modellaufrufe. Die Registergrenze schneidet keine Teilmenge ab.

Die Sammlung bewahrt gezielt amtliche Metadaten und einzeln abgerufene Dokumenttexte des konsolidierten Bundes- und Landesrechts. Öffentlich nachlesbar unter /zukunftswerkstatt/faktenbasis/. Gesonderte amtliche Personal-Gesamtbelege und Ressorttabellen bleiben als eigene Schnappschüsse nachlesbar; daraus entstehen keine belegten quantitativen Personalfolgen eines Antrags. Die Sammlung ist keine vollständige Gesetzesdatenbank und enthält noch keine geprüften NormVerweis-Kanten. Modelle können sie nicht befüllen; ihre rechtlichen Zuordnungen bleiben Vorschläge.

Ein Betreiber kann einen kleinen Einzelbezug auslösen:

    python manage.py ris_import --gesetzesnummer <achtstellige-amtliche-Kennung> --stand YYYY-MM-DD

Der Befehl macht genau eine Anfrage an die feste amtliche Bundesrecht-API und liest ausschließlich die erste Seite mit höchstens zehn Dokumenten. Er sucht nicht nach einem Titel und übernimmt keine Modell-URLs. Stimmen Kennung, Quelle oder Antwortformat nicht, wird keine Norm der Seite übernommen. Ein Fehler ist ein fehlgeschlagener Import, keine leere Faktenbasis. Unveränderte Inhalte bleiben einmal gespeichert; geänderte Inhalte erhalten einen zusätzlichen Schnappschuss. Ein Datenbankfehler rollt die gesamte Übernahme zurück.

Jeder erfolgreiche Import bewahrt die vollständige JSON-Antwort auf. Die Download-Adresse steht am Norm-Schnappschuss. Beide SHA-256-Prüfsummen werden aus kanonischem JSON gebildet: Schlüssel sortiert, keine zusätzlichen Leerzeichen, UTF-8 und unmaskierte Unicode-Zeichen. Der Inhalts-Hash bezieht sich auf das Data-Objekt des Dokuments; der Antwort-Hash auf das gesamte JSON.

Es gibt keinen automatischen oder periodischen Abruf und keine automatische Zuordnung zu Anträgen. Größere Abfragen verlangen vor ihrer Aktivierung eine BKA-Meldung, serielle Abrufe mit mindestens zwei Sekunden Abstand und die vorgegebenen Zeitfenster. Die Meldung wurde noch nicht gesendet. Diesen Einzelimport deshalb nicht als Massendownload-Schleife oder Cron betreiben.

Seit0.59.0 gibt es denselben ausdrücklichen Einzelbezug unter /verwaltung/faktenbasis/: exakte achtstellige Gesetzesnummer und Stichtag, keine freie URL oder Titelsuche. Ein einzelner XML-Dokumenttext wird auf der Seite seines gespeicherten Norm-Schnappschusses angefordert. Vor GET und POST werden bestehende Verwaltungsrechte, aktive echte Mitgliedschaft, geprüfter Nachweis und das Fehlen eines offenen Anmeldeadresswechsels geprüft. CSRF schützt beide Aktionen; GET löst keinen Abruf aus. Administrative Anforderungen werden mit Konto-ID und Ziel, ohne Profilwerte oder Schutzcodes, auditiert; die öffentliche Audit-Fassung schwärzt die Konto-ID nach den bestehenden Regeln.

Beide Fachoperationen und damit beide CLI-Befehle sowie Webaktionen teilen den betrieblichen Datensatz AbrufSperre. Eine kurze atomare Reservierung mit zufälligem Eigentumscode verhindert Parallelabrufe; es wird keine eigene Transaktion über den Netzaufruf gehalten. Nach Abschluss gelten mindestens zwei Sekunden Abstand. Nach Prozessabbruch läuft die technische Reservierung nach60 Sekunden aus; nur der eigene Code darf sie freigeben. Empfangene Daten werden in Blöcken mit Gesamtzeitprüfung gelesen; jeder Socket-Read hat zusätzlich15 Sekunden Zeitgrenze. Die Übertragung wird spätestens nach Ablauf dieser Zeit plus einem laufenden Socket-Read abgebrochen. Weiterleitungen und mehr als2MiB bleiben unzulässig.

Der Registerwert faktenbasis-manuelle-abrufe-je-stunde (Schema sources.manual_requests_per_hour) begrenzt beide Bezugstypen gemeinsam, anfangs auf10 je UTC-Kalenderstunde. Null sperrt weitere Anforderungen. Eine Reservierung verbraucht einen Platz, auch bei anschließendem Quellenfehler. Stundenwechsel setzt den Zähler zurück, hebt aber keine aktive Sperre auf. Abgewiesene Reservierungen erhalten keinen falschen Quellen-Fehlernachweis; der Verwaltungsversuch bleibt auditiert. Der Textabruf liest ausschließlich den tatsächlich erhaltenen Metadatenstand aus der Datenbank.

Die öffentlichen Norm-Schnappschüsse stammen aus den amtlichen Metadaten; die Frage, ob eine Norm für einen Antrag relevant ist oder geändert werden müsste, wird dadurch nicht verifiziert. Konsolidiertes Recht dient der Information; rechtlich verbindlich ist die authentische Kundmachung.

## UTF-8 und erhaltene Textauswertungen ab0.76.0

Neue ausdrückliche Einzelimporte verwenden Textparserfassung3. Der vorgeschaltete
DTD-/Verarbeitungsanweisungs-Scan und der XML-Parser verarbeiten denselben UTF-8-Text;
Nullzeichen sowie UTF-16-/UTF-32-Bytestromfolgen werden abgewiesen. Ein optionales
UTF-8-BOM, Umlaute und die unveränderten Originalbytes samt SHA-256 bleiben erhalten.
Die Änderung korrigiert die Annahme BOM-losen UTF-16-ASCII-XMLs trotz UTF-8-Vorscan.

Frühere Auswertungen der Fassungen1/2 werden weder geändert noch gelöscht. Dieselben
gültigen Originalbytes können bei einem späteren ausdrücklich ausgelösten Import einen
zusätzlichen Stand mit Fassung3 ergeben. Ein fehlgeschlagener Bezug bleibt als Fehler
nachlesbar; er ersetzt keine gespeicherten Texte oder damaligen Modellkontexte. Es gibt
keine automatische Reparatur, Neuberechnung oder Produktionsbefüllung.

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


## Personal-Grundstock ab0.67.0

Die getrennte öffentliche Nachlese `/zukunftswerkstatt/faktenbasis/personal/` zeigt nur
bereits ausdrücklich übernommene Aggregatwerte. Der neue Code befüllt die Produktion nicht
automatisch. Er ist kein Personalregister über einzelne Menschen und erzeugt keine Prognosen.

    python manage.py personal_import --datei <lokal-erhaltenes-amtliches-Original.pdf>
    python manage.py personal_import --amtliche-quelle

Beide Wege akzeptieren zunächst ausschließlich den bekannten Personalbericht2026 des
Bundeskanzleramts, Original-SHA256
`40e720bb4aee9ae26df87452498c9e1021966d4b9a54288c46ccafa7b06ffd63`.
Nur die2025-Zeile von Tabelle20 auf gedruckterSeite75/PDF-Index76 wird deterministisch gelesen;
EinheitVBÄ, keine Kopfzahlen. Publikation, Seite, Tabellenkopf, Spaltenfolge und Einheitsfußnote
werden geprüft. Ein neues/verändertes Dokument wird nicht geraten oder durch eine Modellantwort
ersetzt. ADR-014 begründet die Laufzeitnutzung der bereits vorhandenen Bibliothek pypdf.

Der feste Netzbezug teilt Mindestabstand und Stundenkontingent mit RIS-Einzelabrufen; keine
Weiterleitung und keine freie URL. Socket-/Gesamtzeitgrenze15Sekunden plus höchstens einem
laufenden Read, höchstens6MiB. Der Hash wird vor dem PDF-Parser geprüft. Die lokale Dateivariante
führt keinen Netzaufruf aus. Neue Inhalte und Abrufbelege werden atomar mit Audit übernommen,
unveränderte Wiederholungen behalten ihren ursprünglichen Erfassungszeitpunkt. Fehler ersetzen
keinen älteren Stand. Gewöhnliche Speicher-, Mengen-, Upsert-, PK-Ersetzungs- und Löschwege
sind wie bei den anderen Fakten-Schnappschüssen gesperrt.

Der JSON-Nachweis enthält Werte, Einheit, Datenjahr, Herkunft, Originalhash und Parserfassung.
Das vollständige PDF wird nicht öffentlich gespiegelt; die Quelle bleibt beim Herausgeber.
Bestandszahlen belegen weder freie Kapazität noch einen erforderlichen Stellenauf- oder -abbau.
Diese Aggregatwerte werden noch nicht automatisch in Modellaufträge eingespeist. Eine solche
Integration für neue Aufträge braucht einen eigenen festgehaltenen Kontext; laufende Aufträge
und frühere Einschätzungen bleiben unverändert.

## Landesrechts-Metadaten gezielt übernehmen

    python manage.py landesrecht_import --bundesland Oberoesterreich --gesetzesnummer 10000288 --stand 2026-11-03

Das Beispiel benennt eine amtliche Quelle, keine politische Forderung. Der Befehl unterstützt die
neun in der RIS-OGD-Dokumentation genannten Landesauswahlen (siehe `--help`), aber stets nur genau
ein gewähltes Land, eine achtstellige Gesetzesnummer und einen genauen Stichtag. Es ist ein
ausdrücklicher Einzelbezug der ersten Seite mit höchstens zehn Dokumenten; eine höhere Trefferzahl
ist kein Nachweis, dass die ganze Rechtsvorschrift importiert wurde. Kein Sammel- oder Nachtabruf.

ApplikationLrKons, zurückgeliefertes Bundesland, Gesetzesnummer, Landes-Dokumentkennung und
amtliche Dokumentadresse werden vor jeder Übernahme geprüft. Dieselben Netzgrenzen und derselbe
gemeinsame Abrufschutz wie beim Bundesrecht gelten. Erfolg, Fehler und unveränderte Wiederholungen
bleiben als unveränderliche Importnachweise erhalten. Neue Metadatenstände werden angehängt.

Norm und Import tragen zusätzlich `ebene` und `bundesland`. Vorhandene BrKons-Daten sind durch
die bisherige Importprüfung eindeutigBund; die additive Migration ergänzt nur diese Herkunft,
ohne Originalantwort, Inhaltshash, Stichtag oder ersten Import zu ersetzen. Öffentliche Seiten
nennen das jeweilige Bundesland und den tatsächlichen Importumfang. Die Herkunft ist keine
juristische Relevanzprüfung und keine Feststellung örtlichen Wahlrechts.

Ein einzelner Landes-Dokumenttext kann seit0.69 mit `ris_volltext --norm <Schnappschuss-ID>` oder
der bestehenden ausdrücklichen Verwaltungsaktion übernommen werden. Die benannte Originalquelle,
LrKons-Metadaten und Bundesland müssen zusammenpassen; das XML muss dieselbe Dokumentnummer,
Gesetzesnummer und dasselbe Bundesland nennen. Bundes- und Landespfad bleiben getrennt, unbekannte
Quellen und Umleitungen werden verweigert. Abrufschutz, Rechte und CSRF-Prüfung gelten unverändert.

Die neue TextauswertungFassung2 erhält br-/tab-Grenzen. Sie gilt auch für künftige Bund-Einzelabrufe;
vorhandene Originalbytes und TextauswertungenFassung1 bleiben erhalten. Derselbe Originalhash mit
neuer Parserfassung ergibt einen zusätzlichen Stand, keine Änderung früherer Auswertungen.
Wiederholungen derselben Auswertung behalten den ersten Erfassungszeitpunkt. Fehler löschen keine
früheren Texte. Öffentlich nachlesbar sind Original-XML, Wortlaut, Quelle, Hash, Fassung und Abrufe.

Die explizite KontexterfassungFassung1 bleibt aufBund begrenzt. Seit0.70 verwenden neue
Aufträge Quellenrahmen2 mit ausdrücklicher Bundes-/Landesherkunft, offenem Umfang ohne
räumliche Zuständigkeitsprüfung und eigenem Promptvertrag. Landesquellen werden weder
alsBund ausgegeben noch bestehenden Aufträgen ergänzt. Details: `LANDESKONTEXT.md`.
Die Textauswertung begründet keine rechtliche Geltungs-/Betroffenheitsprüfung oder vollständigen Graphen.

## Getrennte Personal-Ressorttabelle seit0.71

Tabelle7 des bekannten Personalberichts2026 mit Stichtag31.12.2025 kann ausdrücklich
als eigener Tabellenstand übernommen werden. Die grundsätzliche EinheitVBÄ wird mit
der Methodik geprüft. Vierzehn Ressort-/Organezeilen und Gesamtzeile, ursprüngliche
Rundung und leere Teilspalten bleiben erhalten. Kein erfundener Beamten-/Vertrags-Split
oder verfügbare Kapazität. Nachlese, JSON, Einzelimport und Grenzen: `PERSONALRESSORTS.md`.
Die bisherigen Personal-Aggregate und Modellquellen werden dadurch nicht geändert.
