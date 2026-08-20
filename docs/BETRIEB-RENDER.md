# Betrieb auf Render — Stand 20.08.2026

Der Prototyp läuft öffentlich unter **https://parlament.ddoe.at**
(Ausweich-Adresse: https://parlamentplattform.onrender.com, Gesundheitscheck: `/gesund/`).

## Was tatsächlich läuft

| Baustein | Ausprägung |
|---|---|
| Web-Service `parlamentplattform` | Render Frankfurt, Python 3.12, Instance Type **Starter** (0,5 CPU / 512 MB, 7 $/Monat) |
| PostgreSQL `plattform-db` | Render Frankfurt, **basic-256mb** (6 $/Monat), PostgreSQL 16 — Konten und Verfahren überleben jeden Deploy |
| Domain | `parlament.ddoe.at` per **CNAME** in der World4You-DNS-Zone auf `parlamentplattform.onrender.com` (nicht die W4Y-„Subdomain“-Funktion — die mappt nur Webspace-Ordner). Zertifikat stellt Render automatisch aus |
| E-Mail | World4You-Postfach `plattform@ddoe.at`, SMTP `smtp.world4you.com:587` (STARTTLS) |
| Workspace-Plan | **Hobby (0 $)** genügt — der Workspace-Plan schaltet nur Team-Funktionen frei, Rechenleistung wird je Dienst gebucht |

Gesamtkosten: **rund 13 $ im Monat.**

Zwei Render-Eigenheiten, die man kennen muss:

1. **Free-Instanzen können keine E-Mails versenden:** Render blockiert dort seit
   September 2025 ausgehenden SMTP-Verkehr (Ports 25/465/587) komplett. Der
   bezahlte Instance Type ist also nicht nur gegen das Einschlafen, sondern
   Voraussetzung für Bestätigungs- und Anmelde-Mails.
2. **Kein automatischer Deploy bei Push:** Der Dienst wurde per API angelegt und
   hat keinen GitHub-Webhook. Nach jedem Push auf `main` im Dashboard
   **Manual Deploy → Deploy latest commit** klicken (oder einmalig unter
   *Settings → Build & Deploy* das GitHub-Repo verbinden, dann deployt jeder
   Push automatisch).

## Start und Build

- Build: `pip install ".[postgres]" gunicorn whitenoise`
- Start: `migrate` → `kategorien_laden` → `demo_seed` → `collectstatic` → Gunicorn
  (2 Worker, 60 s Timeout). Alle Schritte sind idempotent — `demo_seed` legt nur
  auf leerer Datenbank an, `kategorien_laden` und `gemeinden_laden` aktualisieren.

## Umgebungsvariablen (Werte nur im Render-Dashboard, nie im Repo)

| Variable | Zweck |
|---|---|
| `DDOE_SECRET_KEY`, `DDOE_DEBUG=0` | Django-Grundschutz |
| `DDOE_ALLOWED_HOSTS`, `DDOE_CSRF_ORIGINS` | erlaubte Domains (onrender.com + parlament.ddoe.at) |
| `DDOE_STATIK=whitenoise` | statische Dateien aus der Anwendung |
| `POSTGRES_HOST/PORT/DB/USER/PASSWORD` | aus der *Internal Database URL* von `plattform-db` |
| `DDOE_SMTP_HOST/PORT/USER/PASSWORT` | Postfach `plattform@ddoe.at` (World4You, Port 587) |
| `DDOE_SMTP_TIMEOUT` | optional, Standard 20 s — hängender Mailserver blockiert keinen Worker |
| `DDOE_MAIL_ABSENDER` | Absenderadresse (Standard `plattform@ddoe.at`) |
| `DDOE_UEBERGANGSREGEL=1` | § 4 Abs 4 lit d während des Aufbaus |
| `DDOE_FIX_ADMIN` | optional — fixer Verwaltungs-Erstzugang (Standard `didide@ddoe.at`, F-51) |
| `PYTHON_VERSION=3.12.6` | Laufzeitversion |

## Verwaltung — ohne Superuser

Es gibt keinen Django-Admin und kein `createsuperuser` mehr. Die
**Mitgliederverwaltung** liegt unter `/verwaltung/` (F-51): Das Konto mit der
`DDOE_FIX_ADMIN`-Adresse meldet sich ganz normal per E-Mail-Link an und sieht
den Menüpunkt „Verwaltung“; weitere Admins werden dort ernannt. Jede Handlung
steht im öffentlichen Audit-Log. Die öffentliche Übersichtsseite (`/uebersicht/`,
F-50) braucht gar keinen Zugang.

## Betriebliches

- **Backups:** Render-Postgres hat tägliche Snapshots; zusätzlich monatlich
  `pg_dump` ziehen und verschlüsselt ablegen (Technischer Entwicklungsrat, § 6 Abs 4).
- **Phasenübergänge:** Fristabläufe werden beim nächsten Seitenaufruf verarbeitet
  (lazy, idempotent). Optional täglicher Render-Cron:
  `python manage.py shell -c "from verfahren.models import Antrag; [a.fortschreiben() for a in Antrag.objects.all()]"`.
- **Logs:** Dashboard → Logs; der SMTP-Versand meldet Fehler dort mit vollem Traceback.

## Datenschutz-Einordnung

Render Services, Inc. ist ein US-Unternehmen; Dienst und Datenbank laufen in
Frankfurt. Mitgliedschaftsdaten einer Partei sind besondere Kategorien
personenbezogener Daten (Art 9 DSGVO — politische Meinung). Für den
**Testbetrieb** mit ausdrücklich einwilligenden Testnutzerinnen und -nutzern ist
das mit klarem Hinweis vertretbar; für den **Echtbetrieb** ist der Umzug auf
einen EU-/AT-Anbieter (z. B. Hetzner, Anexia) vorgesehen — das Repository ist
darauf vorbereitet (`docker-compose.yml`, 12-Factor-Konfiguration), der Umzug
ist ein Datenbank-Export/-Import plus DNS-Wechsel. Die Plattform selbst setzt
keine Tracker und keine Dienste Dritter ein; Besuche werden datensparsam als
Tages-Summen gezählt (F-52, ADR-008).
