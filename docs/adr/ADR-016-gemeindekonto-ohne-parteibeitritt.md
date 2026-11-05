# ADR-016: Gemeindekonto ohne Parteibeitritt

Datum: 4.11.2026 · Status: erster Baustein in Umsetzung

## Anlass

Die freiwillige Gemeindebeteiligung soll Einwohnern ab16 mit tatsächlich gemeldetem
Hauptwohnsitz unabhängig von Parteibeitritt und Staatsangehörigkeit offenstehen.
Die bisherige Benutzerklasse `Mitglied` verbindet Anmeldung und Parteirechte.
Ein neues Authentifizierungsmodell würde bestehende Fremdschlüssel und Historien
gefährden. Ein zweiter Login würde doppelte Konten und widersprüchliche Rechte schaffen.

## Entscheidung

Die vorhandene Benutzeridentität bleibt erhalten. `parteikonto` unterscheidet die
bestehende Parteiverwaltung von einem ausdrücklich ohne Beitritt angelegten Konto.
Bestand und bisheriger Beitrittsweg behalten ihren Typ; der neue Gemeindeweg setzt
ihn ausdrücklich auf falsch. Der Typ ist nach Anlage nicht über normale Schreibwege
änderbar. Ein späterer ausdrücklicher Beitrittsprozess ist gesondert zu bauen.
Ein additiver Gemeindezugang trägt die freiwillige Anmeldung und Alters-Selbstauskunft;
die Hauptgemeinde stammt weiterhin aus dem vorhandenen eindeutigen Gemeindestamm.
Parteimitglieder können denselben Zugang mit ihrer vorhandenen Identität ergänzen.

Eine Datenbankbedingung verhindert Mitgliedsnummer, Beitritt, Beitragsreferenz,
Parteiposteinwilligung, Mitgliedsausweis, Parteiprüfstufe oder Verwaltungsrechte am
reinen Gemeindekonto. Parteizähler und Parteiauswahlmengen filtern ausdrücklich.
Auf bestehenden Parteiseiten sieht dieses Konto serverseitig denselben Zugang wie
ein Gast. Schreibanfragen werden abgewiesen; nur Gemeinde- und Anmeldewege behalten
die authentifizierte Identität. Damit hängt die Grenze nicht von versteckten Knöpfen
oder von einer vollständigen Aufzählung heutiger und künftiger Parteiseiten ab.

E-Mail-Bestätigung verwendet einen eigenen Zweck und stellt keine Parteiaufnahme,
Personenprüfung oder Melderegisterbestätigung dar. Vor der Bestätigung bleiben
Zugang und Gemeindezuordnung inaktiv. Geburtsdatum wird nur zur Altersprüfung bei
Anmeldung benutzt, nicht gespeichert. Erfasst wird der Zeitpunkt dieser Selbstauskunft.
Private Gemeindeangaben erscheinen weder öffentlich noch im öffentlichen Verfahrensaudit.

## Grenze dieses Bausteins

Noch keine Einwohnerabstimmung, Stimmrechtsfreischaltung, Parteikonversion,
amtliche Gemeindeanwendung oder neue kostenpflichtige Infrastruktur. Die konkrete
Identitäts-/Einmaligkeitsprüfung, Abstimmungsstichtage und das Verhältnis zu
widersprechenden Parteibeschlüssen bleiben gesondert offen. Bestehende Verfahren,
Stimmen, Mitglieder-IDs und festgehaltene Regeln werden nicht verändert.
Der bisherige Parteiaustritt deaktiviert weiterhin das vorhandene Konto. Einen
Wechsel aus einer Parteimitgliedschaft in einen fortgesetzten reinen Gemeindezugang
regelt dieser erste Baustein noch nicht; diesen Vorgang nicht als vorhanden anbieten.

## Abnahme

Echte Registrierung und Bestätigung, getrennte Tokenzwecke, Wiederanmeldung,
bestehende Identität statt Doppelbeitritt, Altersschwelle und eindeutige Gemeinde,
CSRF/Drossel/Versandfehler, direkte Parteischreibwege, Nummer/Post/Karte/Zähler,
Datenbankschutz, Bestandsmigration sowie Handy/Deutsch/Englisch/ohneJavaScript.
