# Nachrechnen ohne die Plattform

Satzung § 5 Abs 8 verlangt, „dass ihr Ergebnis von jedem Mitglied ohne Spezialkenntnisse überprüfbar
bleibt“. Dafür gibt es hier ein Skript, das **nur die Python-Standardbibliothek** braucht.

## Ein Ergebnis nachrechnen

1. Auf der Antragsseite nach Abstimmungsende den Export laden (`/antrag/<nummer>/export.json`).
2. `python3 verify/nachrechnen.py antrag-<nummer>-export.json`
3. Die ausgegebenen Zahlen mit der Ergebnisseite vergleichen.

Unter `ergebnis` nennt das Skript den Ausgang in einem Wort: `angenommen`, `abgelehnt` oder
`kein_beschluss` — Letzteres, wenn der festgehaltene örtliche Kreis keinen einzigen Stimmberechtigten
hatte. Das Skript errechnet dieses Wort selbst aus Stimmen und Nenner; das Feld `ergebnis` des
Exports liest es dafür nicht und vergleicht es auch nicht damit. Den Vergleich zieht, wer nachrechnet:
Das ausgegebene Wort gehört neben das Feld `ergebnis` im Export und neben die Ergebnisseite. Lauten
sie verschieden, stimmt etwas nicht. Ältere Exporte nennen kein Wort.

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

## Der Abgleich des Exports mit der Audit-Spur

Die Audit-Spur beweist, dass etwas geschah. Damit sie auch beweist, **was** gezählt wurde, legt die
Plattform die Größen, die über ein Ergebnis entscheiden, unter die Kette, und das Skript vergleicht den
Export damit. Stimmt etwas nicht überein, endet es mit `FEHLER`.

| Ausgabe | Was verglichen wird |
|---|---|
| `nenner_versiegelt` | Zahl der Stimmberechtigten (`stimmberechtigte`) und ihr Stichtag (`stichtag`) im Export gegen das Ereignis `phasenwechsel`, mit dem die Abstimmung begann (`neue_phase`: `abstimmung`, Felder `stimmberechtigte` und `stichtag`) |
| `stimmliste_versiegelt` | Die Stimmliste des Exports gegen den Abschluss im Ereignis `phasenwechsel`, das das Ergebnis feststellt: Prüfsumme der Liste (`stimmliste_sha256`), Zahl der Stimmzettel (`stimmzettel`) und Zahl der Stimm-Ereignisse in der Spur (`stimmereignisse`) |
| `regeln_versiegelt` | Die eingefrorenen Regeln (`policy`) gegen `regeln_sha256` im Ereignis der Einbringung (`antrag_eingebracht`, `mandatsfrage_eroeffnet`, `vertrauensfrage_eingebracht`): SHA-256 über den Block als JSON mit sortierten Schlüsseln, ohne Leerzeichen |
| `wortlaut_versiegelt` | Der Wortlaut (`fassungen`) gegen `wortlaut_sha256`: die erste Fassung gegen das Ereignis der Einbringung, die abgestimmte Fassung (`fassung`) gegen das Ereignis `phasenwechsel` des Abstimmungsbeginns; SHA-256 über den Text, Zeichen für Zeichen |

Die Prüfsumme der Stimmliste von Hand: je Stimme eine Zeile `[Pseudonym, Stimme]`, die Zeilen sortiert,
als JSON ohne Leerzeichen (UTF-8), darüber SHA-256. Bei der Zustimmungswahl je Bewerbung
`["bewerbung", Platz in der Einreichreihenfolge, Nummer, zurückgezogen]` und je Zustimmung
`["zustimmung", Pseudonym, Bewerbung, zurückgenommen]`.

Unabhängig von jedem Siegel gilt: Mehr Stimmen als Stimmberechtigte zählt das Skript nicht aus, es
endet mit `FEHLER`.

Die Plattform macht dieselbe Gegenprobe, bevor sie ein Ergebnis feststellt: Stimmzettel gegen
Stimmregister, Zahl der Stimmberechtigten und Stimm-Ereignisse. Fehlt zu einem Stimmzettel die Zeile
im Stimmregister oder führt die Audit-Spur nicht so viele Stimm-Ereignisse wie Stimmzettel, stellt
die Plattform kein Ergebnis fest; der Antrag bleibt in der Abstimmung stehen, und der Befund steht als
Ereignis `auszaehlung_angehalten` in der Audit-Spur (nur Zahlen, keine Pseudonyme). Mehr Stimmen als
Stimmberechtigte halten die Feststellung nicht an: Die Plattform stellt das Ergebnis fest und weist die
Abweichung im Ereignis `phasenwechsel` des Ergebnisses aus (`abweichungen`:
`mehr_stimmen_als_stimmberechtigte`); das Skript endet an einem solchen Export mit `FEHLER`.

Abstimmungen aus der Zeit vor einem dieser Siegel tragen die Felder im Ereignis nicht. Das Skript
rechnet sie wie bisher und gibt `False` aus: nicht versiegelt, kein Fehler.
