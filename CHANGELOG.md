# Änderungsprotokoll

Format nach [Keep a Changelog](https://keepachangelog.com/de/), Versionierung nach [SemVer](https://semver.org/lang/de/).

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
