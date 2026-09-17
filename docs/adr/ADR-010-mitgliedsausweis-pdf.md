# ADR-010: Mitgliedsausweis mit eingebetteter Unicode-Schrift

Status: angenommen zur Umsetzung der Gründeranweisung vom 17.9.2026.

Der eigene WinAnsi-PDF-Schreiber verändert Namen oder lässt Schriftzeichen weg.
Für den einseitigen Ausweis verwenden wir ReportLab 4 und eingebettete DejaVu-Sans-
Schriften mit ihrer vollständigen Lizenz im Repository. Keine externen Fontabrufe
zur Laufzeit. Die gemeinsam genutzte Zeichnung bleibt, einschließlich Logo, QR,
Kartenmaß 88,60 × 56,98 mm und TrimBox mit 1,5 mm Beschnitt.
Fehlende Glyphen lösen einen Fehler aus, statt einen falschen Namen zu drucken.
PDF/X mit Druckprofil ist keine zugesicherte Eigenschaft dieser Ausgabe.

Quellen: https://docs.reportlab.com/reportlab/userguide/ch3_fonts/
https://github.com/dejavu-fonts/dejavu-fonts/blob/master/LICENSE

Postaufträge liegen dauerhaft in der Datenbank. Ein atomarer, zeitlich begrenzter
Besitzvermerk schützt gegen gleichzeitige Bearbeitung. Der bestehende Gunicorn-
Dienst bearbeitet offene Aufträge alle 30 Sekunden; keine zusätzliche Instanz.
SMTP kann nach einem Absturz zwischen Annahme und Erfolgsverbuchung eine doppelte
Zustellung verursachen. Eine bereits verbuchte Nachricht wird nicht erneut gesendet.

### Ergänzung 0.49.1: Maildarstellung und Mitgliedsnummer

Mitgliedsnummern sind eigene, eindeutige und dauerhaft vergebene Daten, keine Primärschlüssel. Die Bestandsmigration berücksichtigt den ausdrücklichen Gründerauftrag: Michael Hackl zuerst, davor angelegte Konten als Testkonten ohne reguläre Nummer. Beziehungen, Audit-Ereignisse, Zahlungsreferenzen und QR-URLs behalten die technischen IDs. Neue bestätigte Anmeldungen erhalten die nächste Nummer durch einen transaktional gesperrten Zähler; Nummern werden nicht aus der aktuellen Anzahl berechnet und nach Austritt nicht wiederverwendet.

Mailtexte enthalten eine reine Textalternative und HTML. Ein gemeinsamer Mailbaustein bettet das Logo als CID-Bild innerhalb multipart/related ein; PDF-Anhänge bleiben eigenständige Anhänge. Inline-Stile und eine Präsentationstabelle sind hier für Mailprogramme erforderlich und verändern das Design-System der Weboberfläche nicht. Benutzereingaben werden vor HTML-Darstellung maskiert. Die revidierte persönliche Vorschau erhält einen eigenen Versandauftrag; frühere erfolgreiche Aufträge bleiben erhalten. Kein automatischer Bestandsversand.
