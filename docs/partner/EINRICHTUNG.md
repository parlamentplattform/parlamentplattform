# Einrichtungs-Checkliste für eine Landesinstanz

*Fahrtenbuch FB-M7 · Stand 3.9.2026 · Vorlagen in `instanz/`*

Ziel: in unter einer Stunde eine lauffähige Instanz, in einem Tag eine betriebsfertige. Jede Zeile ist
abhakbar; die Reihenfolge ist die empfohlene.

## 1. Vor dem Start

- [ ] **System-Kennung** festlegen: `DDOE_SYSTEM_ID = <ländercode>-<kurzname>` (z. B. `se-ddk`), `DDOE_SYSTEM_NAME` = voller Parteiname.
- [ ] **Hosting im eigenen Land** wählen (Datenschutz: politische Meinung ist Art-9-Datum). Docker auf einem eigenen Server (`instanz/docker-compose.yml`) oder ein Plattformdienst (`instanz/render.yaml` als Muster).
- [ ] **Domain** (z. B. `parlament.<partei>.<tld>`) und **E-Mail-Postfach** für Anmelde-Links (SMTP-Zugang).
- [ ] **PostgreSQL 16** — bei Docker enthalten; sonst Zugang notieren.

## 2. Instanz starten

- [ ] Repository klonen: `git clone https://github.com/parlamentplattform/parlamentplattform` und die **letzte Freigabe** auschecken (`git checkout v<Version>`).
- [ ] `instanz/env.example` nach `.env` kopieren und ausfüllen (Secret Key erzeugen, Hosts, CSRF-Origins, SMTP, System-Kennung).
- [ ] `docker compose -f instanz/docker-compose.yml up -d` — beim ersten Start laufen `migrate`, `kategorien_laden`, `collectstatic`.
- [ ] Gesundheitsprüfung: `https://<domain>/gesund/` antwortet `{"status": "ok"}`.
- [ ] Ersten Admin anlegen: `docker compose exec web python manage.py createsuperuser` und die Adresse in `DDOE_FIX_ADMIN` eintragen.

## 3. Landesspezifisch einrichten

- [ ] **Kategorienbaum** (`policies/kategorien-v2.yaml`): Namen übersetzen, Slugs beibehalten (sie sind sprachneutral und Teil des Austauschs); Knoten ergänzen oder deaktivieren, dann `manage.py kategorien_laden`.
- [ ] **Verfahrensordnung** (`policies/grundordnung-v1.yaml`): Schwellen und Fristen für den Alpha-Betrieb setzen — die satzungsfesten Untergrenzen erzwingt der Code; Beschluss der Mitgliederversammlung (§ 5 Abs 7) nachholen.
- [ ] **Parameterregister** (`/verwaltung/parameter/`): Erstbestand prüfen, Werte anpassen — jede Änderung braucht einen Grund und landet im Audit-Log.
- [ ] **Übersetzung:** `locale/<sprache>/LC_MESSAGES/django.po` aus der englischen Vorlage ableiten; `python tools/po_pruefen.py --mo` prüft und kompiliert ohne gettext.
- [ ] **Identitätsprüfung:** Landes-eID anbinden (falls vorhanden) oder Präsenzstellen nach § 13 organisieren; Identitätsstufen im Rollen-Fundament setzen.
- [ ] **Demo-Modus aus:** `demo_seed` nicht im Startbefehl belassen, sobald echte Mitglieder registriert sind.

## 4. Betrieb

- [ ] **Sicherung:** tägliches Datenbank-Backup, verschlüsselt, im eigenen Land; Wiederherstellung einmal geprobt.
- [ ] **Audit-Log** und **Umsetzungsregister** öffentlich erreichbar (`/umsetzung/`, `/umsetzung.json`).
- [ ] **Exporte prüfen:** `https://<domain>/parameter.json` und `/kennzahlen.json` — Schema-Version 1.0, richtige `system_id`, keine personenbezogenen Felder (`SCHEMA.md`).
- [ ] **Freigaben nachziehen:** vierteljährlich `git pull` der Kern-Freigabe, `migrate`, Änderungsprotokoll lesen; Landeserweiterungen als PR in den Kern, wenn sie parametrisierbar sind.
- [ ] **Plattform-Rat:** Ansprechperson benennen, Termin des ersten Abgleichs eintragen.

## 5. Rechtliches (kein Rechtsrat)

- [ ] Datenschutz-Folgenabschätzung (Art 35 DSGVO oder Entsprechung) für Mitgliederdaten und Stimmregister.
- [ ] Impressum, Datenschutzerklärung, Verantwortliche im Sinne des Landesrechts.
- [ ] Prüfpunkte aus dem Anhang des Satzungs-Baukastens durch eine Anwältin oder einen Anwalt im eigenen Land.

---

## English summary

Choose your system id and name, host in your own country (political opinion is Art. 9 data), set up
domain, mail and PostgreSQL; clone the latest release, fill `.env` from `instanz/env.example`, start
`docker compose`, check `/gesund/`, create the first admin. Then translate the category tree (keep the
slugs), set the procedural rules for the alpha, review the parameter register, add a translation,
organise identity verification, switch off the demo seed. In operation: daily encrypted backups,
public audit log and implementation register, check the exports against `SCHEMA.md`, pull the
quarterly core release, name your council representative. Legal: data-protection impact assessment,
imprint and privacy policy, review of the statutes kit's appendix by a lawyer in your country.
