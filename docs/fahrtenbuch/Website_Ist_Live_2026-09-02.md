# Website-Ist-Zustand LIVE: www.ddoe.at und parlament.ddoe.at

- **Erhebungsdatum:** 2026-09-02 (ca. 02:00 UTC)
- **Methode:** ausschließlich WebFetch (Seite wird zu Markdown konvertiert und von einem Modell ausgewertet). Folgen dieser Methode:
  - Ein expliziter HTTP-Statuscode wird nicht zurückgegeben. „Erreichbar: ja" bedeutet: Inhalt wurde geliefert und ausgewertet; „nicht abrufbar" bedeutet: Fehlermeldung des Abrufs.
  - HTML-Attribute (z. B. `data-target` an Zählern), Inline-SVGs und per JavaScript erzeugte Elemente (z. B. QR-Codes als SVG/Canvas) sind in der Markdown-Konvertierung nicht sichtbar. Wo das relevant ist, ist es vermerkt.
  - Wörtliche Zitate: das Auswertungsmodell begrenzt einzelne Zitate; lange Abschnitte wurden darum teils in mehreren Abrufen geholt. Zitate in Anführungszeichen sind so wiedergegeben, wie sie aus den Abrufen kamen.
- Hinweis zum Menü: Der Menüpunkt „Impressum & DSGVO" zeigt auf `/impressum-dsgvo/`; die angefragte URL `/impressum/` liefert dieselbe Seite.

---

## A) https://www.ddoe.at/ (Startseite)

- **Erreichbar:** ja
- **Titel (`<title>`):** „Direkte Demokratie Österreich | Wir sind das Werkzeug — die logisch nächste Form der gesamtgesellschaftlichen Selbstorganisation"

### A.1 Hauptmenü (wörtlich, in Reihenfolge)

| # | Menüpunkt | Linkziel |
|---|-----------|----------|
| 1 | ParlamentPlattform | https://parlament.ddoe.at/ |
| 2 | Blog | https://www.ddoe.at/blog/ |
| 3 | Satzung | https://www.ddoe.at/satzung/ |
| 4 | Spenden | https://www.ddoe.at/mitmachen/ |
| 5 | Impressum & DSGVO | https://www.ddoe.at/impressum-dsgvo/ |

Es gibt **keinen** Menüpunkt „Mitmachen" mehr; der Menüpunkt heißt „Spenden" und führt auf `/mitmachen/`.

Zusätzlich gibt es eine Anker-Navigation innerhalb der Startseite: Warum (#dd-warum) · Das Verfahren (#dd-verfahren) · Rechenschaft (#dd-recht) · Grundsätze (#dd-grund) · Fahrplan (#dd-plan) · Satzung (https://www.ddoe.at/satzung/).

### A.2 Tagline

„Wir sind *das Werkzeug.*" (Header/Hero). Der Site-Titel ergänzt: „die logisch nächste Form der gesamtgesellschaftlichen Selbstorganisation".

### A.3 Hero (Start)

- Überschrift: „Direkte Demokratie Österreich"
- Text (wörtlich): „Die DDÖ ist eine Partei ohne inhaltliches Programm — und mit einem einzigen Versprechen: eine Infrastruktur zu bauen, mit der die Bevölkerung Österreichs ihre Anliegen selbst einbringt, gemeinsam prüft und transparent entscheidet. Überprüfbar für alle. Im Rahmen der Verfassung. Unser Zeithorizont ist ehrlich: 18 Jahre Aufbau — bis zur Mehrheit bei der Nationalratswahl 2044, mit der wir die erste Volksabstimmung zur Einführung der ParlamentPlattform einleiten."
- Buttons:
  - „Alpha-Phase live ansehen →" → https://parlament.ddoe.at/
  - „Mitglied werden" → https://parlament.ddoe.at/mitgliedschaft/
  - „So funktioniert es" → #dd-verfahren (Anker auf den Verfahrens-Abschnitt)

### A.4 Zähler (Statistik-Kacheln im Hero)

In der Markdown-Konvertierung stehen die Zähler auf ihrem Startwert „0" (animierte Counter; Zielwerte liegen in HTML-Attributen, die per WebFetch nicht sichtbar sind):

| Kachel (wörtlich) | Zielwert laut Seitentext (Kontext) |
|---|---|
| „0 Mio. Wahlberechtigte in Österreich" | 6,2 Mio. („6,2 Millionen Stimmberechtigten" im Text) |
| „0 Sitze im Nationalrat" | 183 („183 Abgeordnete" im Text) |
| „0 Schritte von der Idee zum Beschluss" | 5 („fünf öffentliche Schritte") |
| „0 % offener Quellcode" | 100 % (nicht im Text bestätigt; aus Kontext „quelloffen") |

### A.5 Sektionen in Reihenfolge (Kicker/Eyebrow wörtlich → Überschrift wörtlich → Inhalt)

1. **Der historische Moment** — „Zum ersten Mal in der Geschichte können wir uns als ganze Gesellschaft selbst organisieren."
   Bisher sei direkte Demokratie im großen Maßstab logistisch unmöglich gewesen („Ein Parlament aus 6,2 Millionen Stimmberechtigten würde an einem einzigen Tag mehr Anträge hervorbringen, als ein Mensch in einem Jahr lesen kann"). „Das hat sich geändert, seit Computer lesen gelernt haben." KI sortiert, entscheidet nie; Sicherungen (Beratungsfristen, eingefrorene Verfahrensregeln, unantastbarer Wesenskern); „Verantwortung ist ein Muskel."

2. **Diese Partei hat genau zwei Ziele.** — „1. Gesamtgesellschaftliche Selbstorganisation" / „2. Null Korruption"
   „Mehr nicht. Und nichts weniger." Der Weg vollständig innerhalb der Verfassung; Volksabstimmung (Art. 44 B-VG).

3. **Warum es uns gibt** — „Politik ist kein Zuschauersport."
   Vier Karten:
   - „Debatten über Nebenschauplätze" — Aufmerksamkeit dorthin lenken, wo entschieden wird.
   - **„Distanz zwischen Wissen und Macht"** (wörtlich, vollständig): „Die meisten Gesetze betreffen nicht alle — sie betreffen Minderheiten. Eine Regelung für Installateure betrifft Installateure; wer könnte sie besser beurteilen? Wir haben erstmals die Chance, ein System zu bauen, das für Minderheiten funktioniert: Ein Großteil der Gesetze soll von denen entscheidbar sein, die sie tatsächlich betreffen. Dafür muss das System dahinter schlau sein — es muss sich selbst kennenlernen, für die eigenen Schwächen Lösungen finden und sie einbauen. Genau das ist möglich. Die repräsentative Demokratie kann das nicht: Manche ihrer Schwächen sind ihr eingebaut."
   - „Rechenschaft als Ausnahme" — lückenlose, dauerhafte Veröffentlichung jeder Entscheidung als Regel, „festgeschrieben in unserer Satzung".

4. **Die ParlamentPlattform** (id `dd-verfahren`; Ziel des Buttons „So funktioniert es") — „Eine Partei ohne Programm. Mit einem Verfahren."
   Es gibt **keine** H2/H3 mit dem Wortlaut „So funktioniert's"/„So funktioniert es"; der Wortlaut kommt nur als Button/Anker vor. Fünf Schritte:
   1. „Einbringen" — „Jedes Mitglied kann einen Antrag stellen" (ohne Vorprüfung, Zurückweisung nur bei offensichtlicher Rechtswidrigkeit, schriftlich begründet, anfechtbar).
   2. „Unterstützen" — „Der Antrag sammelt Unterstützung" (Schwelle; „nicht ein Vorstand, nicht ein Algorithmus, nicht die Lautstärke").
   3. „Beraten — mindestens 21 Tage" — „Öffentliche Beratung mit Sachverstand" („Wo möglich, rechnet die Zukunftswerkstatt die Auswirkungen durch — als gekennzeichnete Modellrechnung, die informiert, aber nicht entscheidet.")
   4. „Abstimmen — mindestens 7 Tage" — „Ein Mensch, eine Stimme" (schriftlich/vor Ort gleichwertig).
   5. „Veröffentlichen — dauerhaft" — „Alles bleibt überprüfbar" („Vertrauen ist gut — Nachrechnen ist besser.")
   Abschluss: „Eine Regel über allen Regeln:" Spielregeln werden beim Einbringen eingefroren.

5. **Die systemische Herangehensweise** — „Ein Verfahren, das sich selbst verbessert."
   „Die fünf Schritte sind nur die Oberfläche. Darunter ist die ParlamentPlattform als lernendes System gebaut — integer, transparent, und mit 18 Jahren Zeit, zur Reife zu kommen: entwickelt, optimiert und aufgebaut im offenen Betrieb, bis zur Nationalratswahl 2044." Vier Karten:
   - „Offene Parameter statt starrer Regeln" — jede Stellgröße ist ein benannter, versionierter Parameter in einem öffentlichen Register.
   - „Die Zukunftswerkstatt" — „Das Lernwerkzeug der Plattform: Modellrechnungen zu Anträgen, aggregierte Kennzahlen ohne Profilbildung, kaskadierende Lernschleifen bis zum Optimum. Die KI schlägt vor — sie entscheidet nie." Link „Zur Erklärseite →" → https://parlament.ddoe.at/zukunftswerkstatt/
   - „Rückkopplung von allen" — Anstoß-Widget auf jeder Seite; „WeicherFilter" mit offenen Reglern.
   - „Mandatar-Steuerung ab dem ersten Mandat" — „Bis 2044 führen wir die Partei selbst vollständig über das Parlament der Plattform".

6. **Rechenschaft statt Blindvertrauen** — „Unsere Abgeordneten stimmen frei. Sie tun es nur nicht im Verborgenen."
   Freies Mandat (Art. 56 B-VG); Instrument „vollständige Öffentlichkeit".
   **Rechenschaftsregister-Mock** (Tabelle, wörtlich):

   | Beschluss der Plattform | Stimme im Parlament | Begründung der Abgeordneten |
   |---|---|---|
   | Ja — 68 % Zustimmung | Ja | „Entspricht dem Beschluss." |
   | Ja — 54 % Zustimmung | Nein — Abweichung | „Neue Sachlage seit der Abstimmung: … Vollständige Begründung, veröffentlicht binnen 7 Tagen, dauerhaft abrufbar." |

   Bildunterschrift: „Beispieldarstellung des Rechenschaftsregisters nach § 7 des Satzungsentwurfs 2.5 — jede Abweichung bleibt sichtbar, für immer. Vor jeder erneuten Kandidatur entscheiden die Mitglieder auf dieser Grundlage neu."

7. **Was bei uns niemand ändern kann** — „Sechs Selbstbindungen."
   „Ein Mensch — eine Stimme" · „KI unterstützt. Sie entscheidet nie." · „Offener Code" · „Offene Finanzen" · „Schutz vor Übernahme" · **„Minderheiten mit Sachkunde"** (wörtlich): „Oft kennt nur eine kleine Gruppe eine Sachlage wirklich. Unser Verfahren kann Betroffene stärker gewichten und Hürden für sie senken — offen beschlossen, nachprüfbar begründet, zuerst in der Zukunftswerkstatt erprobt."

8. **Ehrlichkeit als Methode** — „Was wir nicht versprechen."
   „1. Wir versprechen keinen Zwang gegen Abgeordnete." · „2. Wir versprechen keine Revolution über Nacht." · „3. Wir digitalisieren keine staatlichen Wahlen." Schluss: „Wer Ihnen mehr verspricht, verspricht zu viel."

9. **Fahrplan** — „Von hier bis zur Volksabstimmung."
   Einleitung: „…ein ehrlicher Zeithorizont von 18 Jahren. Jede Stufe gilt erst als erreicht, wenn sie öffentlich sichtbar ist." Etappen (Jahreszahlen wörtlich):
   - **„2026 — Fundament"**: „Die Alpha-Phase der ParlamentPlattform läuft öffentlich: Anträge, Unterstützung, Beratung, Abstimmung, nachrechenbare Auszählung, Beitragsabgleich, Feedback von jeder Seite. Satzungsentwurf 2.5 in offener Diskussion. Mitglied wird man direkt auf der Plattform — und verbessert sie von innen."
   - **„2027–2028 — Betrieb und Reichweite"**: Verfahrensordnung 1.0 aus dem Echtbetrieb; Regionalgruppen in allen neun Bundesländern; Kandidatenaufstellung als Anträge; 2.600 Unterstützungserklärungen.
   - **„2029 — Erster Antritt"**: Bundesweite Nationalratswahl; Mandatar-Steuerung ab Tag eins; Messlatte „ein Prozent".
   - **„2029–2043 — Wachsen und optimieren"**: „Drei weitere Nationalratswahlen, dazu Länder, Bezirke und Gemeinden … Parallel entwickeln wir die Plattform mit Partnerparteien weltweit weiter — überall dieselbe Art zu lernen, überall eigene Werte. In diesen Jahren entstehen die Basisparameter für den Staatsbetrieb".
   - **„2044 — Mehrheit und Volksabstimmung"**: „Unser erklärtes Ziel: die Mehrheit bei der Nationalratswahl 2044. Mit ihr leiten wir die erste Volksabstimmung zur Einführung der ParlamentPlattform ein … Erst danach beginnt das wahre rekursive Verbessern: das System im Echtbetrieb des Staates."
   - Kasten „Warum 18 Jahre?": „…Achtzehn Jahre offener Betrieb, offene Parameter, offener Code — das ist keine Geduld aus Schwäche, sondern die Bauzeit für Vertrauen."
   → **2044 kommt vor** (5 Treffer auf der Seite: Hero, systemische Herangehensweise 2×, Fahrplan 2×).

10. **Mitmachen** — „Das Werkzeug steht. Jetzt wächst es mit uns."
    Eine Überschrift **„Dieses Werkzeug baut sich nicht von selbst" existiert nicht mehr**; an ihrer Stelle steht die genannte Überschrift. Einleitung: „Die ParlamentPlattform ist keine Ankündigung mehr: Anträge, Unterstützung, Beratung, Abstimmung, nachrechenbare Auszählung, Beitragsabgleich, Feedback auf jeder Seite — das alles läuft bereits, öffentlich, in der Alpha-Phase. … Mitglied wird man ab jetzt direkt auf der Plattform." Drei Karten:
    - **„Mitglied werden"**: „Ab 16 Jahren, Beitrag nach Selbsteinschätzung. Die Einschreibung läuft vollständig über die ParlamentPlattform: Rechte ansehen, registrieren, Beitrag per QR-Code — und von der ersten Stunde an mitentscheiden." Button „Mitglied werden" → **https://parlament.ddoe.at/mitgliedschaft/**
    - **„Fähigkeiten einbringen"**: „Softwareentwicklung, Recht, Moderation, Design, Regionalarbeit, Übersetzung — gebraucht wird jedes Können. Auch dieser Weg führt über die Mitgliedschaft: Der verifizierte Zugang öffnet viele Arten der Mitarbeit, vom ersten Anstoß im Feedback-Widget bis zur Arbeit am offenen Code." Button „Als Mitglied einsteigen" → **https://parlament.ddoe.at/mitgliedschaft/**
    - **„Spenden"**: „Unabhängigkeit kostet. Wir finanzieren uns aus Beiträgen und Spenden — und veröffentlichen, was wir erhalten und wofür wir es ausgeben. Transparenter, als das Gesetz verlangt." Button „Spenden" → **https://www.ddoe.at/mitmachen/**. **Kein QR-Code auf der Startseite** (das Wort „QR-Code" kommt nur in der Karte „Mitglied werden" vor, bezogen auf den Beitrag auf der Plattform).

11. **International** — Zitat: „We are the tool. If you are building citizen-led democracy anywhere in the world — we want to hear from you."
    „Selbstorganisation ist keine österreichische Idee. Wir suchen den Austausch mit Parteien, Plattformen und Initiativen weltweit, die an derselben Frage arbeiten — von Taiwan bis Brüssel." Link „Read in English →" → https://www.ddoe.at/english/. **Kein Link auf https://parlament.ddoe.at/partner/.**

12. **Schlusssatz**: „Demokratie ist kein Zustand. Sie ist ein Werkzeug — und Werkzeuge kann man verbessern."

13. **Footer**: „Weiterlesen": ParlamentPlattform (Alpha-Phase) → https://parlament.ddoe.at/ · Satzungsentwurf 2.5 → /satzung/ · Blog · English · Impressum & DSGVO. „Kontakt": didide@ddoe.at · plattform@ddoe.at · Spenden → /mitmachen/. „© 2026 Direkte Demokratie Österreich (DDÖ) · Unterfreundorf — Wir sind das Werkzeug." Darunter WordPress-Widgets „Neueste Beiträge" (5 Posts, siehe E) und „Neueste Kommentare" („Es sind keine Kommentare vorhanden."), sowie der Satz: „Österreich ist das erste Land welches die logisch nächste Regierungsform etabliert. Schreibe Geschichte und werde Mitglied!"

### A.6 Wortsuche auf der Startseite

| Suchwort | Vorkommen | Beleg |
|---|---|---|
| Simulation | **0** | — |
| StaatsSimulation | **0** | — |
| Zukunftswerkstatt | 3 | Schritt 3 „Beraten"; Karte „Die Zukunftswerkstatt" (Link zur Erklärseite); „Minderheiten mit Sachkunde" |
| Prototyp | **0** | — |
| Alpha | ≥ 3 | Button „Alpha-Phase live ansehen →"; „Die Alpha-Phase der ParlamentPlattform läuft öffentlich" (2026); „in der Alpha-Phase" (Mitmachen); Footer „ParlamentPlattform (Alpha-Phase)" |
| ParlamentPlattform | 15+ | Menü, Hero, Sektion 4, 5, Fahrplan, Mitmachen, Footer |
| parlament.ddoe.at | 4 Links | `/` (Menü, Hero-Button, Footer), `/mitgliedschaft/` (2 Buttons), `/zukunftswerkstatt/` (1 Link) |
| Partner | 1 | „Parallel entwickeln wir die Plattform mit Partnerparteien weltweit weiter" (Fahrplan 2029–2043). Kein Link auf `/partner/`. |
| international | 2 | Sektions-Kicker „International"; Zitat „anywhere in the world" |
| Gemeinwerk | **0** | — |
| Minderheit(en) | 3 | „sie betreffen Minderheiten", „das für Minderheiten funktioniert" (Distanz-Karte); „Minderheiten mit Sachkunde" |
| Betroffene | 1 | „Unser Verfahren kann Betroffene stärker gewichten" (Minderheiten mit Sachkunde); sinngemäß außerdem „von denen entscheidbar sein, die sie tatsächlich betreffen" |
| Berufsgruppe | 0 | (Beispiel „Installateure" steht stattdessen) |
| 2044 | 5 | Hero, systemische Herangehensweise, Fahrplan |
| „So funktioniert" | 1 | nur als Button „So funktioniert es" (#dd-verfahren), keine Überschrift |
| „Dieses Werkzeug baut sich nicht von selbst" | **0** | ersetzt durch „Das Werkzeug steht. Jetzt wächst es mit uns." |

### A.7 Link-Ziele der Buttons

- „Mitglied werden" (Hero und Mitmachen-Karte) → https://parlament.ddoe.at/mitgliedschaft/
- „Fähigkeiten einbringen" → Button-Text „Als Mitglied einsteigen" → https://parlament.ddoe.at/mitgliedschaft/
- „Spenden" → https://www.ddoe.at/mitmachen/
- „Alpha-Phase live ansehen →" → https://parlament.ddoe.at/
- „Zur Erklärseite →" → https://parlament.ddoe.at/zukunftswerkstatt/
- „Read in English →" → https://www.ddoe.at/english/

---

## B) https://www.ddoe.at/mitmachen/

- **Erreichbar:** ja — **die Seite existiert noch** (keine 404, keine Weiterleitung). Sie ist inhaltlich zur **Spenden-Seite** umgebaut.
- **Titel:** „Spenden | Direkte Demokratie Österreich"
- **Menü:** identisch zur Startseite (ParlamentPlattform · Blog · Satzung · Spenden · Impressum & DSGVO); Link „← Startseite".
- **Überschriften:** H1 „Spenden" · H2 „Unabhängigkeit kostet." · H2 „Spenden" · (Footer) H2 „Kontakt" · „Neueste Beiträge" · „Neueste Kommentare"
- **Inhalt (wörtlich):**
  - „Die DDÖ finanziert sich aus Mitgliedsbeiträgen und Spenden — und legt offen, was sie erhält und wofür sie es ausgibt. Unser Ziel: Parteifinanzen, die jederzeit live einsehbar sind."
  - Mitgliedschaft: „Mitglied werden? Das geht ab jetzt direkt auf der ParlamentPlattform. Rechte ansehen, registrieren, Beitrag per QR-Code — alles an einem Ort: parlament.ddoe.at/mitgliedschaft/. Auch wer Fähigkeiten einbringen will — Softwareentwicklung, Recht, Moderation, Design, Regionalarbeit, Übersetzung — beginnt dort mit der Mitgliedschaft: Der verifizierte Zugang öffnet viele Arten der Mitarbeit, vom ersten Anstoß im Feedback-Widget bis zur Arbeit am offenen Code."
  - „Unabhängigkeit kostet Geld. Die DDÖ finanziert sich aus Mitgliedsbeiträgen und Spenden — und legt offen, was sie erhält und wofür sie es ausgibt. Unser Ziel ist, dass unsere Finanzen jederzeit live einsehbar sind: jede Einnahme, jede Ausgabe."
  - **IBAN-Block:** „Direkte Demokratie Österreich" · „IBAN: AT57 2033 0000 0006 9435" · „Verwendungszweck: Spende" · Button „IBAN kopieren". Kein BIC, keine Bankbezeichnung.
  - **QR:** „Der QR-Code ist ein gewöhnlicher Überweisungs-Code (EPC): Banking-App öffnen, scannen, Betrag selbst wählen — die Überweisung läuft direkt von Konto zu Konto, ohne Zahlungsdienstleister und ohne Abzüge." **Ein Bild-Element (`<img>`) für den QR-Code ist in der Markdown-Konvertierung nicht nachweisbar** (einziges Bild: das DDÖ-Logo). Der QR-Code ist vermutlich als Inline-SVG oder per Skript eingebettet — per WebFetch nicht verifizierbar.
  - Gesetzliche Regeln (Parteiengesetz 2012): max. 7.500 Euro pro Person und Jahr; Spenden über 150 Euro quartalsweise an den Rechnungshof; über 500 Euro namentliche Veröffentlichung; anonyme Spenden ab 150 Euro und Auslandsspenden ab 500 Euro unzulässig; „Internationale Freundinnen und Freunde unterstützen uns am besten mit Wissen, Code und Zusammenarbeit — mehr dazu auf Englisch."
- **Link-Ziele:** parlament.ddoe.at/mitgliedschaft → https://parlament.ddoe.at/mitgliedschaft/ · „mehr dazu auf Englisch" → https://www.ddoe.at/english/ · mailto:didide@ddoe.at · mailto:plattform@ddoe.at

---

## C) https://www.ddoe.at/satzung/

- **Erreichbar:** ja
- **Titel:** „Satzungsentwurf 2.5 — Direkte Demokratie Österreich | Direkte Demokratie Österreich"
- **H1:** „Satzungsentwurf 2.5 — Direkte Demokratie Österreich"
- **Version:** **2.5** (Entwurf)
- **Status-Hinweis (wörtlich):** „Status: Entwurf. Dieses Dokument ist die Diskussionsgrundlage für die Satzung 2.x der DDÖ (Stand: Entwurf 2.5). Es ersetzt *nicht* die derzeit geltende, beim Bundesministerium für Inneres hinterlegte Satzung in der Fassung 1.3."
- **Anzahl Paragraphen: 17**
  § 1 Name, Sitz, Tätigkeitsbereich und Vertretung · § 2 Ziel, Zweck und Wesen · § 3 Grundsätze des Wesenskerns · § 4 Mitgliedschaft · § 5 Die ParlamentPlattform und das Verfahren der Willensbildung · § 6 Organe der Partei · § 7 Mandaterteilung, Rechenschaft und Mandatsvereinbarung · § 8 Transparenz, Ethik und Datenschutz · § 9 Stufen der Zielverwirklichung · § 10 Finanzierung der Partei · § 11 Parteischiedsgericht · § 12 Internationale Zusammenarbeit · § 13 Teilhabe, Barrierefreiheit und Minderheiten · § 14 Gliederung der DDÖ · § 15 Satzungsänderung · § 16 Auflösung der Partei · § 17 Inkrafttreten
- Frühere Versionen: 1.3 als geltende Fassung erwähnt; 2.1 nicht auf der Seite (nur im Blog-Slug `satzungsentwurf-2-1`). Kein Änderungsprotokoll, keine PDF-Links.

---

## D) https://www.ddoe.at/english/

- **Erreichbar:** ja
- **Titel:** „English | Direkte Demokratie Österreich"
- **Menü:** identisch (ParlamentPlattform · Blog · Satzung · Spenden · Impressum & DSGVO)
- **Überschriften:** H1 „English" · H2 „We are the tool." · „The idea in one paragraph" · „Five steps, no gatekeepers" · „What makes us different" · „Where we are, honestly" · „An invitation" · „En français · En español · In italiano"
- **Plattform-Verweis:** „We are in the open alpha phase: statute draft 2.5 is public for discussion, and the platform is live at parlament.ddoe.at — motions, support, deliberation, voting, independently recomputable tallies and a feedback widget on every page." „Membership enrolment runs entirely on the platform." Link → https://parlament.ddoe.at/ (nur Startseite; **kein Link auf `/partner/`, `/zukunftswerkstatt/` oder `/mitgliedschaft/`**).
- **Partner-Verweis:** „An invitation": „If you are working on citizen-led democracy anywhere in the world — as a party, a platform project, a research group, a civic-tech collective or a citizens' assembly — we want to exchange knowledge, code and experience." Link „Write to us — partnerships" → `mailto:didide@ddoe.at?subject=International partnership — DDÖ`. FR/ES/IT-Absätze („nous cherchons des partenaires", „buscamos socios", „cerchiamo partner").
- Weitere Inhalte: Roadmap „eighteen years, to the 2044 national election", „one percent at the 2029 election", „roughly twenty-five predecessor parties … from Demoex in Sweden to Agora in Brussels to Team Mirai in Japan". Keine Erwähnung von „prototype", „simulation", „Zukunftswerkstatt".

---

## E) https://www.ddoe.at/blog/

- **Erreichbar:** ja
- **Titel:** „Blog | Direkte Demokratie Österreich"
- **Posts (Titel, Datum, URL):**
  1. „Zum ersten Mal in der Menschheitsgeschichte" — 19.08.2026 — /2026/08/19/zum-ersten-mal-in-der-menschheitsgeschichte/
  2. „We are the tool — an invitation to democratic innovators worldwide" — 19.08.2026 — /2026/08/19/we-are-the-tool/
  3. „Fünfundzwanzig Parteien haben es vor uns versucht. Das haben wir gelernt." — 19.08.2026 — /2026/08/19/lehren-aus-25-parteien/
  4. „Unser neuer Satzungsentwurf steht zur öffentlichen Diskussion" — 19.08.2026 — /2026/08/19/satzungsentwurf-2-1/
  5. „Satzung der DDÖ 1.3" — 10.09.2024 — /2024/09/10/satzung-der-didide-1-1/
- Keine Paginierung; keine Kommentare.

---

## F) https://www.ddoe.at/impressum/

- **Erreichbar:** ja (liefert die Seite „Impressum & DSGVO"; Menü-URL ist `/impressum-dsgvo/`)
- **Titel:** „Impressum & DSGVO | Direkte Demokratie Österreich"; H1 „Impressum & DSGVO"
- **Kontakt-Mail:** didide@ddoe.at (zusätzlich didide@didide.at)
- Medieninhaber: Michael Hackl, A-4076 Unterfreundorf 17; Direkte Demokratie Österreich (DDÖ) / Direkte Digitale Demokratie (DiDiDe); Parteienregisterzahl 502117.

---

## G) https://parlament.ddoe.at/ (ParlamentPlattform)

### G.1 Startseite `/`

- **Erreichbar:** ja
- **Titel:** „Willkommen · DDÖ"
- **Menüpunkte (wörtlich, Reihenfolge):** Parlament (/parlament/) · Mandatare (/mandatare/) · Übersicht (/uebersicht/) · Umsetzungsregister (/umsetzung/) · Zukunftswerkstatt (/zukunftswerkstatt/) · Antrag einbringen (/einbringen/) · Anmelden (/anmelden/) · Mitglied werden (/mitgliedschaft/). Sprachumschalter „EN" vorhanden.
- **Überschriften:** H1 „Wir sind das Werkzeug." · H2 „So funktioniert das System" (H3: Einbringen, Unterstützen, Beraten, Abstimmen, Nachrechnen und umsetzen) · H2 „Die Wege durch die Plattform" („Zwei Antragswege, eine Werkstatt-Schleife — jede Frist ist ein offener Parameter.") · H2 „Woran sich alles messen lässt" (Nachrechenbar · Keine verdeckte Reihung · KI schlägt vor, entscheidet nie · Ohne Hürden) · H2 „Alle Bereiche im Überblick" (acht Bereichskarten) · H3 „Anstoß geben"
- **Alpha-Hinweis (wörtlich):** „Die Plattform ist im Alpha-Betrieb: Alles hier ist echt bedienbar, wächst aber sichtbar weiter — was sich ändert, steht offen im Änderungsprotokoll und in der Zukunftswerkstatt."
- **Kennzahlen:** „6 bestätigte Mitglieder" · „4 laufende Verfahren" · „1 gefasste Beschlüsse"
- **KI-Hinweise:** „KI: Ähnlichkeitshinweis · Themen-Zuordnung"; „KI schlägt vor, entscheidet nie"
- **Feedback-Widget („Anstoß geben"):** „Was fehlt? Was stört? Was wünschen Sie sich? Jede Nachricht wird gespeichert und fließt in die Weiterentwicklung der Plattform ein." / „Sie schreiben anonym — als Mitglied könnten wir nachfragen."
- **Fußzeile:** „Plattform": Parlament · Mandatare · Gremien (/gremien/) · Mitglied werden · Lebensbereiche (/parlament/#feld-favoriten) · Die Plattform in Zahlen (/uebersicht/) · Umsetzungsregister · Zukunftswerkstatt. „Offenheit": Quellcode (AGPL) → https://github.com/parlamentplattform/parlamentplattform · Register als JSON → /umsetzung.json · Offene Parameter → /parameter/ · **Internationale Partner → /partner/** · Satzungsentwurf → https://www.ddoe.at/satzung/ · ddoe.at. Schluss: „Direkte Demokratie Österreich — Ohne Skriptzwang, ohne Tracking, ohne verdeckte Reihung."
- **Version:** **Keine Versionsnummer, kein Build/Commit, kein Datum in Fußzeile oder Startseite.** (Versionsstand nur über das GitHub-CHANGELOG ableitbar: 0.32.0, siehe H.)

### G.2 `/uebersicht/`

- **Erreichbar:** ja · **Titel:** „Übersicht · DDÖ" · H1 „Die Plattform in Zahlen"
- **Mitglieder:** „6 bestätigte Mitglieder · 0 neu in den letzten 7 Tagen"
- **Anträge:** „4 laufende Anträge von 6 insgesamt · 1 neu diese Woche"; nach Phase: 2 in Unterstützung · 1 in Beratung · 1 in Abstimmung · 1 angenommen · 1 abgelehnt
- **Besuche:** „83 Seitenaufrufe heute · 15 Besucher:innen heute · 380 Aufrufe in 7 Tagen"
- **Abstimmungen: Ergebnisse und Beteiligung:**
  - „Testlauf: Listenreihung Gemeinderat St. Marienkirchen an der Polsenz" — läuft — Ja 0 · Nein 0 · Enthaltung 0 — 0 von 5 Stimmberechtigten (0 %)
  - „Jede Ratssitzung als Livestream mit Archiv" — abgelehnt — Ja 1 (50 %) · Nein 1 (50 %) — 2 von 5 (40 %)
  - „Abgeschlossenes Beispiel: Namenskonvention des Prototyps" — angenommen — Ja 3 (60 %) · Nein 1 (20 %) · Enthaltung 1 (20 %) — 5 von 5 (100 %)
- **KI-Verbrauch des Modell-Steckplatzes:** „mistral · mistral-small-latest · 1 archivierte Läufe · 0 davon gescheitert · Tokens diesen Monat: 486 von 1000000 · 0%" → **KI-Anbieter angeschlossen: ja (Mistral)**
- **Entwicklung:** Grafiken (Mitglieder kumuliert, neue Anträge/Woche, Seitenaufrufe/Tag), Zeitachse 02.02.26–02.09.26
- **Meistgelesene Anträge:** „Photovoltaik auf dem Dach des Gemeindeamts" 10 Aufrufe · „Jede Ratssitzung als Livestream mit Archiv" 8 Aufrufe · weitere mit 6 und 5
- **Wie hier gezählt wird:** „ohne Cookies, ohne Werbe-Skripte und ohne Speicherung von IP-Adressen"
- **Version:** keine Versionsangabe.

### G.3 `/zukunftswerkstatt/`

- **Erreichbar:** ja · **Titel:** „Zukunftswerkstatt · DDÖ" · H1 „Die Zukunftswerkstatt"
- **Überschriften:** Zwei Gesichter, ein Werkzeug · Politische Bildung durch Selbermachen · Das Sinnesorgan der Selbstregulation · Vier Grundsätze („Die KI schlägt vor, sie entscheidet nie." · „Der Demos darf atmen, die Stimme wiegt immer gleich." · „Das Gedächtnis ist der Schatz, nicht das Modell." · „Auf Unwissen gebaut.") · Der Weg eines Antrags im Zielbild · Woher die Fakten kommen · Wer wacht worüber · Der Modell-Steckplatz — Rechenschaft in Zahlen · Zuletzt archivierte Läufe · An die demokratischen Bewegungen weltweit · Anstoß geben
- **Wortlaut zur Simulation:** Hier wird der Begriff **„StaatsSimulation" weiterhin verwendet** — als „Rechenkern" der Zukunftswerkstatt: „…mit der StaatsSimulation als Rechenkern, einem digitalen Zwilling des Staatswesens in wachsender Auflösung…"; „Jede Ausgabe der Simulation ist als Einschätzung gekennzeichnet, mit Quellen und Kontextstand."; Prognose-Register. „Prototyp", „Alpha", „2044" kommen hier nicht vor.
- **Modell-Steckplatz:** „Angeschlossen: mistral · mistral-small-latest"; 1 archivierte Läufe; Tokens diesen Monat: 486 von 1000000.
- **Zuletzt archivierte Läufe:** 1 Eintrag — „Testlauf: monatlicher öffentlicher Entwicklungsbericht" (Antrag /antrag/2/), mistral-small-latest, 207+279 Tokens, 2361 ms, 02.09.2026 01:25.
- **Woher die Fakten kommen:** Rechtsinformationssystem des Bundes; amtliche Personal-Aggregate; offene Kerndaten öffentlicher Vergaben; plattformeigene Daten. „Kein KI-System schreibt in die Faktenbasis."
- **Wer wacht worüber:** Koordinationsrat (Faktenbasis, Parameterregister), Integritätsrat (Hervorhebung von Anträgen), Expertenrat (zwei Gruppen, Interessenkonflikt-Prüfung), jedes Mitglied (Beanstandung → Korrekturlauf).
- **An die demokratischen Bewegungen weltweit:** „Labor der Demokratien, auf Jahrzehnte angelegt"; Link „Zur Partner-Seite →" → /partner/; Kontakt plattform@ddoe.at; Link „Alle offenen Parameter →" → /parameter/.

### G.4 `/partner/`

- **Erreichbar:** ja · **Titel:** „Internationale Partner · DDÖ" · H1 „Internationale Partner"
- **Überschriften:** H2 „Der Fahrplan der Zusammenarbeit" · H2 „Was wir mitbringen — und was wir suchen" · H3 „Anstoß geben"
- **Inhalt:** Kooperationsmodell „Die Bürgerinnen und Bürger entscheiden selbst, die Technik ist das Werkzeug, die Mandatare sind die Umsetzer." Trennung von System und Parametern. Fahrplan in 3 Punkten: (1) ParlamentPlattform quelloffen (AGPL), zweisprachig, mit Audit-Log und Parameterregister; (2) offene Standards/Werkzeugtausch inkl. Exportformat „Nachrechenbare Abstimmung"; (3) strukturierter Austausch über ein sprachneutrales Parameterregister. Angebot: nachrechenbare Auszählung, Regel-Einfrieren, Umsetzungsregister, Selbstregulation. Gesucht: Betriebspraxis, Kampagnenerfahrung, eID-Expertise, Wahlerfahrung. Arbeitssprache Englisch oder Deutsch.
- **Konkrete Partner:** **keine** namentlich genannt (keine Organisationen, keine Länder außer Österreich).
- **Links:** „Kontakt aufnehmen" → mailto:plattform@ddoe.at · „Quellcode ansehen" → GitHub. Keine Versions-/Datumsangabe.

### G.5 `/parameter/`

- **Erreichbar:** ja · **Titel:** „Offene Parameter · DDÖ" · H1 „Offene Parameter"
- **5 Parameter-Einträge (wörtlich, Stand jeweils 02.09.2026):**

| Schlüssel | Wert | Beschreibung | Gruppe |
|---|---|---|---|
| gremien-hoechstrunden | 3 Runden | „Höchstzahl der Runden der Entwurfsschleife; danach geht der Vorschlag in jedem Fall zur Endabstimmung" | Gremien |
| gremien-review-tage | 14 Tage | „Frist der Unterstützer in der Entwurfsschleife: Vorschlag annehmen oder mit konkretem Wunsch zurückgeben" | Gremien |
| gremien-rollen-dauer-tage | 730 Tage | „Regeldauer einer Gremien-Rolle (zwei Jahre)" | Gremien |
| gremien-ueberarbeitung-tage | 14 Tage | „Überarbeitungsfrist des Expertenrats je Rückgabe-Runde" | Gremien |
| ki-monatstokens | 1000000 Tokens/Monat | „Hartes Monatsbudget des Modell-Steckplatzes" | KI |

- Link „Register als JSON →" → /parameter.json. Hinweis: Verfahrensfristen (Unterstützung 60 Tage, Beratung 21 Tage, Endabstimmung 28 Tage laut CHANGELOG 0.15.0) sind **nicht** als Parameter im Register enthalten.

### G.6 `/parameter.json`

- **Erreichbar:** ja. Inhalt (wörtlich, 5 Einträge; Felder `schluessel`, `wert`, `einheit`, `beschreibung`, `quelle`, `geaendert_am`; keine Metadaten wie version/commit):

```json
{
 "parameter": [
  {"schluessel": "gremien-hoechstrunden", "wert": "3", "einheit": "Runden",
   "beschreibung": "Höchstzahl der Runden der Entwurfsschleife; danach geht der Vorschlag in jedem Fall zur Endabstimmung.",
   "quelle": "§ 5 Abs 12 („Rundenzahl per Verfahrensordnung") · F-67", "geaendert_am": "2026-09-01T23:05:46.386184+00:00"},
  {"schluessel": "gremien-review-tage", "wert": "14", "einheit": "Tage",
   "beschreibung": "Frist der Unterstützer in der Entwurfsschleife: Vorschlag annehmen oder mit konkretem Wunsch zurückgeben. Nach Ablauf wertet die Frist aus — Untätigkeit hemmt nie.",
   "quelle": "§ 5 Abs 12 · F-67", "geaendert_am": "2026-09-01T23:05:46.373474+00:00"},
  {"schluessel": "gremien-rollen-dauer-tage", "wert": "730", "einheit": "Tage",
   "beschreibung": "Regeldauer einer Gremien-Rolle (zwei Jahre): Bestellung auf öffentliche Ausschreibung, Bestätigung durch die Mitgliederversammlung, automatisches Erlöschen.",
   "quelle": "§ 6 Abs 8 · F-66", "geaendert_am": "2026-09-01T23:05:46.399610+00:00"},
  {"schluessel": "gremien-ueberarbeitung-tage", "wert": "14", "einheit": "Tage",
   "beschreibung": "Überarbeitungsfrist des Expertenrats je Rückgabe-Runde. Verstreicht sie ohne neue Einreichung, geht die zuletzt vorgelegte Fassung zur Endabstimmung.",
   "quelle": "§ 5 Abs 12 · F-67", "geaendert_am": "2026-09-01T23:05:46.380167+00:00"},
  {"schluessel": "ki-monatstokens", "wert": "1000000", "einheit": "Tokens/Monat",
   "beschreibung": "Hartes Monatsbudget des Modell-Steckplatzes. Ist es erschöpft, wird der Steckplatz stumm, bis der Monat wechselt — Kostendeckel der Zukunftswerkstatt.",
   "quelle": "F-60 · L7", "geaendert_am": "2026-09-01T23:05:46.405923+00:00"}
 ]
}
```

### G.7 `/gesund/`

- **Erreichbar:** ja (HTTP 200). Inhalt wörtlich: `{"status": "ok"}` — keine Version, kein Commit, keine weiteren Felder.

### G.8 `/mitgliedschaft/` (Ziel der Buttons „Mitglied werden"/„Fähigkeiten einbringen"; ergänzend geprüft)

- **Erreichbar:** ja · **Titel:** „Mitglied werden · DDÖ" · H1 „Ihre Stimme, direkt."
- Rechte-Karten (Anträge einbringen, Unterstützen, Mitberaten, Abstimmen, Selbst nachrechnen, Umsetzung verfolgen), „Vom Antrag zum Beschluss", Anwartschaft, Beitrag („Richtwert 30 € im Jahr", „Bezahlt wird per QR-Code direkt von Konto zu Konto"), Identität, Region, Zukunftswerkstatt.
- Buttons: „Jetzt Mitglied werden" → /mitglied-werden/ · „Ich bin schon Mitglied — anmelden" → /anmelden/

---

## H) https://github.com/parlamentplattform/parlamentplattform

- **Erreichbar:** ja (öffentlich)
- **README-Titel:** „# ParlamentPlattform" — erster Absatz: „Die offene Beteiligungs- und Entscheidungsinfrastruktur der Direkte Demokratie Österreich (DDÖ)." README-Abschnitte: Warum dieses Projekt anders gebaut ist · Schnellstart · Aufbau des Repositories · Mitmachen · English summary. Status-Zeile in der README: **„Status: Phase 1 — der Prototyp ist öffentlich:"** (hier steht weiterhin „Prototyp", nicht „Alpha").
- **About:** „Offene Beteiligungs- und Entscheidungsinfrastruktur der Direkte Demokratie Österreich (DDÖ) — nachrechenbar, quelloffen, AGPL." Topics: agpl, austria, civic-tech, deliberation, direkte-demokratie, django, e-democracy, open-source, python. Lizenz AGPL-3.0-or-later; Default-Branch main; Stars 0 · Forks 0 · Watchers 0.
- **Anzahl Commits:** **34** (main)
- **Letzter Commit:** `225cde2` (voll: 225cde227129206b39ac0410ea54cccef632c808), **2026-09-02T00:43:31Z**, Nachricht wörtlich: **„push"**, Autor oisxeng; 16 Dateien geändert (+399/−160), u. a. CHANGELOG.md, verfahren/templates/verfahren/partner.html, zukunftswerkstatt.html, uebersicht.html, locale/en. Davor: `1124572` „nez" (2026-09-01 23:59Z), `7325455` „0b", `ba6edbb` „0a", `d1585ad` „P5" (alle 2026-09-01). (Quelle: GitHub-API-Commit-Liste per WebFetch; die HTML-Seite `/commits/main` ist per robots.txt gesperrt.)
- **CI:** Die README enthält **kein CI-Badge**. Auf der Actions-Seite existiert ein Workflow „CI"; 30 Läufe auf main, **alle erfolgreich (grün)**, inklusive der Läufe zu den Commits 225cde2, 1124572, 7325455, ba6edbb, d1585ad. Keine fehlgeschlagenen Läufe sichtbar.
- **Releases:** keine („There aren't any releases here"). **Tags:** Tag-Seite und API per WebFetch nicht abrufbar (robots.txt / 403) — nicht feststellbar; auf der Repo-Seite wird keine Tag-Zahl angezeigt.
- **Versionsstand laut Repo:** CHANGELOG.md neueste Version **[0.32.0] — 2026-09-02 „Nachschärfung 2"** (u. a. „Partner-Seite /partner/ hinzugefügt", „KI-Verbrauch visualisiert", „Flussdiagramm vervollständigt bis Umsetzungsregister"). Weitere Marker: 0.29.0 Modell-Steckplatz (Mistral erster Anbieter), 0.30.0 Parameterregister, 0.16.0 „Zukunftswerkstatt — Umbenennung von StaatsSimulation, alte Route weiterhin verfügbar", 0.13.1 CI-Automatisierung (Auto-Deploy nach grüner Prüfung, Render-Deploy-Hook), 0.10.1 „136 Tests, 99% Kern-Abdeckung", 0.1.0 (2026-08-19) Phase 0. `pyproject.toml` steht dagegen unverändert auf `version = "0.1.0"` (Django >=5.0,<5.3; Python >=3.11). Oberste Verzeichnisse: .github/workflows, anstoss, config, daten, docs, gremien, ki, locale, mandatare, mitglieder, parameter, plattform_core, policies, tests, uebersicht, verfahren, verify; Dateien u. a. CHANGELOG.md, CONTRIBUTING.md, Dockerfile, GOVERNANCE.md, LICENSE, Makefile, README.md, SECURITY.md, docker-compose.yml, manage.py, pyproject.toml, render.yaml.

---

## Abgleich mit den Vorgaben des Gründers

| # | Vorgabe | Ergebnis | Befund |
|---|---------|----------|--------|
| 1 | Mitmachen-Seite entfernt oder auf Plattform-Anmeldung umgeleitet? | **NEIN** | `/mitmachen/` existiert weiterhin (keine 404, keine Weiterleitung). Sie wurde zur Seite „Spenden" umgebaut und verweist für die Mitgliedschaft nur per Textlink auf parlament.ddoe.at/mitgliedschaft/. |
| 2 | „So funktioniert's" neu ausgearbeitet mit systemischem Ansatz bis 2044? | **JA** | Button „So funktioniert es" → Verfahrensabschnitt (5 Schritte) plus neue Sektion „Die systemische Herangehensweise — Ein Verfahren, das sich selbst verbessert." mit „18 Jahren … bis zur Nationalratswahl 2044", offenen Parametern, Zukunftswerkstatt, Rückkopplung, Mandatar-Steuerung. (Eine Überschrift mit dem Wortlaut „So funktioniert's" gibt es nicht — nur den Button.) |
| 3 | „Distanz zwischen Wissen und Macht" umformuliert auf Betroffene/Berufsgruppen? | **JA** | Text: „Die meisten Gesetze betreffen nicht alle — sie betreffen Minderheiten. Eine Regelung für Installateure betrifft Installateure; wer könnte sie besser beurteilen? … von denen entscheidbar sein, die sie tatsächlich betreffen." (Wort „Berufsgruppe" selbst kommt nicht vor; Beispiel Installateure.) |
| 4 | ParlamentPlattform im Menü verlinkt und „Alpha-Phase" statt „Prototyp"? | **JA** | Menüpunkt 1 „ParlamentPlattform" → https://parlament.ddoe.at/; „Alpha-Phase" mehrfach (Hero-Button, Fahrplan 2026, Mitmachen, Footer); „Prototyp" 0 Treffer auf ddoe.at. (Außerhalb der Website: GitHub-README sagt weiterhin „der Prototyp ist öffentlich"; ein Plattform-Antrag heißt „Namenskonvention des Prototyps".) |
| 5 | „Dieses Werkzeug baut sich nicht von selbst": Mitglied werden + Fähigkeiten einbringen → Plattform-Anmeldung? | **JA** | Beide Buttons („Mitglied werden", „Als Mitglied einsteigen") → https://parlament.ddoe.at/mitgliedschaft/. Die Sektionsüberschrift lautet inzwischen „Das Werkzeug steht. Jetzt wächst es mit uns." (nicht mehr „Dieses Werkzeug baut sich nicht von selbst"). |
| 6 | Spenden mit QR-Code? | **JA** (mit Vorbehalt) | Auf `/mitmachen/` (Spenden): IBAN-Block + Text „Der QR-Code ist ein gewöhnlicher Überweisungs-Code (EPC): Banking-App öffnen, scannen, Betrag selbst wählen". Ein Bild-Element für den QR ist per WebFetch nicht nachweisbar (vermutlich Inline-SVG/Skript). Auf der Startseite selbst kein QR-Code. |
| 7 | Menüeintrag „Mitmachen" → „Spenden"? | **JA** | Menü: ParlamentPlattform · Blog · Satzung · **Spenden** (→ /mitmachen/) · Impressum & DSGVO. Kein „Mitmachen"-Eintrag. |
| 8 | „Minderheiten mit Sachkunde": „Zukunftswerkstatt" statt „Simulation"? | **JA** | „…zuerst in der Zukunftswerkstatt erprobt." „Simulation"/„StaatsSimulation": 0 Treffer auf der Startseite. (Auf parlament.ddoe.at/zukunftswerkstatt/ wird „StaatsSimulation" als Rechenkern weiter verwendet.) |
| 9 | Teaser für internationale Partner mit Link zu /partner/ der Plattform? | **NEIN** | Sektion „International" existiert, verlinkt aber nur „Read in English →" (/english/); /english/ verlinkt nur parlament.ddoe.at/ und eine mailto-Adresse. **Kein Link auf https://parlament.ddoe.at/partner/** auf ddoe.at (die Partner-Seite selbst ist live, aber nur aus der Plattform-Fußzeile/Zukunftswerkstatt verlinkt). |
| 10 | Satzung 2.5 online? | **JA** | `/satzung/` zeigt „Satzungsentwurf 2.5" mit 17 Paragraphen; Status „Entwurf" (geltend bleibt Fassung 1.3). Menü „Satzung" und Footer „Satzungsentwurf 2.5" verlinken dorthin. |
