# ADR-015: Browserquellen mit einer Content-Security-Policy begrenzen

Datum:4.11.2026. Technischer Baustein des dokumentierten Sicherheitsrests der
Gesamtprüfung0.45; keine Satzungs-, Rechte-, Kosten- oder Gründerentscheidung.

## Kontext

Die Plattform lädt ihre Skripte selbst und verbietet Inline-Skripte sowie native
Inline-Handler bereits im Vorlagenwächter. Der Browser setzte diese Beschränkung
bisher nicht durch. Eine zusätzliche Bibliothek ist dafür nicht nötig.

## Technische Entscheidung

`config/sicherheitsheader.py` ergänzt die wirksame Richtlinie auf HTML-/XHTML-
Antworten. Bestehende CSP-Header werden nicht überschrieben; PDF-, JSON-, Bild-
und andere Datenantworten bleiben unberührt. Die Middleware liegt vor der
htmx-Umleitungsanpassung, sodass deren endgültige HTML-Antwort den Header erhält.
TLS-Umleitungen und direkt von WhiteNoise gelieferte statische Dateien werden
von ihren bisherigen äußeren Middleware-Schichten behandelt.

```text
default-src 'none'; script-src 'self' 'unsafe-eval'; script-src-attr 'none';
style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self';
connect-src 'self'; manifest-src 'self'; base-uri 'none'; form-action 'self';
frame-ancestors 'none'; object-src 'none'; frame-src 'none'; worker-src 'none';
media-src 'none'
```

Skripte, Verbindungen, Schriften und Manifest kommen vom eigenen Ursprung.
Das eingebettete Ausweislogo braucht data-Bilder. Inline-/Fremdskripte, native
Inline-Handler, fremde Formularziele, Basisadressen, eingebettete Fremdseiten,
Objekt-, Worker- und Medienquellen werden nicht freigegeben. Externe normale
Links bleiben nutzbar. Die Begrenzung von Frames entspricht dem bestehenden
X-Frame-Options-Schutz. Keine Upgrade-Direktive für lokale HTTP-Tests.

## Bewusste Grenzen

Dies ist keine vollständig strikte CSP: Die eingecheckte Alpine-Fassung benutzt
`new Function`, htmx dynamische Ausdrücke. Dafür bleibt `unsafe-eval` nötig.
Bestehende Styles und berechnete Styleattribute brauchen `unsafe-inline` bei
Styles. Eine spätere engere Politik erfordert einen eigenen geprüften Framework-
und Style-Umbau. Vertrauenswürdiger JavaScript-Code kann weiterhin Ausdrücke
auswerten; die Richtlinie ersetzt weder Escaping, Rechteprüfung noch sichere
Inhaltstypen und ist kein Nachweis, dass alle XSS-Wege beseitigt sind.

Keine Nonces, neue Pakete, externen CSP-Berichtsempfänger oder zusätzlichen
serverseitigen Meldedaten. Browser sollen durch diese Änderung keine weiteren
URLs, Formularinhalte oder Kontoinformationen an einen Meldedienst übertragen.

## Prüfung

Lokale Browserproben verwenden synthetische Inhalte. Positive Fälle prüfen
Navigation, Themenwechsel, htmx und eingebetteten Ausweis samt PDF-Download;
negative Fälle prüfen eingefügte Inline-/Fremdskripte, native Handler, fremde
Formziele und Objekte. Die Anwendung bleibt ohne JavaScript bedienbar.
Die tatsächliche Gesamtprüfung einschließlich PostgreSQL und Pflicht-CI bleibt
vor Auslieferung erforderlich; eine einzelne Headerprobe ersetzt sie nicht.

## Quelle

[W3C: Content Security Policy Level3](https://www.w3.org/TR/CSP3/), am4.11.2026
gelesener Arbeitsentwurf vom27.10.2026. Die konkrete Wahl und ihre Ausnahmen
ergeben sich aus den verwendeten lokalen Ressourcen und ihrer Browserprüfung.
