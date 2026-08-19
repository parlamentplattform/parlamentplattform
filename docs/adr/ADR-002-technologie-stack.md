# ADR-002: Python/Django + PostgreSQL + server-gerendertes Frontend

Status: angenommen · Datum: 2026-08-19

## Kontext
Das Projekt muss 2029 noch laufen und von wechselnden Freiwilligen wartbar
sein. Der größte Civic-Tech-Talentpool im deutschsprachigen Raum arbeitet
mit Python/Django (u. a. mein.berlin/adhocracy).

## Entscheidung
Python 3.11+ / Django 5 (LTS-Linie) / PostgreSQL 16. Frontend server-
gerendert (Django-Templates), später ergänzt um HTMX; kein SPA-Framework.
Verfahrenslogik ausschließlich im frameworkfreien Paket plattform_core.

## Konsequenzen
+ "Langweilige Technologie": lange Wartungsfenster, riesige Dokumentation,
  leicht zu besetzen.
+ Ohne JavaScript les- und abstimmbar → Barrierefreiheit (F-32) und kleiner
  Angriffsraum.
− Keine Realtime-Effekte out of the box — für ein Verfahren mit Fristen in
  Tagen ist das kein Verlust.
