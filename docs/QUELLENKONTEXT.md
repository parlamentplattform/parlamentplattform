# Amtlicher Quellenkontext neuer Rechtsbezug-Aufträge

Seit 0.61.0 halten neue öffentliche Rechtsbezug-Aufträge neben ihrem Textkontext
einen getrennten amtlichen Quellenkontext fest. Das ist ein Teil von S11, keine
juristisch verifizierte Antragszuordnung und kein vollständiges Abbild des Rechts.
Die Sammlung in Produktion darf leer bleiben. Es gibt keinen automatischen
RIS-Netzabruf beim Einbringen und keinen zusätzlichen Modellaufruf.

## Auswahlfassung 1

Maßgeblich ist die reine Regel `plattform_core/quellenauswahl.py`, VERSION 1,
verzeichnet seit 3.11.2026 im Regelverzeichnis, Fassung 6. Die Datenbankanbindung
liegt in `faktenbasis/auswahl.py`. Sie bezieht sich ausschließlich auf vorhandene
Bundesrecht-Schnappschüsse; fehlendes Landesrecht oder EU-Recht wird nicht ersetzt.

1. Vor der Auswahl werden Zeitpunkt und Wiener Kalendertag festgehalten. Nur
   erfolgreiche, bis dahin beendete Importe mit Quellenstand bis zu diesem Tag
   sind zulässig. Je amtlicher RIS-Kennung zählt der höchste vorhandene Stand,
   bei gleichem Stand die höhere Schnappschuss-ID. Erst dann wird Text verglichen.
2. Aus diesem Bestand wird in amtlicher Kennungsreihenfolge eine begrenzte Liste
   gelesen. SQL-Fensterzählung und ID-Liste stammen aus derselben Datenbanksicht.
   Es wird keine Vollständigkeit des Rechtsbestands behauptet.
3. Titel, Wortlaut und Begründung des festgehaltenen Antrags bzw. eingereichten
   Vorschlags werden mit Kurztitel, Titel und Abschnitt dieser Normen verglichen.
   NFKC-Normalisierung, Unicode-casefold, Wörter aus Buchstaben/Ziffern; Zahlen,
   Wörter unter Mindestlänge, über 80 Zeichen und veröffentlichte Stoppwörter
   entfallen. Bindestriche trennen Wörter; es gibt keine erfundenen Abkürzungs-
   oder Rechtsgebietszuordnungen. Die Stoppwortliste steht vollständig im Modul.
4. Ein Wort darf Anfang des anderen sein. Schon ein solcher Treffer ergibt einen
   **Kontextkandidaten**, keine rechtliche Betroffenheit. Alle Treffer sind
   gleichwertig; nach amtlicher Kennung folgen die ersten bis zur Quellengrenze.
   Keine Relevanzpunkte, politischen Prioritäten oder semantischen Modellkosten.
5. Je gewählter Quelle wird der tatsächlich vorliegende Dokumenttext desselben
   Norm-Schnappschusses bis zum Erfassungszeitpunkt gelesen. Fehlender Text bleibt
   ausdrücklich fehlend. Ein begrenzter Anfang ist ein gekennzeichneter Ausschnitt.

Registerwerte werden einmal bei der Erfassung gelesen und tatsächlich angewendet
gespeichert; spätere Änderungen wirken nicht auf bestehende Aufträge:

| Registerschlüssel | Anfangswert | Technisch zulässig |
|---|---:|---:|
| quellenkontext-hoechstzahl | 3 Quellen | 0–20 |
| quellenkontext-textzeichen | 1200 Zeichen je Quelle | 0–20000 |
| quellenkontext-mindestwortlaenge | 3 Zeichen | 2–12 |
| quellenkontext-bestandsgrenze | 500 Schnappschüsse | 1–2000 |

Werte außerhalb der Grenzen werden auf diese Grenzen beschränkt. Zusätzlich
versionierte technische Grenzen: 100000 Zeichen für den Auswahltext, höchstens
2000 Zeichen je Metadatenfeld. Überlange Auswahltexte führen zu einem ehrlichen
Erfassungsfehler, nicht zu einem stillen Weglassen des Textrests. Die Suche kann
falsche Treffer liefern und relevante Quellen übersehen. Das wird durch einen
Hash nicht behoben. Null Quellen oder ein leerer Bestand sagen nichts darüber,
ob Rechtsnormen betroffen sind.

## Erhaltene Daten und Nachrechnung

`KIAuftrag.quellenkontext` enthält Formatversion 1, UTC-Erfassung, Quellenstichtag,
die Prüfsumme des zugehörigen Textkontexts (vor dem Aufruf ausdrücklich geprüft),
tatsächlich verwendete Grenzen, vollständige geprüfte Bestands-IDs, Gesamtanzahl,
Treffer- und Auswahl-IDs, Regel- und verwendete Unicode-Fassung, Suchwortanzahl/-hash sowie die Merkmale
einer begrenzten Auswahl. Unveränderliche Norm-Schnappschüsse und der öffentliche
Textkontext erlauben dieselbe Auswahl erneut. Die festgehaltene ID-Liste ist
maßgeblich; nachträgliche Importe werden nicht in den damaligen Bestand geraten.
Die Zeitgrenzen sind keine Behauptung eines vollständigen historischen
Datenbankabbilds: Festgehaltene IDs und Inhalte belegen die tatsächlich gelesene
Auswahl, auch wenn Importe nebenläufig laufen.

Je Quelle stehen Norm-ID, RIS-ID, Gesetzesnummer, Kurztitel, Abschnitt, Stand,
amtliche Adresse und Metadatenhash. Ein Dokumenttext besitzt zusätzlich eigene
ID, Parserfassung, XML-Quelle/-hash, tatsächlichen Ausschnitt, Ausschnitthash,
Gesamtlänge und Kürzungsmerkmal. Die Prüfung lädt keine aktuellen Quellen nach.
Die kanonische Gesamtprüfsumme wird wie beim Textkontext berechnet: JSON ohne
`sha256`, sortierte Schlüssel, UTF-8, unmaskierter Unicode, keine zusätzlichen
Leerzeichen, keine nichtendlichen Zahlen. Der Suchworthash bezieht sich auf die
sortierten unterschiedlichen Suchwörter, mit Zeilenumbruch verbunden, UTF-8.

Nur gewählte Quellen und eine kompakte Auswahlbeschreibung werden an den Anbieter
übergeben. Die lange Bestands-ID-Liste ist ein Nachweis im Archiv, kein unnötiges
Tokenvolumen. Die unveränderte tatsächliche Eingabe und der vollständige Kontext
stehen auch bei einem Anbieterfehler am Lauf. Öffentliche JSON-Archivexporte und
persönliche Datenexporte erhalten beide Kontextfelder; interne Gremien-Eingaben
werden nicht über den öffentlichen Rechtsbezug-Export veröffentlicht.

## Altbestand und Fehler

Migration `ki/0005` ergänzt nur ein leeres JSON-Feld. Ein alter Auftrag mit `{}`
behält ausdrücklich `rechtsbezug-v1`. Quellenfassung1, auch leer, nutzt
`rechtsbezug-v2`; neue Quellenfassung2 seit0.70 nutzt `rechtsbezug-v3`.
Das Antwortformat bleibt Version1. Alte Promptdateien und Eingaben bleiben.
Herkunft, Umfang und die unverändert prüfbare Fassung1 beschreibt `LANDESKONTEXT.md`.
Idempotentes Einreihen gibt zuerst den vorhandenen Auftrag zurück. Speichern,
QuerySet.update, bulk_update und konfliktauflösendes bulk_create können die
festgehaltene Eingabe und Quellen nicht nachträglich ersetzen.

Scheitert die Erfassung, bleibt ein gescheiterter Auftrag mit null Versuchen und
einem getrennten Fehlerobjekt (`version`, `fehler: erfassung`, `erfasst_am`)
erhalten. Dieses Objekt behauptet keinen Quellen- oder Prüfsummennachweis. Ein
Savepoint schützt die Verfahrenstransaktion; kein Anbieter wird aufgerufen. Die
Anzeige verwechselt dies weder mit aufgebrauchten Versuchen noch mit fehlenden
rechtlichen Folgen. Eine spätere Wiederholung ersetzt diesen Stand nicht.

Amtliche Herkunft und rechtliche Deutung bleiben getrennt: Nur die kontrolliert
festgehaltenen Originalquellen sind verlinkt. Modellnormen behalten ihr Etikett
„nicht verifiziert“, unabhängig von einem ähnlich klingenden Titel in der Sammlung.
Verifizierte Norm-Verweis-Kanten, vollständiger Rechtsbestand, automatische
Aktualisierung und weitere Folgenanalysen bleiben offen. Öffentliche Korrekturläufe
sind getrennt in `KORREKTURLAUF.md` beschrieben.


Seit0.61.1 schützt der gewöhnliche ORM zusätzlich den gesamten fertigen Modelllauf sowie die Löschwege für Aufträge und Läufe. Eine Neuanlage mit bereits vorhandener Primärschlüsselnummer ist kein Weg zum Ersetzen alter Daten. Urheber und Einreihzeitpunkt des Auftrags sind geschützt; sein betrieblicher Status bleibt veränderlich. Das ist Anwendungsschutz, kein Ersatz für Datenbank-Zugriffsrechte, Sicherungen oder eine kryptografische Signatur.
