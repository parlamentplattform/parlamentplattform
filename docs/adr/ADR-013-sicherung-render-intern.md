# ADR-013: Monatssicherung im bestehenden Render-Dienst

Status: angenommen auf Gründeranweisung vom 2.11.2026. Ersetzt den Exportteil von ADR-012.

Der GitHub-Sicherungslauf scheiterte vor dem Export an zwei fehlenden Secrets. Die Datenbank
erlaubt keine externen Verbindungen; Standard-GitHub-Runner haben keine feste Quelladresse.
Der Gründer hat der Sicherung innerhalb von Render und der Übertragung der fertigen Datei
nach GitHub zugestimmt. Frequenz: einmal pro Kalendermonat.

## Ablauf

- Der vorhandene Gunicorn-Dienst startet einen eigenen Sicherungsfaden. Fristen-Wächter und
  Postausgang laufen unabhängig davon weiter. `Hintergrundlauf` reserviert atomar zwischen
  Workern; ein verlorener Prozess hält die Reservierung höchstens 15 Minuten.
- Einmal pro UTC-Kalendermonat wird gesichert, sobald der Dienst verfügbar ist. Nach Erfolg
  erfolgen keine weiteren Exporte im selben Monat. Fehlversuche werden frühestens nach 15
  Minuten wiederholt; ein Neustart kann einen liegengebliebenen Monat nachholen.
- `pg_dump` 17 liest über die schon vorhandene interne Datenbankverbindung. Ein exportierter
  PostgreSQL-Snapshot hält Dump und Kontrollzahlen konsistent. Keine Sitzungen oder
  Einmal-Anmeldelinks, keine Datenbankpasswörter in Prozessargumenten oder Protokollen.
- Temporäre Dateien liegen ausschließlich im Render-Dienst und werden nach dem Upload entfernt.
  Ein fein granulierter `DDOE_SICHERUNG_TOKEN` darf nur das private Repository
  `parlamentplattform/sicherung` bearbeiten. Vor jedem Export wird die private Sichtbarkeit geprüft.
  Ist dieses private Repository leer, initialisiert der Lauf eine README für den ersten Release.
  Ein Release bleibt Entwurf, bis Dump und SHA-256-Datei vollständig hochgeladen sind.
- Eine sinkende Audit-Zahl verhindert Veröffentlichung und Aufräumen. Monatssicherungen bleiben
  365 Tage; ältere Sicherungen nach ADR-012 behalten ihre bisherigen Fristen. Fremde Releases
  werden nicht angefasst. Keine Änderung an Verfahrensdaten.
- `/sicherung/status.json` meldet ausschließlich Erfolg und Zeitpunkt, sonst 503. Der
  GitHub-Workflow kontrolliert am zweiten Monatstag den Erfolg und spielt die jüngste Sicherung
  des laufenden Monats in einen isolierten PostgreSQL-17-Dienst zurück. Dort werden Prüfsumme,
  Migrationen und die vollständige Audit-Kette geprüft. Fehler lösen weiterhin GitHub-Meldungen aus.

## Werkzeuge und Konfiguration

Keine neue Python-Abhängigkeit. Die native Debian-Laufzeit hat ältere PostgreSQL-Clients.
`tools/postgres_client.sh` lädt PostgreSQL-17-Client und libpq über den signierten offiziellen
PGDG-Paketindex. Der Repository-Schlüssel wird gegen den veröffentlichten Fingerabdruck geprüft;
APT prüft Paket-Prüfsummen. Pakete werden ohne Rootrechte in ein temporäres eigenes Verzeichnis
entpackt. Systempakete werden nicht geändert. Docker installiert den Client direkt aus Debian.
Die Client-Version bleibt 17, damit die unabhängige Wiederherstellungsprobe dasselbe Format liest.
Für eine Wiederherstellung wird deshalb eine neue PostgreSQL-17-Datenbank verwendet; die
Rückübertragung eines mit Client 17 erzeugten Dumps in Server 16 ist nicht zugesichert.

Der Token liegt im Render-Webdienst für den Upload und als GitHub-Actions-Secret für die
Wiederherstellungsprobe. Der frühere `DDOE_SICHERUNG_DATENBANK_URL` wird nicht mehr benötigt.
Die externe Datenbankfreigabe bleibt leer. Es entsteht keine zusätzliche kostenpflichtige Instanz.

## Grenzen

Der Faden ersetzt keinen hochverfügbaren Scheduler: bei einem vollständigen Dienstausfall wird
die Sicherung erst nach Wiederanlauf nachgeholt. Die unabhängige Monatskontrolle macht das sichtbar.
Aufbewahrung und die vom Gründer festgelegte unverschlüsselte Ablage aus ADR-012 bleiben bestehen.
Ohne Token oder privates Sicherungsrepository ist die Einrichtung nicht abgeschlossen.

Referenzen: [Render-Laufzeiten](https://render.com/docs/native-runtimes),
[Render-Privatnetz](https://render.com/docs/private-network),
[offizielles PostgreSQL-Debian-Repository](https://www.postgresql.org/download/linux/debian/).
