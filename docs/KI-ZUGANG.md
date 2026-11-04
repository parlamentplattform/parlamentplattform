# Gemeinsamer betrieblicher Modellzugang (0.71.1)

Vor der Korrektur konnten zwei überlappende Aufrufe denselben noch nicht verbrauchten
Monatsrest sehen. Der erste Verbrauch war während der zweiten Prüfung noch nicht im
Archiv. Die deterministische Attrappe belegte zwei Starts mit je5 Tokens trotz Grenze5.
Das ist ein Software-Nachweis, keine Behauptung tatsächlich entstandener Mehrkosten.

## Zugang, Prüfung und Archivierung

Text- und Einbettungsaufrufe verwenden dieselbe rein betriebliche Datenbankzeile.
Ihre Sperre umfasst das erneute Lesen der bisherigen Verbrauchsangaben, den tatsächlichen
Anbieteraufruf und die Archivierung. Eine weitere Verbindung erhält einen Wartestatus
statt eines zweiten Anbieterstarts. Ein internes Flag erkennt auch verschachtelte
Aufrufe derselben Verbindung, die sich nicht selbst mit einer Zeilensperre ausschließt.
Das Flag ist kein Tokenverbrauch oder sonstiger Fakten-Schnappschuss.

Auf PostgreSQL wird die Zeile mit `SELECT FOR UPDATE NOWAIT` gesperrt. Damit wird
die Verbindung nicht bis zum Ende der anderen Modellrechnung wartend belegt. Nur der
passende Sperrfehler wird als belegter Zugang behandelt; andere Datenbankfehler werden
nicht verborgen. Maßgeblich sind die [PostgreSQL-Sperren](https://www.postgresql.org/docs/16/explicit-locking.html)
und der [Fehlercode lock_not_available](https://www.postgresql.org/docs/16/errcodes-appendix.html).
SQLite hat keine gleichartige Zeilensperre; dort schützt die bedingte Schreiboperation
im gleichen Transaktionsrahmen. BUSY-/LOCKED-Fehler werden über ihre
[SQLite-Fehlerattribute](https://docs.python.org/3.12/library/sqlite3.html#sqlite3.Error.sqlite_errorcode)
erkannt. Andere Fehler werden weitergereicht. SQLite kann dabei auch andere lokale
Schreibzugriffe blockieren; die Produktion verwendet PostgreSQL.

Es gibt keine ablaufende Zeitlease, die einen noch arbeitenden Anbieter parallel
freigeben könnte. Transaktions-/Verbindungsende löst den Zugang auch bei unerwartetem
Abbruch. Ein normaler Anbieterfehler wird zuerst als Fehlversuch archiviert und erst
danach als stummer Steckplatz weitergereicht. Die Ausnahme darf den Archiveintrag
nicht zurückrollen. Unerwartete Fehler lassen die Betriebsänderung zurückrollen.

## Warten ist kein Anbieter-Versuch

Ein belegter Zugang, fehlender Anbieter oder bereits ausgeschöpfte Monatsgrenze startet
keinen Anbieter. Die technische Auftragsreservierung wird in der Warteschlange deshalb
nicht als verbrauchter Fehlversuch gezählt. Der Auftrag bleibt für den nächsten regulären
Fadenlauf geplant. Es entsteht kein fiktiver KILauf. Bedeutungsvergleiche können wie
bisher auf den lokalen Wortvergleich zurückfallen. Antrag, Abstimmung und Fristen warten
nicht auf den Modellzugang. Rechte, Anbieter, Budgetbeträge und Tagesgrenze bleiben gleich.

## Tatsächliche Grenze der Monatsprüfung

Geprüft wird der im Archiv gemeldete Verbrauch vor dem Start. Ein einzelner schon
gestarteter Lauf kann den Monatsrest überschreiten. Ungemeldeter Verbrauch und ein
späterer Fehler einer äußeren Aufrufertransaktion sind keine Kostenfreiheitsnachweise.
Die Tokenprüfung ist keine Abrechnung oder garantierte Geldobergrenze. Es werden keine
Tarife, Preise oder Verbrauchswerte erfunden. Ein entsprechender alter Systemtext im
Register wird nur bei exakter Übereinstimmung berichtigt; alter und neuer Text bleiben
im Audit nachlesbar. Budgetwert und eigene Beschreibungen der Menschen bleiben erhalten.

Migration ki0007 ergänzt ausschließlich den betrieblichen Zugang und legt die eine
Zeile idempotent an. Alte Läufe, Aufträge und eingefrorene Kontexte werden nicht geändert.
Der lokale und PostgreSQL-CI-Test verwendet echte getrennte Verbindungen und eine
Attrappe ohne Netzaufruf. Der tatsächliche PostgreSQL-Erfolg bleibt vor einer Freigabe
anhand der Pflicht-CI zu bestätigen. Kein neuer Dienst, Anbieter oder Kostenrahmen.
