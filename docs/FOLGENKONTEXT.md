# Vorbereiteter gemeinsamer Folgenkontext

`ki.folgenkontext`, Fassung 1, verbindet einen tatsächlich beobachteten öffentlichen
Textstand, den vorhandenen begrenzten Normrahmen und den getrennten Personal-
Bestandsrahmen. Noch kein Modellaufruf, keine neue Warteschlange oder Bedienhandlung,
keine Änderung früherer Aufträge und keine neue Softwarefreigabe.

Die neue Erfassung liest den Antrag erneut aus der Datenbank. Personenwahlen und
Vertrauensfragen sind ausgeschlossen. Eine Vorschlagsfassung muss zum Antrag
gehören und als eingereicht festgehalten sein; interne Arbeitsentwürfe werden
nicht übernommen. Bestehende Text-, Quellen- und Personalverträge bleiben
unverändert und jeweils gesondert an dieselbe Textprüfsumme gebunden.

Alle Teile nennen denselben Erfassungszeitpunkt. Die normativen Kontextkandidaten
bleiben unvollständige vorhandene Worttreffer ohne juristische Zuständigkeits-
prüfung; die Personaldaten bleiben Bundesbestände ohne Bedarfsschätzung. Es wird
kein Netzabruf und kein Anbieteraufruf ausgelöst. Fehler werden nicht durch neue
Quellen oder einen unbemerkt leeren Altmodus ersetzt.

Die tatsächliche spätere Eingabe ist kanonisches JSON mit öffentlichem Text,
amtlicher Normgrundlage, separater Personal-Bestandsgrundlage und den genau daraus
abgeleiteten Quellen-/Bereichsreferenzen. Kontometadaten oder private H2-Entwürfe
werden nicht beigefügt. Die explizit übergebene Gesamtgrenze wird im Rahmen
festgehalten; zu große Eingaben werden nicht still gekürzt. Ein späterer
angeschlossener Betriebsweg benötigt dafür einen offenen Registerwert.

Der gespeicherte Eingabehash belegt den tatsächlich rekonstruierten Wortlaut.
Spätere Nachlese liest keine heutigen Datenbankstände, Registerwerte oder Dateien
nach. Hashes sind kein Schutz gegen privilegiertes SQL und keine rechtliche
Bestätigung. Der bezeichnete künftige Auftrag `rechtsfolgen-v1` ist noch nicht
als Providerweg angeschlossen; dafür fehlen in dieser Vorbereitung bewusst
Auftragstext, Ausführung, Korrekturweg und Benutzeroberfläche.
