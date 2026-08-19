# ADR-001: Fokussierter Eigenbau des Verfahrenskerns statt Decidim/CONSUL-Basis

Status: angenommen · Datum: 2026-08-19

## Kontext
Es existieren reife Open-Source-Beteiligungsplattformen (Decidim, CONSUL,
Antragsgrün). Eine Analyse von ~25 Vorgängerparteien und der verfügbaren
Software (docs/CONCEPT.md, Abschnitt 4.1) zeigt: Die satzungsprägenden
Mechanismen der DDÖ — Regel-Einfrieren (§ 5 Abs 5), Rechenschaftsregister
(§ 7 Abs 5), Nachrechenbarkeit ohne Spezialkenntnisse (§ 5 Abs 8),
Anwartschaftslogik (§ 4 Abs 4) — sind in keiner der Plattformen vorgesehen
und müssten gegen deren Architektur nachgerüstet werden.

## Entscheidung
Wir bauen den Verfahrenskern selbst — als kleines, frameworkfreies Paket
(plattform_core) plus dünne Django-Anwendung. Wir bauen NICHT selbst:
Identität (Keycloak), Datenbank (PostgreSQL), Web-Framework (Django),
E-Mail, Monitoring.

## Konsequenzen
+ Der Kern bleibt klein genug, dass Laien ihn lesen können — das ist eine
  Satzungsanforderung, kein Nice-to-have.
+ Keine Upgrade-Tretmühle eines fremden Großsystems über die Projektlaufzeit.
− Wir tragen die volle Verantwortung für Korrektheit → kompensiert durch
  Property-based Tests, 90-%-Abdeckungspflicht und die unabhängige
  Zweitimplementierung in verify/nachrechnen.py.
− Kein fertiges Ökosystem (Kommentar-Moderation etc.) → bewusst schrittweise.
