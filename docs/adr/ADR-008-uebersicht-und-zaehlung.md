# ADR-008: Öffentliche Übersicht, eigene Verwaltung, datensparsame Zählung

**Status:** angenommen · 20.08.2026
**Bezug:** F-50, F-51, F-52 · § 2 Abs 5, § 4, § 8 der Satzung · N-03 (keine US-Dienste, keine Tracker)

## Kontext

Die Plattform soll öffentlich zeigen, was sich auf ihr tut (Mitglieder, Anträge,
Abstimmungsergebnisse, Besuche), und braucht eine Mitgliederverwaltung
(Statuswechsel, Datenkorrektur, Adminrollen). Drei naheliegende Abkürzungen
haben wir geprüft und verworfen:

1. **Fertige Analytics (Google Analytics, Matomo Cloud, Plausible Cloud):**
   verbietet sich — N-03 schließt Tracker und Dienste Dritter im Datenpfad aus;
   Mitgliedschaftsdaten einer Partei sind Art-9-Daten.
2. **JavaScript-Diagrammbibliotheken (Chart.js, Plotly …):** Die Plattform
   verspricht Lesen und Abstimmen ohne JavaScript (F-32). Eine Übersichtsseite,
   die ohne Skripte leer bleibt, bricht dieses Versprechen.
3. **Django-Admin als Mitgliederverwaltung:** generisch, englischsprachig
   gedacht, kennt weder unser Statusmodell noch Begründungspflicht oder
   Audit-Kette — und lädt zu Rohzugriffen ein, die kein Verfahren abbilden.

## Entscheidung

1. **Diagramme entstehen serverseitig als SVG** in `plattform_core/diagramme.py`
   — frameworkfrei, getestet, wenige hundert Zeilen, native Tooltips über
   SVG-`<title>`. Die Reihenfarben (Blau/Gold/Dunkelrot) sind mit einem
   Farbfehlsichtigkeits-Prüfwerkzeug validiert (Deutan/Protan/Tritan-Abstand,
   Helligkeit, Chroma); Zahlen stehen immer auch als Text neben der Grafik —
   Farbe trägt nie allein die Information.
2. **Besuche zählt eine eigene Middleware als Tages-Summen.** Keine Cookies,
   keine IP-Speicherung: Für „Besucher je Tag" wird `sha256(Serverschlüssel +
   Tagesdatum + IP + Browserkennung)` gekürzt gespeichert — nicht zurückrechenbar
   und ab Mitternacht wertlos, weil das Datum aus der Formel wandert (dasselbe
   Prinzip nutzen datenschutzfreundliche Zähler wie Plausible). Maschinen
   (Bots, Monitoring, Werkzeuge) werden per Browserkennung ausgefiltert;
   die Zählweise ist auf der Übersichtsseite selbst erklärt.
3. **Die Mitgliederverwaltung ist eine eigene, schmale Anwendung** unter
   `/verwaltung/` (der Django-Admin ist nicht mehr eingehängt). Sie kennt genau
   die Handlungen, die die Satzung vorsieht — pausieren bis Beitragseingang,
   Ausschluss als Vollzug eines Beschlusses, Datenkorrektur, Identitätsstufe,
   Adminrollen — und schreibt jede davon in das öffentliche Audit-Log:
   Aktion, Mitgliedsnummer, Begründung, nie personenbezogene Werte.
4. **Adminrollen ohne Superuser:** Ein fixer Erstzugang (`DDOE_FIX_ADMIN`,
   standardmäßig didide@ddoe.at) ist immer Admin und unantastbar, damit die
   Verwaltung nie herrenlos wird; alle weiteren Admins ernennen und entziehen
   Admins einander, niemand wirkt auf das eigene Konto.

## Konsequenzen

- Übersicht und Diagramme funktionieren in jedem Browser, auch ohne Skripte,
  und halten N-03 ohne Ausnahme ein.
- Die Besucherzahl ist eine ehrliche Untergrenze, kein Werbemaß: Wer den
  Browser wechselt, zählt doppelt; wer als Bot auftritt, zählt gar nicht.
- Eine „Unique Visitors über Wochen"-Metrik ist bewusst unmöglich — dafür
  müsste man Menschen wiedererkennen, und genau das tun wir nicht.
- Der Wegfall des Django-Admins nimmt uns generische Durchgriffe; jede neue
  Verwaltungshandlung muss als eigener, auditierter Codepfad entstehen.
  Das ist Absicht (vgl. ADR-005: es gibt keinen Codepfad zum Ändern des Logs).
