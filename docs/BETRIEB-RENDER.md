# Betrieb auf Render — Stand 29.09.2026 (0.50)

Die Plattform läuft öffentlich unter **https://parlament.ddoe.at**
(Ausweich-Adresse: https://parlamentplattform.onrender.com, Gesundheitscheck: `/gesund/`).

## Was tatsächlich läuft

| Baustein | Ausprägung |
|---|---|
| Web-Service `parlamentplattform` | Render Frankfurt, Instance Type **Starter** (0,5 CPU / 512 MB, 7 $/Monat). **Ehrlich zur Laufzeit:** Der seit 08/2026 laufende Dienst wurde per API mit der **Python-Runtime** (`PYTHON_VERSION=3.12.6`) angelegt; `render.yaml` beschreibt den reproduzierbaren Neuaufbau mit der **Docker-Runtime** (`Dockerfile`, dieselben Befehle und Variablen). Beide führen dieselbe Startkette aus; wer neu aufbaut, bekommt Docker. Beim per API angelegten Python-Dienst wirkt `render.yaml` nicht: Sein **Start Command** steht im Dashboard (*Settings → Build & Deploy*) und muss dort von Hand auf die Kette `migrate` → `gemeinden_laden` → `kategorien_laden` → `clearsessions` → `collectstatic` → Gunicorn gesetzt sein (siehe „Start und Build“). |
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
| `DDOE_UEBERGANGSREGEL=1` | § 4 Abs 4 lit d während des Aufbaus — seit 0.51 beim Einbringen in die Ordnung des Antrags eingefroren: Ein Umschalten wirkt nur auf Anträge, die danach eingebracht werden (§ 5 Abs 5) |
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

- **Sicherung und Wache (seit 0.52):** täglich außerhalb von Render, monatlich geprobt, `/gesund/` alle
  15 Minuten — Abschnitt „Sicherung“ unten, ADR-012. Zusätzlich bleiben die Snapshots von Render-Postgres.
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

## Sicherung (seit 0.52, ADR-012)

Täglich 02:17 UTC sichert `.github/workflows/sicherung.yml` die Datenbank — ohne Sitzungen und
Anmeldelinks — als Release in das private Repository `parlamentplattform/sicherung` (unverschlüsselt,
Entscheidung des Gründers 29.9.2026) und hält sie 90 Tage, die vom Monatsersten 365 Tage. Hat eine neue
Sicherung weniger Audit-Einträge als die vorige, bleibt der Lauf rot und löscht nichts. Am Monatsersten spielt derselbe Workflow die jüngste Sicherung in eine leere Datenbank
zurück und prüft Migrationen und Audit-Kette. `.github/workflows/wache.yml` fragt alle 15 Minuten
`/gesund/`. **Zuständig:** der Technische Entwicklungsrat (§ 6 Abs 4), bis dahin der Gründer.

**Einmal einrichten (nach dem Merge von 0.52):**

0. Das Repository `parlamentplattform/sicherung` braucht einen ersten Commit (auf GitHub „Add a README“),
   sonst kann der Workflow kein Release anlegen.
1. Eine Nur-Lese-Rolle für die Sicherung anlegen (empfohlen — die Adresse des Eigentümers dürfte
   schreiben): Render-Dashboard → Datenbank → *Connect* → „PSQL Command“ im eigenen Terminal ausführen, dann
   `CREATE ROLE sicherung LOGIN PASSWORD '<langes Zufallspasswort>'; GRANT pg_read_all_data TO sicherung;`.
   Die „External Database URL“ kopieren und Benutzer und Passwort darin durch `sicherung` und das neue
   Passwort ersetzen. GitHub → Hauptrepository → *Settings → Secrets and variables → Actions → New
   repository secret*: Name `DDOE_SICHERUNG_DATENBANK_URL`, Wert diese Adresse. Steht bei der Datenbank
   eine IP-Zugriffsliste, muss sie Verbindungen von außen zulassen (GitHub-Runner haben wechselnde
   Adressen) — ein Grund mehr für die Nur-Lese-Rolle.
2. GitHub → *Settings* (des eigenen Kontos) → *Developer settings → Personal access tokens →
   Fine-grained tokens → Generate new token*: Ressourcenbesitzer `parlamentplattform`, *Only select
   repositories* → `sicherung`, Rechte *Contents: Read and write*. Ablaufdatum so lang wie erlaubt und
   im Kalender vormerken. Als Secret `DDOE_SICHERUNG_TOKEN` im Hauptrepository hinterlegen.
3. GitHub → Hauptrepository → *Actions → Sicherung → Run workflow* (mit Probe). Grün heißt: gesichert,
   zurückgespielt, Migrationen und Audit-Kette stimmen. Die Zusammenfassung des Laufs nennt Datei,
   Größe und Prüfsumme.
4. Prüfen, dass Fehlermails ankommen: Sie gehen an das Konto, das die Zeitpläne zuletzt geändert hat
   (*Settings → Notifications → Actions* dieses Kontos).

**Wiederherstellen im Ernstfall:**

1. Neue, leere PostgreSQL-Datenbank anlegen (Render oder anderswo) — nie in die laufende einspielen.
2. Sicherung holen: `gh release download <name> --repo parlamentplattform/sicherung` (oder über die
   Weboberfläche des Repositorys) und die Prüfsumme vergleichen: `sha256sum --check <name>.dump.sha256`.
3. Mit den `POSTGRES_*`-Werten der neuen Datenbank: `tools/sicherung.sh probe <name>.dump` — spielt
   zurück, prüft Migrationen und rechnet die Audit-Kette vollständig nach.
4. Den Dienst auf die neue Datenbank umstellen (Umgebungsvariablen), deployen, `/gesund/` prüfen.
5. Den Kettenkopf (`audit.head` in `/kennzahlen.json`) mit dem letzten bekannten vergleichen und im
   Protokoll unten eintragen.

**Protokoll der Proben:**

| Datum | Quelle | Sicherung | Ergebnis |
|---|---|---|---|
| 29.9.2026 | Demo-Datenbank (lokales PostgreSQL 16, `tools/sicherung.sh`) | 351 KB, 7 Anträge, 5 Konten, 50 Audit-Einträge | zurückgespielt in eine leere Datenbank; keine offene Migration; Audit-Kette vollständig intakt, Kopf `6d979b7d…53652f` wie im Original; Zeilenzahlen gleich. Nach der Prüfung erneut: ohne Sitzungen und Anmeldelinks, gleiches Ergebnis |
| — | Live-Datenbank über den Workflow | — | offen: braucht die beiden Secrets (Schritt 1–3 oben) |

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
die betroffenen Mitglieder mit E-Mail-Einwilligung, ab 0.50), `beitragserinnerung` (Bezug `jahr:<Jahr>`:
von der Verwaltung beauftragt, höchstens einmal je Kalenderjahr, nur mit Einwilligung, ab 0.50) und
`rechtsbezug` (Bezug `antrag:<pk>`: betroffene Gesetze aus der Zukunftswerkstatt an den Antragsteller,
sobald das Ergebnis vorliegt, nur mit Einwilligung, ab 0.50). Die Kontobriefe gehen sofort nach dem
Commit; `neuer_antrag`, `beitragserinnerung` und `rechtsbezug` werden nur angelegt und vom Hintergrundlauf
zugestellt — ein Antrag löst so nie hunderte SMTP-Sendungen in einer Anfrage aus.
Wer die Einwilligung vor der Zustellung zurücknimmt, bekommt den Brief nicht; der Auftrag wird als
erledigt gestempelt, nicht gelöscht. Nach 24 gescheiterten Versuchen (rund 20 Stunden, etwa bei einer
dauerhaft abgewiesenen Adresse) gibt der Postausgang die Verfahrenspost auf und stempelt den Auftrag
ebenso als erledigt ohne Versand; die Kontobriefe werden weiter stündlich versucht.

Der erste Versand erfolgt nach Commit der Registrierung/Freischaltung. Ein fehlerhafter
Anhang verhindert nicht die Nachricht und wird gesondert nachgeliefert. SMTP-Erfolg bedeutet
Annahme durch das konfigurierte Backend, keine Lesebestätigung oder garantierte Inbox-Zustellung.
Ohne SMTP-Konfiguration gilt weiterhin das Konsolenbackend für die Entwicklung.

Bestandskonten werden nicht ungefragt erneut angeschrieben: Poststempel bis 0.48 bezeichnen
den ersten Versuch. Sie werden nicht rückwirkend als neue Versandaufträge interpretiert.

## Kein Rückweg auf 0.50.x (seit 0.51)

Ab 0.51 bringt jeder neu eingebrachte Antrag seine Ordnung in Fassung 5 mit (Felder `uebergangsregel`
und `tendenz_ab_mindestbeteiligung`). Der Code von 0.50 weist unbekannte Felder einer Ordnung ab
(`Policy.aus_dict`, eine Schutzregel): Nach einem Rollback schlügen die Antragsseite, das Parlament und
der Fristen-Wächter bei jedem solchen Antrag fehl. Deshalb gilt: **vorwärts beheben, nicht
zurückrollen.** Die Migration `verfahren` 0025 ist ohne Datenverlust; ihr Rückweg geht nur, solange
keine Reaktion zurückgenommen oder gewechselt wurde — danach bricht er mit einer Meldung ab
(absichtlich: 0.50 würde eine zurückgenommene Reaktion wieder zählen). Keine `--fake`-Migrationen.

## Kein Rückweg auf 0.49

Ab 0.50 führt kein Weg auf 0.49 zurück — weder ein Rollback im Render-Dashboard noch das Ausrollen
eines älteren Commits. Die Migrationen `mitglieder` 0021 und 0022 haben keinen Rückweg (er löschte
Daten, die kein erneutes Vorwärts wiederherstellt), und der Code von 0.49 passt nicht zur Datenbank
von 0.50:

- Er kennt die Spalten `Mitglied.post_einwilligung`, `Mitglied.beitragsreferenz_stamm` und
  `Postauftrag.bezug` nicht. Sie sind in der Datenbank NOT NULL ohne Vorgabewert — Registrierung und
  neue Kontobriefe scheitern.
- Sein Postausgang kennt die Arten `neuer_antrag`, `beitragserinnerung` und `rechtsbezug` nicht und
  verschickt jeden offenen Auftrag dieser Arten als Freischaltungsbrief mit Mitgliedsausweis — auch an
  ungeprüfte Konten.

Der zweite Punkt gilt auch für das kurze Fenster beim Ausrollen von 0.50, in dem die alte Instanz noch
läuft (ihr Postausgang greift alle 30 Sekunden zu), während die neue schon Aufträge anlegt.

Ist ein Rückweg im Notfall unvermeidlich, zuerst in der Shell des Dienstes die offenen Aufträge der
neuen Arten als erledigt stempeln (sie werden danach nicht mehr zugestellt); sonst nicht zurückrollen:

```bash
python manage.py shell -c "from mitglieder.models import Postauftrag; print(Postauftrag.objects.filter(art__in=['neuer_antrag', 'beitragserinnerung', 'rechtsbezug'], erledigt=False).update(erledigt=True))"
```

Registrierung und Kontobriefe bleiben auf 0.49 auch dann gestört, solange die Datenbank auf dem Stand
von 0.50 steht. Fehler werden deshalb vorwärts behoben, nicht durch Zurückrollen.
