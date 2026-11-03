# Freiwillige private Gegenüberstellung beim Einbringen

Nach der Trefferanzeige kann die Person ausdrücklich eine Gegenüberstellung
anfordern. Vor der Schaltfläche steht, welche Texte zum konfigurierten Anbieter
gehen. Kein Chat beim Tippen, beim GET oder bei der menschlichen Wahl. Beide
Wahlwege bleiben gleichwertig und ohne Modellvergleich benutzbar. Auch Fehler
oder Formabweichungen bewahren das Formular. S11 insgesamt bleibt teilweise.

Der private Rahmen `ki.vergleichskontext` Fassung 1 bindet das signierte Angebot
an Konto und vollständiges Formular. Nur die angebotenen öffentlichen aktuellen
Sachantragsfassungen werden gelesen. Geänderte Titel, Fassungen, fehlende Texte
oder inzwischen nicht mehr offene Anträge verlangen ein neues Angebot. Interne
Gremienentwürfe werden nicht gelesen. Titel und Wortlaute werden vollständig oder
gar nicht übernommen; die Gesamtgrenze wird nicht durch stilles Kürzen umgangen.

Die Anbieterprojektion enthält nur den eigenen Titel/Wortlaut sowie
öffentliche Antrags-/Fassungsreferenzen, Titel, Wortlaute und Textprüfsummen.
Konto, E-Mail, Begründung, Gebiet und Vergleichsprozente werden nicht beigefügt.
Der Fingerabdruck normalisiert Formularzeilenenden wie der bestehende Prüfstand;
gespeicherte öffentliche Wortlaute bleiben genau erhalten. Spätere Nachlese
rekonstruiert denselben Input ohne aktuelle Datenbanktexte nachzuladen.

Ein signiertes Angebot für eine zufällige Anforderungskennung speichert selbst
noch keinen Entwurf. Erst eine ausdrückliche Anforderung legt eine private
`Vergleichsanfrage` anlegen. Konto, Texte, Prüfsummen und Erstellzeit bleiben
über gewöhnliche ORM-Wege unveränderlich. Ein bedingtes UPDATE reserviert die
Kennung einmalig. Doppel-POST, Reload oder ein zurückgesetztes Statusfeld können
sie nicht erneut starten; begonnen_am bleibt maßgeblich. Ein Prozessabbruch löst
keine zeitgesteuerte zweite Anbieterausführung aus. Ein neuer Versuch benötigt
eine neue ausdrückliche Anforderung. Eigener Zweck gegenueberstellung und
versionierter öffentlicher Auftrag gegenueberstellung-v1; kein Vektoraufruf wird
als Textbegründung ausgegeben. Je Paar zwei kurze Textteile, keine Entscheidung.

Additive Migrationen legen nur die neue Tabelle und die zusätzliche Zweckkennung
an. Der eigene Datenexport enthält ausschließlich die eigenen privaten
Anforderungen samt tatsächlich gespeicherter Antwort und Laufmetadaten;
öffentliche Antragsarchive und die öffentliche Liste letzter Werkstattläufe
enthalten diese unveröffentlichten Texte oder Anbieterfehler nicht.

Vier offene Registerwerte begrenzen die ausdrücklichen Anforderungen: fünf je
Konto und Stunde, acht Sekunden je Verbindungsschritt, drei angebotene Paare
und insgesamt 20000 Zeichen als Erstbestand. Technische Grenzen sind 1–45
Sekunden, 1–20 Paare und 1–100000 Zeichen; null Stundenanforderungen schaltet die
Funktion ab. Die Textgrenze beschränkt ausschließlich den optionalen Modellweg,
niemals das eigene Einbringen. Bestehender gemeinsamer Anbieterzugang und
Monatsverbrauch gelten zusätzlich. Dies ist keine Budgeterhöhung oder harte
Geldobergrenze. Wie der bisherige synchrone Bedeutungsvergleich gehört dieser
Vorabweg nicht zur Hintergrundwarteschlange und deren Tageskontingent. Eine
mehrdeutige/abgebrochene Anforderung wird niemals automatisch wiederholt.

Der reine Antwortvertrag `plattform_core.gegenueberstellung` Fassung 1 prüft
genau die angebotenen IDs/Fassungen und ihre Reihenfolge, je einen begrenzten
Textteil für Gemeinsamkeit und Unterschied. Er erkennt keine juristische oder
inhaltliche Richtigkeit und ersetzt keine menschliche Entscheidung. Keine
Teilantwort wird bei fehlerhaften Paaren als brauchbar ausgegeben.
