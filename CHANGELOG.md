# Änderungsprotokoll

Format nach [Keep a Changelog](https://keepachangelog.com/de/), Versionierung nach [SemVer](https://semver.org/lang/de/).

## [0.45.0] — 2026-09-11 · Der Koordinationsrat, das Parameterverfahren, die Werkstatt mit drei Spalten — und hundert Befunde

### Hinzugefügt
- **Der Bereich des Koordinationsrats** (`/gremien/koordination/`, § 6 Abs 2) als 2×2-Raster: **Aufgaben** (Austauschanträge der Gruppe 2, Überlastungsmeldungen, Vollzugsberichte, „Hervorhebung beim Integritätsrat beantragen“), **Posteingang der Zukunftswerkstatt**, **Beschlüsse** mit Umsetzungsvermerk, **Parameter & Tests**. Kein Knopf wirkt unmittelbar — jeder legt einen Beschluss an oder vermerkt etwas; der Rat entscheidet als Rat (§ 6 Abs 2 lit e), nicht wer zuerst drückt
- **Der Austausch der Gruppe 1 ist ein Beschluss.** Bis jetzt entschied ein einzelnes Ratsmitglied — und Stattgeben beendete die Rollen der Gruppe 1 **aller** Verfahren, seit 0.44 also fremde Auslosungen. Jetzt enden nur die für **diesen** Antrag gelosten Rollen, und es wird eine neue Runde gelost (§ 6 Abs 7)
- **Überlastungsmeldungen nach § 6 Abs 10.** Die berichtspflichtige Stelle meldet auf `/umsetzung/`; die Meldung ist sofort öffentlich; der Koordinationsrat hat 30 Tage (satzungsfest, keine Stellgröße) für einen Vorschlag — der ist ein Beschluss, und seine Wirkung bringt ihn als **Sachantrag in die Mitgliederversammlung** ein. Die Plattform ist die Mitgliederversammlung; der Vorschlag geht dorthin, wo die Satzung ihn haben will
- **Das Parameterverfahren (§ 6 Abs 11 lit c, FB-J3):** Test anordnen → Beschluss → der Testwert steht im Register mit Band → am Ende fällt der Wert von selbst zurück, die Messgröße wird vorher und während des Tests gegenübergestellt, die Auswertung landet im Posteingang → Einführung wieder per Beschluss, mit Begründung im Register. `plattform_core/parametertest.py` (VERSION 1) rechnet die Gegenüberstellung und hat keine Meinung dazu: Ob ein Wert eingeführt wird, sagen Menschen mit Namen. Die Messgrößen sind die Kennzahlen, die die Plattform ohnehin veröffentlicht (`/kennzahlen.json`) — eine zweite Zählung nur für Tests wäre nicht nachrechenbar. **D-J3g gilt:** Ordnungsschlüssel sind vom Test ausgenommen; kein Test berührt ein laufendes Verfahren (§ 5 Abs 5)
- **Öffentlich zu jedem Parameter:** `/parameter/<schlüssel>/` mit Historie und Tests; der **jährliche Parameterbericht** `/parameter/bericht/<jahr>/` — erzeugt aus dem Register, kein Freitext
- **Das Entwurfsfenster als Drei-Spalten-Arbeitsplatz** (FB-I2): links der rohe Antrag mit Absatznummern, in der Mitte der Entwurf mit **Diff zur vorigen Fassung** (ein Link, kein Skript), rechts die Werkzeuge — Einschätzung der Zukunftswerkstatt als Arbeitsunterlage, Wünsche der Unterstützer aus der Vorrunde mit Haken „berücksichtigt in Fassung n“, interne Beratung mit **Absatz-Kommentar** am Rand des Absatzes. Auf dem Handy stehen die Spalten untereinander, eine Sprungleiste führt hin — nichts wird versteckt
- **Die Einreichung ist ein Beschluss** (§ 6 Abs 2 lit e) — und jede Stimme trägt die **Interessenbindungen zu diesem Antrag** als Pflichtfeld (§ 6 Abs 7; „keine“ ist eine Antwort). Sie stehen öffentlich beim Vorschlag. Solange abgestimmt wird, ruht die Fassung: Über einen Text, der sich unter der Hand ändert, stimmt niemand ab. Offene Einreich-Abstimmungen von vor 0.45 überträgt eine Datenmigration in einen Beschluss — ein laufendes Verfahren wird nicht mitten im Lauf umgestellt (§ 5 Abs 5)
- **Zwei weitere Räte im Code:** Integrations- und Berichtswesenrat, Technischer Entwicklungsrat — mit Bereich, Beschlüssen und Kürzeln IB/TE in den Beschlussnummern. Sechs der sieben Räte der Satzung gibt es jetzt; der Support-Rat steht weiter als Lücke in der Rollenübersicht
- **„Mein Gremium“** wählt, wenn jemand mehrere Rollen hat; **wer eine Rolle hatte, liest weiter** — mit Band, ohne Schreibrecht (FB-I1)
- **Sitzungsprotokolle** je Rat und Jahr als JSON: Die Beschlüsse mit Stimmen, Begründungen und Umsetzungsvermerken *sind* das Protokoll (§ 6 Abs 9)
- **Der jährliche öffentliche Bericht des Integritätsrats** (§ 6 Abs 3 lit c) — erzeugt aus Beschlüssen, Aussetzungen, Regelprüfung und Besetzung des Jahres; nichts daran kann jemand kürzen
- **Unvereinbarkeit bei der Rollenvergabe** (§ 6 Abs 3 lit a): Kein Mitglied des Integritätsrats in einen anderen Rat, niemand aus einem anderen Rat oder mit Mandat in den Integritätsrat — geprüft, wenn die Rolle entsteht, nicht erst beim Losen
- Rollenmatrix **Fassung 2**, Regelverzeichnis **Fassung 2** (neu: die Gegenüberstellung der Parametertests)

### Behoben — die Gesamtprüfung vor 0.45.0
Am 9.9.2026 wurde die ganze Plattform in neun Richtungen geprüft und jeder Befund gegnerisch nachgeprüft: **100 bestätigte Befunde** (18 hoch, 49 mittel, 33 niedrig). Fünf davon behob der Umbau der Einreichung (oben). Die übrigen, nach Gewicht:

*Hoch*

- **#0 · Gespeichertes XSS auf der öffentlichen Übersichtsseite über den Antragstitel (SVG-Balken)** — html.escape statt xml.sax.saxutils.escape in plattform_core/diagramme.py (aria-label, title, text); Hypothesis-Eigenschaftstest und View-Test ueber /uebersicht/ mit einem Titel, der ein onload-Attribut einschleusen will. CSP bewusst nicht , in md festgehalten. (erster Lauf).
- **#1 · Admin kann per E-Mail-Änderung jedes Konto übernehmen und das Stimmgeheimnis brechen** — Verwaltungsseitige E-Mail-Änderung ist ein eigener Vorgang (Modell Adresswechsel): Nachricht mit Einspruchslink an die BISHERIGE Adresse (ohne Versand kein Antrag), Wartefrist aus dem Register (adresswechsel-wartefrist-stunden, Zielwert 72 h), Bestätigung durch einen zweiten Admin, Wirksammachen …
- **#2 · Der „unantastbare" fixe Admin (F-51) ist per E-Mail-Änderung entmachtbar und übernehmbar** — clean_email lehnt jede Adressänderung am fixen Admin ab und verweigert den Wert von DDOE_FIX_ADMIN für jedes andere Konto; zusätzlich prüft Adresswechsel.wirksam_machen dasselbe noch einmal (Tiefenverteidigung) und verwirft den Wechsel. Tests in beide Richtungen.
- **#3 · Entwurfsschleife liest Annahme-Schwelle, Runden und Fristen live aus dem Register** — Fünf Felder in Policy (vorschlag_annahme_anteil, hoechstrunden, review_tage, ueberarbeitung_tage, pruefung_tage; Vorgaben 0.5/3/14/14/7; review/ueberarbeitung ≤ 14 als Obergrenze, ≥ 1) und REGISTER_ZUORDNUNG; Entwurf.fortschreiben, einreichen, zu_den_unterstuetzern, zurueck_an_gruppe_1, …
- **#4 · /uebersicht/ veröffentlicht den Ja/Nein-Stand laufender Abstimmungen** — Laufende Abstimmungen zeigen auf /uebersicht/ nur noch abgegeben/Beteiligung mit „Tendenz verdeckt bis Fristende“; Ja/Nein/Enthaltung und Ergebnisbalken nur für entschiedene Anträge (D-D2 (a)). Test umgedreht und um den Fall nach Fristende ergänzt.
- **#5 · Überarbeitungs-Timeout stellt nie eingereichten Arbeitsstand zur Endabstimmung** — Entwurf.eingereichte_fassung (beim Einreichen gesetzt), vorgelegte_fassung(); _endabstimmung_oeffnen nimmt nur diese Fassung (ohne Einreichung bleibt der Antragstext). Migration 0014 trägt den Wert für bestehende Entwürfe nach. Test: Arbeitsstand nach Rückgabe angehängt, Frist verstrichen → …
- **#6 · Einreich-Quorum zählt alle E1-Rollen statt der für den Antrag gelosten** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#7 · KoRat-Austausch beendet Gruppe 1 aller Anträge und lost keine neue Gruppe** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#8 · Status „in Prüfung“ hält die Beratung ohne jede Frist unbegrenzt offen** — PRUEFUNG-Zweig: (a) keine Gruppe 2 → nach pruefung_tage ab eingereicht_am Vermerk VALIDIERT ohne Beschluss, Audit pruefung_frist_verstrichen, weiter an die Unterstützer; (b) Austauschantrag ohne KoRat-Entscheid → nach pruefung_tage verfristet (neuer Wert Pruefung.KoratEntscheid.VERFRISTET, …
- **#9 · Audit-Kette gabelt sich bei zwei gleichzeitigen anhaengen-Aufrufen (kein Lock)** — AuditEintrag.vorgaenger (unique) in drei Schritten (Migration 0016, Datennachtrag über plattform_core.hashchain.vorgaenger_zuordnen, gegabelte Kette wird gemeldet statt kaschiert); anhaengen liest bei IntegrityError den Kopf neu (bis 3×), Fehler wird außerhalb des inneren atomic gefangen. Tests: …
- **#10 · einreich_stand zählt Expertenräte aller Anträge — Einreichen wird unmöglich** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#11 · Austausch durch Koordinationsrat beendet die Expertenräte fremder Anträge** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#12 · Chat: „Antworten“ ist ohne JavaScript ein toter Knopf — Antworten unmöglich** — „Antworten“ ist ein Link mit ?antwort_auf=<pk>#chat-eingabe; antrag_detail prüft den Beitrag (laufend, sichtbar, derselbe Antrag), belegt verstecktes Feld und Chip serverseitig vor und seedet Alpine mit demselben Wert; nach dem Senden entfernt der htmx-Tausch den Chip, replaceState räumt den …
- **#13 · Übersichtsseite zeigt Ja/Nein laufender Abstimmungen — Startseite verspricht Verdeckung** — Gleicher Fix wie #4: Legende und Balken nur bei nicht laufenden Abstimmungen; laufende Zeilen tragen einen Beteiligungsbalken wie die Kachel, kein „Ergebnis zu …“-Alt-Text.
- **#14 · Gruppe 2 wird nie gelost — Vollzugsbezug ist bei der Ziehung noch unbekannt** — auslosen(antrag, runde, jetzt, gruppen=(1,)) mit Rückführung der Losregel-Indizes auf die tatsächlichen Gruppennummern (Platz, Rolle, Audit, Anzeige); gruppe_2_nachziehen(antrag) — einmal je Antrag, eigene Runde und Anker, Gruppe 1 und frühere Geloste ausgeschlossen — beim Setzen des …
- **#15 · „Ein Konto je Person, mit geprüfter Identität“ — geprüft wird nur die E-Mail, „geprüft“ setzt der Beitrag** — Absatz „Identität“ auf mitgliedschaft.html auf den Ist-Stand gebracht (ein Konto je E-Mail-Adresse, Beitragseingang schaltet frei, Identitätsnachweis nach § 2 Abs 4 geplant); Label Identitaetsstufe.GEPRUEFT jetzt „geprüft (Beitragseingang verbucht)“ mit AlterField-Migration ohne Datenänderung.
- **#16 · „Ein geänderter Wert wirkt nie auf ein laufendes Verfahren“ — vier Gremien-Fristen werden live gelesen** — Kern identisch mit #3: Die vier Gremien-Fristen/Runden kommen aus der eingefrorenen Ordnung, die Registerseite sagt damit für alle Ordnungswerte die Wahrheit. Der Zusatz „wirkt sofort“ für gremien-rollen-dauer-tage/gremien-beschluss-tage, der help_text von Parameter.status und der Satz in …
- **#17 · Mit DEBUG=0 wird kein einziger 500er protokolliert — die Fehlerseite behauptet das Gegenteil** — LOGGING in config/settings.py: django.request auf stderr ohne DEBUG-Filter, root ab WARNING — jeder 500er steht mit Traceback im Render-Log. Die 500-Seite verspricht nur noch, was stimmt.
- **#18 · demo_seed fasst einen Integritätsrats-Beschluss mit Stimmen echter Mitglieder, sobald echte berufen sind** — hervorhebung_beschliessen fasst den Beschluss nur, wenn ausschließlich Demo-Mitglieder (leute) im Integritätsrat sitzen. Test: echtes Mitglied im Rat, demo_seed zweimal → keine Stimme, kein Beschluss in seinem Namen.

*Mittel*

- **#19 · Drossel für Registrierung und Anmeldelink über X-Forwarded-For umgehbar** — klienten_ip liest nie mehr X-Forwarded-For; die Einstellung DDOE_CLIENT_IP_KOPFZEILE nennt die einwertige Proxy-Kopfzeile (Render/Cloudflare: HTTP_CF_CONNECTING_IP), unbesetzt gilt ausschließlich REMOTE_ADDR (gilt auch für die Besuchszählung, die dieselbe Funktion nutzt). Drosselzähler liegen im …
- **#20 · „Beanstanden" ohne Identitäts-/Statusprüfung — ungeprüfte und pausierte Konten posten öffentlichen Text** — beanstanden ruft _mitwirkung_gesperrt auf; ungeprüfte und pausierte Konten erhalten 403, Tests für beide Fälle. melden unverändert.
- **#21 · Unbestätigtes Konto sperrt eine E-Mail-Adresse dauerhaft (Denial-of-Registration)** — Login schickt einem nie bestätigten Konto (inaktiv, ohne Beitritt, nicht ausgeschlossen) einen neuen Bestätigungslink an dieselbe Adresse — gleiche „gesendet“-Seite; die Registrierung überschreibt eine nie bestätigte Zeile mit abgelaufenem Link statt sie abzulehnen (nichts gelöscht, Audit …
- **#22 · Archiv rechnet vergangene Vorschlagsrunden mit dem heutigen Registerwert neu** — Die Auswertung einer Vorschlagsrunde steht jetzt strukturiert am Audit-Ereignis ihrer Entscheidung (Feld auswertung); das Archiv rechnet abgeschlossene Runden damit nach, nur die laufende mit dem Register.
- **#23 · Einreich-Quorum der Gruppe 1 zählt alle gelosten Räte der Partei, nicht die des Antrags** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#24 · Fristanzeige ignoriert Aussetzungen — Seite und Kachel nennen ein falsches Fristende** — _frist_fuer, Kachel-Ring/Resttage, WeicherFilter-Merkmal „ablaufend“ und antrag_detail rechnen mit dem wirksamen Phasenbeginn; für Listen holt _wirksame_beginne alle Aussetzungsabschnitte in einer Abfrage. Tests: Antragsseite und Kachel zeigen Frist + Hemmung.
- **#25 · Zähler und Nenner der Beteiligung folgen verschiedenen Stichtagen (§ 4 Abs 4 lit a)** — Neue Felder geprueft_seit und status_seit; Mitglied.identitaetsstufe_setzen und status_setzen führen sie nach (Verwaltung und beitrag_verbuchen nutzen sie); ist_stimmberechtigt prüft Freischaltung und Status gegen den Stichtag, stimmberechtigte_zaehlen ruft dieselbe Methode. Datenmigration trägt …
- **#26 · Bewerbung kann während der laufenden Wahl zurückgezogen werden — Stimmen verschwinden** — bewerbung_zurueckziehen schreibt fort und weist außerhalb von Unterstützung/Beratung mit Fehlermeldung ab, Bewerbung bleibt zurueckgezogen=False (Test in test_kandidatur.py). Der _beteiligung-Filter liegt in verfahren/views.py (A1) — konkreter Vorschlag in der A2-eigene Helfer …
- **#27 · Zurückgenommene Personenwahl-Zustimmung wird hart gelöscht, Audit unterscheidet nicht** — Zurückgenommene Zustimmungen und zurückgezogene Unterstützungen werden gestempelt statt gelöscht (zurueckgenommen_am / zurueckgezogen_am), jede Richtung mit eigenem Audit-Typ ohne Mitgliedsbezug; alle Zählstellen, der Export und die Auszählung zählen nur gültige.
- **#28 · „Antworten" im Chat gibt es nur mit JavaScript — ohne JS kein Faden, kein Gespräch** — Gemeinsam mit #12 behoben (derselbe Mangel, derselbe Fix): Link statt type=button, serverseitige Vorbelegung, Chip ohne x-cloak bei Vorgabe, ×-Link zurück auf die Seite ohne Parameter.
- **#29 · verify/nachrechnen.py kennt keine Personenwahl und liefert dafür ein falsches Ergebnis** — verify/nachrechnen.py verzweigt nach art: personenwahl_nachrechnen spiegelt tally (zurückgezogene ausgeschlossen, Reihung Zustimmungen dann Einreichreihenfolge, Beteiligung aus zählenden Zustimmungen, Mindestbeteiligung); unbekannte art und doppelte Zustimmung → SystemExit; Schlusszeile ohne …
- **#30 · Angezeigte Frist ignoriert die Hemmung durch Aussetzungen** — Fristen auf Antragsseite und Kacheln rechnen mit dem wirksamen Phasenbeginn; die Antragsseite zeigt ein Band „Ausgesetzt seit … durch Beschluss IR-…“; wer während einer Aussetzung stimmt, bekommt eine eigene Meldung.
- **#31 · Aussetzung ist nicht auf Abstimmung/Vollzug beschränkt, Etikett dann falsch** — aussetzungs_gegenstand(antrag): nur ABSTIMMUNG (Phase Abstimmung) oder VOLLZUG (Phase angenommen); aussetzung_wirkung vermerkt sonst „Ohne Wirkung“; integritaet_beschluss weist das Anlegen in anderen Phasen ab (nach fortschreiben); vollzug_fortschreiben wirft VollzugAusgesetzt bei laufender …
- **#32 · Stichtag der Stimmberechtigung ist das UTC-Datum, nicht das Wiener Datum** — Antrag.stimmberechtigung_stichtag wird beim Übergang in die Abstimmung im Wiener Kalender gesetzt (Migration); Zählung und Einzelprüfung lesen denselben Tag.
- **#33 · Entwurfsschleife rechnet mit dem Aufrufzeitpunkt statt dem Fristzeitpunkt** — Entwurf.fortschreiben rechnet mit wirksam = review_frist bzw. ueberarbeitung_frist (Phasenbeginn, Stichtag, Überarbeitungsfrist, Audit wirksam_ab). Neuer Befehl verfahren_fortschreiben (idempotent, alle laufenden Verfahren, Beschlüsse, Aussetzungen, Parametertests) für einen Cron; …
- **#34 · Werkstatt-Handlungen bleiben nach Beratungsende möglich und sperren den Abstimmungs-Chat** — fenster_aktion bindet jede schreibende Handlung an Phase BERATUNG; Entwurf.einreichen prüft die Phase selbst (gibt False zurück, Audit vorschlag_einreichung_verworfen); Formulare in fenster.html an in_beratung gekoppelt. Test: nach Phasenwechsel keine Fassung, kein Beitrag, kein Bezug, kein …
- **#35 · Bewerbungsrückzug während der Abstimmung löscht Stimmen aus der Beteiligung** — Gleicher Fix wie #26: Rückzug nur bis Abstimmungsbeginn (§ 7 Abs 1) mit Fehlermeldung.
- **#36 · verify/nachrechnen.py rechnet Personenwahlen still falsch nach** — Gleicher Fix wie #29.
- **#37 · Gruppe 2 wird im Echtbetrieb nie gelost — Entwurf entsteht erst in der Beratung** — Derselbe Umbau wie #14: Gruppe 2 wird nachgelost, sobald der Vollzugsbezug feststeht; austausch_wirkung zieht damit nur noch Gruppe 1 nach (bisher hätte es bei Vollzugsbezug eine zweite Gruppe 1 und eine Gruppe 2 gezogen). antrag.html:224 (A1) bleibt richtig — in
- **#38 · Rolle ohne Eindeutigkeit: Doppelberufung zählt doppelt im Quorum und § 6 Abs 3** — Rolle.personen(rollen) zählt Menschen; Nenner in aktive_rollen, _integritaetsrat_beschlussfaehig, Anzeige „besetzt“ (Integritätsrat, Koordinationsrat); rollen_aktion weist eine zweite aktive parteiweite Rolle derselben Person ab (geloste bleiben unberührt). Tests: Doppelberufung abgewiesen; zwei …
- **#39 *(teilweise)* · Kategorie.pfad_kurz löst je gerenderter Zeile eine Abfrage pro Baumebene aus** — Die Lebensbereiche werden mit ihrer Elternkette in einer Abfrage vorgeladen (Parlament, Suche, Antragsseite); ein Abfragezähl-Test hält die Zahl unabhängig von der Zahl der Anträge. Ein gespeichertes Pfad-Feld am Lebensbereich bleibt als Verbesserung offen.
- **#40 *(teilweise)* · Feed und Kacheln zählen je Antrag einzeln, ohne Obergrenze, Gäste laden alles doppelt** — Unterstützungen, Beiträge, Stimmen und Zustimmungen werden je Seite in einer Abfrage gezählt, das Parlament lädt die laufenden Verfahren einmal für alle Bereiche, Gäste materialisieren kein Stimmregister. Die Deckelung der neutralen Gruppen ist eine Produktentscheidung (Fahrtenbuch D-B1a) und …
- **#41 · audit_spur lädt bei jedem Antragsaufruf das gesamte Audit-Log und filtert in Python** — Die Audit-Spur eines Antrags wird in der Datenbank gefiltert; Ausdrucksindex audit_antrag_idx auf ereignis→antrag (Migration).
- **#42 · Chat-Faden und Archiv laden alle Beiträge eines Antrags dreimal, ohne Seitenteilung** — faden_fenster(): jüngste n Wurzelbeiträge samt Antworten (Register chat-faden-wurzeln, Rückfall 50), ältere über ?ab=<pk> als Link bzw. hx-get zum Voranhängen; Abstimmungs-Chat: vorderste der Reihung, weitere dahinter; Zustimmungen/Ablehnungen per annotate statt Prefetch (auch abstimmung_stand, …
- **#43 · Übersicht: eine Stimm-Aggregation je Antrag, über alle je entschiedenen Anträge** — Eine Gruppierungsabfrage über alle gezeigten Anträge statt einer je Antrag; Liste begrenzt auf laufende plus jüngste N entschiedene über zahl("uebersicht-abstimmungen", 20) mit Verweis auf Umsetzungsregister und Parlament. ERSTBESTAND-Eintrag liegt in parameter/models.py (fremde Datei) — als …
- **#44 · Fachliste: zwei Abfragen je Eintrag für die Unvereinbarkeit, auch im Lostopf** — unvereinbarkeiten_laden() (zwei Mengen), unvereinbar_fuer(mitglied_id, …) mit denselben Texten, unvereinbar(mitglied) als Hülle; Fachliste-Ansicht und lostopf_der_fachliste nutzen die Mengen; als_kandidat liest die Fachgebiete aus dem Prefetch. Test: Abfragezahl der Liste und des Lostopfs wächst …
- **#45 · Zwölf Registerwerte liest kein Code — die Registerseite behauptet das Gegenteil** — Jede Stellgröße des Registers wird an ihrer Stelle gelesen (Kacheln, Suche, Fächer, Ähnlichkeit, Filterprofile, Kategorien je Antrag, Bearbeitungsfenster, KI-Antwortlänge, Anstoß-Drossel); der Wächter parameter/test_register.py schlägt an, sobald ein Schlüssel keinen Leser mehr hat.
- **#46 · Abstimmungs-Chat: Absatzwahl per x-cloak versteckt — Kritik ohne JS nie einreichbar** — Regel html:not(.js) .kritikwahl [x-cloak]{display:revert!important} nach der x-cloak-Regel — Absatzwahl und Hinweis stehen ohne JavaScript; Unit-Test auf die Regel, Bildschirmtest ohne JS reicht Kritik mit Absatz 2 ein.
- **#47 · 403.html greift bei CSRF-Fehlern nicht — Django zeigt seine englische Rohseite** — Neue Vorlage 403_csrf.html (Djangos fester Name, keine Einstellung nötig) mit Leiste, Erklärung des CSRF-Falls und Weg zurück; Kommentar in 403.html berichtigt. Test mit Client(enforce_csrf_checks=True).
- **#48 · Hauptnavigation zwischen 760 und 1180 px abgeschnitten — kein Burger, kein Umbruch** — Burger und Panel für Mitglieder unter 1024 px, für Gäste (Klasse leiste gast) unter 1180 px — deren rechter Block ist breiter, Messung bei 1024/1100 px bestätigte den Hinweis des Kurzformen „Umsetzung“/„Werkstatt“ zwischen 1024 und 1279 px; overflow-x:auto statt hidden; Panel-Regeln außerhalb …
- **#49 · Dunkles Thema: Beratungs-Badge und „✓ Unterstützt“ mit 1,57:1 Kontrast unlesbar** — Token --on-deep (hell #E9E4D8, dunkel #0C151E) für Badge Beratung, .knopf:hover, .knopf.gewaehlt sowie die übersehenen .btn-linie:hover, .fluss .punkt, .schrittleiste .punkt.aktiv; Unit-Test verbietet Text auf --deep ohne --on-deep/--on-gold; Kontrast-Bildschirmtest hell/dunkel ≥ 4,5:1.
- **#50 · Eingefahrene Profil-Leiste: unsichtbare Tab-Stopps, Enter wechselt unbemerkt das Profil** — .filter-leiste.zu .innen mit visibility:hidden und verzögertem Umschalten der Sichtbarkeit, dazu :inert="!offen" auf .innen; Bildschirmtest: nach localStorage „zu“ landet kein Tab-Stopp in der Leiste, der Griff bleibt.
- **#51 · „Ihre Gemeinde stimmt über Gemeindesachen ab“ — es gibt keine regionale Stimmberechtigung** — Absatz „Ihre Region“ auf mitgliedschaft.html im Wortlaut des Keine Codeänderung; Katalog über NEUE_TEXTE_B.md.
- **#52 · 500-Seite: „Er ist protokolliert und wird angesehen“ — in Produktion wird der Fehler nirgends protokolliert** — Satz „Er ist protokolliert und wird angesehen“ aus 500.html gestrichen (Alternative des Test, dass „protokolliert“ nicht mehr vorkommt.
- **#53 · Beanstandung: „die Zukunftswerkstatt rechnet den Punkt nach“ — nichts und niemand tut das** — Flash, Hilfetext und Zukunftswerkstatt-Seite versprechen keinen Korrekturlauf mehr („noch nicht gebaut“); Test in test_oeffentliche_texte.py. Der Korrekturlauf selbst ist laut
- **#54 · Rollenmatrix und Regelverzeichnis sind seit 0.44 veraltet und widersprechen sich selbst** — wie_hinein von Expertenrat Gruppe 1 und 2 auf den Stand 0.44 (Fachliste durch die Verwaltung, Auslosung je Antrag zu Beratungsbeginn, Gruppe 2 mitgelost, wenn der Vollzugsbezug zur Ziehung gesetzt ist, sonst Verwaltung), Koordinationsrat-Einschraenkung auf eine Faktenbasis und die Berichte …
- **#55 · Mitgliedschaft, Station 3: Zukunftswerkstatt „rechnet durch, welche Gesetze berührt wären“ — kein Lauf tut das** — Station 3 im Wortlaut des Zusätzlich die Karte „Die Zukunftswerkstatt“ weiter unten als Zielbild gekennzeichnet — über den Vorschlag hinaus, in md vermerkt.
- **#56 · Zukunftswerkstatt-Seite: Unterstützer-Schleife stehe nicht im Satzungsentwurf 2.5 — sie steht in § 5 Abs 12 und 13** — Hinweis unter dem Ablauf ersetzt durch „Alle sechs Schritte entsprechen dem Satzungsentwurf 2.5 (Schritt 4: § 5 Abs 12 und 13). Geltend ist bis zum Beschluss der Mitglieder die Satzung 1.3.“
- **#57 · hashchain.py verspricht einen „täglich veröffentlichten Kettenkopf“ — es gibt keine Veröffentlichung** — Docstring von hashchain.py auf den Ist-Stand (Weg 1 des extern veröffentlichter Kopf ist geplant (F-22), nicht gebaut; Unterstützungen werden bisher nicht protokolliert. Wächter-Test gegen das alte Versprechen.
- **#58 · 14 handgeschriebene .po-Einträge sind syntaktisch ungültig — 14 Absätze bleiben englisch-deutsch** — Die 14 Bloecke mit rohen Zeilenumbruechen in gueltige .po-Syntax gebracht (msgid leer plus je eine Zeile mit maskiertem Zeilenumbruch), .mo neu geschrieben; Test rendert /, /rollen/, /regeln/, /gremien/fachliste/, /gremien/beschluesse/ und die 404-Seite auf Englisch und schliesst die deutschen …
- **#59 · po_pruefen.py liest ungültige Katalogzeilen stumm, meldet Grün und schreibt falsche .mo** — tools/po_pruefen.py: lesen(pfad) prueft jede Zeile gegen die Syntax, sammelt SYNTAX-Fehler mit Zeilennummer (KatalogFehler), pruefen() gibt Exit 1 und --mo schreibt dann nichts; test_design_system.py und test_vorlagen.py::msgids() nutzen den strengen Leser. tests/test_katalog.py ist der …
- **#60 · 21 Texte der Beschluss-/Aussetzungs-Views (0.43/0.44) fehlen im Katalog** — Alle fehlenden Texte der Beschluss-, Aussetzungs-, Regelpruefungs- und Parametertest-Views und ihrer Vorlagen nachgetragen (insgesamt 198 Eintraege, weil der 0.45-Stand mit Koordinationsrat und Parameterverfahren ebenfalls ohne Katalog war); Kurzfassung a von n noetigen Stimmen und Frist …
- **#61 · Auslosungs-Hinweis, Fristring-aria-label und Bot-Schutz-Bild ohne Katalogeintrag** — Auslosungshinweis, Link Die Auslosung ansehen, Fristring-Schluessel %(wert)s %% der Frist verstrichen und Sicherheitsaufgabe als Bild im Katalog; Test rendert _ring.html auf Englisch und prueft die kompilierte .mo.
- **#62 · „Passt alles"-Auswertungszeilen: Katalog hat „%" statt „%%" — Übersetzung greift nie** — Beide Passt-alles-Schluessel enden in msgid und msgstr auf %% statt %; Test gegen die .mo.
- **#63 · Hilfetext der Wohnsitz-Gemeinde: ein Leerzeichen in der .po macht die Übersetzung tot** — Leerzeichen vor dem Punkt in msgid und msgstr des Gemeinde-Hilfetexts entfernt; Test gegen die .mo und Laufzeitprobe /mitglied-werden/ auf Englisch.
- **#64 · TextChoices-Beschriftungen ohne gettext_lazy: „Land/Bezirk/Gemeinde" u. a. deutsch auf englischen Seiten** — Alle Auswahl-Beschriftungen der Modelle sind übersetzbar (gettext_lazy), der Archiv-Export schreibt sie über DjangoJSONEncoder.
- **#65 · Wächter des Abstimmungs-Chat-Blocks kippt nach 14 Tagen — jeder Deploy danach legt den Demo-Antrag neu an** — Wächter des Abstimmungs-Chat-Blocks hängt am Titel (TESTLAUF_TITEL) statt am vergänglichen Status. Test: demo_seed, Frist verstreichen, fortschreiben, demo_seed erneut → genau ein Antrag.
- **#66 · Drossel für Anmeldelinks und Registrierung ist per X-Forwarded-For frei wählbar** — Wie #19 (DDOE_CLIENT_IP_KOPFZEILE, nie XFF[0], Zähler in der Datenbank); Test: ohne konfigurierte Kopfzeile wird ein Request mit gesetztem HTTP_CF_CONNECTING_IP auf REMOTE_ADDR gedrosselt, mit Konfiguration zählt die Kopfzeile. Einmal-Kennung der Rechenaufgabe siehe #68.
- **#67 · Anstoß-Widget ohne Anmeldung hat nur eine Sitzungs-Drossel — ohne Cookie ist sie wirkungslos** — anstoss/views.py ruft drossel_zuviel(request, 'anstoss', limit=tagesgrenze) unmittelbar vor Anstoss.objects.create — leere und Honigtopf-POSTs verbrauchen kein Budget; Tests: 21 POSTs ohne Cookie → der 21. liefert warte, zwei POSTs ohne Cookie innerhalb 60 s werden beide gespeichert (Bauart …

*Niedrig*

- **#68 · Rechen-Captcha trivial lösbar — die Aufgabe steht lesbar im signierten Token der Seite** — Die Rechenaufgabe liegt in der Sitzung (bis zu drei offene je Sitzung), das versteckte Feld trägt nur eine zufällige Kennung; nach einem Formularfehler wird dieselbe Aufgabe erneut gezeigt, eine gelöste Aufgabe ist verbraucht (kein zweites Absenden). Modul- und Funktions-Docstrings ehrlich …
- **#69 · Registereintrag chat-bearbeitungsfenster-minuten hat keine Wirkung im Code** — Kommentar.bearbeitungsfenster_minuten() liest chat-bearbeitungsfenster-minuten; darf_bearbeiten und der Hinweistext im Chat nutzen denselben Wert.
- **#70 · Neutrale Grundordnung sortiert nach Phasenbeginn, offengelegt ist „Phase und Frist"** — Neutraler Sortierschlüssel (Phase, Fristende) in _weicherfilter_reihen und in den neutralen Gruppen; Test mit zwei Ordnungen (14 und 7 Tage): früheres Fristende zuerst.
- **#71 · Kennzahlen-Export und Übersicht rechnen Personenwahlen mit 0 Stimmen** — Gemeinsamer Helfer parameter.kennzahlen.abgegeben_je_antrag zählt bei Personenwahlen die Pseudonyme mit Zustimmung zu einer nicht zurückgezogenen Bewerbung; votes.turnout_mean und die Übersicht nutzen ihn; Personenwahlen erscheinen ohne Ja/Nein-Balken, mit Gewählt-Zeile, Badge weiter nach Phase …
- **#72 · select_for_update().count() sperrt nichts — Beschlussnummer nicht abgesichert** — GremienBeschluss.save ohne wirkungsloses select_for_update: _naechste_nummer (höchste vergebene + 1), bis zu drei Versuche bei IntegrityError außerhalb des inneren Savepoints, ehrliche Docstring. Test simuliert das Wettrennen (Konkurrent nimmt die Nummer zwischen Zählen und Schreiben).
- **#73 · Beschlussnummer nimmt das UTC-Jahr statt des Wiener Jahres** — Jahr der Beschlussnummer aus timezone.localtime(angelegt_am). Test: 31.12. 23:40 UTC → KR-2027-01.
- **#74 · Rückwärtsmigration 0003 löscht alle Systembeiträge samt Voten der Unterstützer** — Rückwärtsfunktion von gremien/0003 durch RunPython.noop ersetzt, Begründung in der Migrations-Docstring; Wächter-Test prüft reverse_code.
- **#75 · Hash-Kette versiegelt den Zeitstempel nicht — zeit ist unbemerkt änderbar** — anhaengen schreibt den Zeitpunkt als „zeit“ ins versiegelte Ereignis (Spalte zeit trägt denselben Wert); alte Einträge bleiben prüfbar. Test: Manipulation der Zeit im Ereignis wird erkannt.
- **#76 · Beschlussnummer nimmt das UTC-Jahr, die Anzeige das Wiener Datum** — Identisch mit #73 (Wiener Jahr); vergebene Nummern bleiben unverändert.
- **#77 · Beschlussliste: bis zu drei Abfragen je Beschluss für Quorum und Antrag** — quoren_fuer(beschluesse) rechnet den Nenner je Seite mit einer Abfrage (gleiche Regel wie aktive_rollen); auswertung(aktive=None) nimmt ihn entgegen, abschliessen bleibt unverändert; beide Listen mit select_related("antrag"). Test: Abfragezahl der öffentlichen Liste konstant, Nenner stimmen mit …
- **#78 · /parameter/ und parameter.json führen bei jedem Aufruf 36 Idempotenz-Abfragen aus** — erstbestand_sicherstellen() holt den Bestand mit in_bulk in einer Abfrage und schreibt nur Fehlendes oder Abweichendes (get_or_create nur fuer Fehlende, gegen Rennen); der Aufruf in den Lese-Views bleibt wie vom Tests: genau eine Abfrage bei vollstaendigem Bestand, keine Einzelabfragen je …
- **#79 · Meine Gespräche: dieselbe unbegrenzte Liste wird je Anfrage dreimal gebaut** — /gespraeche/ lädt einmal (grenze=None), zählt daraus, schneidet auf den Registerwert und puffert den Zähler an der Anfrage; der Kontextprozessor nimmt ihn. Test: genau eine Antworten-Abfrage je Aufruf. Der langfristige SQL-Zähler für die übrigen Seiten ist als eigener Schritt notiert.
- **#80 · Auslosung: Fachliste zweimal vollständig geladen, Rollen-Prefetch ohne Verwendung** — Auslosungsseite lädt nur die Namen der gezogenen Schlüssel; wirkungslose values_list-Abfrage und Rollen-Prefetch gestrichen, Kontextvariable namen entfällt. Test: Abfragezahl unabhängig von der Fachlistengröße, Fachliste nur mit IN (…).
- **#81 · Antrag, Beschluss, Fachliste ohne Index auf den Filter- und Sortierfeldern** — Antrag.Meta.indexes (phase+phase_beginn, Teilindex hervorgehoben=True), GremienBeschluss (status+frist), Fachliste (gestrichen_am); eigene Migrationen verfahren/0019 und gremien/0016. Test per Datenbank-Introspektion.
- **#82 · Beitrags-Anker „#n“ und leerer Stern unter 2:1 Kontrast (Link bzw. Umschalter)** — .blase-anker in --muted (Hover --ink); --stern-aus hell #7E8C96 (≥ 3,06:1 auf Weiß, surface-2 und bg), dunkel #7B8790 (≥ 4,1:1); Unit- und Kontrast-Bildschirmtest.
- **#83 · Sprachwechsel verliert Abfrageparameter (Fächer-Ast, Suche, Filter)** — _sprache.html gibt request.get_full_path als next mit; Test: Fächer-Ast und Suche stehen im next-Feld, set_language leitet dorthin um.
- **#84 · 500-Seite: lang="de" bei englischem Text** — 500.html liest die Sprache über {% get_current_language as SPRACHE %}; Test rendert ohne Kontext unter en und de und prüft lang-Attribut samt Überschrift.
- **#85 · Anstoß-Textfeld und mehrere Verwaltungsfelder ohne Label oder aria-label** — Anstoß-Textfeld, Verwaltungs-, Parameter-, Mandatar- und Gremienformulare tragen Labels oder aria-label.
- **#86 · Startseiten-Diagramm nennt „höchstens 3 Runden“ fest, obwohl der Wert aus dem Register kommt** — index.html nennt die Rundenzahl per blocktranslate aus fristen.runden; Test mit gremien-hoechstrunden = 2. Neuer Text in NEUE_TEXTE.
- **#87 · Mandatare-Seite: „die Wahl unserer Kandidaten läuft bereits“ auch dann, wenn keine Kandidatur läuft** — Satz „die Wahl unserer Kandidaten läuft bereits“ steht nur noch unter {% if kandidaturen %}; sonst neuer wahrer Satz. Test ohne Kandidatur.
- **#88 · Markdown-Export eines Antrags: zwölf Beschriftungen ohne Katalogeintrag — halb englisch, halb deutsch** — Die zwoelf Beschriftungen des Markdown-Exports (Phase, Eingebracht, Unterstuetzungen, Fassung, Beitraege, Auswertung, zurueckgegeben, Absatz, Antwort auf, Runde, Entwurfsfassung, Pruefung) im Katalog; Test laedt den Export auf Englisch und schliesst deutsche Beschriftungen aus. …
- **#89 · „ueber" statt „über" in zwei Fähigkeitstiteln der Rollenübersicht** — Elf Titel in rollen.py ohne ue/ae/oe (nicht nur die zwei genannten: auch Wuensche, beraet, prueft, Fuer, Zurueckgegebenen, moegliche); test_vorlagen.py prueft Sprachregeln und Ersatzschreibungen ueber eine Wortliste (kein Silbenmuster) auch fuer die Datentexte aus rollen.py, regelwerk.py und …
- **#90 *(teilweise)* · /rollen/, /regeln/ und /parameter/: englische Überschriften über rein deutschen Inhalten aus plattform_core** — Die Texte der Rollenmatrix, des Regelverzeichnisses und des Erstbestands sind als übersetzbar markiert und laufen durch den Katalog; die langen Einträge selbst (≈ 480) liegen noch auf Deutsch vor — die Seiten sagen das in anderer Sprache offen. Übersetzung ist Datenpflege und folgt.
- **#91 *(teilweise)* · Verwaltungs-Views: rund 45 Meldungen und Formularbeschriftungen ohne gettext** — Alle Meldungen und Formularbeschriftungen der Mitgliederverwaltung sind übersetzbar; ein Wächter-Test hält es. Die Verwaltungsansichten der Mandatare und Rollen folgen mit ihrer nächsten Änderung.
- **#92 · Rund 60 veraltete Katalogeinträge — msgids, die es im Code nicht mehr gibt** — 84 tote Eintraege entfernt (Abgleich gegen den 0.45-Stand, daher mehr als rund 60); jeder vorher per Suche ueber Vorlagen, Python, .txt, .js und .yaml gegengeprueft, Filterargumente und Variablenform von translate im Abgleich beruecksichtigt (noch nie lebt). …
- **#93 · README (englische Zusammenfassung) nennt die Plattform „public prototype"** — README: A public prototype is live -> The platform is public and in its alpha phase. (erster Lauf).
- **#94 · /gesund/ prüft die Datenbank nicht — Render hält einen Dienst ohne DB für gesund** — /gesund/ fuehrt SELECT 1 aus und antwortet ohne Datenbank mit 503 (config/gesund.py, vor den App-Routen eingehaengt); Test mit werfendem Cursor. (erster Lauf).
- **#95 · render.yaml (Neuaufbau) deployt jeden Push, unabhängig von der CI** — render.yaml autoDeployTrigger off (CI-Hook bleibt der Weg), Partner-Muster docs/partner/instanz/render.yaml checksPass, Satz in docs/BETRIEB-RENDER.md. (erster Lauf).
- **#96 · ruff und Produktionsabhängigkeiten ohne Obergrenze — die CI wird beim nächsten Release wieder stumm rot** — Obergrenzen in pyproject.toml (ruff <0.17, gunicorn <27, whitenoise <7, psycopg <4, requests <3, PyYAML <7, segno <2); Job nicht_ausgerollt meldet eine rote Pruefung auf main sichtbar, CI-Abzeichen in der README. Die vom (erster Lauf).
- **#97 · CI führt `manage.py check` ohne `--deploy` aus — die Definition of Done verlangt `--deploy`** — Eigener CI-Schritt check --deploy --fail-level WARNING mit DDOE_DEBUG=0, Schluessel aus github.sha, ALLOWED_HOSTS und whitenoise; security.W021 begruendet in SILENCED_SYSTEM_CHECKS. (erster Lauf).
- **#98 · Statische Dateien laufen mit max-age=60 — ohne Manifest gibt es keine langen Cache-Zeiten** — CompressedManifestStaticFilesStorage; CI-Schritt collectstatic mit DDOE_STATIK=whitenoise; Test rendert base.html mit Manifest-Speicher. (erster Lauf).
- **#99 · KI-Steckplatz: Abbruch während des Lesens der Antwort wird nicht abgefangen — 500 statt Archiv-Eintrag** — Zweite except-Klausel in ki/anbieter.py faengt URLError, OSError, http.client.HTTPException und ValueError - jeder Netz- und Protokollfehler wird AnbieterFehler und steht im Archiv. Tests: read() wirft IncompleteRead -> SteckplatzStumm und KILauf erfolgreich=False; RemoteDisconnected aus urlopen …

### Bewusst nicht behoben
NICHT_*Hoch*

- **#0 · Gespeichertes XSS auf der öffentlichen Übersichtsseite über den Antragstitel (SVG-Balken)** — html.escape statt xml.sax.saxutils.escape in plattform_core/diagramme.py (aria-label, title, text); Hypothesis-Eigenschaftstest und View-Test ueber /uebersicht/ mit einem Titel, der ein onload-Attribut einschleusen will. CSP bewusst nicht , in md festgehalten. (erster Lauf).
- **#1 · Admin kann per E-Mail-Änderung jedes Konto übernehmen und das Stimmgeheimnis brechen** — Verwaltungsseitige E-Mail-Änderung ist ein eigener Vorgang (Modell Adresswechsel): Nachricht mit Einspruchslink an die BISHERIGE Adresse (ohne Versand kein Antrag), Wartefrist aus dem Register (adresswechsel-wartefrist-stunden, Zielwert 72 h), Bestätigung durch einen zweiten Admin, Wirksammachen …
- **#2 · Der „unantastbare" fixe Admin (F-51) ist per E-Mail-Änderung entmachtbar und übernehmbar** — clean_email lehnt jede Adressänderung am fixen Admin ab und verweigert den Wert von DDOE_FIX_ADMIN für jedes andere Konto; zusätzlich prüft Adresswechsel.wirksam_machen dasselbe noch einmal (Tiefenverteidigung) und verwirft den Wechsel. Tests in beide Richtungen.
- **#3 · Entwurfsschleife liest Annahme-Schwelle, Runden und Fristen live aus dem Register** — Fünf Felder in Policy (vorschlag_annahme_anteil, hoechstrunden, review_tage, ueberarbeitung_tage, pruefung_tage; Vorgaben 0.5/3/14/14/7; review/ueberarbeitung ≤ 14 als Obergrenze, ≥ 1) und REGISTER_ZUORDNUNG; Entwurf.fortschreiben, einreichen, zu_den_unterstuetzern, zurueck_an_gruppe_1, …
- **#4 · /uebersicht/ veröffentlicht den Ja/Nein-Stand laufender Abstimmungen** — Laufende Abstimmungen zeigen auf /uebersicht/ nur noch abgegeben/Beteiligung mit „Tendenz verdeckt bis Fristende“; Ja/Nein/Enthaltung und Ergebnisbalken nur für entschiedene Anträge (D-D2 (a)). Test umgedreht und um den Fall nach Fristende ergänzt.
- **#5 · Überarbeitungs-Timeout stellt nie eingereichten Arbeitsstand zur Endabstimmung** — Entwurf.eingereichte_fassung (beim Einreichen gesetzt), vorgelegte_fassung(); _endabstimmung_oeffnen nimmt nur diese Fassung (ohne Einreichung bleibt der Antragstext). Migration 0014 trägt den Wert für bestehende Entwürfe nach. Test: Arbeitsstand nach Rückgabe angehängt, Frist verstrichen → …
- **#6 · Einreich-Quorum zählt alle E1-Rollen statt der für den Antrag gelosten** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#7 · KoRat-Austausch beendet Gruppe 1 aller Anträge und lost keine neue Gruppe** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#8 · Status „in Prüfung“ hält die Beratung ohne jede Frist unbegrenzt offen** — PRUEFUNG-Zweig: (a) keine Gruppe 2 → nach pruefung_tage ab eingereicht_am Vermerk VALIDIERT ohne Beschluss, Audit pruefung_frist_verstrichen, weiter an die Unterstützer; (b) Austauschantrag ohne KoRat-Entscheid → nach pruefung_tage verfristet (neuer Wert Pruefung.KoratEntscheid.VERFRISTET, …
- **#9 · Audit-Kette gabelt sich bei zwei gleichzeitigen anhaengen-Aufrufen (kein Lock)** — AuditEintrag.vorgaenger (unique) in drei Schritten (Migration 0016, Datennachtrag über plattform_core.hashchain.vorgaenger_zuordnen, gegabelte Kette wird gemeldet statt kaschiert); anhaengen liest bei IntegrityError den Kopf neu (bis 3×), Fehler wird außerhalb des inneren atomic gefangen. Tests: …
- **#10 · einreich_stand zählt Expertenräte aller Anträge — Einreichen wird unmöglich** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#11 · Austausch durch Koordinationsrat beendet die Expertenräte fremder Anträge** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#12 · Chat: „Antworten“ ist ohne JavaScript ein toter Knopf — Antworten unmöglich** — „Antworten“ ist ein Link mit ?antwort_auf=<pk>#chat-eingabe; antrag_detail prüft den Beitrag (laufend, sichtbar, derselbe Antrag), belegt verstecktes Feld und Chip serverseitig vor und seedet Alpine mit demselben Wert; nach dem Senden entfernt der htmx-Tausch den Chip, replaceState räumt den …
- **#13 · Übersichtsseite zeigt Ja/Nein laufender Abstimmungen — Startseite verspricht Verdeckung** — Gleicher Fix wie #4: Legende und Balken nur bei nicht laufenden Abstimmungen; laufende Zeilen tragen einen Beteiligungsbalken wie die Kachel, kein „Ergebnis zu …“-Alt-Text.
- **#14 · Gruppe 2 wird nie gelost — Vollzugsbezug ist bei der Ziehung noch unbekannt** — auslosen(antrag, runde, jetzt, gruppen=(1,)) mit Rückführung der Losregel-Indizes auf die tatsächlichen Gruppennummern (Platz, Rolle, Audit, Anzeige); gruppe_2_nachziehen(antrag) — einmal je Antrag, eigene Runde und Anker, Gruppe 1 und frühere Geloste ausgeschlossen — beim Setzen des …
- **#15 · „Ein Konto je Person, mit geprüfter Identität“ — geprüft wird nur die E-Mail, „geprüft“ setzt der Beitrag** — Absatz „Identität“ auf mitgliedschaft.html auf den Ist-Stand gebracht (ein Konto je E-Mail-Adresse, Beitragseingang schaltet frei, Identitätsnachweis nach § 2 Abs 4 geplant); Label Identitaetsstufe.GEPRUEFT jetzt „geprüft (Beitragseingang verbucht)“ mit AlterField-Migration ohne Datenänderung.
- **#16 · „Ein geänderter Wert wirkt nie auf ein laufendes Verfahren“ — vier Gremien-Fristen werden live gelesen** — Kern identisch mit #3: Die vier Gremien-Fristen/Runden kommen aus der eingefrorenen Ordnung, die Registerseite sagt damit für alle Ordnungswerte die Wahrheit. Der Zusatz „wirkt sofort“ für gremien-rollen-dauer-tage/gremien-beschluss-tage, der help_text von Parameter.status und der Satz in …
- **#17 · Mit DEBUG=0 wird kein einziger 500er protokolliert — die Fehlerseite behauptet das Gegenteil** — LOGGING in config/settings.py: django.request auf stderr ohne DEBUG-Filter, root ab WARNING — jeder 500er steht mit Traceback im Render-Log. Die 500-Seite verspricht nur noch, was stimmt.
- **#18 · demo_seed fasst einen Integritätsrats-Beschluss mit Stimmen echter Mitglieder, sobald echte berufen sind** — hervorhebung_beschliessen fasst den Beschluss nur, wenn ausschließlich Demo-Mitglieder (leute) im Integritätsrat sitzen. Test: echtes Mitglied im Rat, demo_seed zweimal → keine Stimme, kein Beschluss in seinem Namen.

*Mittel*

- **#19 · Drossel für Registrierung und Anmeldelink über X-Forwarded-For umgehbar** — klienten_ip liest nie mehr X-Forwarded-For; die Einstellung DDOE_CLIENT_IP_KOPFZEILE nennt die einwertige Proxy-Kopfzeile (Render/Cloudflare: HTTP_CF_CONNECTING_IP), unbesetzt gilt ausschließlich REMOTE_ADDR (gilt auch für die Besuchszählung, die dieselbe Funktion nutzt). Drosselzähler liegen im …
- **#20 · „Beanstanden" ohne Identitäts-/Statusprüfung — ungeprüfte und pausierte Konten posten öffentlichen Text** — beanstanden ruft _mitwirkung_gesperrt auf; ungeprüfte und pausierte Konten erhalten 403, Tests für beide Fälle. melden unverändert.
- **#21 · Unbestätigtes Konto sperrt eine E-Mail-Adresse dauerhaft (Denial-of-Registration)** — Login schickt einem nie bestätigten Konto (inaktiv, ohne Beitritt, nicht ausgeschlossen) einen neuen Bestätigungslink an dieselbe Adresse — gleiche „gesendet“-Seite; die Registrierung überschreibt eine nie bestätigte Zeile mit abgelaufenem Link statt sie abzulehnen (nichts gelöscht, Audit …
- **#22 · Archiv rechnet vergangene Vorschlagsrunden mit dem heutigen Registerwert neu** — Die Auswertung einer Vorschlagsrunde steht jetzt strukturiert am Audit-Ereignis ihrer Entscheidung (Feld auswertung); das Archiv rechnet abgeschlossene Runden damit nach, nur die laufende mit dem Register.
- **#23 · Einreich-Quorum der Gruppe 1 zählt alle gelosten Räte der Partei, nicht die des Antrags** — Durch die Umstellung der Einreichung und des Austauschs auf Beschlüsse mit antragsgebundenem Nenner (siehe oben).
- **#24 · Fristanzeige ignoriert Aussetzungen — Seite und Kachel nennen ein falsches Fristende** — _frist_fuer, Kachel-Ring/Resttage, WeicherFilter-Merkmal „ablaufend“ und antrag_detail rechnen mit dem wirksamen Phasenbeginn; für Listen holt _wirksame_beginne alle Aussetzungsabschnitte in einer Abfrage. Tests: Antragsseite und Kachel zeigen Frist + Hemmung.
- **#25 · Zähler und Nenner der Beteiligung folgen verschiedenen Stichtagen (§ 4 Abs 4 lit a)** — Neue Felder geprueft_seit und status_seit; Mitglied.identitaetsstufe_setzen und status_setzen führen sie nach (Verwaltung und beitrag_verbuchen nutzen sie); ist_stimmberechtigt prüft Freischaltung und Status gegen den Stichtag, stimmberechtigte_zaehlen ruft dieselbe Methode. Datenmigration trägt …
- **#26 · Bewerbung kann während der laufenden Wahl zurückgezogen werden — Stimmen verschwinden** — bewerbung_zurueckziehen schreibt fort und weist außerhalb von Unterstützung/Beratung mit Fehlermeldung ab, Bewerbung bleibt zurueckgezogen=False (Test in test_kandidatur.py). Der _beteiligung-Filter liegt in verfahren/views.py (A1) — konkreter Vorschlag in der A2-eigene Helfer …
- **#27 · Zurückgenommene Personenwahl-Zustimmung wird hart gelöscht, Audit unterscheidet nicht** — Zurückgenommene Zustimmungen und zurückgezogene Unterstützungen werden gestempelt statt gelöscht (zurueckgenommen_am / zurueckgezogen_am), jede Richtung mit eigenem Audit-Typ ohne Mitgliedsbezug; alle Zählstellen, der Export und die Auszählung zählen nur gültige.
- **#28 · „Antworten" im Chat gibt es nur mit JavaScript — ohne JS kein Faden, kein Gespräch** — Gemeinsam mit #12 behoben (derselbe Mangel, derselbe Fix): Link statt type=button, serverseitige Vorbelegung, Chip ohne x-cloak bei Vorgabe, ×-Link zurück auf die Seite ohne Parameter.
- **#29 · verify/nachrechnen.py kennt keine Personenwahl und liefert dafür ein falsches Ergebnis** — verify/nachrechnen.py verzweigt nach art: personenwahl_nachrechnen spiegelt tally (zurückgezogene ausgeschlossen, Reihung Zustimmungen dann Einreichreihenfolge, Beteiligung aus zählenden Zustimmungen, Mindestbeteiligung); unbekannte art und doppelte Zustimmung → SystemExit; Schlusszeile ohne …
- **#30 · Angezeigte Frist ignoriert die Hemmung durch Aussetzungen** — Fristen auf Antragsseite und Kacheln rechnen mit dem wirksamen Phasenbeginn; die Antragsseite zeigt ein Band „Ausgesetzt seit … durch Beschluss IR-…“; wer während einer Aussetzung stimmt, bekommt eine eigene Meldung.
- **#31 · Aussetzung ist nicht auf Abstimmung/Vollzug beschränkt, Etikett dann falsch** — aussetzungs_gegenstand(antrag): nur ABSTIMMUNG (Phase Abstimmung) oder VOLLZUG (Phase angenommen); aussetzung_wirkung vermerkt sonst „Ohne Wirkung“; integritaet_beschluss weist das Anlegen in anderen Phasen ab (nach fortschreiben); vollzug_fortschreiben wirft VollzugAusgesetzt bei laufender …
- **#32 · Stichtag der Stimmberechtigung ist das UTC-Datum, nicht das Wiener Datum** — Antrag.stimmberechtigung_stichtag wird beim Übergang in die Abstimmung im Wiener Kalender gesetzt (Migration); Zählung und Einzelprüfung lesen denselben Tag.
- **#33 · Entwurfsschleife rechnet mit dem Aufrufzeitpunkt statt dem Fristzeitpunkt** — Entwurf.fortschreiben rechnet mit wirksam = review_frist bzw. ueberarbeitung_frist (Phasenbeginn, Stichtag, Überarbeitungsfrist, Audit wirksam_ab). Neuer Befehl verfahren_fortschreiben (idempotent, alle laufenden Verfahren, Beschlüsse, Aussetzungen, Parametertests) für einen Cron; …
- **#34 · Werkstatt-Handlungen bleiben nach Beratungsende möglich und sperren den Abstimmungs-Chat** — fenster_aktion bindet jede schreibende Handlung an Phase BERATUNG; Entwurf.einreichen prüft die Phase selbst (gibt False zurück, Audit vorschlag_einreichung_verworfen); Formulare in fenster.html an in_beratung gekoppelt. Test: nach Phasenwechsel keine Fassung, kein Beitrag, kein Bezug, kein …
- **#35 · Bewerbungsrückzug während der Abstimmung löscht Stimmen aus der Beteiligung** — Gleicher Fix wie #26: Rückzug nur bis Abstimmungsbeginn (§ 7 Abs 1) mit Fehlermeldung.
- **#36 · verify/nachrechnen.py rechnet Personenwahlen still falsch nach** — Gleicher Fix wie #29.
- **#37 · Gruppe 2 wird im Echtbetrieb nie gelost — Entwurf entsteht erst in der Beratung** — Derselbe Umbau wie #14: Gruppe 2 wird nachgelost, sobald der Vollzugsbezug feststeht; austausch_wirkung zieht damit nur noch Gruppe 1 nach (bisher hätte es bei Vollzugsbezug eine zweite Gruppe 1 und eine Gruppe 2 gezogen). antrag.html:224 (A1) bleibt richtig — in
- **#38 · Rolle ohne Eindeutigkeit: Doppelberufung zählt doppelt im Quorum und § 6 Abs 3** — Rolle.personen(rollen) zählt Menschen; Nenner in aktive_rollen, _integritaetsrat_beschlussfaehig, Anzeige „besetzt“ (Integritätsrat, Koordinationsrat); rollen_aktion weist eine zweite aktive parteiweite Rolle derselben Person ab (geloste bleiben unberührt). Tests: Doppelberufung abgewiesen; zwei …
- **#39 *(teilweise)* · Kategorie.pfad_kurz löst je gerenderter Zeile eine Abfrage pro Baumebene aus** — Die Lebensbereiche werden mit ihrer Elternkette in einer Abfrage vorgeladen (Parlament, Suche, Antragsseite); ein Abfragezähl-Test hält die Zahl unabhängig von der Zahl der Anträge. Ein gespeichertes Pfad-Feld am Lebensbereich bleibt als Verbesserung offen.
- **#40 *(teilweise)* · Feed und Kacheln zählen je Antrag einzeln, ohne Obergrenze, Gäste laden alles doppelt** — Unterstützungen, Beiträge, Stimmen und Zustimmungen werden je Seite in einer Abfrage gezählt, das Parlament lädt die laufenden Verfahren einmal für alle Bereiche, Gäste materialisieren kein Stimmregister. Die Deckelung der neutralen Gruppen ist eine Produktentscheidung (Fahrtenbuch D-B1a) und …
- **#41 · audit_spur lädt bei jedem Antragsaufruf das gesamte Audit-Log und filtert in Python** — Die Audit-Spur eines Antrags wird in der Datenbank gefiltert; Ausdrucksindex audit_antrag_idx auf ereignis→antrag (Migration).
- **#42 · Chat-Faden und Archiv laden alle Beiträge eines Antrags dreimal, ohne Seitenteilung** — faden_fenster(): jüngste n Wurzelbeiträge samt Antworten (Register chat-faden-wurzeln, Rückfall 50), ältere über ?ab=<pk> als Link bzw. hx-get zum Voranhängen; Abstimmungs-Chat: vorderste der Reihung, weitere dahinter; Zustimmungen/Ablehnungen per annotate statt Prefetch (auch abstimmung_stand, …
- **#43 · Übersicht: eine Stimm-Aggregation je Antrag, über alle je entschiedenen Anträge** — Eine Gruppierungsabfrage über alle gezeigten Anträge statt einer je Antrag; Liste begrenzt auf laufende plus jüngste N entschiedene über zahl("uebersicht-abstimmungen", 20) mit Verweis auf Umsetzungsregister und Parlament. ERSTBESTAND-Eintrag liegt in parameter/models.py (fremde Datei) — als …
- **#44 · Fachliste: zwei Abfragen je Eintrag für die Unvereinbarkeit, auch im Lostopf** — unvereinbarkeiten_laden() (zwei Mengen), unvereinbar_fuer(mitglied_id, …) mit denselben Texten, unvereinbar(mitglied) als Hülle; Fachliste-Ansicht und lostopf_der_fachliste nutzen die Mengen; als_kandidat liest die Fachgebiete aus dem Prefetch. Test: Abfragezahl der Liste und des Lostopfs wächst …
- **#45 · Zwölf Registerwerte liest kein Code — die Registerseite behauptet das Gegenteil** — Jede Stellgröße des Registers wird an ihrer Stelle gelesen (Kacheln, Suche, Fächer, Ähnlichkeit, Filterprofile, Kategorien je Antrag, Bearbeitungsfenster, KI-Antwortlänge, Anstoß-Drossel); der Wächter parameter/test_register.py schlägt an, sobald ein Schlüssel keinen Leser mehr hat.
- **#46 · Abstimmungs-Chat: Absatzwahl per x-cloak versteckt — Kritik ohne JS nie einreichbar** — Regel html:not(.js) .kritikwahl [x-cloak]{display:revert!important} nach der x-cloak-Regel — Absatzwahl und Hinweis stehen ohne JavaScript; Unit-Test auf die Regel, Bildschirmtest ohne JS reicht Kritik mit Absatz 2 ein.
- **#47 · 403.html greift bei CSRF-Fehlern nicht — Django zeigt seine englische Rohseite** — Neue Vorlage 403_csrf.html (Djangos fester Name, keine Einstellung nötig) mit Leiste, Erklärung des CSRF-Falls und Weg zurück; Kommentar in 403.html berichtigt. Test mit Client(enforce_csrf_checks=True).
- **#48 · Hauptnavigation zwischen 760 und 1180 px abgeschnitten — kein Burger, kein Umbruch** — Burger und Panel für Mitglieder unter 1024 px, für Gäste (Klasse leiste gast) unter 1180 px — deren rechter Block ist breiter, Messung bei 1024/1100 px bestätigte den Hinweis des Kurzformen „Umsetzung“/„Werkstatt“ zwischen 1024 und 1279 px; overflow-x:auto statt hidden; Panel-Regeln außerhalb …
- **#49 · Dunkles Thema: Beratungs-Badge und „✓ Unterstützt“ mit 1,57:1 Kontrast unlesbar** — Token --on-deep (hell #E9E4D8, dunkel #0C151E) für Badge Beratung, .knopf:hover, .knopf.gewaehlt sowie die übersehenen .btn-linie:hover, .fluss .punkt, .schrittleiste .punkt.aktiv; Unit-Test verbietet Text auf --deep ohne --on-deep/--on-gold; Kontrast-Bildschirmtest hell/dunkel ≥ 4,5:1.
- **#50 · Eingefahrene Profil-Leiste: unsichtbare Tab-Stopps, Enter wechselt unbemerkt das Profil** — .filter-leiste.zu .innen mit visibility:hidden und verzögertem Umschalten der Sichtbarkeit, dazu :inert="!offen" auf .innen; Bildschirmtest: nach localStorage „zu“ landet kein Tab-Stopp in der Leiste, der Griff bleibt.
- **#51 · „Ihre Gemeinde stimmt über Gemeindesachen ab“ — es gibt keine regionale Stimmberechtigung** — Absatz „Ihre Region“ auf mitgliedschaft.html im Wortlaut des Keine Codeänderung; Katalog über NEUE_TEXTE_B.md.
- **#52 · 500-Seite: „Er ist protokolliert und wird angesehen“ — in Produktion wird der Fehler nirgends protokolliert** — Satz „Er ist protokolliert und wird angesehen“ aus 500.html gestrichen (Alternative des Test, dass „protokolliert“ nicht mehr vorkommt.
- **#53 · Beanstandung: „die Zukunftswerkstatt rechnet den Punkt nach“ — nichts und niemand tut das** — Flash, Hilfetext und Zukunftswerkstatt-Seite versprechen keinen Korrekturlauf mehr („noch nicht gebaut“); Test in test_oeffentliche_texte.py. Der Korrekturlauf selbst ist laut
- **#54 · Rollenmatrix und Regelverzeichnis sind seit 0.44 veraltet und widersprechen sich selbst** — wie_hinein von Expertenrat Gruppe 1 und 2 auf den Stand 0.44 (Fachliste durch die Verwaltung, Auslosung je Antrag zu Beratungsbeginn, Gruppe 2 mitgelost, wenn der Vollzugsbezug zur Ziehung gesetzt ist, sonst Verwaltung), Koordinationsrat-Einschraenkung auf eine Faktenbasis und die Berichte …
- **#55 · Mitgliedschaft, Station 3: Zukunftswerkstatt „rechnet durch, welche Gesetze berührt wären“ — kein Lauf tut das** — Station 3 im Wortlaut des Zusätzlich die Karte „Die Zukunftswerkstatt“ weiter unten als Zielbild gekennzeichnet — über den Vorschlag hinaus, in md vermerkt.
- **#56 · Zukunftswerkstatt-Seite: Unterstützer-Schleife stehe nicht im Satzungsentwurf 2.5 — sie steht in § 5 Abs 12 und 13** — Hinweis unter dem Ablauf ersetzt durch „Alle sechs Schritte entsprechen dem Satzungsentwurf 2.5 (Schritt 4: § 5 Abs 12 und 13). Geltend ist bis zum Beschluss der Mitglieder die Satzung 1.3.“
- **#57 · hashchain.py verspricht einen „täglich veröffentlichten Kettenkopf“ — es gibt keine Veröffentlichung** — Docstring von hashchain.py auf den Ist-Stand (Weg 1 des extern veröffentlichter Kopf ist geplant (F-22), nicht gebaut; Unterstützungen werden bisher nicht protokolliert. Wächter-Test gegen das alte Versprechen.
- **#58 · 14 handgeschriebene .po-Einträge sind syntaktisch ungültig — 14 Absätze bleiben englisch-deutsch** — Die 14 Bloecke mit rohen Zeilenumbruechen in gueltige .po-Syntax gebracht (msgid leer plus je eine Zeile mit maskiertem Zeilenumbruch), .mo neu geschrieben; Test rendert /, /rollen/, /regeln/, /gremien/fachliste/, /gremien/beschluesse/ und die 404-Seite auf Englisch und schliesst die deutschen …
- **#59 · po_pruefen.py liest ungültige Katalogzeilen stumm, meldet Grün und schreibt falsche .mo** — tools/po_pruefen.py: lesen(pfad) prueft jede Zeile gegen die Syntax, sammelt SYNTAX-Fehler mit Zeilennummer (KatalogFehler), pruefen() gibt Exit 1 und --mo schreibt dann nichts; test_design_system.py und test_vorlagen.py::msgids() nutzen den strengen Leser. tests/test_katalog.py ist der …
- **#60 · 21 Texte der Beschluss-/Aussetzungs-Views (0.43/0.44) fehlen im Katalog** — Alle fehlenden Texte der Beschluss-, Aussetzungs-, Regelpruefungs- und Parametertest-Views und ihrer Vorlagen nachgetragen (insgesamt 198 Eintraege, weil der 0.45-Stand mit Koordinationsrat und Parameterverfahren ebenfalls ohne Katalog war); Kurzfassung a von n noetigen Stimmen und Frist …
- **#61 · Auslosungs-Hinweis, Fristring-aria-label und Bot-Schutz-Bild ohne Katalogeintrag** — Auslosungshinweis, Link Die Auslosung ansehen, Fristring-Schluessel %(wert)s %% der Frist verstrichen und Sicherheitsaufgabe als Bild im Katalog; Test rendert _ring.html auf Englisch und prueft die kompilierte .mo.
- **#62 · „Passt alles"-Auswertungszeilen: Katalog hat „%" statt „%%" — Übersetzung greift nie** — Beide Passt-alles-Schluessel enden in msgid und msgstr auf %% statt %; Test gegen die .mo.
- **#63 · Hilfetext der Wohnsitz-Gemeinde: ein Leerzeichen in der .po macht die Übersetzung tot** — Leerzeichen vor dem Punkt in msgid und msgstr des Gemeinde-Hilfetexts entfernt; Test gegen die .mo und Laufzeitprobe /mitglied-werden/ auf Englisch.
- **#64 · TextChoices-Beschriftungen ohne gettext_lazy: „Land/Bezirk/Gemeinde" u. a. deutsch auf englischen Seiten** — Alle Auswahl-Beschriftungen der Modelle sind übersetzbar (gettext_lazy), der Archiv-Export schreibt sie über DjangoJSONEncoder.
- **#65 · Wächter des Abstimmungs-Chat-Blocks kippt nach 14 Tagen — jeder Deploy danach legt den Demo-Antrag neu an** — Wächter des Abstimmungs-Chat-Blocks hängt am Titel (TESTLAUF_TITEL) statt am vergänglichen Status. Test: demo_seed, Frist verstreichen, fortschreiben, demo_seed erneut → genau ein Antrag.
- **#66 · Drossel für Anmeldelinks und Registrierung ist per X-Forwarded-For frei wählbar** — Wie #19 (DDOE_CLIENT_IP_KOPFZEILE, nie XFF[0], Zähler in der Datenbank); Test: ohne konfigurierte Kopfzeile wird ein Request mit gesetztem HTTP_CF_CONNECTING_IP auf REMOTE_ADDR gedrosselt, mit Konfiguration zählt die Kopfzeile. Einmal-Kennung der Rechenaufgabe siehe #68.
- **#67 · Anstoß-Widget ohne Anmeldung hat nur eine Sitzungs-Drossel — ohne Cookie ist sie wirkungslos** — anstoss/views.py ruft drossel_zuviel(request, 'anstoss', limit=tagesgrenze) unmittelbar vor Anstoss.objects.create — leere und Honigtopf-POSTs verbrauchen kein Budget; Tests: 21 POSTs ohne Cookie → der 21. liefert warte, zwei POSTs ohne Cookie innerhalb 60 s werden beide gespeichert (Bauart …

*Niedrig*

- **#68 · Rechen-Captcha trivial lösbar — die Aufgabe steht lesbar im signierten Token der Seite** — Die Rechenaufgabe liegt in der Sitzung (bis zu drei offene je Sitzung), das versteckte Feld trägt nur eine zufällige Kennung; nach einem Formularfehler wird dieselbe Aufgabe erneut gezeigt, eine gelöste Aufgabe ist verbraucht (kein zweites Absenden). Modul- und Funktions-Docstrings ehrlich …
- **#69 · Registereintrag chat-bearbeitungsfenster-minuten hat keine Wirkung im Code** — Kommentar.bearbeitungsfenster_minuten() liest chat-bearbeitungsfenster-minuten; darf_bearbeiten und der Hinweistext im Chat nutzen denselben Wert.
- **#70 · Neutrale Grundordnung sortiert nach Phasenbeginn, offengelegt ist „Phase und Frist"** — Neutraler Sortierschlüssel (Phase, Fristende) in _weicherfilter_reihen und in den neutralen Gruppen; Test mit zwei Ordnungen (14 und 7 Tage): früheres Fristende zuerst.
- **#71 · Kennzahlen-Export und Übersicht rechnen Personenwahlen mit 0 Stimmen** — Gemeinsamer Helfer parameter.kennzahlen.abgegeben_je_antrag zählt bei Personenwahlen die Pseudonyme mit Zustimmung zu einer nicht zurückgezogenen Bewerbung; votes.turnout_mean und die Übersicht nutzen ihn; Personenwahlen erscheinen ohne Ja/Nein-Balken, mit Gewählt-Zeile, Badge weiter nach Phase …
- **#72 · select_for_update().count() sperrt nichts — Beschlussnummer nicht abgesichert** — GremienBeschluss.save ohne wirkungsloses select_for_update: _naechste_nummer (höchste vergebene + 1), bis zu drei Versuche bei IntegrityError außerhalb des inneren Savepoints, ehrliche Docstring. Test simuliert das Wettrennen (Konkurrent nimmt die Nummer zwischen Zählen und Schreiben).
- **#73 · Beschlussnummer nimmt das UTC-Jahr statt des Wiener Jahres** — Jahr der Beschlussnummer aus timezone.localtime(angelegt_am). Test: 31.12. 23:40 UTC → KR-2027-01.
- **#74 · Rückwärtsmigration 0003 löscht alle Systembeiträge samt Voten der Unterstützer** — Rückwärtsfunktion von gremien/0003 durch RunPython.noop ersetzt, Begründung in der Migrations-Docstring; Wächter-Test prüft reverse_code.
- **#75 · Hash-Kette versiegelt den Zeitstempel nicht — zeit ist unbemerkt änderbar** — anhaengen schreibt den Zeitpunkt als „zeit“ ins versiegelte Ereignis (Spalte zeit trägt denselben Wert); alte Einträge bleiben prüfbar. Test: Manipulation der Zeit im Ereignis wird erkannt.
- **#76 · Beschlussnummer nimmt das UTC-Jahr, die Anzeige das Wiener Datum** — Identisch mit #73 (Wiener Jahr); vergebene Nummern bleiben unverändert.
- **#77 · Beschlussliste: bis zu drei Abfragen je Beschluss für Quorum und Antrag** — quoren_fuer(beschluesse) rechnet den Nenner je Seite mit einer Abfrage (gleiche Regel wie aktive_rollen); auswertung(aktive=None) nimmt ihn entgegen, abschliessen bleibt unverändert; beide Listen mit select_related("antrag"). Test: Abfragezahl der öffentlichen Liste konstant, Nenner stimmen mit …
- **#78 · /parameter/ und parameter.json führen bei jedem Aufruf 36 Idempotenz-Abfragen aus** — erstbestand_sicherstellen() holt den Bestand mit in_bulk in einer Abfrage und schreibt nur Fehlendes oder Abweichendes (get_or_create nur fuer Fehlende, gegen Rennen); der Aufruf in den Lese-Views bleibt wie vom Tests: genau eine Abfrage bei vollstaendigem Bestand, keine Einzelabfragen je …
- **#79 · Meine Gespräche: dieselbe unbegrenzte Liste wird je Anfrage dreimal gebaut** — /gespraeche/ lädt einmal (grenze=None), zählt daraus, schneidet auf den Registerwert und puffert den Zähler an der Anfrage; der Kontextprozessor nimmt ihn. Test: genau eine Antworten-Abfrage je Aufruf. Der langfristige SQL-Zähler für die übrigen Seiten ist als eigener Schritt notiert.
- **#80 · Auslosung: Fachliste zweimal vollständig geladen, Rollen-Prefetch ohne Verwendung** — Auslosungsseite lädt nur die Namen der gezogenen Schlüssel; wirkungslose values_list-Abfrage und Rollen-Prefetch gestrichen, Kontextvariable namen entfällt. Test: Abfragezahl unabhängig von der Fachlistengröße, Fachliste nur mit IN (…).
- **#81 · Antrag, Beschluss, Fachliste ohne Index auf den Filter- und Sortierfeldern** — Antrag.Meta.indexes (phase+phase_beginn, Teilindex hervorgehoben=True), GremienBeschluss (status+frist), Fachliste (gestrichen_am); eigene Migrationen verfahren/0019 und gremien/0016. Test per Datenbank-Introspektion.
- **#82 · Beitrags-Anker „#n“ und leerer Stern unter 2:1 Kontrast (Link bzw. Umschalter)** — .blase-anker in --muted (Hover --ink); --stern-aus hell #7E8C96 (≥ 3,06:1 auf Weiß, surface-2 und bg), dunkel #7B8790 (≥ 4,1:1); Unit- und Kontrast-Bildschirmtest.
- **#83 · Sprachwechsel verliert Abfrageparameter (Fächer-Ast, Suche, Filter)** — _sprache.html gibt request.get_full_path als next mit; Test: Fächer-Ast und Suche stehen im next-Feld, set_language leitet dorthin um.
- **#84 · 500-Seite: lang="de" bei englischem Text** — 500.html liest die Sprache über {% get_current_language as SPRACHE %}; Test rendert ohne Kontext unter en und de und prüft lang-Attribut samt Überschrift.
- **#85 · Anstoß-Textfeld und mehrere Verwaltungsfelder ohne Label oder aria-label** — Anstoß-Textfeld, Verwaltungs-, Parameter-, Mandatar- und Gremienformulare tragen Labels oder aria-label.
- **#86 · Startseiten-Diagramm nennt „höchstens 3 Runden“ fest, obwohl der Wert aus dem Register kommt** — index.html nennt die Rundenzahl per blocktranslate aus fristen.runden; Test mit gremien-hoechstrunden = 2. Neuer Text in NEUE_TEXTE.
- **#87 · Mandatare-Seite: „die Wahl unserer Kandidaten läuft bereits“ auch dann, wenn keine Kandidatur läuft** — Satz „die Wahl unserer Kandidaten läuft bereits“ steht nur noch unter {% if kandidaturen %}; sonst neuer wahrer Satz. Test ohne Kandidatur.
- **#88 · Markdown-Export eines Antrags: zwölf Beschriftungen ohne Katalogeintrag — halb englisch, halb deutsch** — Die zwoelf Beschriftungen des Markdown-Exports (Phase, Eingebracht, Unterstuetzungen, Fassung, Beitraege, Auswertung, zurueckgegeben, Absatz, Antwort auf, Runde, Entwurfsfassung, Pruefung) im Katalog; Test laedt den Export auf Englisch und schliesst deutsche Beschriftungen aus. …
- **#89 · „ueber" statt „über" in zwei Fähigkeitstiteln der Rollenübersicht** — Elf Titel in rollen.py ohne ue/ae/oe (nicht nur die zwei genannten: auch Wuensche, beraet, prueft, Fuer, Zurueckgegebenen, moegliche); test_vorlagen.py prueft Sprachregeln und Ersatzschreibungen ueber eine Wortliste (kein Silbenmuster) auch fuer die Datentexte aus rollen.py, regelwerk.py und …
- **#90 *(teilweise)* · /rollen/, /regeln/ und /parameter/: englische Überschriften über rein deutschen Inhalten aus plattform_core** — Die Texte der Rollenmatrix, des Regelverzeichnisses und des Erstbestands sind als übersetzbar markiert und laufen durch den Katalog; die langen Einträge selbst (≈ 480) liegen noch auf Deutsch vor — die Seiten sagen das in anderer Sprache offen. Übersetzung ist Datenpflege und folgt.
- **#91 *(teilweise)* · Verwaltungs-Views: rund 45 Meldungen und Formularbeschriftungen ohne gettext** — Alle Meldungen und Formularbeschriftungen der Mitgliederverwaltung sind übersetzbar; ein Wächter-Test hält es. Die Verwaltungsansichten der Mandatare und Rollen folgen mit ihrer nächsten Änderung.
- **#92 · Rund 60 veraltete Katalogeinträge — msgids, die es im Code nicht mehr gibt** — 84 tote Eintraege entfernt (Abgleich gegen den 0.45-Stand, daher mehr als rund 60); jeder vorher per Suche ueber Vorlagen, Python, .txt, .js und .yaml gegengeprueft, Filterargumente und Variablenform von translate im Abgleich beruecksichtigt (noch nie lebt). …
- **#93 · README (englische Zusammenfassung) nennt die Plattform „public prototype"** — README: A public prototype is live -> The platform is public and in its alpha phase. (erster Lauf).
- **#94 · /gesund/ prüft die Datenbank nicht — Render hält einen Dienst ohne DB für gesund** — /gesund/ fuehrt SELECT 1 aus und antwortet ohne Datenbank mit 503 (config/gesund.py, vor den App-Routen eingehaengt); Test mit werfendem Cursor. (erster Lauf).
- **#95 · render.yaml (Neuaufbau) deployt jeden Push, unabhängig von der CI** — render.yaml autoDeployTrigger off (CI-Hook bleibt der Weg), Partner-Muster docs/partner/instanz/render.yaml checksPass, Satz in docs/BETRIEB-RENDER.md. (erster Lauf).
- **#96 · ruff und Produktionsabhängigkeiten ohne Obergrenze — die CI wird beim nächsten Release wieder stumm rot** — Obergrenzen in pyproject.toml (ruff <0.17, gunicorn <27, whitenoise <7, psycopg <4, requests <3, PyYAML <7, segno <2); Job nicht_ausgerollt meldet eine rote Pruefung auf main sichtbar, CI-Abzeichen in der README. Die vom (erster Lauf).
- **#97 · CI führt `manage.py check` ohne `--deploy` aus — die Definition of Done verlangt `--deploy`** — Eigener CI-Schritt check --deploy --fail-level WARNING mit DDOE_DEBUG=0, Schluessel aus github.sha, ALLOWED_HOSTS und whitenoise; security.W021 begruendet in SILENCED_SYSTEM_CHECKS. (erster Lauf).
- **#98 · Statische Dateien laufen mit max-age=60 — ohne Manifest gibt es keine langen Cache-Zeiten** — CompressedManifestStaticFilesStorage; CI-Schritt collectstatic mit DDOE_STATIK=whitenoise; Test rendert base.html mit Manifest-Speicher. (erster Lauf).
- **#99 · KI-Steckplatz: Abbruch während des Lesens der Antwort wird nicht abgefangen — 500 statt Archiv-Eintrag** — Zweite except-Klausel in ki/anbieter.py faengt URLError, OSError, http.client.HTTPException und ValueError - jeder Netz- und Protokollfehler wird AnbieterFehler und steht im Archiv. Tests: read() wirft IncompleteRead -> SteckplatzStumm und KILauf erfolgreich=False; RemoteDisconnected aus urlopen …

## [0.44.0] — 2026-09-08 · Die Fachliste und das Los des Expertenrats

### Hinzugefügt
- **Die öffentlich geführte Fachliste (§ 6 Abs 7):** `/gremien/fachliste/` — mit Fachgebieten, **Interessenbindungen und Honoraren**. Die Satzung nennt beides ausdrücklich; ohne diese Angabe wäre die Auslosung eine Auswahl unter Unbekannten. Der Schlüssel neben dem Namen ist die Kennung, mit der die Ziehung rechnet
- **Die Auslosung des Expertenrats je Antrag.** Zu Beratungsbeginn wird aus der Fachliste gelost — erst dann, denn erst dann steht fest, dass beraten wird. `plattform_core/losziehung.py` (VERSION 1) löst dabei einen Widerspruch, der in § 6 Abs 7 mit § 2 Abs 6 steckt: **nachrechenbar und unvorhersehbar zugleich.** Der Anker ist der Kopf der Audit-Kette im Augenblick der Ziehung — er steht dann fest und war vorher von niemandem auszurechnen
- **Die Ziehung steht öffentlich:** `/gremien/auslosung/<antrag>/` zeigt Anker, Audit-Nummer, Lostopf, jeden Loswert und jeden Ausgeschlossenen mit Grund — dazu die Anleitung, wie man sie mit einem Prüfsummenwerkzeug nachrechnet. Die Antragsseite verweist darauf
- **Rollen gelten für einen Antrag.** Bis jetzt schrieb, wer in Gruppe 1 berufen war, an **jedem** Entwurf. § 6 Abs 7 will das Gegenteil: „für die Beratung zu einzelnen Anträgen". `Rolle.hat_fuer()` bindet Schreiben und Mitstimmen an die Sache; auch der **Nenner des Quorums** zählt nur noch die für diese Sache Gelosten

### Technisch
- **Zwei Gruppen, durch die Konstruktion getrennt (§ 6 Abs 7):** Gruppe 2 wird aus dem Rest desselben Lostopfes gezogen, nicht aus dem ganzen. Eine Prüfung, die man vergessen kann, gibt es nicht. Reicht der Topf nicht für beide, wird gar nicht gelost — eine halb besetzte zweite Gruppe sähe nach Prüfung aus und wäre keine
- **Die Unvereinbarkeiten prüft der Lostopf, nicht die Ansicht** (§ 6 Abs 3 lit a: kein anderer Rat, kein Mandat). Wer sie in der Ansicht prüft, vergisst sie irgendwo
- **Gruppengrößen und Losregel-Fassung stehen in der eingefrorenen Verfahrensordnung** (§ 5 Abs 5). Die Ziehung findet rund zwei Monate nach dem Einbringen statt; läse sie aus dem laufenden Register, wirkte eine Änderung rückwirkend. Zwei neue Stellgrößen (`expertenrat-gruppe1-groesse`, `expertenrat-gruppe2-groesse`) setzen die Werte für **künftige** Anträge; unter drei kommen sie nicht (§ 6 Abs 8, satzungsfest im Code). Schema 1.3
- **Nach einem Widerruf der Einwilligung (§ 8 Abs 4)** steht der Schlüssel statt des Namens; Loswert und Platz bleiben, die Ziehung bleibt nachrechenbar
- **Verfahren ohne Ziehung laufen unverändert weiter:** Wo keine Auslosung vorliegt, gelten die parteiweiten Rollen. Ein laufendes Verfahren wird nicht mitten im Lauf umgestellt

### Behoben
- `auslosen()` griff über `antrag.entwurf` zu und vergiftete damit den Objekt-Cache des Aufrufers: Wer danach `antrag.entwurf` las, bekam „kein Entwurf", obwohl längst einer angelegt war. Jetzt eine frische Abfrage — dieselbe Falle, vor der der Phasenautomat schon warnt
- Ein eigener Test hing vom Los ab: Er nahm an, dieselbe Person werde nicht für zwei Anträge gelost. Sie kann es, und das ist richtig so — der Test wählt jetzt gezielt jemanden, der nur beim ersten dabei ist
- `/parameter.json` zeigte die geltende Verfahrensordnung als **gespeicherten Rohdatensatz**. Ältere Fassungen kennen die neuen Felder nicht — sie wirken über den eingebauten Vorgabewert, standen aber nicht im Export. Eine Partnerinstanz hätte eine Ordnung ohne Gruppengrößen gelesen und ihre eigene ohne sie gebaut. Exportiert wird jetzt die **wirksame** Ordnung

## [0.43.0] — 2026-09-08 · Das Regelverzeichnis, die Aussetzung und die jährliche Prüfung

### Hinzugefügt
- **Das öffentliche Regelverzeichnis (§ 2 Abs 6):** `/regeln/` zeigt **20 Regeln**, geordnet nach Wirkung — bindend zuerst, dann reihend, zuordnend, rechnend, darstellend. Je Regel: Fassung, Datum, Begründung, Satzungsbezug und eine Anleitung, wie ein Mensch das Ergebnis selbst nachrechnet. Von Hand gepflegt, nicht erzeugt: Ein Programm kann aufzählen, welche Regeln es gibt — eine **Begründung** kann es nicht schreiben, und genau die verlangt der Absatz. Ein Wächter hält die Liste gegen `plattform_core`: Ein Modul, das weder verzeichnet noch begründet ausgenommen ist, lässt ihn anschlagen
- **Die Aussetzung nach § 6 Abs 3 lit d.** Der Integritätsrat kann eine laufende Abstimmung oder den Vollzug eines Beschlusses aussetzen. Sie ist zu begründen, zu veröffentlichen und binnen sieben Tagen durch Antrag an das Parteischiedsgericht zu bestätigen — **sonst endet sie von selbst.** Solange sie wirkt, ruht das Verfahren vollständig: Es wird nicht abgestimmt, und die Frist rückt nicht näher; danach läuft der Antrag mit genau der Restzeit weiter, die er hatte
- **Die jährliche Prüfung der automatisierten Regeln (§ 2 Abs 6 letzter Halbsatz).** Der Integritätsrat legt sie an, das Verzeichnis wird dabei **eingefroren**, wie es in diesem Augenblick steht, und der Rat beschließt „geprüft" oder „beanstandet". Der Vermerk „geprüft am …" wäre ohne die Liste, auf die er sich bezieht, wertlos — Regeln ändern sich, und ein Jahr später wüsste niemand mehr, was geprüft worden ist

### Behoben
- **Sieben Regeln ohne Fassungsnummer.** `tally`, `eligibility`, `phases`, `policy`, `similarity`, `klassifikation` und `beitraege` entscheiden oder ordnen zu und trugen keine Version. Eine Regel ohne Fassung kann keine dokumentierte Änderung haben — und genau die verlangt § 2 Abs 6. Alle sieben tragen jetzt `VERSION = 1`, mit dem Hinweis, was die Zahl beziffert: das Verfahren, nicht die Werte
- **Die Offenlegung der Stimmberechtigung war falsch.** Im Modultext stand: „Beitritt am 31. Jänner + 3 Monate ⇒ Stichtag 30. April genügt nicht, 1. Mai genügt." Der Code klemmt auf den Monatsletzten — der 30. April genügt sehr wohl; der Satz widersprach sogar seinem eigenen nächsten Halbsatz. Wer den Text las und selbst nachrechnete, kam bei genau der Regel auf einen Tag zu spät, die darüber entscheidet, **wer überhaupt abstimmen darf**
- **Der Kontoauszug versprach zu viel:** „camt kennt das Problem nicht." Liefert die Bank keine der vier möglichen Referenzen, fällt auch der camt-Leser auf denselben Fingerabdruck zurück und hat dieselbe Grenze wie CSV — zwei betragsgleiche Zahlungen desselben Menschen am selben Tag fallen zusammen
- **Das Austauschschema hielt seine eigene Zusage nicht ein.** Sein Docstring verspricht, neue Kennungen erhöhen die Nebenversion; in 0.42.0 kamen zwei dazu, ohne dass sie stieg. `SCHEMA_VERSION` steht jetzt auf **1.2** — Partnerinstanzen sehen daran, dass etwas hinzugekommen ist
- Zwei falsche Angaben im Verzeichnis selbst, gefunden von der Belegprüfung: `diagramme.py` berief sich auf „§ 2 Abs 1 lit c" — den Absatz gibt es nicht —, und die Nachrechen-Anleitung für den Kontoauszug ließ Präfix und Trennzeichen weg, führte also nicht zum selben Wert

### Technisch
- `plattform_core/aussetzung.py` (VERSION 1): Die sieben Tage sind eine **Konstante, keine Stellgröße** — wer sie im Register verlängern könnte, könnte eine Abstimmung beliebig lange anhalten, ohne je ein Gericht anzurufen. Die Hemmung wird **gerechnet, nicht gespeichert**: Eine Summe am Antrag bekäme jede Folgephase erneut geschenkt, weil der Phasenbeginn bei jedem Wechsel neu geschrieben wird. Überlappende Aussetzungen zählen einmal, sonst hemmten zwei gleichzeitige doppelt
- `Antrag.wirksamer_phase_beginn()` — der gespeicherte Beginn bleibt unangetastet, damit die Historie lesbar bleibt; gerechnet wird mit dem wirksamen
- Die Rollenübersicht zieht nach: Der Integritätsrat hat statt einer Zeile jetzt **neun von zwölf** Fähigkeiten verfügbar. Offen bleiben die Betroffenheit nach § 5 Abs 6, der jährliche öffentliche Bericht und das externe Sicherheitsaudit

## [0.42.0] — 2026-09-05 · Interne Beschlüsse, der Integritätsrat und „Wer darf was"

### Hinzugefügt
- **Interne Beschlüsse für alle Räte (FB-I4).** `plattform_core/gremienbeschluss.py` (VERSION 1) übersetzt § 6 Abs 2 lit e für ein Gremium, das sich nicht in einem Raum trifft: **Anwesend ist, wer abgestimmt hat.** Beschlussfähig ab der aufgerundeten Hälfte der aktiven Rollen, entschieden mit einfacher Mehrheit der abgegebenen Stimmen. Ein Gleichstand ist **kein** Beschluss — sonst entschiede die Reihenfolge der Optionen. Ein Beschluss schließt, wenn alle gestimmt haben oder die Frist um ist; jede Stimme steht mit Namen und Begründung (§ 6 Abs 9)
- **Die Prüfung der Gruppe 2 ist ein Beschluss des Gremiums (FB-I3).** Bis 0.41 entschied, wer zuerst auf einen der drei Knöpfe drückte — eine einzige Person, sofort, ohne Frist. Gruppe 2 ist als Redundanz und Korruptionsprüfung gedacht (§ 6 Abs 7); eine Redundanz aus einer Person ist keine. Jetzt: Quorum, Frist aus dem Register (`gremien-pruefung-tage`), die vier Prüfpunkte als Haken, die in die **veröffentlichte** Begründung wandern — eine Prüfliste, die niemand sieht, prüft nichts
- **Die Beschlüsse der Räte sind öffentlich:** `/gremien/beschluesse/` und `/gremien/beschluss/<nummer>/`, ohne Anmeldung, mit Auszählung, jeder Stimme und jeder Begründung. Jeder Beschluss trägt eine zitierfähige Nummer („IR-2026-04"), je Gremium und Jahr fortlaufend
- **Der Integritätsrat bekommt seinen Bereich (FB-I6):** `/gremien/integritaet/`. Das Aufsichtsorgan war das einzige ohne Ort — „Mein Gremium" führte für seine Mitglieder auf die öffentliche Besetzungsliste. Vier Anlässe mit Wirkung: Hervorhebung und ihre Aufhebung (§ 5 Abs 10 lit b), Zurückweisung und ihre Aufhebung (§ 5 Abs 2). **Kein Knopf wirkt unmittelbar** — jeder legt einen Beschluss an, über den der Rat danach abstimmt
- **Die Rollenübersicht „Wer darf was" (FB-K6):** `/rollen/` zeigt alle vierzehn Rollen — vom Gast bis zum Parteischiedsgericht — mit Satzungsbezug, einem Satz aus der Satzung, den Fähigkeiten und dem Weg hinein. Jede Fähigkeit trägt ● verfügbar, ◐ teilweise oder ○ geplant mit Bauschritt. Stand heute: **164 Fähigkeiten, davon 66 verfügbar, 33 teilweise, 65 geplant.** Die Willkommensseite trägt vier Karten (Gast · Mitglied · Mitglied in Aufnahme oder pausiert · Mandatar) und den Weg zur vollen Liste

### Behoben
- **Ein Gremium ohne besetzte Rollen konnte beschließen.** Die Hälfte von null ist null, und `abgegeben >= 0 and abgegeben > 0` machte eine einzelne Stimme beschlussfähig — erreichbar, sobald eine Berufung vor dem Fristende endet. Dann hätte die Stimme eines Menschen allein entschieden, dessen Amt schon abgelaufen war
- **Das Verwaltungswerkzeug konnte die Hervorhebung setzen.** § 5 Abs 10 lit b sagt, sie erfolge niemals durch einen Algorithmus — und ebenso wenig durch einen Haken im Backend. `hervorgehoben` und `hervorhebung_begruendung` sind im Admin jetzt schreibgeschützt
- **`_endabstimmung_oeffnen` setzte die Phase ohne jede Prüfung.** Ein zurückgewiesener Antrag bekam von der Entwurfsschleife trotzdem noch eine Endabstimmung
- **Eine Hervorhebung ohne Beschluss.** Am Antrag „Jede Ratssitzung als Livestream mit Archiv" stand „Beschluss IR-2026-03 vom 12.08.2026" — eine Nummer ohne Beschluss, ein Datum ohne Sitzung, seit jeher ein Platzhalter in den Demodaten. Nachträglich einen Beschluss zu erfinden, damit die Zahl stimmt, wäre auf einer Plattform, deren Zweck Nachprüfbarkeit ist, das Schlechteste. Die Hervorhebung fällt deshalb bei jedem Deploy, solange kein Beschluss sie deckt; auf einer frischen Datenbank fasst die Demo ihn wirklich, mit drei Stimmen
- Die Zurückweisung war eine Einbahnstraße. § 5 Abs 2 macht sie beim Parteischiedsgericht bekämpfbar; der Beschluss merkt sich jetzt Phase und Phasenbeginn, und die Aufhebung gibt dem Antrag genau die Restfrist zurück, die er hatte

### Technisch
- `GremienBeschluss`/`GremienStimme` sind generisch: ein Gegenstand, eine Optionsliste, eine Frist, ein **Anlass**. Die Wirkungstabelle verzweigt allein über den Anlass — die alte Bedingung (`gremium == EXPERTENRAT_2 and entwurf_id`) hätte beim zweiten Anlass desselben Rates nicht mehr getragen. Es gibt nur Anlässe, deren Wirkung gebaut ist; einer ohne wäre ein Knopf, der schweigend nichts tut
- **Satzungsfest im Code, nicht im Register:** die Mindestbesetzung des Integritätsrats (§ 6 Abs 3 lit a: drei bis sieben). Ein unterbesetzter Rat kann abstimmen, aber seine Beschlüsse entfalten keine Wirkung — mit Vermerk am Beschluss statt stummer Unterlassung
- `plattform_core/rollen.py` (VERSION 1) führt die Rollenmatrix als reine Daten. Zwölf Wächter-Tests halten sie gegen den Code: jede Rolle des Codes in der Matrix, `GREMIUMSKUERZEL` und `Gremium.values` deckungsgleich, jede genannte Adresse auflösbar, kein ○ ohne Bauschritt, kein ◐ ohne Angabe, was fehlt
- Der Satzungsbezug steht bewusst nur an der **Rolle**, nicht an jeder Fähigkeit: Eine Belegprüfung fand in Stichproben mehrere falsche Paragrafen, und ein falscher Paragraf neben einer Zeile ist schlechter als keiner
- Zwei neue Stellgrößen: `gremien-pruefung-tage` (7) und `gremien-beschluss-tage` (7), beide mit Schema-Kennung

### Entschieden (Fahrtenbuch Teil D)
- **D-I3:** Bleibt die Prüfung der Gruppe 2 ohne Ergebnis, geht der Vorschlag weiter an die Unterstützer — mit offengelegtem Vermerk, dass Gruppe 2 ihn **nicht** validiert hat. „Validiert" wäre eine Unbedenklichkeitsbescheinigung, die niemand ausgestellt hat; Liegenbleiben gäbe einem Rat die Blockademacht, die das übrige Verfahren nirgends kennt (§ 5 Abs 12)
- **D-I1a:** § 6 Abs 7 (Los je Antrag) und § 6 Abs 8 (Bestellung auf zwei Jahre) widersprechen einander für den Expertenrat. Gelesen wird: Die Zweijahresbestellung gilt der **Fachliste**, das Los dem **einzelnen Antrag** — dann tragen beide Absätze wörtlich
- **D-J3g:** Kein zweiter Weg zur Verfahrensordnung. Ein Parametertest darf Registerwerte setzen, aber keine Ordnung in Kraft setzen; über sie beschließt nach § 5 Abs 7 die Mitgliederversammlung

## [0.41.0] — 2026-09-05 · Fristen im Register, Verfahrensordnung auf Knopfdruck

### Hinzugefügt
- **Das Parameterregister in zweiter Fassung (FB-J2):** Stellgrößen stehen jetzt in **Gruppen** (Verfahren, Gremien, WeicherFilter, Fächer, Zukunftswerkstatt, Schutz, Kacheln) statt in einer Liste aus zweiunddreißig Zeilen. Jeder Wert trägt seinen **Status** — gültig, im Test, vorgeschlagen —, ein Wert im Test sein sichtbares Band mit Hypothese und Enddatum, und jede Änderung ihre **Begründung am Wert selbst**. Im Audit-Log stand sie immer schon; dort findet sie nur niemand
- **Fünfundzwanzig weitere Stellgrößen** aus dem Code ins Register geholt — darunter die Ähnlichkeitsschwelle, die entscheidet, wie oft die Plattform Menschen beim Einbringen zu einem bestehenden Antrag lenkt, die Mindestlänge einer Kritik an einem Entwurf und die Zahl der hervorgehobenen Abstimmungen auf der Startseite. Alle mit Schema-Kennung, damit Partnerinstanzen sie vergleichen können (Schema 1.1)
- **„Neue Fassung aus dem Register erzeugen"** in der Verwaltung (FB-J1) — und getrennt davon **„In Kraft setzen"**. Zwei Schritte, weil das eine eine Rechnung ist und das andere eine Entscheidung: Über die Verfahrensordnung beschließt nach § 5 Abs 7 die Mitgliederversammlung; solange die Plattform diese Abstimmung nicht führen kann, handelt die Verwaltung stellvertretend — mit Pflicht-Grund, im öffentlichen Audit-Log, und die abgelöste Fassung bleibt bestehen
- **Ein Abgleich Register ↔ geltende Ordnung**, Feld für Feld. Die Ordnung folgt dem Register absichtlich nicht von selbst: Sie wird beim Einbringen als Kopie an den Antrag geheftet (§ 5 Abs 5). Der Abgleich macht den Abstand sichtbar, statt ihn zu verschweigen
- **Das Flussdiagramm der Startseite liest seine Fristen aus dem Register.** Vorher standen 60, 21 und 28 als Text im Bild — wer eine Frist änderte, bekam auf der ersten Seite weiter die alte Zahl zu sehen

### Behoben
- **Der Archiv-Export war nicht vollständig.** `audit_spur()` schnitt auf die letzten 60 Ereignisse — gedacht als schmale Zeitleiste für die Anzeige, aber der Export benutzte dieselbe Funktion. Wer 200 Ereignisse hatte, bekam 60 und erfuhr es nicht. Das bricht die Zusage „vollständig" (§ 5 Abs 3 lit e) und Grundregel 7. Jetzt: Anzeige gekürzt **mit Hinweis**, Export vollständig
- **Der Zähler am Gesprächs-Griff zählte nur die ersten dreißig Gespräche** — er zeigte ausgerechnet dann zu wenig, wenn viel los ist, und verschwieg genau die Gespräche, für die er da ist
- **`policies/grundordnung-v1.yaml` entfernt.** Sie nannte sich „die QUELLE der Policies", wurde von keiner Zeile Code gelesen und trug Werte aus dem ersten Testbetrieb (14/21/7), die allem widersprachen, was gilt (60/21/28). Sie lag im Übertragungspaket — eine Partnerpartei hätte ihre Instanz danach gebaut. An ihrer Stelle liegt jetzt eine **erzeugte** Fassung der tatsächlich aktiven Ordnung
- Auf der Registerseite stand `ADR-007` in einer Quellenangabe — eine Kennung eines internen Dokuments, die der Wächter für Vorlagen nicht sieht, weil sie in Daten steht

### Technisch
- `plattform_core.policy.aus_register()` baut eine Verfahrensordnung aus Registerwerten. Fehlt ein Schlüssel, wirft sie: Eine Ordnung mit stillschweigend ergänzten Werten wäre schlimmer als gar keine
- **Die Satzungsminima bleiben im Code** (Beratung ≥ 21 Tage, Abstimmung ≥ 7, Beteiligung ≥ 5 %) und sind bewusst **keine** Stellgröße — sonst könnte die Verwaltung sie über das Register aushebeln. Ein Test belegt, dass sich eine satzungswidrige Fassung nicht erzeugen lässt
- Fünf Tests zu **Grundregel 4** (`parameter/test_grundregeln.py`): kein Parameter, der eine Stimme gewichtet; die Auszählung liest kein Register; jede Stimme zählt eins, unabhängig von der Reihenfolge; kein multiplizierender Code in den zählenden Modulen; der WeicherFilter fasst die Auszählung nicht an. Geprüft wird der Syntaxbaum, nicht der Text — sonst schlägt das Wort „Kreuzmultiplikation" in einer Erklärung Alarm
- Neue Migration `parameter/0003_register_v2.py` (Gruppe, Status, Testfelder, Änderungshistorie)

## [0.40.0] — 2026-09-04 · Die Partner-Seite spricht sechs Sprachen

### Hinzugefügt
- **Vier eigene Seiten für die Kurzfassungen (FB-M9):** `/partner/fr/`, `/partner/es/`, `/partner/it/` und `/partner/ja/`. Der Text steht in der Landessprache und trägt sein eigenes `lang` — der Rahmen bleibt englisch, denn die Plattform selbst gibt es nur auf Deutsch und Englisch, und mehr zu versprechen hieße, eine Übersetzungspflege zuzusagen, die niemand leisten kann
- **Eine Sprachleiste** auf allen Partner-Seiten: `English · Deutsch · Français · Español · Italiano · 日本語`. Die aktuelle Fassung ist markiert (`aria-current`), Deutsch und Englisch führen auf die vollständige Seite
- **Die Sprachautomatik führt weiter:** Wer mit spanischem Browser `/partner/` aufruft, landet auf `/partner/es/` statt auf der englischen Seite. Zwei Ausnahmen sind eingebaut — eine eigene Sprachwahl schlägt die Automatik, und **wer von der Plattform selbst kommt, wird nicht umgeleitet**: Sonst hätte der Weg „Kurzfassung → vollständige Seite auf Englisch" sofort wieder auf der Kurzfassung geendet
- `hreflang`-Angaben samt `x-default` auf allen sechs Fassungen, damit Suchmaschinen die richtige ausliefern

### Technisch
- Neu: `plattform_core/kurztext.py` (VERSION 1) — liest die Kurzfassungen aus `docs/partner/kurz/`. Bewusst **kein** Markdown-Übersetzer: Für Überschrift, Absätze und den kursiven Schlusssatz braucht es keine neue Abhängigkeit, und was die Datei sonst enthält, soll nicht unbemerkt durchrutschen. Das Arbeitsmaterial hinter dem waagrechten Strich (Glossar, offene Punkte) bleibt draußen
- Ein Test lädt **jede ausgelieferte Sprachfassung** und prüft, dass sie sich anzeigen lässt — sonst fiele eine kaputte Datei erst im Betrieb auf

## [0.39.7] — 2026-09-04 · Die Einladung an Partnerparteien in vier Sprachen

### Hinzugefügt
- **Die Partner-Kurzfassung in fünf Sprachen** (`docs/partner/kurz/`): `de.md` als Ausgangstext mit Belegtabelle, dazu **Französisch, Spanisch, Italienisch und Japanisch**. Acht bis zehn kurze Sätze — worum es geht, was wir geben, was wir suchen, wie es weitergeht —, gedacht als erster Kontakt für Menschen, die kein Deutsch lesen (FB-M9)
- **Ein Glossar je Sprache**, verbindlich für alles Weitere in dieser Sprache: Satzungs-Baukasten, Plattform-Rat, Übertragungspaket, Alpha-Phase, Instanz. Was hier festgelegt ist, gilt auf jeder künftigen Seite — deshalb steht es in der Datei und nicht im Kopf
- Jede Datei nennt am Ende, **was eine Muttersprachlerin noch ansehen sollte**. Das betrifft den Klang, nicht den Inhalt

### Wie die Übersetzungen geprüft wurden
- Jede Fassung wurde von einer zweiten Instanz **wörtlich ins Deutsche zurückübersetzt, bevor sie das Original gesehen hat**, und erst dann verglichen. Über zwei Runden: **kein einziger sinnändernder Fehler, keine verschobene Aussage** — die Unterscheidung frei/kostenlos, „eigene Server, eigenes Recht, eigene Sprache", „Daten verlassen die Instanz nie", „eine Stimme je Land", „Alpha-Phase" (nie „Prototyp") stehen überall unverändert
- Eine dritte Runde hat die benannten Idiomatik-Stellen behoben — etwa die Kollokation `dépouiller le scrutin` statt `les voix`, oder `移管パッケージ` (Übergang einer Behördenzuständigkeit) → `導入パッケージ`
- **Was offenbleibt:** Ob die Fassungen für Muttersprachler völlig unauffällig klingen, lässt sich so nicht abschließend prüfen; das Urteil darüber schwankte zwischen den Durchgängen. Die Sachtreue ist gesichert, die letzte Politur braucht einen Menschen mit dieser Muttersprache

### Dokumentation
- **Fahrtenbuch:** FB-M9 auf 🟡 — die Texte liegen vor, offen ist die Einbindung (Seiten `/partner/<sprache>/`, Sprachleiste, `hreflang`, Erweiterung der Sprachautomatik) und die Umstellung der drei Links auf ddoe.at; beides mit S14b

## [0.39.6] — 2026-09-04 · Kennzahlen ohne Schalter, ehrliche Angabe zum Übertragungspaket

### Geändert
- **Die Zählerklärung auf `/uebersicht/` nennt jetzt auch die Kennzahlen der Zukunftswerkstatt:** Sie entstehen als Summen, nie als Einzelwerte — „deshalb gibt es dafür nichts ein- oder auszuschalten (§ 6 Abs 11 lit d)". Das ist die sichtbare Seite der Entscheidung zu D-J7: Die Frage Opt-in oder Opt-out setzt eine personenbezogene Messung voraus, die die Satzung gar nicht erlaubt. Wird zusammengefasst, **bevor** etwas gespeichert wird, entstehen keine personenbezogenen Daten — dann braucht es keine Einwilligung und folgerichtig auch keinen Schalter
- **Das Übertragungspaket sagt jetzt, in welcher Sprache es vorliegt.** Weder die Partner-Seite noch der neue Text auf ddoe.at erwähnten, dass es überwiegend deutsch ist: Der Satzungs-Baukasten (rund 60.000 Zeichen) und das Schema haben gar keinen englischen Teil, Einstieg und Einrichtung je eine englische Zusammenfassung. Wer aus dem Ausland herunterlädt, wurde enttäuscht. Der Hinweis steht jetzt beim Knopf — mit dem Angebot, mit dem ersten Partner zu übersetzen, der es braucht. Derselbe Satz ist auf ddoe.at nachgezogen

### Dokumentation
- **Satzung (vom Gründer freigegeben):** § 5 Abs 13 neu (Form der Entscheidung der Unterstützer) und § 6 Abs 11 lit d präzisiert (Kennzahlen ohne Einwilligung). Der Satzungs-Baukasten für Partnerparteien trägt beide Änderungen automatisch — ein Test hat gemeldet, dass er nachzuziehen war
- **Fahrtenbuch:** FB-M9 neu (Partner-Seite in mehreren Sprachen, freigegeben, Zuordnung S14b); FB-M2 auf ✅ (die Bausteine sind auf ddoe.at eingespielt); D-J7 als entschieden eingetragen, mit vier Bauvorschriften für S13 — kein Ereignisprotokoll, keine Kennung im Erhebungsweg, Mindestzahl gegen Rückschluss, ein Test gegen Fremdschlüssel auf Mitglieder

## [0.39.5] — 2026-09-04 · Die Partner-Seite begrüßt die Welt auf Englisch

### Geändert
- **Wer nicht ausdrücklich Deutsch möchte, sieht `/partner/` auf Englisch (FB-M1)** — auch bei Spanisch, Französisch, Japanisch oder ganz ohne Sprachangabe. Bisher fiel jede Sprache, die weder Deutsch noch Englisch ist, auf die Voreinstellung `de-at` zurück: ausgerechnet auf der einen Seite, deren Zielgruppe per Definition nicht deutschsprachig ist. Eine **eigene Sprachwahl behält immer Vorrang** — wer auf DE stellt, bekommt Deutsch. Die Regel gilt nur für diese Seite; das Parlament bleibt unberührt
- Die Bildschirmtests legen die Browsersprache jetzt **ausdrücklich** fest (`de-AT`). Vorher erbten sie die Sprache des Rechners — dieselben Tests prüften auf einem englischen System eine andere Oberfläche, ohne dass es auffiel

### Hinzugefügt
- Vier Tests für die Sprachregel, ein Bildschirmtest über vier Sprachen, und einer, der belegt, dass die Regel nicht auf andere Seiten abfärbt

### Dokumentation
- **Fertige Bausteine für ddoe.at** (`ddoe-at_Partner-Verlinkung_2026-09-04.md` im Arbeitsordner): der Knopf „Start a sister party — the partner page →" in der Sektion „International", ein Absatz samt Knopf **vor** dem `mailto:` unter „An invitation", je ein Link an den Absätzen FR · ES · IT, optional ein Nachsatz im Blogpost vom 19.08. Einspielen kann sie nur der Gründer — die Zugangsdaten der Website liegen nicht in diesem Ordner
- **Satzungsbaustein § 5 Abs 13** für die Unterstützer-Schleife (`Satzungsbaustein_Unterstuetzerschleife_2026-09-04.md`): Form der Entscheidung, Bezugsbeitrag der Plattform, „oben **und** über der Schwelle", Stille als Annahme, Textstellenbezug für Einwände, Offenlegung der Reihung. Ein neuer Absatz, keine Nummer verschiebt sich
- **Fahrtenbuch:** FB-K6 „Rollenübersicht (Wer darf was)" neu aufgenommen (vom Gründer freigegeben, Umsetzung nach S8 ff.); FB-M1 und FB-M2 nachgezogen; Kopf, Fußzeile, FB-K2 und FB-P1 auf den Stand vom 4.9. gebracht — das Dokument hinkte der Auslieferung um fünf Fassungen hinterher

## [0.39.4] — 2026-09-04 · Ein Weg zurück, eine zweisprachige Verwaltung, keine internen Kürzel mehr

Drei Entscheidungen des Gründers vom 4.9.2026, umgesetzt.

### Hinzugefügt
- **Eigene Fehlerseiten (404, 403, 500) — der Weg zurück.** Bisher lieferte die Produktion Djangos nackte englische Minimalseite: keine App-Leiste, keine Gestaltung, kein Weg zurück, mitten in einer deutschen Anwendung. Jetzt: **404** im App-Look mit „Zum Parlament" und „Zur Startseite" und dem Hinweis, dass der Inhalt nicht verloren ist — Verfahren werden hier nicht gelöscht; **403** für die abgelaufene Sitzung mit dem Weg zur Anmeldung; **500** bewusst **selbsttragend** — sie erbt nicht von `base.html`, bringt ihre wenigen Farben selbst mit und kommt ohne Skript und ohne Datenbankzugriff aus, damit sie auch dann steht, wenn die Anwendung fällt
- Fünf Tests dazu, darunter einer, der eine unbekannte Adresse abruft und prüft, dass wirklich die **eigene Seite** kommt. Die bisherigen Tests prüften nur den Statuscode — deshalb fiel es nie auf

### Geändert
- **Die Verwaltung spricht Englisch (Fahrtenbuch „laufend": i18n der Verwaltung).** Acht Seiten waren komplett unübersetzt — wer umschaltete, bekam dort weiter Deutsch: Anstöße, Mitgliederliste, einzelnes Mitglied, Beiträge & Bank, kein-Zugang, Rollen, Mandate, Parameter. Jetzt sind sie es, mit **139 neuen Katalogeinträgen** (1186 gesamt, 0 ohne Übersetzung). Auch die Statuswörter der Anstöße („neu", „gesichtet", „erledigt") sind übersetzbar — sie standen als nackte Zeichenketten im Modell und wären sonst deutsch geblieben
- **Interne Kennungen sind aus allen Nutzer-Texten verschwunden.** `F-22`, `F-23`, `F-43`, `F-47`, `F-59`, `F-60`, `F-68`, `ADR-006`, `Ring 0b` standen im Archiv jeder Antragsseite, im Parameterregister, im Beitrittsformular, im Umsetzungsregister und in den Hilfetexten der Formulare — für Besucher Rauschen, teils Verweise auf Dokumente, die gar nicht öffentlich sind. Im Quelltext (Kommentare, Docstrings) bleiben sie: dort helfen sie beim Arbeiten
- **Die Quellenangaben des Parameterregisters nennen nur noch Nachlesbares:** statt „A0-07 („mehr als 50%") · § 5 Abs 12 · FB-G6" jetzt „§ 5 Abs 12 · Anweisung des Gründers: „mehr als 50%"". Der Satzungsbezug und das wörtliche Zitat bleiben — sie sind der eigentliche Nachweis (§ 2 Abs 6). Bestehende Registereinträge werden beim Deploy nachgezogen; der **Wert** bleibt unangetastet, die Quelle ist Beschreibung
- Auf `/zukunftswerkstatt/` steht „Satzungsentwurf 2.5" statt 2.3, und die Unterstützer-Schleife ist nicht mehr „Zielbild", sondern gebaut — für sie liegt ein eigener **Satzungsbaustein zur Beschlussfassung** vor (§ 5 Abs 13 neu, im Arbeitsordner des Gründers)

### Behoben
- Verschachtelte doppelte Anführungszeichen in fünf Attributen (`data-label="{% translate "Wann" %}"`) — für Django gültig, im Quelltext gebrochenes HTML
- Vier veraltete Code-Kommentare, die „die gesamte Verwaltung ist bewusst nur deutsch" behaupteten

### Hinzugefügt (Wächter)
- **Gegen interne Kennungen** in Nutzer-Texten und in den Quellenangaben des Registers. Er hat sich gleich bewährt: Er fing eine Kennung, die mit den neuen Übersetzungen hereinkam

## [0.39.3] — 2026-09-04 · Die Sprachregeln gelten überall — und ein Wächter hält sie

### Geändert
- **„Prototyp" ist aus allen Nutzer-Texten verschwunden** (FB-K2, seit 2.9. offen): Die Statuszeile der README heißt „Alpha-Phase — die Plattform ist öffentlich", der Demo-Antrag „Namenskonvention der Plattform", die Betriebs- und Konzeptdokumente sprechen von der Alpha-Phase. Damit sind die drei im Fahrtenbuch benannten Stellen erledigt

### Hinzugefügt
- **Ein Wächter über die Sprachregeln** (`verfahren/test_vorlagen.py`): Kein Nutzer-Text darf „Prototyp", „Regierungsform", „Vorlage" (im Sinne des Vorschlags) oder „Minderheiten" enthalten. Geprüft wird der Übersetzungskatalog — dort stehen genau die Texte, die Nutzer lesen; Kommentare und Bezeichner im Code sind nicht gemeint. Begründete Ausnahmen stehen benannt im Test („Docker- und Render-Vorlage" ist eine Einrichtungsdatei). Gegen einen erfundenen Verstoß gehalten: Er schlägt an und nennt Wort und Fundstelle

### Anmerkung
- Der Demo-Antrag heißt erst auf einer **frischen** Datenbank anders; in der laufenden Produktion trägt er weiter seinen alten Titel. Ihn dort umzubenennen hieße, den Titel eines abgestimmten Antrags nachträglich zu ändern — das entscheidet der Gründer, nicht der Code

## [0.39.2] — 2026-09-04 · Durchgang durch alles, was der Nutzer zu sehen bekommt

Nach dem gemeldeten Kommentartext (0.39.1) haben vier unabhängige Durchgänge jede Seite auf Dinge
abgesucht, die dort nicht hingehören. Von 30 Meldungen hielten 23 der Nachprüfung stand; die
eindeutigen sind hier behoben, die Entscheidungsfragen liegen dem Gründer vor.

### Behoben
- **Das Gesprächs-Panel blieb auf „Meine Gespräche" für immer auf „Wird geladen …" stehen.** Ursache: Das Panel liegt auf jeder Seite und brachte die Kennung `#gespraeche-liste` mit; auf `/gespraeche/` trug die Seitenliste dieselbe Kennung. htmx nimmt beim Auflösen seines Ziels den **ersten** Treffer im Dokument — also tauschte das Panel die Liste hinter sich aus und füllte sich selbst nie. Die Teilvorlage nimmt jetzt eine eigene Kennung entgegen
- **Auf `/mandatare/` stand der rohe Datenbankwert der Phase** („· abstimmung" statt „· Abstimmung") — öffentlich sichtbar, ohne Anmeldung
- **Das Archiv beschriftete abgeschlossene Verfahren mit „· läuft"** (FB-G7). „Läuft" steht jetzt nur noch an der wirklich laufenden Phase, nie an einem Endzustand
- **Die Phasennamen im Archiv waren hart deutsch** und blieben in der englischen Oberfläche stehen. Sie kommen jetzt aus dem gemeinsamen, übersetzten Bestand — dieselbe Phase heißt überall gleich
- **Im WeicherFilter-Feed stand der Phasenname zweimal** in derselben Zeile („angenommen" als Abzeichen, darunter noch einmal „angenommen · 31.08.2026"). Unten steht jetzt nur noch „seit 31.08.2026"

### Geändert
- **Sprachregeln aus CLAUDE.md durchgesetzt:** „Der Prototyp enthält …" auf `/uebersicht/` heißt jetzt „Die Plattform ist in der Alpha-Phase und enthält …" (nie „Prototyp"); auf `/zukunftswerkstatt/` steht dreimal „Vorschlag" statt „Vorlage". Der englische Katalog zieht mit („proposal" statt „draft")
- **Die drei Gremien-Ansichten siezen**, wie die ganze übrige Plattform: „Sie sehen diesen Bereich als Aufsicht (Verwaltung) …"

### Hinzugefügt
- **Ein Wächter gegen doppelte Kennungen** (`verfahren/test_vorlagen.py`): Keine Seite darf dieselbe `id` zweimal vergeben — geprüft für Gespräche, Parlament und Antragsseite. Gegen den echten Fehler gehalten: Er schlägt an und nennt die doppelte Kennung
- Ein Bildschirmtest öffnet das Panel **auf `/gespraeche/` selbst** — dort, wo der Fehler saß (`tests/e2e/test_chat.py`)
- Tests für die Archiv-Korrekturen: Phasennamen folgen der Sprache, Endzustände laufen nicht mehr (`verfahren/test_archiv.py`)

## [0.39.1] — 2026-09-04 · Behoben: Kommentartext stand auf jeder Seite

### Behoben
- **Am linken Rand jeder Seite stand roher Kommentartext** (vom Gründer gemeldet). Ursache: In `_gespraeche_panel.html` war eine Entwickler-Anmerkung als `{# … #}` über **zwei Zeilen** geschrieben. Django wertet diese Kurzform nur **einzeilig** aus — mehrzeilig wird der Kommentar zum Seiteninhalt. Weil das Gesprächs-Panel über den Kontextprozessor auf jeder Seite liegt, war der Text überall zu sehen, seit 0.38.0. Die Anmerkung steht jetzt in einem `{% comment %}`-Block

### Hinzugefügt
- **Ein Wächter gegen genau diesen Fehler** (`verfahren/test_vorlagen.py`): Kein Template darf einen mehrzeiligen `{# … #}`-Kommentar enthalten, jeder `{% comment %}` muss geschlossen sein, und **keine ausgelieferte Seite** darf Reste der Vorlagensprache im sichtbaren Text tragen — geprüft als Gast und als Mitglied über Startseite, Parlament, Antragsseite, Archiv-Export, Parameterregister und Gespräche. Der Wächter wurde gegen den echten Fehler geprüft: Mit dem alten Kommentar schlägt er an und nennt Datei und Zeile

## [0.39.0] — 2026-09-04 · S7: Der Abstimmungs-Chat zum Vorschlag und das Archiv

### Hinzugefügt
- **Der Abstimmungs-Chat (FB-G6):** Sobald der Expertenrat seinen Vorschlag eingereicht hat, öffnet sich Zone 3 neu — als Abstimmung, die als Gespräch geführt wird. Oben steht der **Vorschlag als gepinnte Karte** mit Gold-Rahmen und einem aufklappbaren **Wort-Diff zum Antrag** (Einfügungen grün, Streichungen rot durchgestrichen, „+12 / −3 Wörter“). Darunter der Faden, **nach Engagement gereiht**
- **Der Systembeitrag „✓ Passt alles"**: Die Plattform legt ihn beim Öffnen an — ohne Verfasser, deutlich als Systembeitrag. Er ist der Beitrag, auf den sich die Auswertung bezieht, damit niemand raten muss, welcher Beitrag Zustimmung zum Vorschlag bedeutet
- **Zustimmen und Ablehnen (👍 / 👎)** an jedem Beitrag: eine Reaktion je Mitglied, umschaltbar bis Fristende. **Reagieren dürfen nur die Unterstützer** des Antrags — das ist ihre Abstimmung nach § 5 Abs 12; alle anderen sehen die Zähler und dürfen mitreden
- **Kritik mit Textstellenbezug:** Ein Umschalter „Das ist konkrete Kritik am Vorschlag" verlangt einen **Absatz des Vorschlags** und mindestens 80 Zeichen — ohne beides wird der Beitrag nicht als Kritik angenommen. Kritik-Beiträge tragen ein rotes Etikett „Kritik · Absatz 3" und gehen bei einer Rückgabe als **Wünsche der Unterstützer** ins Entwurfsfenster, nach Engagement gereiht
- **Das Archiv (FB-G7):** ein vierter Reiter an jeder Antragsseite. Eine **Zeitleiste** von der Antragstellung bis heute, je Phase ein aufklappbarer Block mit den Beiträgen, die dort geschrieben wurden — auch denen, die bei einer Hochstufung geräumt wurden. Dazu die Runden des Expertenrats mit Fassungen und Prüfungen, die **Auswertung jeder Vorschlagsrunde** („Passt alles 67 % · an erster Stelle · zur Endabstimmung") und die **Audit-Spur** mit Hash-Kurzform. Öffentlich lesbar wie die Antragsseite
- **Export des Archivs** als **JSON** (vollständig, mit Antwortbezug und Reaktionszählern) und **Markdown** (lesbar, gleiche Gliederung), Dateiname `antrag-<id>-archiv.<ext>`. Ohne Kontaktdaten — Anzeigenamen wie überall
- **Die Ruhephase (FB-G6):** Während der Expertenrat am Vorschlag arbeitet, ruht der Chat. Ein Band sagt es, Mitlesen bleibt möglich, die Eingabezeile weicht einem Hinweis
- Die Demo zeigt den Abstimmungs-Chat jetzt: ein Antrag mit eingereichtem Vorschlag, „Passt alles" mit 2 👍 / 1 👎 und einer Kritik am ersten Absatz

### Geändert
- **Das Votum-Formular ist abgelöst (FB-G6):** Wo die Unterstützer bisher „annehmen / mit Wunsch zurückgeben" angeklickt haben, entscheiden sie jetzt im Chat. Die Auswertung nach Fristablauf verlangt **beides** — der Beitrag „Passt alles" muss **an erster Stelle stehen** *und* **mehr als 50 %** Zustimmung tragen (Parameter `vorschlag-annahme-prozent`); sonst geht der Vorschlag mit der Kritik zurück an den Expertenrat. **Stille hemmt nie**: Liegt keine einzige Reaktion vor, geht der Vorschlag weiter (§ 5 Abs 12)
- Ausgewertet wird **erst nach Fristablauf** — vorher sind Reaktionen umschaltbar. Bisher wertete die Schleife sofort aus, sobald alle Unterstützer gestimmt hatten
- Das Entwurfsfenster zeigt statt der Votenliste den Live-Stand „Passt alles: 2 👍 / 1 👎 (67 %) · 1 Kritik-Beitrag" mit Weg in den Chat, und bei einer Überarbeitung die **Wünsche der Vorrunde** mit Absatzbezug und Zählern
- Bestehende Voten wurden in den Chat überführt: annehmen → 👍, zurückgeben → 👎 samt Wunsch als Kritik-Beitrag. Die Voten selbst bleiben als Nachweis stehen (Grundregel 7)

### Technisch
- Neu: `plattform_core/vorschlagschat.py` (Regel `engagement-v1`, versioniert und nachrechenbar) und `plattform_core/wortdiff.py` (Wort-Diff auf Wortebene statt Zeilenebene), beide framework-frei und einzeln getestet
- Neu: `verfahren/archiv.py` — eine Quelle für Anzeige, JSON und Markdown
- `Kommentar` um `system`, `ist_kritik` und `bezug_absatz` erweitert; `mitglied` darf leer sein (Systembeitrag). Migrationen `verfahren.0014_abstimmungschat` und `gremien.0003_voten_in_den_abstimmungschat`
- Neue Registereinträge `vorschlag-annahme-prozent` (50) und `vorschlag-chat-reihung` (1) mit Schema-Kennungen in `docs/SCHEMA.md`
- Tests: `plattform_core/test_vorschlagschat.py` (11), `plattform_core/test_wortdiff.py` (7), `verfahren/test_archiv.py` (7), `tests/e2e/test_abstimmungschat.py` (5); 703 Tests und 51 Bildschirmtests grün, Katalog vollständig (1045 Einträge)

## [0.38.0] — 2026-09-04 · S6: Das Chatsystem — Faden, Gedächtnis, Gespräche, Räumung

### Hinzugefügt
- **Ein eigenes Chatsystem (FB-G1):** Aus der flachen Kommentarliste wird ein Faden aus Sprechblasen. Jeder Beitrag zeigt einen Initialen-Kreis (Farbton aus dem Namen), den Anzeigenamen, die Zeit relativ („vor 2 Std.“) und darunter die Zeile „Antworten · Zustimmen · Ändern · Zurückziehen · Melden“. **Antworten stehen eine Ebene eingerückt** unter ihrem Beitrag; tiefere Antworten bleiben auf dieser Ebene. Eigene Beiträge tragen eine Gold-Kante, jeder Beitrag einen Anker `#k-<id>`
- **Die Eingabezeile klebt unten:** Das Feld wächst bis sechs Zeilen mit, der Zeichenzähler erscheint ab 3.500 von 4.000. „Antworten“ setzt die Zeile in den Antwort-Modus (Chip „Antwort an Mitglied 3 ×“). Gesendet wird per htmx — der neue Beitrag gleitet ein, das Feld leert sich, die Seite lädt nicht neu. Ohne JavaScript ist es ein gewöhnliches Formular, das auf den Anker zurückspringt
- **Ändern und Zurückziehen:** Ändern geht in den ersten fünf Minuten (danach steht „bearbeitet“ dabei), Zurückziehen ersetzt den Text durch „[vom Verfasser entfernt]“ — die Antworten darunter bleiben stehen
- **Zustimmen (👍):** eine Zustimmung je Mitglied und Beitrag, rein informativ. Sie ändert **keine** Reihung (Grundregel 6); die Reihung bleibt chronologisch
- **Melden und Ausblenden (Art 16 DSA, § 5 Abs 2):** Jeder Beitrag lässt sich mit Grund melden. Die Verwaltung kann einen Beitrag ausblenden — der Grund steht öffentlich an seiner Stelle, der Vorgang im Audit
- **Das Scroll-Gedächtnis (FB-G2):** Die Chatleiste steht wieder dort, wo man aufgehört hat zu lesen — auch nach einem Ausflug auf andere Seiten und nach einem Neustart des Browsers. Gemerkt wird nicht die Pixelzahl, sondern **welcher Beitrag** im Blick stand (gedrosselt alle zwei Sekunden und beim Verlassen der Seite, je Antrag und Gerät). Beim Öffnen wird die Stelle ohne Animation wiederhergestellt und nachgezogen, bis das Layout steht; wer selbst scrollt, wird nicht mehr angefasst. Dazu die goldene Trennlinie **„n neue Beiträge“** aus dem serverseitigen Lesestand — geräteübergreifend und auch ohne JavaScript (Anker `#neu`)
- **„Meine Gespräche“ (FB-G3, FB-G4):** Am linken Bildschirmrand klebt ein Griff mit der Zahl ungelesener Gespräche; dahinter gleitet ein Panel von links herein (Schleier, Escape, Fokusfalle). Die Liste zeigt drei Spalten — **Thema · Antrag · Chatpartner** — mit Vorschau, Zeit und Gold-Punkt bei Ungelesenem, und führt mit einem Klick direkt zum Beitrag des Gegenübers, der dort kurz gold aufleuchtet. Ein Gespräch entsteht **implizit**, sobald zwischen zwei Menschen an einem Antrag eine Antwort liegt — niemand muss jemanden benennen. Am Handy entfällt der Randgriff; dort führt das sechste Ziel der Tableiste auf `/gespraeche/`, dieselbe Liste als eigene Seite

### Geändert
- **Chats werden bei jeder Hochstufung geräumt (FB-G5):** Rückt ein Antrag eine Phase weiter, werden alle Beiträge der vorigen Phase mit `archiviert_am` gestempelt. Sie verschwinden aus dem Chat und aus den Gesprächen; Zone 3 beginnt leer mit dem Phasen-Band „Beratung begonnen am … — n Beiträge aus der vorigen Phase im Archiv“. **Gelöscht wird nichts** (§ 5 Abs 3 lit e) — der Audit-Eintrag des Übergangs führt die Zahl mit. Der Stempel greift an beiden Stellen, an denen die Phase vorrückt (Phasenautomatik und Öffnen der Endabstimmung), ist idempotent und trägt den Zeitpunkt des Übergangs
- Der Chat ist **geschlossen**, während der Expertenrat arbeitet, und nach Verfahrensende — mitlesen bleibt möglich, die Eingabezeile weicht einem Hinweis. Gäste lesen mit und sehen statt der Zeile den Anmeldehinweis
- Die Tableiste am Handy hat ein sechstes Ziel „Chats“ (nur für Mitglieder)

### Technisch
- Neu: `verfahren/chat.py` (Regeln), `verfahren/kontext.py` (Zähler auf jeder Seite), `verfahren/templatetags/chat.py`, Migration `0013_chatsystem.py` mit Nachtrag der Phase für vorhandene Beiträge
- Neue Modelle `Reaktionsart`, `Reaktion`, `Lesestand`, `Meldung`; `Kommentar` um `antwort_auf`, `phase`, `bearbeitet_am`, `archiviert_am`, `geloescht`, `ausgeblendet_am`, `ausgeblendet_grund` erweitert
- Tests: `verfahren/test_chat.py` (14) und `tests/e2e/test_chat.py` (6); 677 Tests grün, Katalog vollständig (996 Einträge)

## [0.37.0] — 2026-09-04 · S5: Die Antragsseite in drei Zonen — Text · Einschätzung · Chat

### Geändert
- **Die Antragsseite ist neu gebaut (FB-F1):** aus einer langen Spalte werden drei Zonen. Auf dem Desktop stehen **Text (58 %) links** und **Einschätzung (42 %, klebend) rechts** nebeneinander — die Einschätzung ist die Lesehilfe zum Text —, der **Chat** darunter über die volle Breite. Darüber eine **Reiterleiste**, die unter der App-Leiste klebt: Beim Scrollen markiert sie die Zone, in der man liest (am Seitenende gewinnt der Chat). Am Handy ist nur eine Zone sichtbar; die Reiter schalten um, waagrechtes **Wischen** blättert weiter. Ohne JavaScript stehen alle Zonen untereinander und die Reiter sind gewöhnliche Ankerlinks
- **Der Kopf ist aufgeräumt:** Zurück-Pfeil, Titel, Chip-Zeile (Phase farbig, Ebene · Ort, Lebensbereiche als klickbare Chips), Stern rechts, eine Meta-Zeile, bei Hervorhebung ein Gold-Band
- **Zone „Text":** Wortlaut in Lesegröße (17 px, höchstens 75 Zeichen je Zeile), darunter die **Handlungskarte der Phase** (Unterstützen · Bewerbungen · Abstimmen · Ergebnis · Umsetzung) mit goldener Kante. Bewerbungen erscheinen als Karten mit Initialen-Zeichen (FB-F4)
- **Die eingefrorenen Regeln stehen jetzt lesbar (FB-F1):** „Unterstützungsschwelle 3 · Frist zum Unterstützen 60 Tage · Beratung 21 Tage · Abstimmung 7 Tage · Mindestbeteiligung 5 % · Mehrheit: Ja mehr als Nein" — statt eines JSON-Blocks. Das JSON bleibt eine Ebene tiefer unter „Rohdaten"; alle Fassungen sind aufklappbar

### Hinzugefügt
- **Zone „Einschätzung" (FB-F2):** die Kopfkarte mit der Kennzeichnung **„Modellrechnung — sie schlägt vor, sie entscheidet nie"** (Grundregel 5), Modell, Stand und Lauf-Nummer mit Link ins Archiv. Liegt noch keine Rechnung vor, sagt die Zone das ehrlich und zeigt als **Skelett-Umrisse**, was kommen wird (Ähnliche Anträge · Berührte Gesetze · Folgen für Judikatur und Exekutive · Aufwand, Last und Dauer · Ausschreibung). Bei **Personenwahlen entfällt die Zone** — über Menschen rechnet keine Maschine (FB-F4)
- **Beanstanden (§ 6 Abs 11 lit b):** Mitglieder halten einen Fehler in der Einschätzung öffentlich fest; der Vermerk trägt den Namen, bleibt stehen (append-only) und ist zugleich die Anforderung eines Korrekturlaufs. Jede Beanstandung geht in die Audit-Kette; die Antwort der Werkstatt erscheint darunter
- 12 neue Tests (7 Einbau, 5 Bildschirmtests) und vier Bilder der Antragsseite in der Sichtprüfung — 668 gesamt

## [0.36.0] — 2026-09-03 · S14a: Internationale Zusammenarbeit — ein Kern, viele Instanzen

### Hinzugefügt
- **Das sprachneutrale Parameter-Schema (FB-M5, § 12 Abs 5)** in `plattform_core/schema.py` (Version 1.0, rein und getestet): jede Stellgröße trägt neben ihrem deutschen Registerschlüssel eine englische, stabile Kennung (`support.threshold`, `deliberation.window_days`, `draft_loop.max_rounds` …). Dazu sieben aggregierte Kennzahlen (`members.active`, `votes.turnout_mean`, `implementation.by_status` …) und eine Prüfung, die fremde Exporte gegen das Schema hält und personenbezogene Felder beanstandet. Dokumentiert in **`docs/SCHEMA.md`**, entschieden in **ADR-009**
- **`/kennzahlen.json`** — der aggregierte Lernfortschritt dieser Instanz (Mitglieder, Anträge je Phase, abgeschlossene Abstimmungen, mittlere Beteiligung, Umsetzungsstände, Lebensbereiche). Zählungen und Anteile über das Ganze, nie über einen Menschen
- **`/parameter.json` erweitert:** Kopf mit `schema_version`, `system_id`, `system_name` und Softwarestand, Schema-Kennung je Eintrag und die aktive Verfahrensordnung als Kennungsliste. Die bisherigen Felder bleiben unverändert; neues Feld `schema_key` im Register (Migration trägt die Kennungen nach), Instanz-Kennung über `DDOE_SYSTEM_ID`
- **Die Partner-Seite neu (FB-M1, M6, M7, M8):** die **Gemeinsame Vision** (Fassung 0.1, Entwurf zur Freigabe), das Modell **„Ein Kern, viele Instanzen"** mit Schaubild (Kern, Landesinstanzen, Parameter-Schema als Brücke, wandernde Kennzahlen), die **Schnittstelle** als Tabelle mit allen offenen Adressen, der **Einstieg in zwei Spuren** (bestehende Partei umgestalten · neu gründen) und das Übertragungspaket
- **Das Übertragungspaket (FB-M7)** unter `/partner/paket/` als ZIP, erzeugt aus dem Repo-Stand: Gemeinsame Vision, Einstiegs-Fahrplan, Einrichtungs-Checkliste, **Satzungs-Baukasten**, Schema, Instanz-Vorlagen (`docker-compose.yml`, `env.example`, `render.yaml`), Kategorienbaum, Verfahrensordnung und der Erstbestand der Stellgrößen mit Kennungen
- **`tools/satzung_baukasten.py`** erzeugt den Satzungs-Baukasten aus der Satzung: österreichische Eigennamen und Rechtsbezüge werden zu Platzhaltern (`[PARTEINAME]`, `[LAND]`, `[REGISTRIERUNGSBEHÖRDE]` …), vorangestellt eine Einordnung, welche Paragrafen den Kern des Modells bilden und welche Landesrecht sind
- 19 neue Tests (Schema-Kern, Exporte, Partner-Seite, Paket, Baukasten) — 656 gesamt

### Geändert
- **Der Ordner `docs/fahrtenbuch/` ist nicht mehr im Repository** (`.gitignore`): Bauplan, wörtliche Anweisungen des Gründers, Soll/Ist, Inventar, Website-Prüfung und Satzungsentwurf sind interne Arbeitsdokumente. Öffentlich ist das Erzeugnis in `docs/partner/`. Werkzeug und Test arbeiten ohne den Ordner weiter; die Dateien der Historie bleiben davon unberührt
- 52 englische Texte für die Partner-Seite ergänzt

## [0.35.0] — 2026-09-02 · S3: Der WeicherFilter komplett — neun Regler, Favoriten zuerst, Profil-Leiste, Overlay, Live-Vorschau

### Hinzugefügt
- **Regel v2 des WeicherFilters (FB-B1, FB-B2, FB-B6)** in `plattform_core/weicherfilter.py`: neun Regler mit dem Wortlaut des Fahrtenbuchs — *Mehr wie das, wofür ich gestimmt habe · … wogegen ich gestimmt habe · … was ich unterstützt habe · Interessantes außerhalb meiner Favoriten · Mehr Unterstützungsanträge · Mehr Abstimmungen · Mehr chronologisch (Neues zuerst) · Nur noch kurz online · Wenig fehlt*. Wofür und wogegen sind zwei Regler (D-B2); „Nur noch kurz online" misst die eigene Phasendauer statt pauschal 60 Tage; „Wenig fehlt" kennt jetzt auch die Mindestbeteiligung einer Abstimmung. Punkte = Σ Regler × Merkmal, jedes Merkmal in [0, 1], Gleichstand behält die Grundordnung — nachzulesen unter `/parameter/#weicherfilter`
- **„★ Favoriten zuerst" (FB-B1):** in der neutralen Voreinstellung stehen Anträge aus abonnierten Lebensbereichen innerhalb jeder Phase vorn; der Schalter ist als Chip im Feldkopf sichtbar und abschaltbar (je Konfiguration und für die Voreinstellung, `favoriten_zuerst` an `FilterProfil` und `Mitglied`) — eine offene Partition, keine verdeckte Reihung
- **Die Feed-Zeile (FB-B1):** Titel mit Stern, farbige Chips (Abstimmung gold, Beratung petrol, Unterstützung grau; Ebene · Ort; Lebensbereich), Mini-Balken mit „2 von 3 Unterstützungen · noch 59 Tage" bzw. „40 % Beteiligung", rechts die Direkt-Handlung der Phase (Unterstützen / Abstimmen ▸ mit Ja · Nein · Enthaltung inline / Mitreden / Zur Wahl ›), Gold-Haken „Erfasst" nach der Handlung. Bei aktivem Profil eine einzige punktgereihte Liste und je Zeile das Aufklapp-Feld **„Warum hier?"** mit der Rechnung je Regler (statt des Tooltips, der auf Touch unerreichbar war)
- **Profil-Leiste mit Pfeil (FB-B4):** 40 px unter dem Feldkopf mit Chips Neutral · Konfigurationen · „● Ungespeichert" · ⚙ Regler; der runde Pfeil fährt sie in 260 ms ein, übrig bleibt ein 14-px-Griff, der Zustand wird je Gerät gemerkt (`localStorage` `ddoe.filterleiste`); der aktive Name bleibt im Feldkopf lesbar
- **Regler-Overlay von rechts (FB-B5):** 340 px (Handy: volle Feldbreite), halbtransparent mit Weichzeichner, gleitet in 320 ms herein, der Feed darunter bleibt sichtbar. Kopfzeile mit Name, „● Ungespeichert", Stift (Umbenennen inline) und ×; Schalter, neun Regler mit Wert und `aria-valuetext`; Aktionszeile Speichern (nur bei Änderung) · Als neue Konfiguration speichern (Inline-Namensfeld; bei 5/5 „eine löschen oder überschreiben") · Zurücksetzen · Löschen mit Inline-Rückfrage; Escape und Außenklick schließen, der Fokus kehrt zum Auslöser zurück; auch das ⚙-Symbol im Feldkopf öffnet
- **Live-Vorschau (FB-B2):** beim Ziehen eines Reglers ordnet htmx nach 400 ms Ruhe nur die Liste neu (`filter/vorschau/`, speichert nichts); ohne JavaScript bleiben Regler und Formular nativ bedienbar
- **Konfigurationen (FB-B3):** Umbenennen (`filter/<pk>/umbenennen/`), Löschen mit Rückfrage, Namen bis 24 Zeichen, Schalter je Konfiguration; Datenmigration übernimmt alte Reglerstände (`gestimmt` → `ja` und `nein`)
- 35 neue Tests (Kern v2, Einbau, Parameterseite, Datenmigration, fünf Bildschirmtests) — 646 gesamt

### Geändert
- **Der Stern steht überall (FB-C4):** an jedem Antrag und jedem Lebensbereich — im Fächer, im Feed, in den Kacheln, in der Feldsuche, auf der Startseite, der Antragsseite und im Umsetzungsregister. Mitglieder schalten ihn, Gäste sehen denselben Stern als Weg zur Anmeldung (bisher sahen Gäste gar keinen)
- Die Parameterseite erklärt die Regel v2 Regler für Regler (Anker `#weicherfilter`); der Link im Overlay heißt „Regel v2 nachlesen ›"
- Englischer Katalog um 57 Texte ergänzt (darunter Reste aus S2: „Mitreden", „Erfasst", „Unterstützt")

## [0.34.0] — 2026-09-02 · S2/S4: Kacheln nach Vorgabe und der Favoriten-Fächer mit fünf Ebenen

### Hinzugefügt
- **Der Favoriten-Fächer nach Layout-Regel v2 (FB-C1, FB-C2, FB-C3):** immer **fünf Ebenen** — Anker 24 px, darüber 22/20/18/16 px — nach der Auffächer-Regel: Ebenen bis zwölf Knoten vollständig, die erste größere nur für den **entfalteten Ast** (drei Kinder nebeneinander, deren Kinder als kleine Säule, ab dem vierten „+n"). Im Ruhezustand ist der Ast des ersten Favoriten entfaltet; alle Äste kommen vorab mit, Alpine blendet beim Zeigen um — keine Netzlast. Neuer deterministischer Kern `plattform_core/faecher.py` (VERSION 2): Randpillen bündig, bis zu drei versetzte Reihen, jede Pille mit zugeteilter Breite b = r·Spanne/(n−1+r) als `max-width` und CSS-Ellipse, voller Name als Tooltip, Prozentlagen, damit der Fächer sein Feld füllt und bei mehr Platz luftiger wird. **Rechenprobe über alle 312 Anker und alle Äste: keine zwei Pillen überlappen** (`tests/test_faecher_layout.py`, 320 Fälle), dazu die Bildschirmprobe in `tests/e2e/test_faecher.py`
- **Optik und Bewegung des Fächers:** Säulentöne (12 % je Säule, ohne Beschriftung), Faden bis zur Wurzel wird beim Zeigen gold und 2 px, Klick zoomt vom Klickpunkt hinein (320 ms) bevor htmx das Feld tauscht, Mitte-Modus ab Tiefe 3 mit **vollständigem Rückweg** bis zur Wurzel, **Brotkrume** im Feldkopf, Suchtreffer heben den Anker 1,5 s gold hervor. Handy: 20/18/16/15/14 px, Fächer ≥ 600 px breit und waagrecht rollbar, der Feldkörper zeigt zuerst den Anker
- **Stern-Tausch ohne Feldflackern (FB-C4):** `kategorie_abonnieren` antwortet auf htmx nur mit dem Stern (`_kategorie_stern.html`, `aria-pressed`, Pop 220 ms) — im Fächer, in der Feldsuche und im Kachelkopf; ohne JavaScript wie bisher Seitenwechsel mit Meldung
- **Kachel nach Vorgabe (FB-D1, FB-D2, FB-D3):** Thema-Chip mit eigenem Themen-Stern, Titel (ganze Kachel klickbar, Knöpfe bleiben eigene Ziele), Phasen-Chip mit Balken, Frist mit Kreisring, Direkt-Handlung je Phase (Unterstützen · Ja/Nein/Enthaltung · Mitreden · Zur Wahl), Hervorhebungsgrund nur bei „Wichtige Abstimmungen"; Raster 2×2, ab 700 px Feldbreite 3×2, gleich große Kacheln
- **Rückmeldung in der Kachel (FB-A2):** nach Unterstützen oder Abstimmen zeigt die Kachel 1,5 s den Gold-Haken „Erfasst" statt einer Flash-Meldung
- **Meine Region als 3×3-Raster (FB-E1):** drei Bänder Gemeinde · Bezirk · Land teilen sich die Feldhöhe, jedes mit senkrechtem Zeilenkopf (Ebene · Ort, farbiger Balken) und einer waagrecht wischbaren Spur mit drei gleich großen Kacheln (Scroll-Snap; am Handy ragt die nächste an); ab der vierten Kachel „› n weitere". **Leerzustände kurz (FB-E3):** „Noch nichts in Ihrer Gemeinde. Antrag einbringen →"
- **„Mehr vorhanden" (FB-A5):** sobald ein Feldkörper mehr enthält als sichtbar, liegt unten ein weicher Verlauf mit der Pille „↓ n weitere" (n = Kacheln, Zeilen oder Bänder unter der Sichtkante); Klick rollt eine Feldhöhe weiter, am Ende verschwindet sie; neu gerechnet beim Rollen, bei Größenänderung und nach jedem htmx-Tausch. Das Favoriten-Feld bleibt ohne Pille (der Fächer zeigt zuerst den Anker)
- 48 neue Tests (Fächer-Rechenprobe, Fächer-Einbau, Kachel-Raster, Regionsbänder, sieben Bildschirmtests) — 636 gesamt, dazu vier Fächer-Bilder in der Sichtprüfung

### Geändert
- `faecher_layout` erwartet jetzt `reihenfolge` in den Kategoriezeilen (Geschwister in Baumreihenfolge) und bekommt die Favoriten-Slugs (`abos`) für den Ruhe-Ast; Ausgabe in Prozent statt in 1000er-Einheiten

### Behoben
- Beschriftungen im Fächer überlappten und waren hart abgeschnitten („Bildungssy", „Infrastruktu") — jetzt Ellipse innerhalb der zugeteilten Breite, nie unter sechs Zeichen
- Der Rückweg im Mitte-Modus brach ab Tiefe 5 ab

## [0.33.0] — 2026-09-02 · S1 App-Rahmen: eine Leiste, bildschirmfüllendes Parlament, Konto-Menü, Handy-Tableiste

### Geändert
- **Eine App-Leiste statt zwei Nav-Zeilen (FB-A1, FB-N3, FB-N8):** 56 px hoch (am Handy 52), klebt oben; links die Wortmarke, in der Mitte sechs Hauptpunkte in der beschlossenen Reihenfolge **Parlament · Mandatare · Gremien · Umsetzungsregister · Zukunftswerkstatt · Übersicht** (Gremien ist neu im Hauptmenü, D-N8), rechts der **gefüllte Gold-Knopf „＋ Antrag einbringen"** und der **Konto-Avatar** mit Popover: Mein Gremium · Beitrag · Verwaltung · Sprache · Erscheinungsbild · Mehr · Abmelden. Der aktive Punkt folgt jetzt dem Bereich, nicht dem genauen Pfad — auch eine Antragsseite markiert „Parlament". Gäste sehen ⋯ Mehr · Anmelden · Mitglied werden · EN
- **Das Parlament füllt den Bildschirm (FB-A1):** Das 2×2-Raster misst `100dvh` minus Leiste und Band, Lücke und Rand je 12 px, Feldkopf 44 px — die Seite scrollt nicht mehr, nur die Feldkörper scrollen innen. Auf dem Tablet bleiben zwei Spalten mit Mindesthöhe; **am Handy ist jedes Feld ein Bildschirm, der einrastet**, darunter die feste **Tableiste** (Filter · Favoriten · ＋ · Wichtig · Region) mit 48-px-Goldkreis in der Mitte. **Auf `/parlament/` gibt es keine Fußzeile mehr** — ihre Links stehen im ⋯-Menü und im Konto-Menü
- **Gast- und Pausiert-Hinweis als 32-px-Band unter der Leiste (FB-A6)** statt als Kasten über dem Raster; beide zählen in der Höhenrechnung mit, das Raster verrutscht nicht. Flash-Meldungen liegen im Parlament als schließbarer Stapel unter der Leiste (die Rückmeldung in der Kachel folgt mit S2)
- **Anstoß im Parlament in der App-Leiste (FB-K3):** als Sprechblasen-Symbol mit Popover darunter — es verdeckt „Meine Region" nicht mehr; auf allen anderen Seiten bleibt die schwebende Pille, 12 px kleiner
- **Sans-Schrift für alles Bedienbare (FB-P2, D-P2):** Body 16/1.55, H1 26/700, H2 19/600, H3 16/600. Serif bleibt der Wortmarke und dem Bühnen-Titel der Erklärseiten vorbehalten
- **Werkzeug statt Werbefläche (FB-A2):** Der zweisätzige Regler-Hilfetext weicht dem Link „Offene Regel v1 ›" auf das Parameterregister, der Hinweis auf eine noch nicht gebaute Profilseite entfällt. Ein Test lässt in keinem Feld einen Satz über acht Wörter zu. Gäste sehen in Abstimmungskacheln „Anmelden zum Abstimmen"

### Hinzugefügt
- **Erscheinungsbild-Schalter System / Hell / Dunkel (FB-P3)** im Konto- und ⋯-Menü, gemerkt je Gerät; ein winziges Skript im Kopf setzt das Thema vor dem ersten Zeichnen, damit nichts aufblitzt. Ohne JavaScript bleibt der Schalter verborgen und die Systemeinstellung gilt
- **Alpine.js wird endlich benutzt (FB-P4):** Komponenten für Menüs, Anstoß, Erscheinungsbild, Tableiste und Meldungen liegen in `app.js`; die Templates tragen **keinen einzigen Inline-Handler** mehr und kein Inline-Skript. Die Anstoß-Rückmeldung läuft über den `HX-Trigger`-Header. Jedes Aufklappen ist ein natives `<details>` — ohne JavaScript öffnet und schließt alles wie zuvor
- **Skelett-Zustände** für den htmx-Feldtausch und **Bewegungs-Tokens** nach Spezifikation (160/260/320/420 ms, eine Easing-Familie); die beiden `prefers-reduced-motion`-Blöcke sind zu einem zusammengeführt
- **Dark Mode ohne Lücken (FB-P3):** alle Farben über Tokens mit den Namen der Design-Spezifikation, dunkel doppelt hinterlegt (Systemeinstellung und Schalter); Vollzugsampel, Status-Badges, Ergebnislegende und QR-Kasten laufen über Token-Klassen statt fester Hex-Werte
- **Bildschirmtests mit Playwright** (`tests/e2e/`, Chromium): die vier Abnahmen aus FB-A1 mit und ohne JavaScript, hell und dunkel, dazu Menüs, Erscheinungsbild und reduzierte Bewegung; ein eigener Lauf legt die zehn Bilder der Sichtprüfung unter `docs/sichtpruefung/0.33.0/` ab. Ohne Playwright überspringen sie sich, der Pflicht-Check bleibt grün
- **`tools/po_pruefen.py`** prüft den Übersetzungskatalog und schreibt die `.mo` — ein Ersatz für `compilemessages` auf Rechnern ohne gettext; zwanzig neue englische Texte, „Verwaltung" war bisher gar nicht übersetzbar
- 33 neue Tests (App-Rahmen, Design-System, Bildschirmtests) — 316 gesamt

### Behoben
- Die Rasterzeilen des Parlaments wuchsen mit ihrem Inhalt, statt den Bildschirm zu teilen (`1fr` bedeutet `minmax(auto, 1fr)`)
- `hidden` wurde von Komponentenregeln überstimmt — die Erscheinungsbild-Gruppe war ohne JavaScript sichtbar, aber wirkungslos
- Die Versionsnummern in `pyproject.toml` und `plattform_core.__version__` standen noch auf 0.1.0 und folgen jetzt dem Änderungsprotokoll

## [0.32.0] — 2026-09-02 · Nachschärfung 2: Werkzeug statt Werbung, vollständiges Flussdiagramm, KI-Verbrauch, Partner-Seite

### Geändert
- **Arbeitsbereiche sind Werkzeug, keine Werbefläche (Grundsatz des Gründers):** Alle Erklär- und Werbesätze sind aus den Mitglieder-Arbeitsbereichen entfernt — der „Vier Bereiche"-Satz über dem Parlament, die drei Feld-Fußsätze (Regler-Rechnung, Mandatars-Richtschnur, Hervorhebungs-Hinweis) und die Intro-Absätze der Gremien-Bereiche (Werkstatt, Prüfung, Koordination). Erklärt und beworben wird nur noch dort, wo Nichtmitglieder lesen (Willkommensseite, Mitgliedschaft, öffentliche Seiten)
- **Flussdiagramm vervollständigt:** Die Sachantrag-Bahn führt jetzt bis zum Ende — Beschluss → **Umsetzungsregister** (öffentlich, mit Verlauf) → **Staatsapparat** (Standardprozedur: Mandatare bringen ein · Vollzug · Prognoseabgleich). Und die **KI ist eingezeichnet**, wo sie wirklich auftritt: beim Einbringen (Ähnlichkeitshinweis · Themen-Zuordnung) und in der Werkstatt (Durchrechnung · Einschätzung) — als gestrichelte Gold-Plaketten mit der Kennzeichnung „sie schlägt vor, sie entscheidet nie". Das Diagramm bricht aus der Textspalte aus und ist am Desktop vollständig ohne Scrollen sichtbar
- **Übersicht („Die Plattform in Zahlen"): KI-Verbrauch veranschaulicht** — Anbieter/Modell, archivierte und gescheiterte Läufe, Tokens gegen das Monatsbudget als Meter mit Prozent, samt Verweisen auf Lauf-Archiv und Parameterregister
- **Menü-Politur:** Pill-Hover statt Unterstreichung, die aktuelle Seite ist markiert, das mobile Menü gleitet auf. **Favoriten-Sterne** deutlich sichtbarer (größer, goldener Schein am aktiven Stern). **Aufgleiten statt Aufspringen** auch für Anstoß-Fenster und Regler-Overlay; Felder gleiten mit mehr Weg auf

### Hinzugefügt
- **P9-Erststufe: die Partner-Seite `/partner/`** (§ 12, „Labor der Demokratien") — System und Parameter getrennt gedacht, der Fahrplan der Zusammenarbeit in drei Stufen (Software bereitstellen und gemeinsam einrichten → gemeinsame Standards und Werkzeuge → Lernfortschritt und Parameter gemeinsam erheben), was wir mitbringen und was wir suchen, Kontakt-Knopf; unaufdringlich über die Fußzeile erreichbar, die Partner-Rolle mit eigener Oberfläche ist angekündigt (Rollen-Fundament steht). Quellen: Strategie Fassung 3 (Kap. 10) und das Kooperationspapier vom 24.8. mit den Linien A–E
- 3 neue Tests (Arbeitsbereichs-Regel, Partner-Seite DE/EN, KI-Verbrauch in der Übersicht) — 265 gesamt

## [0.31.0] — 2026-09-01 · Detail-Nachschärfung nach den Gründer-Vorgaben: Fächer direkt, Suche statt Seiten, Politur

### Geändert
- **Der Favoriten-Fächer erscheint direkt im Feld** (P2 präzisiert): kein Liste/Fächer-Umschalter, kein Tiefen-Ansicht-Link mehr — der Fächer *ist* der Bereich, unten die Wurzel **„Lebensbereiche"**. **Oben im Feldkopf sitzt jetzt die Suche** (Name, Beschreibung, Schlagworte — Treffer mit Pfad, laufenden Verfahren im ganzen Ast und Abo-Stern; Klick öffnet den Fächer am Treffer). **Die alte Lebensbereiche-Seite `/kategorien/` ist komplett weggefallen** — alte Adressen leiten in den Fächer, Kategorie-Chips an Anträgen und alle Verweise zeigen direkt dorthin. Knoten-Beschriftungen in **moderner Sans-Schrift** und mit mehr Platz
- **Bewegung und Hochglanz (Look-Auftrag):** Der Fächer **gleitet hinein** statt zu springen; dazu weiche Seitenübergänge (View Transitions), gestaffeltes Auftauchen der Felder, Karten und Schritte, einfahrende Filter-Leiste und Regler-Overlay, wachsende Fortschrittsbalken, Hover-Tiefe mit Gold-Kante auf Kacheln, Stern-Pop, Glanz-Verlauf auf Karten, einheitliche Fokus-Ringe. Alles Zugabe: ohne JavaScript und bei reduzierter Bewegung (`prefers-reduced-motion`) bleibt jede Funktion unverändert
- **Anstoß-Widget:** trägt jetzt ein **X zum Schließen**, und **nach dem Absenden schließt es sich von selbst** — eine Bestätigungsblase „Danke — Ihre Meldung ist gespeichert" (mit eigenem X) übernimmt die Rückmeldung; Fehlerhinweise (warte/leer) halten das Fenster offen
- **Willkommensseite:** neues **Flussdiagramm „Die Wege durch die Plattform"** — Sachantrag mit Fristen, die Entwurfsschleife als eigene Bahn (inkl. Gruppe-2-Prüfung, Rückschleife „höchstens 3 Runden" und Gold-Pfeil „Untätigkeit hemmt nie") und die Mandats-Kandidatur; als zweisprachiges, dark-mode-fähiges Inline-SVG
- **Mandatare:** Der Leerzustand sagt unmissverständlich, dass die Kandidaten-Wahl **hier auf der ParlamentPlattform** läuft — nicht im österreichischen Parlament
- Die frühere Feld-Liste gemerkter Anträge ist mit der Präzisierung bewusst entfallen (der Stern bleibt überall; eine eigene Anzeige kann als WeicherFilter-Regler zurückkehren); Tests entsprechend fortgeschrieben (262 gesamt)

## [0.30.0] — 2026-09-01 · Ring 0b, Teil 2: Das Parameterregister (F-68)

### Hinzugefügt
- **Neue App `parameter`: die offenen Stellschrauben des Systems an einem Ort** — öffentlich unter **`/parameter/`** (auch in der Fußzeile), je Eintrag mit Wert, Einheit, Beschreibung und **Herkunft** (Satzungs-/Konzeptstelle), dazu `/parameter.json` als offener Export. **Erstbestand** (wird bei jedem Deploy sichergestellt, bestehende Werte bleiben unangetastet): die Entwurfsschleifen-Fristen (14 + 14 Tage), die Höchstrunden (3), die Rollen-Dauer (730 Tage, § 6 Abs 8) und das KI-Monatsbudget (1 Mio. Tokens)
- **Der Code liest jetzt aus dem Register** — mit ehrlichem Rückfall auf die eingebauten Zielwerte, wenn ein Eintrag fehlt oder unlesbar ist: Die Gremien-Werkstatt holt Review-/Überarbeitungsfrist, Höchstrunden und Rollen-Dauer von hier, der Modell-Steckplatz sein Monatsbudget (das Register führt; die Umgebungsvariable bleibt Rückfall vor dem Erstbestand)
- **Änderungen nur dokumentiert:** Verwaltungsbereich mit Pflicht-Grund je Änderung — alt, neu und Grund landen im öffentlichen Audit-Log („parameter_geaendert"). Künftig beschließt die Mitgliederversammlung über die versionierte Verfahrensordnung (F-65: Änderungen als dokumentierte Experimente); die Seite sagt diesen Weg offen an
- 8 neue Tests (Erstbestand idempotent und nie überschreibend, Rückfall-Logik, öffentliche Seite + JSON, Pflicht-Grund + Audit, Register-Durchgriff in Schleifen-Frist, Rollen-Dauer und KI-Budget). **Ring 0b ist damit komplett** — F-60 und F-68 in Erstfassung umgesetzt

## [0.29.0] — 2026-09-01 · Ring 0b, Teil 1: Der Modell-Steckplatz (F-60)

### Hinzugefügt
- **Neue App `ki`: der anbieterneutrale Modell-Steckplatz.** Welcher Anbieter dahinter steckt, ist eine Einstellung, kein Code-Umbau: Erster Stecker ist **Mistral** (Envs `DDOE_KI_SCHLUESSEL`, optional `DDOE_KI_MODELL`, Standard mistral-small-latest) — über die Standardbibliothek, ohne Anbieter-SDK; eine **Attrappe** trägt Tests und Vorführungen ohne Netz. **Ohne Schlüssel ist der Steckplatz ehrlich leer:** Die Oberflächen sagen das an Ort und Stelle, nichts bricht
- **Lauf-Archiv (append-only):** Jeder Aufruf hinterlässt einen `KILauf` — Zweck, Eingabe, Antwort, Anbieter, Modell, Tokenverbrauch, Dauer; **auch der gescheiterte**. Ein **hartes Monats-Tokenbudget** (`DDOE_KI_MONATSTOKENS`, Standard 1 Mio.; Zielwert → F-68) deckelt die Kosten: erschöpft heißt stumm bis zum Monatswechsel, geprüft *vor* jedem Anbieter-Aufruf
- **Erste Nutzung — die Werkstatt-Einschätzung:** Gruppe 1 kann im Entwurfsfenster eine **KI-Einschätzung einholen** (Zusammenfassung, Unklarheiten, Vollzugs-/Kostenfragen, Formulierungsvorschläge; ab Runde 2 samt Abgleich mit den Unterstützer-Wünschen der Vorrunde). Das Ergebnis erscheint als Beitrag in der dokumentierten internen Beratung — **deutlich gekennzeichnet** („KI-Vorschlag · Modell"): Sie schlägt vor, sie entscheidet nie (L7). Der Auftragstext steht bewusst offen im Quellcode
- **Öffentliche Rechenschaft:** Die Zukunftswerkstatt-Seite zeigt den Steckplatz in Zahlen — angeschlossener Anbieter samt Modell (oder ehrlich „kein Anbieter angeschlossen"), archivierte Läufe, Tokens diesen Monat gegen das Budget, die letzten Läufe samt gescheiterten
- 9 neue Tests (leerer Steckplatz, Archivierung, Budget-Stopp, Fehler-Archivierung, Mistral-Anfragebau ohne Netz, Werkstatt-Kennzeichnung, öffentliche Zahlen)

## [0.28.0] — 2026-09-01 · Die Willkommensseite erklärt das System

### Geändert
- **Die Startseite `/` ist jetzt der erklärende Einstieg für alle** — erreichbar auch übers Header-Logo. Neu darauf: **„So funktioniert das System"** (der Weg jedes Antrags in fünf Schritten: Einbringen → Unterstützen → Beraten samt Entwurfsschleife → geheim Abstimmen mit verdeckten Zwischenständen → Nachrechnen und Umsetzen), ein **Grundsätze-Band** (nachrechenbar · keine verdeckte Reihung · KI schlägt vor, entscheidet nie · ohne Hürden/AGPL) und der **vollständige Bereichs-Überblick** mit neun erklärten Karten (Parlament, Antrag einbringen, Mandatare, Gremien, Lebensbereiche, Zahlen, Umsetzungsregister, Zukunftswerkstatt, Mitgliedschaft) plus ehrlichem Alpha-Hinweis
- Der frühere Mitglieder-Redirect von `/` ins Parlament ist bewusst gefallen: Der Einstieg zeigt allen dieselbe Übersicht, das Parlament bleibt von überall einen Klick entfernt (Nav und Held-Knopf). Zwei Tests fortgeschrieben/ergänzt; Seite vollständig zweisprachig

## [0.27.0] — 2026-09-01 · Ring 0a, Teil 2: Gruppe 2 und der Koordinationsrat

### Hinzugefügt
- **Prüfbereich der Gruppe 2 `/gremien/pruefung/` (§ 6 Abs 7):** Die Korruptions-Redundanz hat ihre Oberfläche. Vorschläge mit Vollzugs-/Beschaffungsbezug erscheinen mit vollem Wortlaut; Gruppe 2 kann **validieren** (weiter zu den Unterstützern), **begründet zurückgeben** (die Werkstatt ist wieder am Zug — eine laufende Überarbeitung bekommt frische Zeit, ohne Rundenzählung) oder den **Austausch der Gruppe 1 beim Koordinationsrat beantragen**. Jede Prüfung wird auditiert, und **jede Begründung steht öffentlich auf der Antragsseite** — auch die spätere Entscheidung des KoRats
- **Koordinationsrats-Bereich `/gremien/koordination/`:** offene Austauschanträge samt Begründung der Gruppe 2, Entscheidung mit veröffentlichter Begründung — **Stattgeben beendet alle aktiven Rollen der Gruppe 1** (dokumentierter Grund „Austausch durch den Koordinationsrat", § 6 Abs 7) und übergibt den Entwurf der neu besetzten Gruppe; Ablehnen lässt die Prüfung bei Gruppe 2. Dazu die Übersicht aller aktiven Rollen und der **Zukunftswerkstatt-Posteingang als Platzhalter** für Ring 0b (KI-Vorprüfung als Vorschlag, nie als Entscheidung)
- „Mein Gremium" verzweigt jetzt je Rolle (Gruppe 1 → Werkstatt, Gruppe 2 → Prüfung, KoRat → Koordination); der `demo_seed` besetzt die Gremien selbstständig auch auf bestehenden Datenbanken (2× Gruppe 1, 1× Gruppe 2, 1× KoRat) und öffnet ein Demo-Entwurfsfenster am Beratungs-Antrag
- 9 neue Tests (Zugriffe, alle drei Prüfwege, beide KoRat-Entscheide, Blockadefreiheit der Prüfphase); F-66 und F-67 sind damit in Erstfassung umgesetzt

## [0.26.0] — 2026-09-01 · Ring 0a, Teil 1: Die Gremien-Werkstatt — Rollen auf Zeit, Entwurfsfenster, Entwurfsschleife

### Hinzugefügt
- **Neue App `gremien` (F-66, § 6): Rollen auf Zeit.** Berufungen in Expertenrat Gruppe 1/Gruppe 2, Koordinationsrat und Integritätsrat sind befristet (Standard: zwei Jahre, § 6 Abs 8), erlöschen automatisch am Ablaufdatum und tragen die MV-Bestätigung als eigenes Merkmal; eine vorzeitige Beendigung braucht einen dokumentierten Grund. Öffentliche Besetzungsseite **`/gremien/`** (zweisprachig, mit Ausschreibungs-Hinweis und ehrlichem Alpha-Vermerk), Verwaltungsbereich „Gremien-Rollen" (berufen/bestätigen/beenden — jede Handlung im Audit-Log), Nav-Punkt **„Mein Gremium"** nur für aktive Rolleninhaber
- **Das Entwurfsfenster des Expertenrats (F-66):** Zu jedem Sachantrag in der Beratung kann Gruppe 1 ein Fenster öffnen — der Antragswortlaut wird als Fassung 1 übernommen. **Fassungen sind append-only** (nichts wird überschrieben, nichts gelöscht), die interne Beratung wird als dokumentierte Beiträge geführt (§ 6 Abs 9), und die **Einreichung entscheidet eine offene, dokumentierte interne Abstimmung** (nötig: mindestens die Hälfte der aktiven Rollen als Ja und mehr Ja als Nein). Ein Vollzugs-/Beschaffungs-Häkchen schickt den Vorschlag zuerst zur getrennt besetzten Gruppe 2 (§ 6 Abs 7; deren Oberfläche folgt in 0.27.0). Admins sehen die Werkstatt als Aufsicht, schreiben können nur Rolleninhaber
- **Die Entwurfsschleife (§ 5 Abs 12, F-67):** Der eingereichte Vorschlag liegt den Unterstützern des Antrags offen vor — **annehmen oder mit konkretem Wunsch zurückgeben** (14 Tage; Voten offen geführt, direkt auf der Antragsseite samt Vorschlags-Wortlaut). Eine Rückgabe-Mehrheit startet eine Überarbeitungsrunde (14 Tage, höchstens 3 Runden — Zielwerte, wandern mit F-68 ins Register); die Annahme macht den Vorschlag zur **neuen letzten Antragsfassung** und öffnet die Endabstimmung (§ 5 Abs 3 lit d)
- **Fristlogik ohne Blockademacht — „Untätigkeit hemmt nie":** Die Beratung bleibt nur offen, solange die Schleife *arbeitet* (eingereicht, in Prüfung, im Review oder in laufender Überarbeitung). Ein bloß geöffnetes, nie eingereichtes Fenster hält nichts auf; bleibt das Unterstützer-Review still, geht der Vorschlag nach Fristablauf zur Endabstimmung; verstreicht eine Überarbeitungsfrist, geht die zuletzt vorgelegte Fassung. **Verfahren ohne Entwurfsfenster laufen exakt wie bisher** (§ 5 Abs 5)
- 19 neue Tests (Rollen, Fenster, Schleife inkl. aller Fristfälle und Blockadefreiheit); alle Oberflächen ohne JavaScript voll bedienbar; öffentliche und Mitglieder-Seiten vollständig übersetzt

## [0.25.0] — 2026-09-01 · P5: Der WeicherFilter — der Bereich, in dem man den Algorithmus selbst steuert

### Hinzugefügt
- **Acht offene Regler** im Feld d des Parlaments (⚙ im Kopf): mehr aus Lebensbereichen, in denen ich abgestimmt bzw. unterstützt habe · Entdeckungen außerhalb meiner Favoriten · mehr Unterstützungsphase · mehr laufende Abstimmungen · Neues zuerst · bald Ablaufendes zuerst · knapp vor der Schwelle zuerst. **Bis zu fünf speicherbare Profile** (serverseitig beim Mitglied), umschaltbar über die Chip-Leiste am oberen Feldrand; der Regler-Bereich liegt als halbtransparentes Overlay am rechten Rand mit „Anwenden & speichern" und „Als neues Profil"
- **Die Reihung ist eine offene, versionierte, nachrechenbare Regel** (§ 2 Abs 6, § 5 Abs 10 lit d): Der Kern (`plattform_core/weicherfilter.py`, Regel v1) rechnet Punkte = Regler × Merkmal, alle Merkmale liegen in [0, 1] und sind dokumentiert; **jeder Antrag zeigt seinen Punktewert samt Aufschlüsselung** (Titel-Hinweis). Bei Punktgleichheit bleibt die neutrale Grundordnung erhalten
- **Die Voreinstellung bleibt streng neutral** (Phase und Frist, chronologisch) — genau wie bisher; der „Neutral"-Chip stellt sie jederzeit wieder her. Profile wirken ausschließlich auf die eigene Ansicht, nie auf gemeinsame Reihung, Schwellen oder Ergebnisse; Gäste sehen immer die neutrale Ordnung. Ohne JavaScript voll bedienbar (native Schieberegler, echte Formulare); mit htmx wechselt nur das Feld

## [0.24.0] — 2026-09-01 · P3/P4: Kacheln für Wichtige Abstimmungen und Meine Region

### Geändert
- **Wichtige Abstimmungen als Kacheln (P3):** Thema + Stern, phasengerechter Stand als schmaler Fortschrittsbalken — Unterstützungen zur Schwelle, Beiträge in der Beratung, **Beteiligung in Prozent der Stimmberechtigten** während der Abstimmung — dazu **Resttage bis Fristende** und die Begründung des Integritätsrats. Bewusste Klarstellung zur Fahrplan-Zeile „Tendenz wofür": **Die Tendenz bleibt bis Fristende verdeckt** (die Kachel sagt das offen dazu) — alles andere widerspräche F-15 (kein Bandwagon-Effekt); das Ergebnis zeigt die Antragsseite nach Fristende
- **Meine Region als Kachel-Raster (P4):** immer drei Zeilen — Gemeinde, Bezirk, Land — mit **direkt abstimmbaren Feldern**: Ja/Nein/Enthaltung sitzen in der Kachel, die eigene Stimme ist markiert, ohne JavaScript kehrt man aufs Parlament zurück, mit htmx wechselt nur das Feld. Mit hinterlegtem Wohnsitz zeigt jede Zeile **die eigene Region** (leere Zeilen sagen es ehrlich und laden zum ersten Antrag ein); Gäste sehen alle regionalen Anträge samt Ortsangabe. Personenwahl-Kacheln führen zur Wahl der Bewerbungen statt zu Ja/Nein
- **Bezirks-Anträge** sind jetzt einbringbar: Wer seine Wohnsitz-Gemeinde hinterlegt hat, kann „Mein Bezirk" wählen — das Gebiet kommt wie immer aus dem Profil, nie aus freier Eingabe (F-43); damit ist § 14 auf allen vier Ebenen bespielbar

## [0.23.0] — 2026-09-01 · M1: Die Mandatare-Seite

### Hinzugefügt
- **Öffentliche Mandatare-Seite `/mandatare/` (§ 7 Abs 9 des Satzungsentwurfs 2.5, F-71)** — neuer Menüpunkt: jeder Mandatsträger mit **Foto, aktuellen Aufgaben und Entscheidungsprozessen samt Fristen**; überfällige Fristen werden markiert, und wo eine Aufgabe zur Abstimmung geworden ist, führt sie direkt zum **betreuten Antrag** im Parlament (F-70). Beendete Mandate verschwinden aus der Liste, bleiben aber dokumentiert
- **Ehrlicher Leerzustand:** Solange die DDÖ kein Mandat hält, sagt die Seite genau das — und zeigt die laufenden Mandats-Kandidaturen, denn die Wahl der Kandidaten läuft bereits über das Parlament
- **Verwaltungsbereich „Mandatare"** (bis die Mandatar-Rolle M2 die Pflege an die Mandatare selbst übergibt): Mandat anlegen/beenden, Aufgaben mit Frist und Antrags-Verknüpfung veröffentlichen, Statusführung — jede Handlung auditiert. Fotos liegen als streng begrenztes Binärfeld in der Datenbank (JPEG/PNG/WebP, max. 800 kB, Magic-Byte-Prüfung ohne Zusatzbibliothek) und überleben so jeden Neustart des flüchtigen Dienst-Speichers
- Neue App `mandatare` mit acht Tests; Fahrplan Abschnitt F: M1 und M3 damit umgesetzt, M2 (Instant-Reports) folgt auf dem Rollen-Fundament aus Ring 0a

## [0.22.0] — 2026-09-01 · M3: Mandats-Kandidaturen als Anträge

### Hinzugefügt
- **Neue Antragsart „Mandats-Kandidatur" (§ 7 Abs 1 des Satzungsentwurfs 2.5, F-70):** Das Parlament wählt jetzt auch Personen. Jedes Mitglied kann für ein Mandat einen Antrag stellen — besteht bereits einer, **beteiligt man sich daran** und wird im Antragsfenster als wählbar geführt (Bewerben bis zum Abstimmungsbeginn, mit öffentlicher Vorstellung und Wählbarkeits-Bestätigung; ein Rückzug bleibt dokumentiert)
- **Zustimmungswahl:** In der Abstimmungsphase stimmt man den einzelnen Bewerbungen zu — mehreren gleichzeitig, jede Zustimmung bis Fristende zurücknehmbar. **Die meiste Zustimmung gewinnt**, die Zustimmungsreihenfolge ergibt die Listenreihung; bei Stimmengleichheit steht die früher eingereichte Bewerbung vorn (offene, nachrechenbare Regel). Zwischenstände werden nicht angezeigt (kein Bandwagon, wie F-15)
- **Geheim und nachrechenbar wie jede Stimme:** Zustimmungen laufen über dasselbe Stimmregister (Pseudonym + Prüfcode, F-25); die Anwartschaft folgt der Personenwahl-Regel (§ 4 Abs 4); die Mindestbeteiligung der eingefrorenen Policy gilt auch hier. Der JSON-Export enthält Bewerbungen und Zustimmungen zum unabhängigen Nachrechnen; ausgezählt wird im framework-freien Kern (`plattform_core.tally.personenwahl_auszaehlen`)
- Ja/Nein-Abstimmen ist bei Kandidaturen gesperrt; der Ähnlichkeitshinweis entfällt bewusst — Kandidaturen für dasselbe Mandat sollen sich am bestehenden Antrag beteiligen. Demo: „Testlauf: Listenreihung Gemeinderat" mit zwei Bewerbungen läuft als Abstimmung

## [0.21.0] — 2026-09-01 · P2: Der Favoriten-Fächer

### Hinzugefügt
- **Der Favoriten-Fächer** im Bereich „Meine Favoriten" des Parlaments (`/parlament/?fach=`): der Kategoriebaum als grafischer Fächer — unten (bzw. ab der dritten Ebene **in der Mitte**) der aktuelle Knoten in Schrift 24, darüber die Unterebenen in 2-Punkt-Schritten kleiner, mit Fäden verbunden; unter dem Mitte-Anker bleibt der Weg zurück nach oben klickbar (Beschluss 1.9. gegen das Festzoomen am unteren Rand). **An jedem Knoten sitzt der Favoriten-Stern** (Lebensbereich-Abo, mit Rücksprung auf den Fächer); werden die Enkel zu viele (mehr als zwölf), zeigt jedes Kind stattdessen „+n"
- **Ohne JavaScript voll bedienbar:** Knoten sind echte Links, Sterne echte Formulare; die Fäden liegen als SVG-Ebene hinter HTML-Beschriftungen (lesbar, barrierefrei, dunkelmodus-fest). Mit JavaScript wechselt htmx nur das Favoriten-Feld statt der ganzen Seite. Die Fokus-Ansicht `/kategorien/` bleibt als Tiefen-Ansicht mit Suche bestehen
- Layout-Mathematik als reines, framework-freies Modul `plattform_core/faecher.py` mit eigenen Tests (Modus-Wechsel ab Ebene 3, Schriftgrößen-Treppe, Enkel-Deckelung, Rückfall auf die Wurzel)

## [0.20.0] — 2026-09-01 · Das Postfach der Plattform

### Geändert
- Alle Plattform-Mails (E-Mail-Bestätigung, Anmeldelink, Beitragsbestätigung, Beitragserinnerung) tragen als Absender jetzt **„ParlamentPlattform <plattform@ddoe.at>"** — das neue Postfach ist zugleich Antwort- und öffentliche Kontaktadresse (Zukunftswerkstatt-Seite, künftig P9-Kontaktknopf). Der SMTP-Anschluss war vorbereitet; es fehlen nur die drei Werte im Render-Dashboard (`DDOE_SMTP_HOST`, `DDOE_SMTP_USER`, `DDOE_SMTP_PASSWORT` — siehe Betriebsdoku)

### Hinzugefügt
- Lastenheft: **F-70 Mandats-Kandidaturen als Anträge** und **F-71 Mandatar-Steuerung** (Mandatare-Seite mit Foto/Aufgaben/Entscheidungsprozessen, Rolle „Mandatar" mit Instant-Reports und betreuten Abstimmungen) aufgenommen — satzungsfest im Entwurf 2.5 (§ 7 Abs 1 und Abs 9); Bauschritte M1–M3 im Oberflächen-Fahrplan, Abschnitt F

## [0.19.0] — 2026-09-01 · Der Anstoß: Feedback auf jeder Seite

### Hinzugefügt
- **Das Anstoß-Widget (F-69)** begleitet jetzt jede Seite der Plattform: ein goldener Knopf rechts unten öffnet eine kleine Karte für Feedback und Wünsche — von Mitgliedern (dem Konto zugeordnet, Rückfragen möglich) wie von Gästen (anonym). Ohne JavaScript voll funktionsfähig (Formular mit Rücksprung auf die Ausgangsseite); mit JavaScript sendet htmx ohne Neuladen. Schutz ohne Captcha: Honigtopf-Feld und Sendeabstand (60 Sekunden, Tagesgrenze je Sitzung)
- **Gespeichert wird in der eigenen Datenbank der Plattform** — bewusst kein Dritt- oder FTP-Server: keine zusätzlichen Zugangsdaten, automatische Sicherung mit der Render-Postgres, DSGVO-Hoheit bleibt vollständig bei uns. Neue Verwaltungsseite „Anstöße" (`/verwaltung/anstoesse/`) mit Statusführung (neu → gesichtet → erledigt), Filter und Export als CSV und JSON zur gemeinsamen Auswertung
- Neue App `anstoss` mit eigenem Datenmodell, neun Tests und Lastenheft-Eintrag F-69

## [0.18.0] — 2026-09-01 · Willkommensseite und Parlament getrennt

### Geändert
- **„/" und „/parlament/" sind jetzt zwei Seiten** (P1-Leitidee: das Parlament ist zum Benutzen da, erklärt und beworben wird gesondert): Die Willkommensseite zeigt Gästen die Bühne mit Kennzahlen, drei Wegweiser-Karten (Parlament · Mitgliedschaft · Zukunftswerkstatt) und die wichtigen Abstimmungen; das Vier-Felder-Parlament wohnt unter `/parlament/`. Angemeldete Mitglieder landen auf „/" ohne Umweg im Parlament — auch direkt nach der Anmeldung; Gäste sehen im Parlament eine schlanke Hinweisleiste statt der großen Bühne
- Alle „zurück"-Wege (Antragsseite, Einbringen-Formular, Einführung) führen jetzt zielgenau ins Parlament; der Favoriten-Stern kehrt ohne JavaScript standardmäßig auf genau die Seite zurück, von der aus er gedrückt wurde

### Entfernt
- Verwaiste Vorlage `staatssimulation.html` entfernt — sie war beim Geräteabgleich zurückgeblieben, weil der Archiv-Abgleich keine Löschungen überträgt (die Weiterleitung `/staatssimulation/` → `/zukunftswerkstatt/` bleibt selbstverständlich bestehen)

## [0.17.0] — 2026-09-01 · P1: Das Parlament als Vier-Felder-Raster

### Hinzugefügt
- **Die Parlament-Seite ist jetzt ein bildschirmfüllendes 2×2-Raster** gleich großer, direkt bedienbarer Felder (mobil untereinander), je mit eigenem Kopf, scrollbarem Korpus und Fußzeile: **WeicherFilter** (Bereich d — vorerst streng neutrale Reihung nach Phase und Frist; die Regler folgen in P5), **Meine Favoriten** (Bereich a — samt „Neu aus Ihren Lebensbereichen"), **Wichtige Abstimmungen** (Bereich b — Kacheln mit Begründung des Integritätsrats) und **Meine Region** (Bereich c — gruppiert nach Gemeinde/Bezirk/Land). Die Leitgestalt des § 5 Abs 10 bleibt exakt gewahrt
- **App-Fundament:** htmx 2.0.10 und Alpine.js 3.17.1 als **eingecheckte statische Dateien** (kein CDN, kein Tracking, kein Build-Schritt). Erster Nutzen: Favoriten-Sterne schalten ohne Seiten-Neuladen — ohne JavaScript funktioniert derselbe Klick wie bisher als normale Übermittlung
- Terminus-Beschluss im Satzungsentwurf 2.4 nachgezogen: Der Expertenrat erarbeitet einen **„Vorschlag"** (nicht „Vorlage") — § 5 Abs 3 lit d und Abs 12; Satzungsseite auf ddoe.at aktualisiert
- Fahrplan ergänzt: P2-Fächer mit **Mitte-Anker ab der dritten Ebene**, P7-**Abstimmungs-Chat** über den Vorschlag des Expertenrats (Zustimmen/Ablehnen je Kommentar, offene nachrechenbare Reihung, „Passt alles" > 50 % stuft hoch, Archiv-Registerkarte mit Export) und **P9 Internationale-Partner-Seite** (Strategie-Darstellung, Kooperations-Fahrplan, Kontakt; später Konto mit bestätigter Rolle „Internationaler Partner")

## [0.16.0] — 2026-09-01 · Die Zukunftswerkstatt bekommt ihren Namen

### Geändert
- **Die StaatsSimulation heißt jetzt „Zukunftswerkstatt"** — Untertitel: *Werkzeug zur rekursiven Optimierung der gesamtgesellschaftlichen Selbstorganisation* (Beschluss des Parteigründers, Satzungsentwurf 2.4 § 6 Abs 11). Die StaatsSimulation bleibt als **Rechenkern** der Zukunftswerkstatt bestehen — neben Parameterregister, Prognose-Register und Kennzahlenwesen
- Plattform durchgängig umbenannt: Route `/zukunftswerkstatt/` (die alte Adresse `/staatssimulation/` leitet dauerhaft weiter — keine toten Links), Menü, Fußbereich, Erklär- und Mitgliedschafts-Seite, Lastenheft (Abschnitt 3.9, Leitplanke L7), englische Übersetzungen
- Der geplante selbstgeregelte Feed (P5 des Oberflächen-Fahrplans) heißt **„WeicherFilter"** — satzungsfest verankert in § 5 Abs 10 lit d des Entwurfs 2.4

## [0.15.0] — 2026-09-01 · Aufgeräumtes Menü und die neuen Fristen

### Geändert
- **Menü verschlankt:** „Lebensbereiche" ist aus dem Hauptmenü genommen (die Fokus-Ansicht bleibt über den Favoriten-Bereich, Kategorie-Chips und den Fußbereich erreichbar); **„Antrag einbringen"** ist jetzt ein hervorgehobener Menü-Knopf; der doppelte Button im Bereich d der Parlament-Seite ist entfernt
- **Verfahrensordnung Version 2** (per Daten-Migration, § 5 Abs 5-konform — laufende Verfahren behalten ihre eingefrorenen Regeln): Unterstützungsfrist **60 Tage** (vorher 14), Beratung **21 Tage** (unverändert — deckt die drei Wochen des Expertenrats-Erstvorschlags), Endabstimmung **28 Tage** (vorher 7). Die Fristen der künftigen Entwurfsschleife (je zwei Wochen Unterstützer-Review und Überarbeitung) sind als Zielwerte im Oberflächen-Fahrplan festgehalten und werden mit der Expertenrats-Station (F-66/F-67) wirksam

## [0.14.0] — 2026-09-01 · Das Schaufenster der Mitgliedschaft

### Hinzugefügt
- **Öffentliche Seite `/mitgliedschaft/`** (deutsch und englisch): erst plakativ, was Mitglieder können — sechs illustrierte Rechte-Karten (einbringen, unterstützen, mitberaten, abstimmen, selbst nachrechnen, Umsetzung verfolgen) —, dann das **Flussdiagramm „Vom Antrag zum Beschluss"** (sechs Stationen samt StaatsSimulation und Expertenrat in der Beratung), die Details ehrlich erklärt (Anwartschaft samt Übergangsregel, Beitrag als Selbsteinschätzung, Identität und Pseudonym, regionale Zuständigkeit) und der StaatsSimulations-Block mit Verweis auf die Erklärseite. Alle „Mitglied werden"-Einstiege (Menü, Startseiten-Bühne, Fußbereich) führen jetzt zuerst hierher; das Registrierungsformular bleibt direkt verlinkt
- Neue Fluss-Strecken-Gestaltung (nummerierte Stationen mit Verbindungslinie) im zentralen Stylesheet

### Geändert
- Das Hauptfenster heißt im Menü und Fußbereich jetzt **„Parlament"** (englisch „Parliament")

## [0.13.1] — 2026-09-01 · Die CI rollt selbst aus

### Hinzugefügt
- **CI-Job „ausrollen":** Nach jeder bestandenen Prüfung auf `main` stößt die CI den Render-Deploy-Hook an — Deploys passieren damit automatisch nach jedem Push, aber **nur bei grüner Prüfung** (rote Commits gehen nie live; das kann Renders natives Auto-Deploy nicht). Einmalig nötig: Deploy-Hook-URL aus dem Render-Dashboard als GitHub-Actions-Secret `RENDER_DEPLOY_HOOK` hinterlegen; ohne Secret wird der Schritt sauber übersprungen. Hintergrund: Der Dienst ist als öffentliche Git-URL verbunden — Renders eigenes Auto-Deploy hat keinen Webhook und feuert nie (alle bisherigen Deploys liefen per API)

## [0.13.0] — 2026-09-01 · Die StaatsSimulation bekommt ihr Schaufenster

### Hinzugefügt
- **Öffentliche Seite `/staatssimulation/`** (deutsch und englisch, im Hauptmenü und Fußbereich verlinkt): die Gesamtstrategie der StaatsSimulation als Aufklärung für alle und als Einladung an die verwandten demokratischen Bewegungen weltweit — die zwei Gesichter (politische Bildung nach außen, Sinnesorgan der Selbstregulation nach innen), die vier Grundsätze („Die KI schlägt vor, sie entscheidet nie" · „Der Demos darf atmen, die Stimme wiegt immer gleich" · „Das Gedächtnis ist der Schatz, nicht das Modell" · „Auf Unwissen gebaut"), der Antragsweg im Zielbild (inklusive Expertenrat und Unterstützer-Schleife, ehrlich als Zielbild gekennzeichnet), Faktenbasis, Aufsicht und Kontakt
- **Lastenheft, Abschnitt 3.9** „Die StaatsSimulation" mit F-60–F-68 (Simulations-Fundament, Ähnlichkeit Stufe 2, Rechtsfolgen-Check, Vollzug und Lastampel, Vergabe-Check, Lernschleife mit Prognose-Register, Gremien-Werkstatt mit den Oberflächen für Expertenrat 1/2 und Koordinationsrat, Expertenrats-Station im Antragsweg, Parameterregister) und **Leitplanke L7** („Die Simulation berät alle und regiert niemanden")

### Geändert
- Menüpunkt heißt jetzt klarer **„Umsetzungsregister"** statt „Umsetzung"

## [0.12.0] — 2026-08-31 · Der Beitragsabgleich: das Konto meldet sich selbst

### Hinzugefügt
- **Beitragsabgleich (F-59, § 4 Abs 3):** Die Plattform liest — nur lesend, über einen PSD2-Kontoinformationsdienst (GoCardless Bank Account Data) — die Umsätze des Vereinskontos und verbucht Eingänge anhand der persönlichen Beitragsreferenz (F-38): Beitragsdatum aktualisiert, Beitragspause beendet, Erstkonto freigeschaltet („geprüft"), Audit-Eintrag (ohne Betrag — die Höhe ist Selbsteinschätzung und bleibt privat), Bestätigungsmail. **Datensparsam:** gespeichert werden nur Betrag, Buchungstag, Umsatz-Kennung und ein Ja/Nein-Namenshinweis — nie IBAN oder Absendername
- **Beitragsseite `/beitrag/` im Hauptmenü:** QR-Kasten jederzeit erreichbar (nicht mehr nur auf der Willkommensseite) samt **„Ich habe überwiesen"** — der Klick löst sofort einen Kontoabruf aus; bei Echtzeitüberweisung ist der Eingang meist im selben Moment verbucht und die Mitwirkung frei. Eigene Eingänge als private Liste
- **Verwaltung „Beiträge & Bank":** Kopplung des Vereinskontos per Klick (die Zustimmung erteilt die Kontoinhaberin selbst im Online-Banking — die Plattform sieht nie Bankzugangsdaten; Erneuerung alle 180 Tage), Abrufstand (PSD2-Kontingent 4/Tag), Prüfhinweise bei abweichendem Absendernamen, manueller Sofort-Abgleich — und die **Erinnerungsliste:** alle Mitglieder, deren letzter Eingang über zwölf Monate zurückliegt (oder die nie eingezahlt haben), mit Haken je Zeile oder „Alle erinnern"; die E-Mail nennt die persönliche Referenz und verlinkt die Beitragsseite. Versendet wird ausschließlich auf Knopfdruck
- Nachholender Abgleich beim Öffnen der Beitragsverwaltung (wenn der letzte Abruf länger als sechs Stunden zurückliegt); Management-Kommando `beitraege_abrufen` für einen späteren Zeitplan-Dienst
- **Kontoauszug-Upload als Weg ohne Drittanbieter:** In „Beiträge & Bank" lässt sich der Umsatz-Export aus dem Online-Banking (George) direkt abgleichen — **camt.053-XML** (ISO-20022, exakte Umsatz-Kennungen) oder **CSV** (Spalten werden tolerant über die Kopfzeile erkannt, deutsche Beträge und Datumsformate inklusive; Dedupe über einen Fingerabdruck aus Datum, Betrag und Verwendungszweck). Gleiche Zuordnung, gleiche Freischaltung, gleiche Prüfhinweise wie beim API-Abruf; die Datei wird nur gelesen, nie gespeichert. Damit funktioniert der Abgleich sofort — die PSD2-Kopplung bleibt eingebaut und wartet auf einen verfügbaren Kontoinformationsdienst
- 17 neue Tests (153 gesamt); alles vollständig zweisprachig; F-59 im Lastenheft, neue Umgebungsvariablen in der Betriebsdoku

### Behoben
- Erster 0.12.0-Deploy scheiterte mit `ModuleNotFoundError: requests` — die Bibliothek für die Dienst-Abrufe fehlte in den Produktionsabhängigkeiten (in der Entwicklungsumgebung war sie global vorhanden); jetzt in `dependencies` deklariert
- **QR-Code: Empfängername mit Umlaut** — „Direkte Demokratie Österreich" statt „Oesterreich": Der EPC-Payload deklariert UTF-8 (dritte Zeile „1"), und seit der EU-Empfängerprüfung (Verification of Payee) zählt der exakte Kontowortlaut

## [0.11.0] — 2026-08-26 · Neues Gewand: Bühne, Dark Mode, Mobilmenü

### Hinzugefügt
- **Startseiten-Bühne für Gäste:** Auftakt in Nachtblau mit dem Leitsatz „Wir sind das Werkzeug.", zwei Wegen (Mitglied werden · zu den laufenden Abstimmungen) und drei öffentlichen Kennzahlen (bestätigte Mitglieder, laufende Verfahren, gefasste Beschlüsse — identisch mit der Übersichtsseite). Angemeldete Mitglieder sehen weiterhin sofort ihr Hauptfenster
- **Dark Mode:** Die gesamte Plattform folgt `prefers-color-scheme` — dunkle Flächen, angepasste Meldungs- und Statusfarben, ausreichende Kontraste; die servergerenderten SVG-Diagramme bringen ihren eigenen Papiergrund mit und bleiben so auf dunklen Seiten lesbare Blätter (validierte Farbpalette unverändert)
- **Mobilmenü ohne JavaScript:** aufklappbare Navigation über einen reinen CSS-Schalter (Checkbox), animierter Burger, große Touch-Ziele — das Versprechen „ohne Skriptzwang" gilt auch fürs Menü. Dazu ein Skip-Link („Zum Inhalt springen") und sichtbare Fokusringe für Tastaturbedienung
- **Neuer Fußbereich:** dreispaltig mit Kurzporträt, Plattform-Wegen und Offenheit (Quellcode AGPL, Register-JSON, Satzungsentwurf, ddoe.at) samt Schlusszeile „Ohne Skriptzwang, ohne Tracking, ohne verdeckte Reihung."
- Die Mitglieder-Tabelle der Verwaltung wird auf schmalen Bildschirmen zu beschrifteten Karten (`data-label`)

### Geändert
- Vollständige Überarbeitung des zentralen Stylesheets: durchgängige Farbvariablen (hell/dunkel), weiche Schatten, Karten-Hover in den Lebensbereichen, verfeinerte Formulare und Chips, Kopfzeile mit Goldlinie, Marken-Untertitel und Punktgitter; `prefers-reduced-motion` und eine Druckansicht werden respektiert

### Behoben
- **23 falsch zugeordnete englische Übersetzungen** (stumme msgmerge-Übernahmen aus 0.9/0.10): u. a. „Umsetzung" → *Support*, „in Umsetzung" → *gathering support*, „zurückgestellt" → *returned*, „Suchen" → *Visits*, „alle" → *lapsed*, „Ihre erste Abstimmung" → *No votes yet.* — alle Stellen tragen jetzt die richtige Übersetzung (310 Einträge, 0 fuzzy)

## [0.10.1] — 2026-08-26 · CI repariert: alle Testsuiten zählen

### Behoben
- **CI schlug mit „Abdeckung 81 % < 90 %" fehl:** pytest sammelte die Testsuiten von `uebersicht` und `plattform_core` gar nicht ein (fehlende `testpaths`) — 11 Tests liefen weder lokal noch in CI, und `test_diagramme.py` zählte zugleich als unabgedeckter Kern-Code. Jetzt laufen alle **136 Tests**, Testdateien sind aus der Abdeckungsmessung ausgenommen (`omit`), Kern-Abdeckung **99 %**

## [0.10.0] — 2026-08-20 · Das Umsetzungsregister

### Hinzugefügt
- **Umsetzungsregister** (F-55, § 6 Abs 10): öffentliches Register unter `/umsetzung/` — jeder angenommene Antrag mit Vollzugsstatus (offen / in Umsetzung / blockiert / umgesetzt / zurückgestellt), Statusfilter mit Zählung, JSON-Export mit voller Historie (F-23). In der Navigation verlinkt
- **Vollzugsgeschichte auf der Antragsseite:** bei angenommenen Anträgen erscheint der aktuelle Stand samt vollständiger, append-only geführter Historie (Vermerk, Zeitpunkt, eintragende Person); Admins schreiben direkt dort fort — mit öffentlichem Vermerk nach dem F-56-Raster (Stand, Hindernis, nächster Schritt, Termin)
- Jeder Eintrag ist dauerhaft (nie ändern, nie löschen) und landet im öffentlichen Audit-Log (F-22); geführt wird das Register laut Satzung vom Integrations- und Berichtswesenrat — bis das Rollensystem (F-05) kommt, übernehmen die Admins
- Demo-Daten: der angenommene Beispielantrag trägt eine zweistufige Vollzugsgeschichte; 5 neue Tests (125 gesamt); vollständig zweisprachig

## [0.9.1] — 2026-08-20 · Lastenheft: Systemgrenzen und Selbstregulation

### Hinzugefügt (nur Dokumentation)
- **Leitplanke L6** („Das System kennt seine Grenzen und zeigt sie"), neuer Abschnitt **3.7 Lastmanagement und Vollzug** mit F-54 Taktung, F-55 Umsetzungsregister, F-56 Vollzugsbericht, F-57 Überlastungsmeldung, F-58 Lastmetriken, neues **Kapitel 9 „Systemgrenzen und Selbstregulation"** (Engpasskette, Regelkreis, Simulationsszenario „Lastgrenze"), Risiko **Beschluss-Inflation** und Traceability-Ergänzung — übernommen aus dem freigegebenen Begleitdokument vom 20.08.2026, dort als F-40–F-44 nummeriert (hier F-54–F-58, da F-40–F-44 bereits das Vier-Bereiche-Hauptfenster bezeichnen)
- Satzungsbezüge zeigen auf den **Satzungsentwurf 2.3** (§ 2 Abs 7 Selbstregulation, § 5 Abs 11 Taktung und Überlastungsschutz, § 6 Abs 10 Vollzugsrückmeldung und Umsetzungsregister) — im Bausteindokument noch als § 5 Abs 10 geplant, in 2.2/2.3 ist Abs 10 bereits die Leitgestalt des Hauptzugangs

## [0.9.0] — 2026-08-20 · Eine Wurzel, vier Säulen — und die Einführung

### Hinzugefügt
- **Kategorienbaum v2** (F-45): Alles führt jetzt auf **„Das gesellschaftliche Zusammenleben"** zurück — darunter vier Säulen (Sicherheit & Soziales Fundament · Wirtschaft, Arbeit & Finanzen · Lebensraum & Infrastruktur · Bildung, Entwicklung & Gesellschaft) und zwölf Bereiche mit den Beschreibungen des Parteigründers; darunter unverändert die bisherigen 295 Kategorien (312 Knoten, 6 Ebenen). Alle Slugs sind stabil geblieben — bestehende Favoriten und Zuordnungen überleben den Umbau
- **Fokus-Ansicht** (F-45): Jede Kategorie ist eine eigene Seite — oben der Stamm als klickbare Brotkrume bis zur Wurzel, in der Mitte der aktuelle Bereich mit Stern und laufenden Anträgen des Astes, darunter die Unterbereiche als Karten zum Hineinklicken. Dazu eine **Suche** über Namen, Beschreibungen und Schlagworte. Ohne JavaScript; die Ast-Zählung läuft jetzt mit zwei Datenbankabfragen statt einer je Knoten
- **Einführung nach der Bestätigung** (F-53): drei geführte, bebilderte Schritte — Lebensbereiche finden, die erste Abstimmung verstehen, einen Antrag einbringen lernen — mit Fortschrittsleiste, jederzeit überspringbar; Abschluss ist der Beitrags-QR. Der Bestätigungslink führt jetzt hierher
- Kategorie-Chips bei Anträgen sind verlinkt und zeigen den kurzen Pfad (letzte drei Ebenen)

### Geändert
- Alte Gesamtbaum-Seite durch die Fokus-Ansicht ersetzt; neue Texte vollständig übersetzt (Deutsch/Englisch)
- 8 neue Tests (120 gesamt)

## [0.8.0] — 2026-08-20 · Zweisprachig: Deutsch und Englisch

### Hinzugefügt
- **Vollständige englische Oberfläche** (F-33, vorgezogen): alle mitgliederseitigen Seiten, Formulare, Meldungen, Diagrammbeschriftungen und System-E-Mails; 232 übersetzte Texte. Umschalter **DE/EN** in der Kopfzeile (ohne JavaScript, per Django-`set_language`); ohne Wahl entscheidet die Browsersprache. Übersetzte, menschliche Phasennamen (Filter `phase_name`) statt technischer Werte — auch auf Deutsch eine Verbesserung („Unterstützung" statt „unterstuetzung")
- Kompilierter Sprachkatalog (`locale/en/…/django.mo`) ist eingecheckt — der Betrieb braucht kein gettext

### Geändert
- Inhalte (Anträge, Beratungen, Kategorienamen) bleiben bewusst in ihrer Originalsprache; mehrsprachige Kategorienamen folgen mit dem EuroVoc-Anschluss (ADR-007). Die Mitgliederverwaltung bleibt vorerst deutsch (internes Werkzeug)
- 5 neue Tests (112 gesamt)

## [0.7.0] — 2026-08-20 · Öffentliche Übersicht und Mitgliederverwaltung

### Hinzugefügt
- **Öffentliche Übersichtsseite** `/uebersicht/` (F-50): Mitglieder mit Verlauf, Anträge je Phase, neue Anträge je Woche, Besuche je Tag, meistgelesene Anträge — und je Abstimmung Ergebnis (Ja/Nein/Enthaltung) samt Beteiligung als 100-%-Balken. Abstimmungsverhalten ausschließlich als Summe; Einzelstimmen bleiben pseudonym. In Navigation und Fußzeile verlinkt
- **Servergerenderte SVG-Diagramme** (`plattform_core/diagramme.py`): Linie, Säulen, Anteilsbalken — ohne JavaScript, ohne Diagramm-Bibliothek; Farbpalette auf Farbfehlsichtigkeit geprüft, native Tooltips, Werte immer auch als Text (ADR-008)
- **Datensparsame Besuchszählung** (F-52): Tages-Summen je Plattform und je Antrag — keine Cookies, keine IP-Speicherung; anonyme Tageskennung, die um Mitternacht wertlos wird; Maschinen ausgefiltert; Zählweise öffentlich erklärt
- **Mitgliederverwaltung** `/verwaltung/` (F-51, ersetzt den Django-Admin): Suche und Filter, Stammdaten korrigieren (Gemeinde stets gegen das amtliche Verzeichnis), Identitätsstufe setzen, Beitragseingang vermerken, **pausieren** (Mitwirkungsrechte ruhen bis zum Beitragseingang), **ausschließen** (vollzieht den Beschluss nach § 4 Abs 6, umkehrbar), Admins ernennen und entziehen. Fixer Erstzugang per `DDOE_FIX_ADMIN` (Standard didide@ddoe.at) — immer Admin, unantastbar; niemand wirkt auf das eigene Konto. Jede Handlung im öffentlichen Audit-Log, ohne personenbezogene Werte
- Mitglied: Felder `status`, `status_grund`, `beitrag_zuletzt_am`, `ist_admin`; pausierte Mitglieder sehen einen Hinweis mit Beitrags-QR-Link, Mitwirkungs-Sperren greifen in allen handelnden Ansichten und in der Stimmberechtigung

### Geändert
- Django-Admin aus den URLs entfernt — `/verwaltung/` ist jetzt die eigene, auditierte Verwaltung
- Dokumentation auf den echten Stand gebracht: README (Phase 1, Live-Adresse), `docs/BETRIEB-RENDER.md` (Starter-Instanz, SMTP-Sperre auf Free-Instanzen, manueller Deploy nach Push, Postgres, `DDOE_FIX_ADMIN`), CONCEPT (F-50–F-52, Phasenstand), `render.yaml` (parlament.ddoe.at, vollständiger Startbefehl), neue ADR-008
- 18 neue Tests (107 gesamt)

## [0.6.1] — 2026-08-19 · Robuster Mailversand

### Behoben
- **Versandstörungen hinterlassen kein „halbes" Konto mehr:** Konto-Anlage und Bestätigungs-Mail laufen in einer Transaktion — scheitert der Versand (z. B. SMTP nicht erreichbar), wird alles zurückgerollt, die Adresse bleibt frei, und das Formular meldet die Störung ehrlich statt einer „E-Mail unterwegs"-Seite ohne E-Mail. Gleiches offenes Verhalten beim Anmeldelink
- **SMTP-Timeout** (`DDOE_SMTP_TIMEOUT`, Standard 20 s): Ein hängender Mailserver hält den Web-Worker nicht mehr bis zum Gunicorn-Timeout fest (vorher: 60 s Blockade + Fehler 500)

### Geändert
- 2 neue Tests (96 gesamt)

## [0.6.0] — 2026-08-19 · Captcha-Bild und amtliches Gemeindeverzeichnis

### Hinzugefügt
- **Sichtbares Captcha** (F-49): Die Sicherheits-Rechenfrage steht jetzt als verzerrtes Bild im Formular (selbst erzeugtes SVG mit Störlinien — kein Drittanbieter, keine Datenweitergabe); die Aufgabe erscheint nicht mehr im Seitentext. Temporär bis zur ID-Austria-Anbindung; Barrierefreiheits-Ausweich per E-Mail-Hinweis
- **Amtliches Gemeindeverzeichnis** (F-43): 2.092 Gemeinden (Statistik Austria, Gebietsstand 2026, CC BY 4.0) als `daten/gemeinden.csv` + `manage.py gemeinden_laden`. Die Wohnsitz-Gemeinde wird beim Registrieren live vorgeschlagen (natives Auswahlfeld, ohne JavaScript-Pflicht) und gegen das Verzeichnis geprüft: Tippfehler werden abgewiesen (mit Vorschlägen), mehrdeutige Namen wie „Krumbach" verlangen die Präzisierung „Name (Bezirk)", „Sankt"/„St." wird toleriert
- Bezirk und **Bundesland werden automatisch zugeordnet** (Feld entfällt im Formular); neuer Verweis `Mitglied.wohnsitz` ins Verzeichnis — Grundlage für die spätere Bezirks-Ebene regionaler Anträge

### Geändert
- Demo-Daten und Tests auf amtliche Gemeindenamen umgestellt; 2 neue Tests (94 gesamt)

## [0.5.0] — 2026-08-19 · Menschlichkeitsprüfung, Beitrags-QR, voller Kategorienbaum

### Hinzugefügt
- **Menschlichkeitsprüfung** (F-49) bei Registrierung und Anmeldelink — vier Lagen, ohne Drittanbieter, ohne JavaScript-Pflicht: Honigtopf-Feld, signierte Mindestzeit, Rechenfrage, IP-Drossel (5 Registrierungen bzw. 10 Anmeldelinks je Stunde und IP)
- **Zahlen mit Code** (F-38): EPC-QR-Code auf der Willkommensseite — Banking-App scannt, Empfänger/IBAN/persönliche Referenz sind vorausgefüllt; Überweisung direkt von Konto zu Konto, ohne Zahlungsdienstleister, ohne Prozentgebühren (neue Abhängigkeit: segno)
- **Kategorienbaum voll ausgebaut:** 295 Knoten — 24 Hauptkategorien, 96 Unterkategorien, 175 Detailkategorien über alle Lebensbereiche; die automatische Zuordnung trifft die Detailebene (z. B. „Tempo 30 vor Schulen" → Verkehr › Straßen › Tempolimits & Verkehrsberuhigung)
- Konzept: F-48 (spätere App mit klar getrenntem, opt-in „Für dich"-Bereich — beeinflusst nie die gemeinsame Reihung), F-49 dokumentiert

### Geändert
- Einheitliches **Favoriten**-Wording für Lebensbereiche (statt „Abo"): „Favorisieren Sie, was Sie betrifft: Neues daraus erscheint in Ihrem Hauptfenster unter Favoriten. Favoriten sind rein persönlich und beeinflussen nie ein Ergebnis." — Detailkategorien sind einzeln favorisierbar
- 5 neue Tests (92 gesamt)

## [0.4.0] — 2026-08-19 · Kategorienbaum, automatische Zuordnung, Regionalbindung

### Hinzugefügt
- **Kategorienbaum** (F-45, ADR-007): 24 Hauptkategorien (Lebensbereiche) mit ~100 Unter- und Detailkategorien in `policies/kategorien-v1.yaml` (z. B. Wirtschaft › Bauwirtschaft › Installateur) — versioniert, stabile Slugs, Deaktivieren statt Löschen, kein „Sonstiges"; EuroVoc-Domänen als Anschluss-Ebene für RIS/EUR-Lex; Import per `manage.py kategorien_laden` (rekursiv, idempotent)
- **Automatische Zuordnung** (F-47, Stufe 1): Beim Einbringen ordnet die Plattform den Antrag selbst in den Baum ein — niemand kreuzt Kategorien an. Deterministische, nachrechenbare Schlagwort-Klassifikation (`plattform_core/klassifikation.py`), tiefste passende Ebene gewinnt, Vorfahren werden nicht doppelt vergeben; jede Zuordnung wird auditiert; Stufe 2 ersetzt die Schlagworte durch lokale Embeddings bei gleicher Schnittstelle
- **Kategorie-Abos mit Ast-Wirkung** (F-46): Ein Abo (z. B. „Energie") umfasst alle Unterkategorien; Bereich a zeigt „Neu in Ihren Lebensbereichen"; Baum-Seite mit Aufklapp-Unterkategorien und Abo je Knoten
- **Regionalbindung** (F-43): Regionale Anträge nur in der ansässigen Region — Mitglieder erfassen Gemeinde und Bundesland bei der Registrierung, das Gebiet eines Antrags kommt zwingend aus dem Wohnsitzprofil (keine freie Eingabe, Manipulationsversuche laufen ins Leere); Ebenen-Auswahl zeigt „Meine Gemeinde (…)" / „Mein Bundesland (…)"

### Geändert
- Einbringen-Formular ohne Kategorien- und Gebietsfelder (automatisch bzw. profilgebunden); Erfolgsmeldung nennt die automatisch zugeordneten Lebensbereiche; Antrags-Chips zeigen den vollen Pfad

## [0.3.0] — 2026-08-19 · Das Hauptfenster in vier Bereichen

### Hinzugefügt
- Startseite als **Hauptfenster nach § 5 Abs 10 des Satzungsentwurfs 2.2** (Leitgestalt aus Satzung 1.3): a) persönliche Favoriten, b) hervorgehobene Abstimmungen, c) regionaler Bereich, d) Anträge & Gesetzesvorschläge (F-40)
- **Favoriten** (F-41): Stern an jedem Antrag; laufende Abstimmungen der eigenen Favoriten stehen im Hauptfenster zuerst. Favoriten sind rein persönlich und wirken nie auf Reihung oder Ergebnis
- **Hervorhebung wichtiger Abstimmungen** (F-42): Felder `hervorgehoben` + öffentliche Begründung am Antrag; Entscheidung des Integritätsrats (im Prototyp über die Verwaltung), niemals eines Algorithmus — die Begründung wird im Hauptfenster und am Antrag angezeigt
- **Regionale Ebenen** (F-43): Anträge tragen Ebene (Bund/Land/Bezirk/Gemeinde) und Gebiet; das Einbringen-Formular fragt beides ab (Gebiet ist bei regionalen Anträgen Pflicht), regionale Anträge erscheinen im Bereich c
- **Ähnlichkeitsübersicht mit Beteiligung** (F-44): Die Treffer beim Einbringen zeigen jetzt die Zahl der Unterstützungen; Hinweis auf die kommende Folgenabschätzung per StaatsSimulation (F-36) direkt im Formular
- Acht neue Ansichts-Tests (77 gesamt); Demo-Daten decken alle vier Bereiche ab; F-40 bis F-44 im Konzept dokumentiert

## [0.2.0] — 2026-08-19 · Phase 1: Benutzbare Plattform

### Hinzugefügt
- Selbstregistrierung mit Double-Opt-in (F-37): Konto wird erst mit bestätigter E-Mail aktiv; Anwartschaft (§ 4 Abs 4) beginnt mit der Bestätigung; Willkommensseite mit persönlicher Beitragsreferenz und IBAN (F-38)
- Passwortloser Login per E-Mail-Einmallink (30 min gültig, nur als SHA-256-Hash gespeichert); Architektur vorbereitet für den späteren Umstieg auf ID Austria (F-39, ADR-002)
- Antrag einbringen im Browser (F-10) mit Ähnlichkeitshinweis (F-35, ADR-006): rein lexikalischer Trigramm-Jaccard-Vergleich, deterministisch und von Hand nachrechenbar; der Hinweis schlägt vor und blockiert nie (§ 2 Abs 6) — „Trotzdem einbringen“ ist immer gleichwertig möglich
- Unterstützen (umschaltbar), Beratungsbeiträge (nur in offenen Phasen) und Abstimmen (Ja/Nein/Enthaltung, änderbar bis Fristende) direkt auf der Antragsseite
- Feststellung der Stimmberechtigtenzahl automatisch bei Abstimmungsbeginn — festgeschrieben und danach unveränderlich (§ 4 Abs 4 lit a); Übergangsregel § 4 Abs 4 lit d über `DDOE_UEBERGANGSREGEL` konfigurierbar
- Stimmlisten-Export als JSON je Antrag (erst nach Abstimmungsende, § 5 Abs 3 lit d), kompatibel mit `verify/nachrechnen.py`; Seite „Meine Stimme prüfen“ zeigt das eigene Pseudonym (F-21)
- Ansichts-Tests für alle Flüsse (Registrierung, Login, Einbringen inkl. Ähnlichkeit, Schwellen-Übergang, Anwartschafts-Prüfung, Export-Sperre, unabhängiges Nachrechnen im Test)
- ADR-006 (Ähnlichkeitshinweis und Folgenabschätzung in drei Stufen), Konzept-Kapitel 3.4 (F-35 bis F-39)

### Geändert
- Basis-Layout mit Anmelde-Navigation, Statusmeldungen und Formular-Stilen; Antragsseite zeigt Fristen, Beratung und Handlungs-Schaltflächen je nach Phase und Berechtigung
- `ruff format` einheitlich über die gesamte Codebasis angewendet (reine Formatierung, keine Verhaltensänderung)

## [0.1.0] — 2026-08-19 · Phase 0: Fundament

### Hinzugefügt
- Verfahrenskern `plattform_core`: Phasenautomat (§ 5 Abs 3), Policy-Modell mit satzungsfesten Untergrenzen und Einfrier-Mechanik (§ 5 Abs 5), ganzzahlig exakte Auszählung (§ 5 Abs 4), Stimmberechtigung mit Anwartschaftslogik (§ 4 Abs 4), Audit-Hash-Kette (§ 5 Abs 8)
- Eigenschaftstests (Hypothesis) für Reihenfolgeunabhängigkeit, Monotonie, Determinismus, Endgültigkeit von Endphasen und Manipulationserkennung; Kern-Zweigabdeckung ≥ 90 % als CI-Pflicht
- Django-Anwendung: Mitglieder mit Identitätsstufen, Anträge mit Fassungshistorie und Policy-Snapshot, getrenntes Stimmregister (Pseudonym ↔ Person, zugriffsbeschränkt), read-only-Audit-Admin
- Unabhängiges Nachrechen-Skript `verify/nachrechnen.py` (nur Standardbibliothek)
- Verfahrensordnung als versionierte YAML (`policies/`), Demo-Seed, Docker-Compose-Setup, CI (ruff, pytest, Coverage-Gate), ADR-001 bis ADR-005, Konzeptdokument mit Satzungs-Traceability
