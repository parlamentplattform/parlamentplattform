# Nachrechnen ohne die Plattform

Satzung § 5 Abs 8 verlangt, „dass ihr Ergebnis von jedem Mitglied ohne Spezialkenntnisse überprüfbar
bleibt“. Dafür gibt es hier ein Skript, das **nur die Python-Standardbibliothek** braucht.

## Ein Ergebnis nachrechnen

1. Auf der Antragsseite nach Abstimmungsende den Export laden (`/antrag/<nummer>/export.json`).
2. `python3 verify/nachrechnen.py antrag-<nummer>-export.json`
3. Die ausgegebenen Zahlen mit der Ergebnisseite vergleichen.

Das Skript zählt die Stimmen unter Pseudonym zweitens und unabhängig von der Plattform aus
(`plattform_core/tally.py` ist die erste Zählung). Die eigene Stimme findet man in der Liste über das
Pseudonym, das die Plattform einem nach der Anmeldung zeigt.

## Die Audit-Spur nachrechnen (seit 0.52.0)

Der Export trägt im Block `audit` jeden Eintrag des Audit-Logs, dessen Ereignis die Nummer dieses Antrags
unter `antrag` nennt:

| Feld | Bedeutung |
|---|---|
| `lfd` | laufende Nummer in der Kette |
| `ereignis` | der Inhalt, so wie er versiegelt wurde (samt Zeitstempel `zeit`) |
| `vorgaenger` | der Hash des Eintrags davor in der Kette |
| `hash` | SHA-256 über `vorgaenger` und den Inhalt (JSON mit sortierten Schlüsseln, ohne Leerzeichen, UTF-8) |
| `geschwaerzt` | `true`, wenn ein schutzwürdiger Wert durch „•“ ersetzt wurde (Mitgliedsnummer, Pseudonym einer Stimme, Begründung zu einer Person) |

`hash` oder `vorgaenger` fehlen (`null`), wo sie das Durchprobieren eines geschwärzten Werts erlaubten:
bei geschwärzten Einträgen aus der Zeit vor 0.52.0 und beim Eintrag danach. Neuere geschwärzte Einträge
tragen ein geheimes Zufallssalz, ihr Hash darf offen stehen.

Das Skript prüft jeden ungeschwärzten Eintrag mit Hash und Vorgänger: Passt sein Hash zu seinem Inhalt und seinem Vorgänger, wurde
er seit dem Schreiben nicht verändert. Es meldet `audit_nachgerechnet` und `audit_geschwaerzt`; stimmt ein
Eintrag nicht, bricht es mit seiner Nummer ab.

Was das Skript **nicht** kann: die Kette als Ganzes prüfen. Die Einträge eines Antrags liegen verstreut
zwischen denen anderer Anträge. Die ganze Kette rechnet die Plattform täglich nach
(`manage.py audit_pruefen`); das Ergebnis und der Hash des letzten geprüften Eintrags (`audit.head`)
stehen öffentlich in `/kennzahlen.json`. Wer sich diesen Kopf notiert, erkennt später, ob jemand die
Kette von dort an neu gerechnet hat.
