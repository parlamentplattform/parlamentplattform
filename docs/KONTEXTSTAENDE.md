# Textstände der Zukunftswerkstatt

Seit 0.58.0 halten neue Aufträge ihren tatsächlich gespeicherten Textstand vor dem Modellaufruf fest. Antragsfassungen und Fassungen des Expertenratsvorschlags besitzen getrennte Nummernräume: Antrag 1 und Vorschlag 1 sind verschiedene Quellen. Ein fehlender alter Wortlaut wird nicht durch den neuesten ersetzt.

Der Schnappschuss enthält Formatfassung 1, Antrag-ID, Quellenart antrag/vorschlag, Quellen-ID und Fassungsnummer, Titel, Wortlaut, Begründung, Ebene, deutsche Ebenenbezeichnung, Gebiet und Erfassungszeitpunkt. Es werden keine Konto-, E-Mail- oder Meldeadressfelder aus einem Mitgliederprofil übernommen. Angaben im öffentlichen Antragstext bleiben Teil dieses Textes. Der Eintrag gehört dem tatsächlichen Antrag; die Warteschlange nimmt nur den aktuell eingereichten Vorschlag oder einen bereits früher eingereihten Vorschlag entgegen, keine unfertigen Arbeitsstände. Personenwahlen sind ausgeschlossen.

Die SHA-256-Prüfsumme bezieht sich auf dieses JSON ohne das Feld sha256: sortierte Schlüssel, keine zusätzlichen Leerzeichen, UTF-8, unmaskierte Unicode-Zeichen. Der Zeitpunkt wird genau wie gespeichert einbezogen. Beispiel zum Nachrechnen eines aus dem Archivexport entnommenen Textkontexts:

    import hashlib, json
    daten = dict(textkontext)
    gespeichert = daten.pop("sha256")
    roh = json.dumps(daten, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    assert hashlib.sha256(roh).hexdigest() == gespeichert

Ein Lauf bewahrt den Kontext zusätzlich mit der öffentlichen Auftrag-ID und Versuchsnummer auf, unabhängig davon, ob der Anbieter erfolgreich antwortet. Reservierungscodes gehören nicht hinein. Eine gescheiterte Anforderung ohne neuen Lauf verweist nicht auf irgendeinen früheren Erfolg. Gespeicherte Eingaben und ihre Kontexte werden nicht überschrieben; der bearbeitbare Auftragsstatus bleibt davon getrennt.

Die Einreichung eines Vorschlags und einer späteren Überarbeitung reiht jeweils idempotent einen Rechtsbezug-Auftrag ein. Das Speichern unfertiger Arbeitsfassungen ruft kein Modell auf. Ein eigener Savepoint schützt eine übergeordnete Beschluss-Transaktion vor Einreihungsfehlern. Budget, Tageskontingent, Anbieter und Verfahrensfristen bleiben unverändert. Textvektoren bleiben im Nummernraum der ursprünglichen Antragsfassungen und verwenden ebenfalls den festgehaltenen Titel/Wortlaut.

Ältere Aufträge/Läufe behalten leere Kontextfelder. Für einen neu ausgeführten alten Auftrag wird der erhaltene ursprüngliche Wortlaut mit dem tatsächlichen späteren Erfassungszeitpunkt gelesen; der alte Auftrag wird nicht nachträglich umgeschrieben. Historische Angaben aus einem alten Auftragsverweis sind kein eigens festgehaltener Kontextnachweis.

Die Antragsseite stellt den jüngsten Auftragsstatus vor frühere Ergebnisse. Frühere Einschätzungen und Fehlversuche bleiben nach Zeitpunkt/Laufnummer absteigend lesbar, mit einstellbarer Seitengröße. JSON-/Markdown-Archivexporte enthalten alle öffentlichen Rechtsbezug-Aufträge und -Läufe samt unveränderten Eingaben, Antworten und Kontexten. Interne Gremien-Eingaben anderer Zwecke werden dort nicht mitexportiert; die allgemeine Laufübersicht zeigt nur ihre bisherigen Metadaten und gegebenenfalls den Kontextnachweis, keine internen Texte. Im persönlichen Datenexport stehen die eigenen Kontextfelder ebenfalls zur Verfügung.

Seit 0.61.0 besitzen neue Rechtsbezug-Aufträge zusätzlich einen gesonderten amtlichen Quellenkontext aus vorhandenen Schnappschüssen (docs/QUELLENKONTEXT.md). Textkontext-Version1 bleibt unverändert; alte Aufträge erhalten keine späteren Quellen. Ein Hash bestätigt weder die rechtliche Relevanz einer Norm noch die Richtigkeit einer Modellantwort. Rechtsbezüge bleiben gekennzeichnete, nicht verifizierte Vorschläge ohne Wirkung auf die Entscheidung. Weitere Simulationsschritte, Korrekturläufe und laufende Aktualisierung amtlicher Kontexte sind separate offene Aufgaben.
