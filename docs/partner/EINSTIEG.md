# Der Einstieg — zwei Spuren, ein Ziel

*Satzung § 12 · Fahrtenbuch FB-M7 · Stand 3.9.2026*

Es gibt zwei Wege, sich dieser Idee im eigenen Land anzuschließen: eine **bestehende Partei zur
direkten Demokratie umgestalten** oder eine **neue Partei gründen**. Beide Spuren enden am selben
Punkt — einer eigenen ParlamentPlattform-Instanz unter eigener Satzung, verbunden mit dem
gemeinsamen Kern. Wir begleiten beide.

## Spur A · Eine bestehende Partei umgestalten

| Schritt | Was zu tun ist | Was wir beisteuern |
|---|---|---|
| A1 · Vision teilen | `GEMEINSAME_VISION.md` lesen, intern beschließen, ob das Werkzeug-Prinzip (keine Programme, Verfahren statt Meinung) gewollt ist | Gespräch (Deutsch/Englisch), Fragen beantworten |
| A2 · Satzung anpassen | `SATZUNG_BAUKASTEN.md` auf die eigene Satzung legen: Kern-Paragrafen (§ 2, § 3, § 5, § 6, § 7, § 12) übernehmen, Landesrecht in § 1, § 4, § 8, § 10, § 11, § 13–17 einarbeiten, Übergangsregeln für laufende Strukturen | Kommentar je §, Erfahrungen aus der Rechtsprüfung in Österreich |
| A3 · Mitglieder entscheiden | Satzungsänderung nach eigenem Recht beschließen — idealerweise schon **auf der Plattform** im Alpha-Betrieb (nachrechenbar) | Alpha-Instanz auf unserer Infrastruktur für die Abstimmung, wenn gewünscht |
| A4 · Instanz aufsetzen | `EINRICHTUNG.md` abarbeiten: Server im eigenen Land, Domain, E-Mail, `DDOE_SYSTEM_ID`, Kategorienbaum und Verfahrensordnung übersetzen und beschließen | Einrichtung gemeinsam (Bildschirm teilen), Übersetzungsgerüst (`locale/`), Prüfung der Exporte |
| A5 · Übergang | Bestehende Gremien in Rollen überführen (§ 6), Mandatare in die Mandatar-Steuerung (§ 7), Mitglieder registrieren (ein Konto je Mensch, geprüfte Identität) | Anleitung Rollen und Identitätsstufen |
| A6 · Verbinden | `/parameter.json` und `/kennzahlen.json` veröffentlichen, Sitz im Plattform-Rat, erster Abgleich-Termin | Aufnahme in die Gegenüberstellung, Protokoll |

## Spur B · Eine neue Partei gründen

| Schritt | Was zu tun ist | Was wir beisteuern |
|---|---|---|
| B1 · Kern-Gruppe | Fünf bis zehn Menschen, die die Vision teilen; Arbeitssprache festlegen | Erstgespräch, Vorlage für die Gründungserklärung |
| B2 · Satzung | `SATZUNG_BAUKASTEN.md` ausfüllen (Platzhalter `[PARTEINAME]`, `[LAND]`, `[SITZ]` …), Landesrecht prüfen lassen (Anhang) | Kommentar je §, Liste der Prüfpunkte |
| B3 · Gründung nach Landesrecht | Hinterlegung/Registrierung bei der zuständigen Behörde `[REGISTRIERUNGSBEHÖRDE]`, Bankkonto, Datenschutz | Erfahrungsbericht Österreich (Parteiengesetz, Vereinsrecht) — kein Rechtsrat |
| B4 · Instanz aufsetzen | wie A4 — `EINRICHTUNG.md` | wie A4 |
| B5 · Alpha-Betrieb | Erste Mitglieder, erste Anträge, Kategorienbaum nachschärfen, Verfahrensordnung beschließen (§ 5 Abs 7) | Demo-Daten, Betriebsbegleitung in den ersten Monaten |
| B6 · Verbinden | wie A6 | wie A6 |

## Was wir grundsätzlich beisteuern

- **Software:** die ParlamentPlattform (AGPL-3.0-or-later), zweisprachig (DE/EN) mit Übersetzungsgerüst,
  Docker- und Render-Vorlage, nachrechenbare Auszählung samt Prüfwerkzeug `verify/nachrechnen.py`.
- **Satzung:** der Baukasten mit Kommentar; die österreichische Rechtsprüfung als Erfahrungswert.
- **Einrichtung:** Aufsetzen der Instanz gemeinsam, Schnittstellen prüfen, erste Freigaben einspielen.
- **Kontinuität:** vierteljährliche Kern-Freigaben, Plattform-Rat, geteilte Kennzahlen, gemeinsame
  Weiterentwicklung — jede Partei mit einer Stimme.

## Was das Land selbst tut

- Server und Daten **im eigenen Land** (Datenschutz, Art 9 DSGVO oder Entsprechung), eigene Domain,
  eigene E-Mail-Adresse, eigene Identitätsprüfung (eID des Landes oder Präsenzstelle, § 2 Abs 4 / § 13).
- Satzung nach Landesrecht, Verfahrensordnung und Kategorienbaum in eigener Sprache und eigener
  Ordnung, Werte der Stellgrößen selbst lernen.
- Ehrliche Kennzahlen zurückgeben und im Plattform-Rat mitarbeiten.

## Zeitrahmen (Erfahrungswert)

Spur A: drei bis sechs Monate bis zum Beschluss, danach vier Wochen bis zum Alpha-Betrieb.
Spur B: je nach Landesrecht drei bis neun Monate bis zur Registrierung; die Instanz kann davor
schon als Alpha laufen.

---

## English summary

Two tracks lead to the same point — your own ParlamentPlattform instance under your own statutes,
connected to the shared core. **Track A (transform an existing party):** share the vision, lay the
statutes kit over your statutes (core paragraphs § 2, 3, 5, 6, 7, 12; national law in § 1, 4, 8, 10,
11, 13–17), let the members decide — ideally on the platform itself —, set up the instance
(`EINRICHTUNG.md`), move bodies into roles and representatives into representative steering,
publish `/parameter.json` and `/kennzahlen.json`, take a seat in the platform council.
**Track B (found a new party):** a core group, fill in the statutes kit, register under national law,
set up the instance, run an alpha with first members and motions, connect. **We contribute:** the
software (AGPL), the statutes kit with commentary, joint setup, quarterly core releases and the
council. **You contribute:** servers and data in your own country, identity verification, statutes
and procedures in your own language, honest metrics.
