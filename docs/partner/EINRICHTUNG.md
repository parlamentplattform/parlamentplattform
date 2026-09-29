# Einrichtungs-Checkliste für eine Landesinstanz

*Fahrtenbuch FB-M7 · Stand 29.9.2026 · Vorlagen in `instanz/`*

Ziel: in unter einer Stunde eine lauffähige Instanz, in einem Tag eine betriebsfertige. Jede Zeile ist
abhakbar; die Reihenfolge ist die empfohlene.

## 1. Vor dem Start

- [ ] **System-Kennung** festlegen: `DDOE_SYSTEM_ID = <ländercode>-<kurzname>` (z. B. `se-ddk`), `DDOE_SYSTEM_NAME` = voller Parteiname.
- [ ] **Hosting im eigenen Land** wählen (Datenschutz: politische Meinung ist Art-9-Datum). Docker auf einem eigenen Server (`instanz/docker-compose.yml`) oder ein Plattformdienst (`instanz/render.yaml` als Muster).
- [ ] **Domain** (z. B. `parlament.<partei>.<tld>`) und **E-Mail-Postfach** für Anmelde-Links (SMTP-Zugang).
- [ ] **PostgreSQL 16** — bei Docker enthalten; sonst Zugang notieren.

## 2. Instanz starten

- [ ] Repository klonen: `git clone https://github.com/parlamentplattform/parlamentplattform`. Es gibt keine Versions-Tags: **`main` ist die Freigabe** — die CI prüft jeden Stand dort (`pruefen (3.11)`, `pruefen (3.12)`, `pruefen_postgres`), und ausgerollt wird nur ein grüner. Ob ein Stand die Prüfung schon vor dem Zusammenführen bestanden hat, hängt am Branch-Schutz des Repositorys; maßgeblich ist deshalb der Prüfstatus des Commits auf GitHub. Die Nummer steht im `CHANGELOG.md`.
- [ ] `instanz/env.example` nach `.env` kopieren und ausfüllen (Secret Key erzeugen, Hosts, CSRF-Origins, SMTP, System-Kennung).
- [ ] `docker compose -f instanz/docker-compose.yml up -d` — beim ersten Start laufen `migrate`, `gemeinden_laden`, `kategorien_laden`, `collectstatic`. **Gemeindeverzeichnis:** `gemeinden_laden` liest `daten/gemeinden.csv` (österreichische Gemeinden); ohne Verzeichnis kann sich niemand registrieren. Eine Landesinstanz ersetzt die Datei durch ihr eigenes Verzeichnis (gleiche Spalten) und lädt sie mit demselben Befehl.
- [ ] Gesundheitsprüfung: `https://<domain>/gesund/` antwortet `{"status": "ok"}`.
- [ ] Ersten Admin anlegen: **kein `createsuperuser`** (es gibt keinen Django-Admin). Die Adresse der ersten Verwaltungsperson in `DDOE_FIX_ADMIN` eintragen, dann mit genau dieser Adresse ganz normal über `/mitglied-werden/` registrieren und die E-Mail bestätigen — das Konto sieht den Menüpunkt „Verwaltung“ und ernennt dort weitere Admins.

## 3. Landesspezifisch einrichten

- [ ] **Kategorienbaum** (`policies/kategorien-v2.yaml`): Namen übersetzen, Slugs beibehalten (sie sind sprachneutral und Teil des Austauschs); Knoten ergänzen oder deaktivieren, dann `manage.py kategorien_laden`.
- [ ] **Verfahrensordnung** (`policies/grundordnung-v1.yaml`): Schwellen und Fristen für den Alpha-Betrieb setzen — die satzungsfesten Untergrenzen erzwingt der Code; Beschluss der Mitgliederversammlung (§ 5 Abs 7) nachholen.
- [ ] **Parameterregister** (`/verwaltung/parameter/`): Erstbestand prüfen, Werte anpassen — jede Änderung braucht einen Grund und landet im Audit-Log.
- [ ] **Übersetzung:** `locale/<sprache>/LC_MESSAGES/django.po` aus der englischen Vorlage ableiten; `python tools/po_pruefen.py --mo` prüft und kompiliert ohne gettext.
- [ ] **Identitätsprüfung:** Landes-eID anbinden (falls vorhanden) oder Präsenzstellen nach § 13 organisieren; Identitätsstufen im Rollen-Fundament setzen.
- [ ] **Demo-Modus aus:** `DDOE_DEMO` nicht setzen (Standard ist aus, sobald `DDOE_DEBUG=0`); `demo_seed` legt dann nichts an. Demo-Konten einer Testphase als Testkonten stilllegen, damit sie in keinem Nenner zählen.

## 4. Betrieb

- [ ] **Sicherung:** tägliches Datenbank-Backup, verschlüsselt, im eigenen Land; Wiederherstellung einmal geprobt.
- [ ] **Audit-Log** und **Umsetzungsregister** öffentlich erreichbar (`/umsetzung/`, `/umsetzung.json`).
- [ ] **Exporte prüfen:** `https://<domain>/parameter.json` und `/kennzahlen.json` — Schema-Version mit derselben Hauptversion wie in `SCHEMA.md` (heute 1.7, maßgeblich ist `plattform_core/schema.py: SCHEMA_VERSION`), richtige `system_id`, keine personenbezogenen Felder (`SCHEMA.md`).
- [ ] **Freigaben nachziehen:** vierteljährlich `git pull` von `main` (grüne CI = Freigabe), `migrate`, `gemeinden_laden`, `kategorien_laden`, Änderungsprotokoll lesen; Landeserweiterungen als PR in den Kern, wenn sie parametrisierbar sind.
- [ ] **Plattform-Rat:** Ansprechperson benennen, Termin des ersten Abgleichs eintragen.

## 5. Rechtliches (kein Rechtsrat)

- [ ] Datenschutz-Folgenabschätzung (Art 35 DSGVO oder Entsprechung) für Mitgliederdaten und Stimmregister.
- [ ] Impressum, Datenschutzerklärung, Verantwortliche im Sinne des Landesrechts.
- [ ] Prüfpunkte aus dem Anhang des Satzungs-Baukastens durch eine Anwältin oder einen Anwalt im eigenen Land.

---

## English summary

Choose your system id and name, host in your own country (political opinion is Art. 9 data), set up
domain, mail and PostgreSQL; clone `main` (there are no release tags — a green CI run is the release), fill `.env` from `instanz/env.example`, start
`docker compose` (migrations, municipality register from `daten/gemeinden.csv`, category tree), check `/gesund/`, register the first admin with the address set in `DDOE_FIX_ADMIN` (there is no `createsuperuser`). Then translate the category tree (keep the
slugs), set the procedural rules for the alpha, review the parameter register, add a translation,
organise identity verification, switch off the demo seed. In operation: daily encrypted backups,
public audit log and implementation register, check the exports against `SCHEMA.md`, pull the
quarterly core release, name your council representative. Legal: data-protection impact assessment,
imprint and privacy policy, review of the statutes kit's appendix by a lawyer in your country.
