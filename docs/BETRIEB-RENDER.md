# Testbetrieb auf Render — Schritt für Schritt

Ziel: Die Plattform öffentlich erreichbar machen (z. B. `plattform.ddoe.at`),
damit Interessierte sich registrieren und den Verfahrensweg ausprobieren können.

## Warum Render, und warum nur für den Testbetrieb

Der bestehende Webhoster von ddoe.at (World4You, Shared Hosting) kann PHP/MySQL,
aber keine Python-Anwendungen und keine Container — die Plattform kann dort
nicht laufen. Render kann beides, deployt direkt aus diesem Repository und
betreibt Dienst und Datenbank im **Rechenzentrum Frankfurt**.

**Datenschutz-Einordnung:** Render Services, Inc. ist ein US-Unternehmen.
Mitgliedschaftsdaten einer Partei sind besondere Kategorien personenbezogener
Daten (Art 9 DSGVO — politische Meinung). Für den **Testbetrieb** mit
ausdrücklich einwilligenden Testnutzerinnen und -nutzern und einem klaren
Hinweis auf der Registrierungsseite ist das vertretbar. Für den **Echtbetrieb**
mit echten Mitgliederdaten empfehlen wir den Umzug auf einen EU-/AT-Anbieter
(z. B. Hetzner Deutschland, Anexia Österreich) — das Repository ist darauf
vorbereitet (`docker-compose.yml`, 12-Factor-Konfiguration), der Umzug ist ein
Datenbank-Export/-Import plus DNS-Wechsel.

## Einrichtung (einmalig, ca. 15 Minuten)

1. **Render mit GitHub verbinden:** render.com → Dashboard → *New* → *Blueprint*
   → Repository `parlamentplattform/parlamentplattform` autorisieren und wählen.
   Render liest `render.yaml` und schlägt an: Web-Service `parlamentplattform`
   + Datenbank `plattform-db` (beide Frankfurt). Bestätigen.
2. **Warten:** Erster Build dauert einige Minuten. Der Dienst ist danach unter
   `https://parlamentplattform.onrender.com` erreichbar; `/gesund/` muss
   `{"status": "ok"}` liefern.
3. **SMTP eintragen** (sonst landen Bestätigungs-Mails nur im Log):
   Service → *Environment* → `DDOE_SMTP_HOST`, `DDOE_SMTP_PORT` (587),
   `DDOE_SMTP_USER`, `DDOE_SMTP_PASSWORT` — die Zugangsdaten des Postfachs
   `plattform@ddoe.at` (bei World4You anlegbar). *Save* löst einen Neustart aus.
4. **Verwaltungskonto anlegen:** Service → *Shell* →
   `python manage.py createsuperuser`
5. **Verfahrensordnung laden:** Für den Start genügt die Demo-Ordnung:
   Service-Shell → `python manage.py demo_seed` (legt auch Beispiel-Anträge an)
   — oder nur die Verfahrensordnung von Hand über `/verwaltung/`.
6. **Eigene Adresse `plattform.ddoe.at`:** Service → *Settings* → *Custom Domain*
   `plattform.ddoe.at` hinzufügen; im World4You-DNS einen **CNAME**
   `plattform` → `parlamentplattform.onrender.com` setzen. Zertifikat stellt
   Render automatisch aus. (`DDOE_ALLOWED_HOSTS`/`DDOE_CSRF_ORIGINS` in
   `render.yaml` enthalten die Domain bereits.)

## Laufende Kosten (Stand der Blueprint-Pläne)

Web-Service *Starter* und PostgreSQL *basic-256mb* liegen zusammen bei rund
**15 US-Dollar im Monat**. Kleiner geht es mit dem Free-Web-Service (schläft
nach Inaktivität ein, erster Aufruf dauert dann ~1 Minute) — für eine erste
stille Testphase ausreichend, für den verlinkten Button auf ddoe.at nicht.

## Betriebliches

- **Deploys:** Jeder Push auf `main` deployt automatisch (CI muss grün sein —
  Branch-Schutz). Rollback im Render-Dashboard per Klick.
- **Backups:** Render-Postgres hat tägliche Snapshots; zusätzlich monatlich
  `pg_dump` ziehen und verschlüsselt ablegen (Verantwortung: Technischer
  Entwicklungsrat, § 6 Abs 4).
- **Phasenübergänge:** Fristabläufe werden beim nächsten Seitenaufruf
  verarbeitet (lazy, idempotent). Für einen ruhenden Dienst optional einen
  Render-Cron-Job anlegen: `python manage.py shell -c "from verfahren.models
  import Antrag; [a.fortschreiben() for a in Antrag.objects.all()]"` täglich.
- **Nicht geeignet:** Netlify und Cloudflare Pages sind Static-/Edge-Hosting —
  dort kann die Django-Anwendung nicht laufen. Cloudflare kann später als
  DNS/Schutzschicht vor die Domain, ist für den Start aber nicht nötig.
