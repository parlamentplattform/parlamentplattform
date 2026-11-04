# Sicherheitsmeldungen

Wenn du eine Schwachstelle findest, melde sie bitte **nicht** als öffentliches Issue.

- E-Mail: didide@ddoe.at, Betreff „SECURITY"
- Wir bestätigen den Eingang **binnen 48 Stunden**, halten dich über die Behebung auf dem Laufenden und nennen dich — wenn du möchtest — nach der Behebung öffentlich als Finderin oder Finder.
- Koordinierte Offenlegung: Wir veröffentlichen behobene Schwachstellen mit Beschreibung und Zeitleiste im CHANGELOG. Bei einer Plattform, deren Versprechen Überprüfbarkeit ist, gehört auch das Scheitern dokumentiert.
- Bitte keine Tests gegen den Produktivbetrieb mit echten Mitgliederdaten; eine lokale Instanz ist in zwei Minuten aufgesetzt (`docker compose up`).

HTML-Antworten begrenzen Browserquellen durch eine Content-Security-Policy.
Die nötigen Ausnahmen für dynamische Alpine-Ausdrücke und bestehende Styles
stehen in [ADR-015](docs/adr/ADR-015-browserquellen-csp.md). Die Richtlinie ersetzt
weder Escaping noch Rechteprüfung; externe Meldedienste sind nicht eingerichtet.
