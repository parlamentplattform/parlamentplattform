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
