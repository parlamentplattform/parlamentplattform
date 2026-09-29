# ADR-012: Tägliche Sicherung in ein privates GitHub-Repository, Wiederherstellungsprobe und Wache

Status: angenommen zur Umsetzung der Gründeranweisung vom 28.9.2026 („ein privates github unter dem
parlamentplattform zugang anlegen zum sichern.“) und seiner Antworten vom 29.9.2026 (Repository
`parlamentplattform/sicherung`, von ihm angelegt; „ich denke eine verschlüsselung ist hier nicht
wichtig. es reicht dass das repo privat ist.“). Bestandsaufnahme 28.9.2026, A9/A10; Fahrtenbuch Schritt 2.

## Ausgangslage

Es gab nur die täglichen Snapshots von Render-Postgres — beim Anbieter selbst, nicht außerhalb — und
keine je geprobte Wiederherstellung. Fiel das Render-Konto aus, war alles weg, was die Plattform je
beschlossen hat. Einen Alarm bei 500/503 gab es nicht; Render startet eine kranke Instanz zwar neu,
sagt es aber niemandem.

## Entscheidung

1. **Sichern:** `.github/workflows/sicherung.yml`, täglich 02:17 UTC. `pg_dump` (Fassung 17, sichert
   Server 16 und 17) im Custom-Format, komprimiert, ohne Eigentümer und Rechte; geprüft mit
   `pg_restore --list`, dazu eine SHA-256-Datei (`tools/sicherung.sh sichern`). Ablage als Release im
   privaten Repository `parlamentplattform/sicherung` — ein Release je Lauf.
2. **Aufbewahren:** 90 Tage (`AUFBEWAHRUNG_TAGE` im Workflow). Ältere Releases löscht der Lauf nach
   einer gelungenen neuen Sicherung. Releases statt Commits, weil gelöschte Commits in der Geschichte
   blieben und das Repository ohne Grenze wüchse. Das sind Sicherungskopien, keine Verfahrensdaten —
   Grundregel 7 betrifft die Datenbank selbst, nicht ihre Kopien.
3. **Proben:** am Monatsersten und bei jedem Start von Hand: die jüngste Sicherung in einen leeren
   PostgreSQL-16-Dienst zurückspielen, `migrate --check` (Schema passt zum Code auf `main`) und
   `audit_pruefen --voll` (die Kette ist nach dem Zurückspielen intakt; `tools/sicherung.sh probe`).
4. **Wache:** `.github/workflows/wache.yml`, alle 15 Minuten `https://parlament.ddoe.at/gesund/`; drei
   Fehlversuche im Abstand von 30 Sekunden machen den Lauf rot.
5. **Keine neue Abhängigkeit der Plattform.** `pg_dump`/`pg_restore` und `gh` laufen nur auf dem
   Runner von GitHub Actions; das Hauptrepository ist öffentlich, die Minuten kosten nichts.

**Secrets** (nur im Hauptrepository, nie im Repo): `DDOE_SICHERUNG_DATENBANK_URL` (externe Adresse der
Render-Datenbank) und `DDOE_SICHERUNG_TOKEN` (fein granulierter Token, nur für
`parlamentplattform/sicherung`, Rechte „Contents: Read and write“). Ein Deploy-Key reicht nicht: Er darf
Git schreiben, aber keine Releases anlegen oder löschen. Zuständig für die Verwahrung: der Technische
Entwicklungsrat (§ 6 Abs 4), bis dahin der Gründer.

## Unverschlüsselt — Entscheidung des Gründers mit ihrem Preis

Der Bauplan empfahl, jede Sicherung mit `age` zu verschlüsseln (öffentlicher Schlüssel im Workflow,
privater außerhalb von GitHub). Der Gründer hat entschieden: das private Repository genügt. Festgehalten,
was das heißt:

- Eine Sicherung ist die ganze Datenbank: Namen, E-Mail-Adressen, Wohnorte, Beitragsreferenzen und die
  Brücke Mitglied ↔ Pseudonym (`StimmRegister`), über die sich Stimmen Personen zuordnen lassen.
  Mitgliedschaftsdaten einer Partei sind besondere Kategorien nach Art 9 DSGVO (politische Meinung).
- Lesen kann sie jede Person mit Zugang zum Repository, GitHub selbst, und wer ein Konto mit diesem
  Zugang übernimmt. GitHub ist ein US-Anbieter — wie Render (siehe BETRIEB-RENDER, Datenschutz-Einordnung).
- Die Verschlüsselung ließe sich jederzeit nachrüsten: ein Schritt im Workflow (`age -r <öffentlicher
  Schlüssel>`), einer in der Probe (`age -d` mit einem weiteren Secret), kein Geld.

## Nicht gewählt

- **Verschlüsselte Ablage bei einem EU-Speicher** (S3-kompatibel): wäre für den Echtbetrieb die bessere
  Wahl, kostet aber einen weiteren Dienst mit Vertrag — eigene Entscheidung, wenn der Umzug zu einem
  EU-/AT-Anbieter kommt.
- **Render-Cron mit `pg_dump`:** bezahlter Dienst, und die Sicherung läge wieder beim selben Anbieter.

## Folgen

- Geplante Läufe laufen nur auf `main`. GitHub schickt Fehlschläge per E-Mail an das Konto, das den
  Zeitplan zuletzt geändert hat, und schaltet geplante Läufe in einem öffentlichen Repository nach
  60 Tagen ohne Aktivität ab — dann gibt es eine E-Mail, und ein Klick schaltet sie wieder ein.
- Die erste echte Probe ist erst möglich, wenn beide Secrets gesetzt sind; bis dahin ist die Probe auf
  der Demo-Datenbank geprobt und protokolliert (BETRIEB-RENDER › Sicherung).
