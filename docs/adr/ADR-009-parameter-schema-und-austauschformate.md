# ADR-009: Sprachneutrales Parameter-Schema und offene Austauschformate

**Status:** angenommen (3.9.2026) · **Bezug:** Satzung § 12 Abs 5, Fahrtenbuch FB-M5/M6, A0-09

## Kontext

Die Partei will die ParlamentPlattform nicht als Dienst für andere Länder betreiben, sondern als
**gemeinsame Grundsoftware**: Jedes Land betreibt seine eigene Instanz auf eigenen Servern, mit
eigener Satzung, eigenem Kategorienbaum und eigenen Stellgrößen, die dort selbst lernen. Die
Weiterentwicklung des Kerns findet gemeinsam statt. Dafür braucht es eine Verabredung, *was*
zwischen den Instanzen vergleichbar ist — ohne dass ein System dem anderen gleichen muss und ohne
dass personenbezogene Daten die Instanz verlassen.

## Entscheidung

1. **Ein Kern, viele Instanzen.** Das Repository `parlamentplattform/parlamentplattform` ist der
   Kern; Landesspezifisches liegt in Konfiguration und Daten (`policies/*.yaml`, Parameterregister,
   Übersetzungen, `.env`), nicht im Code. Instanzen folgen versionierten Kern-Freigaben (SemVer).
2. **Sprachneutrale Kennungen.** Jede Stellgröße trägt eine `schema_key` (englisch, stabil,
   `bereich.name`). Das Register bleibt in Landessprache; die Kennung ist die Brücke. Kennungen und
   Kennzahlen stehen in `plattform_core/schema.py` (rein, getestet) und in `docs/SCHEMA.md`.
3. **Zwei Exporte je Instanz:** `/parameter.json` (Stellgrößen und Verfahrensordnung) und
   `/kennzahlen.json` (aggregierte Zählungen und Anteile). Beide tragen denselben Kopf
   (`schema_version`, `system_id`, `system_name`, `software`, `exportiert_am`), sind öffentlich und
   CORS-offen. `system_id` = `<ländercode>-<kurzname>` (`DDOE_SYSTEM_ID`).
4. **Werte bleiben eigen.** Das Schema definiert Bedeutung und Einheit, nie Sollwerte. Ein Import
   dient der Gegenüberstellung; übernommen wird nur durch Beschluss der eigenen Mitgliederversammlung.
5. **Nie personenbezogen.** Die Prüfung `pruefe_export` beanstandet Felder wie `email`, `name`,
   `pseudonym`, `mitglied`. Abstimmungs-Exporte (`/antrag/<id>/export.json`) bleiben ein eigenes,
   bereits bestehendes Format (ADR-003) und sind nicht Teil des Parameter-Austauschs.
6. **Versionierung.** Neue Kennungen erhöhen die Nebenversion, umgedeutete Kennungen die
   Hauptversion; Leser verarbeiten unbekannte Kennungen tolerant.

## Folgen

- Das Parameterregister bekommt das Feld `schema_key` (Erstbestand mit Kennungen; lokale Einträge
  dürfen leer bleiben). `/parameter.json` bleibt abwärtskompatibel (bisherige Felder unverändert).
- `/kennzahlen.json` ist neu und liest nur Zählungen aus Antrag, Mitglied, Vollzug und Kategorie.
- Das Übertragungspaket (`/partner/paket/`, FB-M7) enthält Schema, Verfahrensordnung, Kategorienbaum
  und den Erstbestand mit Kennungen — eine neue Instanz startet schema-konform.
- Der Import fremder Exporte (`partner_import`, Modell `PartnerParameter`) folgt in S14b.
