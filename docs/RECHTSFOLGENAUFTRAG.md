# Eigener Rechtsfolgenauftrag

Dieser lokale0.73-Bau ist noch keine Live- oder S11-Gesamtabnahme. Neue Webanträge
und eingereichte Vorschlagsfassungen erhalten einen kombinierten Auftrag statt
des bisherigen Rechtsbezugs. Vorhandene alte Aufträge bleiben unverändert und
werden nicht verdoppelt. Der Eingaberahmen wird offen aus dem Register gelesen
und im Auftrag festgehalten. Keine zusätzliche automatische Rechnung und keine
echten Anbieteraufrufe oder Produktionsimporte während der lokalen Prüfung.

`KIAuftrag.folgenkontext` hält öffentlichen Text, amtlichen Normrahmen und
getrennten Personalbestand mit derselben Zeit und Textprüfsumme fest. Die
additive Migration0010 setzt Altaufträge auf `{}`; keine Datenmigration ergänzt
ihnen neue Quellen oder Auftragstexte. Norm- und Textfelder sind weiterhin
vorhanden, müssen aber exakt mit dem neuen Rahmen übereinstimmen. Übliche
ORM-Schreib-, Mengen- und Konflikt-Upsertwege schützen auch dieses neue Feld.

Idempotent je Antrag, Quellenart und Fassung. Bereits vorhandene Aufträge werden
vor einer neuen Faktenerfassung zurückgegeben. Eine neuere eingereichte
Vorschlagsfassung erhält eine eigene Identität; ein früher öffentlich beauftragter
Vorschlag bleibt abrufbar. Neue interne Entwürfe und Personenfragen sind ausgeschlossen.
Ein zu großer Kontext wird nicht gekürzt. Erfassungsfehler bleiben als gescheiterter
Auftrag sichtbar und werden weder zum Quellenleerstand noch zu einem alten Prompt
umgedeutet. Ein Savepoint schützt umgebende Verfahrenstransaktionen.

Der Worker lädt ausschließlich `rechtsfolgen-v1`, rekonstruiert die unveränderte
Eingabe ohne heutige Quellen und verwendet `lauf_ausfuehren` mit dem gemeinsamen
Zugang und Monatsrahmen. Dieser Zweck zählt im vorhandenen Tageskontingent mit.
Antwort, Fehler, Tokens, Zeitpunkt, Auftragstextfassung, Auftragsnummer, Versuch
und tatsächlicher Kontext bleiben im Laufarchiv. Eine falsche Antwortform löst
keine automatische zweite Modellrechnung aus und gibt keine Teilantwort frei.
Formprüfung bestätigt keine Rechtsaussage. Personalbestände belegen keine
Stellenfolgen: alle numerischen Deltas bleiben unbekannt, auch0istkein Nachweis.

Der eigene Datenexport enthält den eigenen Folgenrahmen. Der genau gebundene
Korrekturweg ist in FOLGENKORREKTUR.md beschrieben. Öffentliche Hauptanzeige,
Historie, Ergebnispost und Hauptexport sind in RECHTSFOLGENANZEIGE.md beschrieben.
Der offene Eingabeparameter und die Umstellung neuer Aufträge bestehen. Die
vollständige Prüfung und Freigabe folgen vor einer Auslieferung.
Die Umstellung ersetzt für neue Aufträge die bisherige automatische Rechtsbezug-
Rechnung; sie verändert keine alten Kontexte, laufenden Regeln oder Budgetwerte.
Keine Auslieferung vor vollständiger Prüfung.
