# Betrieb auf Render — Stand 29.09.2026 (0.50)

Die Plattform läuft öffentlich unter **https://parlament.ddoe.at**
(Ausweich-Adresse: https://parlamentplattform.onrender.com, Gesundheitscheck: `/gesund/`).

## Was tatsächlich läuft

| Baustein | Ausprägung |
|---|---|
| Web-Service `parlamentplattform` | Render Frankfurt, Instance Type **Starter** (0,5 CPU / 512 MB, 7 $/Monat). **Ehrlich zur Laufzeit:** Der seit 08/2026 laufende Dienst wurde per API mit der **Python-Runtime** (`PYTHON_VERSION=3.12.6`) angelegt; `render.yaml` beschreibt den reproduzierbaren Neuaufbau mit der **Docker-Runtime** (`Dockerfile`, dieselben Befehle und Variablen). Beide führen dieselbe Startkette aus; wer neu aufbaut, bekommt Docker. |
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
2. **Automatischer Deploy läuft über die CI, nicht über Render:** Der Dienst ist
   als öffentliche Git-URL verbunden (kein Render-Webhook; das `autoDeploy: yes`
   im Dashboard feuert deshalb nie). Stattdessen stößt der CI-Job **ausrollen**
   nach jeder **bestandenen** Prüfung auf `main` den Render-Deploy-Hook an —
   rote Commits gehen so nie live. Einmalige Einrichtung: In Render unter
   *Settings → Deploy Hook* die URL kopieren und im GitHub-Repo als
   Actions-Secret **`RENDER_DEPLOY_HOOK`** hinterlegen (*Settings → Secrets and
   variables → Actions*). Solange das Secret fehlt, überspringt die CI den
   Schritt und es gilt der manuelle Weg: Dashboard → **Manual Deploy → Deploy
   latest commit**.
   **Neuaufbau aus `render.yaml`:** Ein per Blueprint angelegter Dienst ist mit
   GitHub verbunden und würde ohne Angabe **jeden Push** ausrollen (Render-Standard
   `commit`) — zusätzlich zum Hook, also doppelt und auch rote Commits. Deshalb steht
   in `render.yaml` `autoDeployTrigger: off` (der Hook bleibt der einzige Weg); das
   Partner-Muster `docs/partner/instanz/render.yaml` nutzt `checksPass` (Render wartet
   selbst auf grüne GitHub-Checks, kein Secret nötig). Beides darf man nicht kombinieren.
   Die CI hält vor dem Ausrollen außerdem `manage.py check --deploy --fail-level WARNING`
   und `collectstatic` mit Manifest-Speicher; Abhängigkeiten tragen in `pyproject.toml`
   Obergrenzen, damit CI und Produktion nicht auseinanderlaufen. Ist die Prüfung auf
   `main` rot, schlägt der Job `nicht_ausgerollt` sichtbar an, und das CI-Abzeichen in
   der README wird rot.

## Start und Build

- Build: `pip install ".[postgres]" gunicorn whitenoise` (Python-Runtime) beziehungsweise das `Dockerfile` (Docker-Runtime).
- Start: `migrate` → `gemeinden_laden` → `kategorien_laden` → `clearsessions` → `collectstatic` → Gunicorn
  (2 Worker, 60 s Timeout; `gunicorn.conf.py` startet den Hintergrundfaden). Alle Schritte sind idempotent;
  `gemeinden_laden` und `kategorien_laden` aktualisieren. **`demo_seed` läuft in Produktion nicht mehr**
  (seit 0.50): Ohne `DDOE_DEMO=1` legt es nichts an — die fünf Demo-Konten des Aufbaus zählten bis 0.49 in
  jedem Nenner der Stimmberechtigten mit (Bestandsaufnahme 28.9.2026, A1); sie sind als Testkonten
  stillgelegt. `gemeinden_laden` gehört in jede Startkette: Ohne das amtliche Gemeindeverzeichnis kann
  sich niemand registrieren (A13).

## Umgebungsvariablen (Werte nur im Render-Dashboard, nie im Repo)

| Variable | Zweck |
|---|---|
| `DDOE_SECRET_KEY`, `DDOE_DEBUG=0` | Django-Grundschutz |
| `DDOE_ALLOWED_HOSTS`, `DDOE_CSRF_ORIGINS` | erlaubte Domains (onrender.com + parlament.ddoe.at) |
| `DDOE_STATIK=whitenoise` | statische Dateien aus der Anwendung — mit Manifest (Inhalts-Hash im Dateinamen, lange Cache-Zeit); `collectstatic` ist deshalb Pflicht vor dem Start |
| `POSTGRES_HOST/PORT/DB/USER/PASSWORD` | aus der *Internal Database URL* von `plattform-db` |
| `DDOE_SMTP_HOST/PORT/USER/PASSWORT` | Postfach `plattform@ddoe.at` (World4You, Port 587) |
| `DDOE_SMTP_TIMEOUT` | optional, Standard 20 s — hängender Mailserver blockiert keinen Worker |
| `DDOE_MAIL_ABSENDER` | Absender (Standard `ParlamentPlattform <plattform@ddoe.at>`) |
| `DDOE_UEBERGANGSREGEL=1` | § 4 Abs 4 lit d während des Aufbaus |
| `DDOE_DEMO` | Standard `0` in Produktion (`1` nur mit `DDOE_DEBUG=1`): steuert, ob `demo_seed` Demo-Daten anlegt |
| `DDOE_WAECHTER_MINUTEN` | optional, Standard 10 — Takt des Fristen-Wächters im Hintergrundfaden |
| `DDOE_KI_SCHLUESSEL`, `DDOE_KI_MODELL`, `DDOE_KI_EINBETTUNGSMODELL` | optional — KI-Steckplatz der Zukunftswerkstatt (Mistral; Einbettungsmodell für den Bedeutungsvergleich, Vorgabe `mistral-embed`); ohne Schlüssel bleibt der Steckplatz leer, und `/datenschutz/` nennt keinen KI-Anbieter |
| `DDOE_FIX_ADMIN` | optional — fixer Verwaltungs-Erstzugang (Standard `didide@ddoe.at`, F-51) |
| `DDOE_BANK_SECRET_ID` / `DDOE_BANK_SECRET_KEY` | Beitragsabgleich F-59: Schlüsselpaar des Kontoinformationsdiensts (GoCardless Bank Account Data → User Secrets). Ohne sie bleibt die Bankanbindung schlicht aus |
| `DDOE_BASIS_URL` | optional, Standard `https://parlament.ddoe.at` — Basis für Rückkehr-Link der Bankkopplung und Links in Beitragsmails |
| `PYTHON_VERSION=3.12.6` | Laufzeitversion |

## Verwaltung — ohne Superuser

Es gibt keinen Django-Admin und kein `createsuperuser` mehr. Die
**Mitgliederverwaltung** liegt unter `/verwaltung/` (F-51): Das Konto mit der
`DDOE_FIX_ADMIN`-Adresse meldet sich ganz normal per E-Mail-Link an und sieht
den Menüpunkt „Verwaltung“; weitere Admins werden dort ernannt. Jede Handlung
steht im öffentlichen Audit-Log. Die öffentliche Übersichtsseite (`/uebersicht/`,
F-50) braucht gar keinen Zugang.

## Betriebliches

- **Backups — offene Aufgabe (Bestandsaufnahme 28.9.2026, A10):** Heute gibt es nur die täglichen
  Snapshots von Render-Postgres (beim Anbieter, nicht außerhalb) und keine geprobte Wiederherstellung.
  Empfehlung: täglicher externer `pg_dump` (z. B. GitHub-Action mit Zeitplan, verschlüsselt mit einem
  Schlüssel außerhalb von Render), Ablage im eigenen Land, Wiederherstellung einmal im Quartal geprobt —
  mit Prüfung der Audit-Kette nach dem Einspielen. **Zuständig:** der Technische Entwicklungsrat (§ 6 Abs 4);
  bis er besetzt ist, der Gründer. Speicherort und Schlüsselverwahrung sind noch nicht entschieden.
- **Fristen-Wächter (seit 0.50, D-J1a):** Phasenübergänge, Beschlussfristen, Aussetzungen, Parametertests und
  Stufe 2 der Vertrauensfrage wertet der Hintergrundfaden aus `gunicorn.conf.py` alle `DDOE_WAECHTER_MINUTEN`
  aus (`verfahren/hintergrund.py`, `manage.py verfahren_fortschreiben`), unter einer Datenbanksperre, sodass
  zwei Worker nie dasselbe tun; Seitenaufrufe schreiben zusätzlich bis zum Stand fort. **Kein Render-Cron
  nötig.** Beim Hosting ohne Gunicorn ist `python manage.py verfahren_fortschreiben` regelmäßig auszuführen.
- **Logs:** Dashboard → Logs. Jeder Serverfehler (Status 500) steht dort mit vollem Traceback
  (`LOGGING` in `config/settings.py`, Logger `django.request` → stderr, unabhängig von DEBUG);
  ebenso abgewiesene Hosts und CSRF-Verstöße (`django.security`) und der SMTP-Versand.
- **Gesundheitscheck:** `/gesund/` führt `SELECT 1` aus und antwortet ohne Datenbank mit 503 —
  Render startet die Instanz dann neu und übernimmt keinen Deploy, dessen Instanz die
  Datenbank nicht erreicht.

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


## Automatischer Postausgang (ab 0.49)

`gunicorn.conf.py` startet nach Initialisierung jedes Webworkers einen Hintergrundlauf (derselbe Faden
trägt seit 0.50 den Fristen-Wächter, siehe oben). Alle 30 Sekunden prüft dieser höchstens 50 fällige Postaufträge. Die Datenbank reserviert
einen Auftrag atomar für fünf Minuten. Nach Fehlern erfolgt der nächste Versuch nach
2, 4, 8, 16, 32 und danach jeweils 60 Minuten. Ein Neustart verliert die Aufträge nicht.
Der Dienst muss mit Gunicorn aus dem Projektverzeichnis starten, damit die Konfiguration
geladen wird. Beim Hosting ohne Gunicorn ist `python manage.py post_versenden` regelmäßig
auszuführen. `runserver` betreibt keinen dauerhaften Hintergrundlauf.

Arten der Aufträge: `willkommen` und `freischaltung` (Kontobriefe mit Ausweis-PDF), `ausweis_vorschau*`
(Vorschau an das eigene Konto), `neuer_antrag` (Bezug `antrag:<pk>`: „Neuer Antrag in Ihrer Region“ an
die betroffenen Mitglieder mit E-Mail-Einwilligung, ab 0.50) und `beitragserinnerung` (Bezug `jahr:<Jahr>`:
von der Verwaltung beauftragt, höchstens einmal je Kalenderjahr, nur mit Einwilligung, ab 0.50). Die
Kontobriefe gehen sofort nach dem Commit; `neuer_antrag` und `beitragserinnerung` werden nur angelegt und
vom Hintergrundlauf zugestellt — ein Antrag löst so nie hunderte SMTP-Sendungen in einer Anfrage aus.
Wer die Einwilligung vor der Zustellung zurücknimmt, bekommt den Brief nicht; der Auftrag wird als
erledigt gestempelt, nicht gelöscht.

Der erste Versand erfolgt nach Commit der Registrierung/Freischaltung. Ein fehlerhafter
Anhang verhindert nicht die Nachricht und wird gesondert nachgeliefert. SMTP-Erfolg bedeutet
Annahme durch das konfigurierte Backend, keine Lesebestätigung oder garantierte Inbox-Zustellung.
Ohne SMTP-Konfiguration gilt weiterhin das Konsolenbackend für die Entwicklung.

Bestandskonten werden nicht ungefragt erneut angeschrieben: Poststempel bis 0.48 bezeichnen
den ersten Versuch. Sie werden nicht rückwirkend als neue Versandaufträge interpretiert.
