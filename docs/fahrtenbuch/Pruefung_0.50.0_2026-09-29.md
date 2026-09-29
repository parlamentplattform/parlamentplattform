# Prüfung 0.50.0 — Bauwelle 28./29.9.2026

*Prüfbericht zu Teil 6 der Bauwelle 0.50.0 (Betrieb, Direkt-Handlung, Einwilligung, Zukunftswerkstatt, Fächer). Zweig `claude/cool-rubin-jepfi0`, Prüfstand `6745178` (Ausgangslage der Behebungen), Stand des Berichts `dbda81a` (vor dem Commit dieses Berichts), Datum 29.9.2026. Die Befunde beziehen sich auf Satzungsentwurf 2.5 (§-Zitate nach `docs/partner/SATZUNG_BAUKASTEN.md`), CLAUDE.md § 3 und § 6, das Fahrtenbuch und die ADRs.*

## 1. Nullmessung vorher und nachher

| Prüfung | Vorher (HEAD `645701a`) | Nachher |
|---|---|---|
| `ruff check .` | grün | grün |
| `makemigrations --check` | keine fehlenden Migrationen | keine fehlenden Migrationen |
| pytest SQLite (ohne Bildschirmtests) | 1 621 grün | 1 709 grün, 6 übersprungen (die Nebenläufigkeitstests laufen nur auf PostgreSQL) |
| Kern-Abdeckung `plattform_core` (Zweige) | 97 % | 97 % (1 498 Anweisungen, 462 Zweige) |
| pytest PostgreSQL 16 | 1 621 grün | 1 715 grün (ganze Suite samt Nebenläufigkeitstests) |
| Startkette PostgreSQL (`migrate`, Gemeinden, Kategorien, `demo_seed` ×2 mit `DDOE_DEMO=1`) | grün | grün (Datenbank `plattform_kette050`: `demo_seed` zweimal, zweiter Lauf „nichts zu tun“, Wächter 0 Übergänge; Audit-Kette 45 Einträge nachgerechnet) |
| Katalog (`po_pruefen`, `test_katalog`) | 2 290 Einträge, 0 offen | 2 302 Einträge, 0 offen, 0 unsicher, 0 doppelt; `test_katalog` grün |
| `check --deploy` | 6 Hinweise wie `main` | 6 Hinweise, dieselben |
| Bildschirmtests (Chromium) | 83 grün | 97 grün |

## 2. Methode

Sechs Richtungen, je ein **Prüfer** (stellt Befunde mit Datei:Zeile und Nachstellung auf) und ein getrennter **Widerleger** (versucht jeden Befund zu widerlegen — bevorzugt mit einem neuen Test, der auf dem Prüfstand rot ist; sonst Django-Client, PostgreSQL-Sonde oder Browser-Sonde mit Chromium). Urteil je Befund: bestätigt / unbestätigt / widerlegt. Die Richtungen: 1 Rechte und Sperren · 2 Satzung und Grundregeln · 3 Verfahren, Zeit, Nebenläufigkeit (PostgreSQL) · 4 Bedienbarkeit ohne JavaScript, Barrierefreiheit, Design-Regeln · 5 Ehrlichkeit der Texte und Übersetzung · 6 Daten und Betrieb. Zwölf Agenten, dazu die Nachstellung einer Nebenbeobachtung durch den Hauptprüfer.

Ergebnis: **105 Rohbefunde — 101 bestätigt, 2 widerlegt, 2 unbestätigt**, dazu **1 Nebenbeobachtung**, vom Widerleger rot nachgestellt und vom Hauptprüfer unabhängig nachgelaufen (N-1). Doppelnennungen zusammengezogen ergeben **59 Befunde P-1 … P-59** (2 hoch, 29 mittel, 28 niedrig, 0 kritisch) und **12 niedrige Befunde, die als Folgeschritt stehen bleiben** (Abschnitt 5). Beim Nachprüfen kamen **2 weitere niedrige Befunde** dazu (P-60, P-61), bei der Sichtprüfung ein mittlerer (P-62: das Favoriten-Feld blitzte nach jedem Fächer-Wechsel neu auf) und drei Nachbesserungen an eigenen Behebungen (P-5 Transaktion je Übergang, P-11 Ziel der Beanstandung, P-15 Uhr im Drosseltest).

Behoben wurde in sechs Arbeitszweigen (Cluster K1, K2, K3a, K3b, K4, K5, je in eigenem Arbeitsverzeichnis): je Befund zuerst ein Test, der auf dem Prüfstand rot ist, dann die kleinste Änderung, dann grün, ein Commit je Befund. Jeder Cluster wurde danach von einem getrennten Nachprüfer gegen die Befunde gelesen (Test auf dem Prüfstand rot, danach grün, Minimalität, Grundregeln). Der Hauptprüfer hat die Commits per Cherry-Pick in den Zweig übernommen (kein Rebase des Zweigs), Konflikte in drei Testdateien und einer Importzeile aufgelöst, vier erste Zeilen ohne Verb in den Imperativ gesetzt und die Hinweise der Nachprüfer abgearbeitet (Abschnitt 8).

**Einschränkung:** www.ddoe.at und parlament.ddoe.at sind aus der Prüfumgebung gesperrt (Netzwerkrichtlinie). Alle §-Zitate stützen sich auf `docs/partner/SATZUNG_BAUKASTEN.md` (Wortlaut des Satzungsentwurfs 2.5 mit Platzhaltern). Die Live-Fassung (`/parameter.json`) und den Render-Dienst (Start Command) konnte die Prüfung nicht einsehen.

## 3. Befunde

Urteil „bestätigt“ heißt: vom Widerleger nachgestellt (Test, Client-, PostgreSQL- oder Browser-Sonde). Behebung mit Commit im Zweig; mehrere Commits bei Nachbesserungen.

| Nr. | Richtung | Schwere | Datei:Zeile | Befund und Beleg | Urteil | Behebung |
|---|---|---|---|---|---|---|
| P-1 | 4 | hoch | `verfahren/templates/verfahren/base.html:34` | Fokusring im hellen Modus auf App-Leiste und Bühne 1,3–1,9:1 (Rückschritt der Welle) — R4-1: Test des Widerlegers `v4/e2e/test_r4_sonden.py::test_r4_1_fokusring_in_leiste_und_buehne_hell_mindestens_3_zu_1` rot | bestätigt | Commit 7954ffd |
| P-2 | 2, 5 | hoch | `verfahren/templates/verfahren/index.html:76-79` | „Jeder Zugriff wird protokolliert“ (Stimmregister) — es gibt kein Zugriffsprotokoll — R5-1: Test des Widerlegers `v5/test_r5_1_zugriff_protokolliert.py` rot; R2-1: Test des Widerlegers `v2/test_r2_1_zugriff_protokolliert.py` rot | bestätigt | Commit 0abdf8a, 17296c3 |
| P-3 | 3 | mittel | `gremien/models.py:1083-1122` | GremienBeschluss.abschliessen ohne Zeilensperre — Beschluss doppelt geschlossen, Wirkung/Audit doppelt — R3-1: Test des Widerlegers `v3/test_r3_1_beschluss_doppelt.py` rot | bestätigt | Commit 00b83df |
| P-4 | 3 | mittel | `mandatare/models.py:1107-1188` | Stufe 2 der Vertrauensfrage ohne Zeilensperre — doppelter Vollzug im Audit — R3-2: Test des Widerlegers `v3/test_r3_2_vf_stufe2_parallel.py` rot | bestätigt | Commit 2edadc6 |
| P-5 | 3, 6 | mittel | `verfahren/management/commands/verfahren_fortschreiben.py:25-44` | Fristen-Wächter ohne Fehlergrenze je Verfahren — ein werfender Antrag hält alle folgenden und alle Nachläufe an — R3-5: Test des Widerlegers `v3/test_r3_5_waechter_fehlergrenze.py` rot; R6-1: Test des Widerlegers `v6/test_r6_1_giftpille.py` rot | bestätigt | Commit 9359a46, 416223a |
| P-6 | 2, 3 | mittel | `gremien/models.py:1091-1108` | Beschluss nach Fristablauf trägt den Auswertungs- statt den Fristzeitpunkt (A4-Rest) — R3-3: Test des Widerlegers `v3/test_r3_3_fristzeitpunkt.py` rot; R2-18: Test des Widerlegers `v2/test_r2_18_beschluss_zeitpunkt.py` rot | bestätigt | Commit c9f97c5 |
| P-7 | 1, 2 | mittel | `verfahren/hinweise.py:159-168` | Testkonten unterstützen weiter und zählen im Zähler, nicht im Nenner — R1-2: Test des Widerlegers `v1/test_r1_2_testkonto_zaehler.py` rot; R2-17: Test des Widerlegers `v2/test_r2_17_testkonto_im_zaehler.py` rot | bestätigt | Commit 27a4299 |
| P-8 | 4 (Widerleger) | mittel | `verfahren/static/verfahren/js/app.js:182` | Gold-Haken „Erfasst“ erscheint auch, wenn die Handlung scheiterte — N-1: Browser-Sonde rot, vom Hauptprüfer nachgelaufen | bestätigt | Commit fb11934 |
| P-9 | 1 | mittel | `verfahren/views_aktionen.py:320-322` | Abgelaufene Sitzung: Direkt-Handlung mit htmx löscht das Feld (B1-Symptom) — R1-1: Test des Widerlegers `v1/e2e/test_r1_1_sitzung_abgelaufen.py` rot | bestätigt | Commit 7a69fdb |
| P-10 | 1, 5 | mittel | `verfahren/views_aktionen.py:711` | Beanstandung hängt am Textvektor-Lauf statt an der Einschätzung — R1-6: Test des Widerlegers `v1/test_r1_6_beanstandung_lauf.py` rot; R5-3: Test des Widerlegers `v5/test_r5_3_beanstandung_vektorlauf.py` rot | bestätigt | Commit 1a9549b |
| P-11 | 5 | mittel | `verfahren/views.py:960-965` | Rechtsbezug-Lauf wird zur „Einschätzung“ (Gremien-Fenster zeigt rohes JSON, Zone 2 verliert Skelett) — R5-2: Test des Widerlegers `v5/test_r5_2_rechtsbezug_als_einschaetzung.py` rot | bestätigt | Commit 75ba640, 4b50132 |
| P-12 | 3, 6 | mittel | `mitglieder/post.py:326-335` | Regionalpost legt je Empfänger einen Auftrag in der Anfrage an (2 000 Konten ≈ 4,7 s) — R3-6: Test des Widerlegers `v3/test_r3_6_regionalpost_laufzeit.py` rot; R6-5: nachgestellt | bestätigt | Commit 41dab0f |
| P-13 | 3 | mittel | `mitglieder/postausgang.py:97-110` | Verfahrenspost an dauerhaft abgewiesene Adresse ohne Endzustand (stündlich, endlos) — R3-7: Test des Widerlegers `v3/test_r3_7_post_endlos.py` rot | bestätigt | Commit 333e10c |
| P-14 | 3 | mittel | `ki/anbieter.py:24` | Einbringen wartet bis 45 s je Socket-Operation auf den Einbettungs-Anbieter — R3-8: Test des Widerlegers `v3/test_r3_8_einbettung_zeitgrenze.py` rot | bestätigt | Commit f0d3cba |
| P-15 | 1 | mittel | `verfahren/views_aktionen.py:244` | Bedeutungsstufe: jeder Einbringen-POST ruft den Anbieter, ohne Drossel — ein Konto kann das Monatsbudget leeren — R1-3: Test des Widerlegers `v1/test_r1_3_4_bedeutungsstufe.py::test_r1_3_wiederholtes_einbringen_ohne_trotzdem_ist_gedrosselt` rot | bestätigt | Commit 8d1ee6f, e106b79 |
| P-16 | 1, 2, 5 | mittel | `verfahren/aehnlichkeit.py:82` | Entwurf geht vor dem Einbringen an den KI-Anbieter; Datenschutz/ADR-011 sagen „ohnehin öffentlich“ — R2-3: Test des Widerlegers `v2/test_r2_3_entwurf_an_anbieter.py` rot; R5-4: Test des Widerlegers `v5/test_r5_4_entwurf_an_ki.py` rot; R1-4: Test des Widerlegers `v1/test_r1_3_4_bedeutungsstufe.py::test_r1_4_entwurf_ohne_einbringen_geht_nicht_an_den_anbieter` rot | bestätigt | Commit e912cd6 |
| P-17 | 2, 5 | mittel | `verfahren/templates/verfahren/datenschutz.html:36-37` | Datenschutz-Entwurf: Ausschluss anonymisiert nicht, Referenz nicht aus Mitgliedsnummer, GoCardless sieht Mitgliederdaten, Lichtbild nicht im Profil widerrufbar, Besuchs-Kennung/IP, Cookies, Datenarten — R2-9: Test des Widerlegers `v2/test_r2_9_datenschutz_vs_code.py` rot; R5-5: Test des Widerlegers `v5/test_r5_5_ausschluss_anonymisiert.py` rot; R5-6: Test des Widerlegers `v5/test_r5_6_lichtbild_widerruf.py` rot; R5-8: Test des Widerlegers `v5/test_r5_8_besuchskennung.py` rot; R5-9: Test des Widerlegers `v5/test_r5_9_referenz_mitgliedsnummer.py` rot; R5-7: Test des Widerlegers `v5/test_r5_7_messages_cookie.py` rot; R5-16: Test des Widerlegers `v5/test_r5_16_datenarten.py` rot | bestätigt | Commit 051b41f, 01b734b |
| P-18 | 2, 3, 5 | mittel | `verfahren/hinweise.py:51-57` | Pausierte landen über den Kachel-Hinweis auf „Willkommen … jetzt Anwärter … ab sofort abstimmen“ — R2-10: Test des Widerlegers `v2/test_r2_10_pausiert_willkommen.py` rot; R3-10: Test des Widerlegers `v3/test_r3_10_stimmrechts_satz.py` rot; R5-13: Test des Widerlegers `v5/test_r5_13_willkommen_pausiert.py` rot | bestätigt | Commit 27df635 |
| P-19 | 2 | mittel | `plattform_core/schema.py:247-257` | Anteil der Unterstützungsschwelle fehlt in /parameter.json und in den Registerschlüsseln der Ordnungsregel — R2-5: Test des Widerlegers `v2/test_r2_5_anteil_im_export.py` rot | bestätigt | Commit b16b068 |
| P-20 | 2, 3 | mittel | `ki/rechtsbezug.py:102-118` | „Betroffene Gesetze“ nennt die Fassung nicht; Auftrag rechnet mit fremder Fassung — R2-7: Test des Widerlegers `v2/test_r2_7_rechtsbezug_fassung.py` rot; R3-15: Test des Widerlegers `v3/test_r3_11_12_13_15_17_warteschlange.py` rot | bestätigt | Commit 90eee58 |
| P-21 | 4 | mittel | `verfahren/templates/verfahren/parlament.html:12` | ?fokus= mit JavaScript: nach Esc bleibt die Fokus-Klasse — Raster zerbricht — R4-2: Test des Widerlegers `v4/e2e/test_r4_sonden.py::test_r4_2_fokus_aus_adresse_mit_js_verlassen_stellt_2x2_her` rot | bestätigt | Commit c7109f8 |
| P-22 | 4 | mittel | `verfahren/templates/verfahren/base.html:738` | Stimmknöpfe: gewählter Zustand und Fokusring gleich (dunkel), Fokus auf gewähltem Knopf unsichtbar — R4-3: Test des Widerlegers `v4/e2e/test_r4_sonden.py::test_r4_3_stimmknopf_auswahl_ohne_ring_und_fokus_sichtbar` rot | bestätigt | Commit 1751701 |
| P-23 | 4 | mittel | `verfahren/static/verfahren/js/app.js:361` | Alt+1…4 verschluckt beim Tippen Zeichen (macOS ⌥2 = “, Windows-Alt-Codes) — R4-4: Test des Widerlegers `v4/e2e/test_r4_sonden.py::test_r4_4_alt_ziffer_im_eingabefeld_bleibt_beim_tippen` rot | bestätigt | Commit 2966d72 |
| P-24 | 4 | mittel | `verfahren/static/verfahren/js/app.js:162` | Fokus nach einer Stimme aus dem Feed geht verloren (Knopf in geschlossenem details) — R4-5: Test des Widerlegers `v4/e2e/test_r4_sonden.py::test_r4_5_fokus_nach_feedstimme_bleibt_im_feld` rot | bestätigt | Commit 3d773b1 |
| P-25 | 4 | mittel | `verfahren/templates/verfahren/_faecher.html:21` | Fokus nach Fächer-/Brotkrumen-Link geht verloren — R4-6: Test des Widerlegers `v4/e2e/test_r4_sonden.py::test_r4_6_fokus_nach_faecherlink_bleibt_im_faecher` rot | bestätigt | Commit 07f14ad |
| P-26 | 1, 2, 5 | mittel | `mitglieder/views.py:89-98` | Einwilligungstext der Registrierung nennt Beitragserinnerung und „ganz Österreich“ nicht — R5-10: Test des Widerlegers `v5/test_r5_10_einwilligung_beitragserinnerung.py` rot; R2-8: Test des Widerlegers `v2/test_r2_8_einwilligung_text.py` rot; R1-5: Test des Widerlegers `v1/test_r1_5_11_texte.py::test_r1_5_registrierung_nennt_die_beitragserinnerung` rot | bestätigt | Commit 1b74dcf |
| P-27 | 2, 5 | mittel | `docs/adr/ADR-003-offene-verifizierbare-abstimmung.md:29-39` | Vertrauensfrage laut § 7 Abs 10 lit e geheim, läuft seit 0.48 pseudonym-offen; ADR-Nachtrag ohne ❓ — R2-2: Test des Widerlegers `v2/test_r2_2_vertrauensfrage_geheim.py` rot; R5-12: Test des Widerlegers `v5/test_r5_12_vertrauensfrage_geheim.py` rot | bestätigt | Commit fe543ef |
| P-28 | 6 | mittel | `mitglieder/postausgang.py:27` | Rollback auf 0.49 / Deploy-Überlappung: alter Postausgang verschickt neue Postarten als Freischaltung mit Ausweis — R6-2: nachgestellt | bestätigt | Commit 91fa16c |
| P-29 | 6 | mittel | `mitglieder/migrations/0022_post_einwilligung_und_postbezug.py:34-46` | Rückweg von 0021/0022: Stamm neu abgeleitet, Einwilligung beim erneuten Vorwärts für alle auf ja — R6-3: Test des Widerlegers `v6/test_r6_3_rueckweg_einwilligung.py` rot | bestätigt | Commit cc61c1f |
| P-30 | 6 | mittel | `mitglieder/migrations/0022_post_einwilligung_und_postbezug.py:14` | Migration 0022 setzt die Einwilligung auch auf Partner-Instanzen — R6-4: nachgestellt | bestätigt | Commit 1cc2300 |
| P-31 | 2, 3 (H-1 ✱) | mittel | `mitglieder/models.py:243-266` | Pause verschiebt das Beitrittsdatum (Ausweis, Verwaltung, Export, Kurve); Umweg über Ausschluss hebt die Verschiebung auf; ohne Spur im Audit — R2-4: Test des Widerlegers `v2/test_r2_4_pause_anwartschaft.py` rot; R3-9: Test des Widerlegers `v3/test_r3_9_pause_ausschluss.py` rot | bestätigt | nicht gebaut — Entscheidung des Gründers 29.9.2026 „a“ (H-1): Verschieben bleibt, kein Feld; Rest als Folgeschritt |
| P-32 | 3 | niedrig | `gremien/models.py:1132-1137` | Verklemmung: faellige_abschliessen in einer Transaktion für alle Beschlüsse — R3-4: Test des Widerlegers `v3/test_r3_4_verklemmung.py` rot | bestätigt | Commit 5d553db |
| P-33 | 6 | niedrig | `gunicorn.conf.py:21-24` | Wächter läuft im Faden hinter dem Postausgang; dessen Ausnahme lässt ihn ausfallen — R6-14: Test des Widerlegers `v6/test_r6_14_waechter_hinter_post.py` rot | bestätigt | Commit cd3737a |
| P-34 | 2, 6 | niedrig | `parameter/kennzahlen.py:63` | Kennzahl members.active zählt Testkonten — R2-12: Test des Widerlegers `v2/test_r2_12_kennzahl_testkonten.py` rot; R6-8: Test des Widerlegers `v6/test_r6_8_kennzahl_testkonten.py` rot | bestätigt | Commit 0185f59 |
| P-35 | 6 | niedrig | `mitglieder/bank.py:131` | Bankabgleich N+1 (only() ohne Stamm) — R6-7: Test des Widerlegers `v6/test_r6_7_bank_nplus1.py` rot | bestätigt | Commit 6b7013c |
| P-36 | 6 | niedrig | `Dockerfile:13` | Dockerfile-CMD ohne gemeinden_laden (A13-Rest) — R6-10: nachgestellt | bestätigt | Commit c21ecdb |
| P-37 | 6 | niedrig | `mitglieder/profil.py:550-573` | Datenexport ohne Beitragsreferenz-Stamm — R6-11: Test des Widerlegers `v6/test_r6_11_export_referenz.py` rot | bestätigt | Commit c71a759 |
| P-38 | 6 | niedrig | `mitglieder/migrations/0021_referenzstamm_und_testkonten.py:23-65` | Datenmigration 0021 ohne Test — R6-12: Test des Widerlegers `v6/test_r6_12_migration_0021.py` rot | bestätigt | Commit 321cb70 |
| P-39 | 6 | niedrig | `mitglieder/migrations/0021_referenzstamm_und_testkonten.py:59-65` | Stilllegung beendet Rollen ohne Rollenbezug im Audit — R6-13: nachgestellt | bestätigt | Commit 1391c5c |
| P-40 | 5, 6 | niedrig | `CLAUDE.md:64` | Doku: Check „pruefen“ heißt jetzt „pruefen (3.11)/(3.12)“; Postart rechtsbezug fehlt; Start Command im Dashboard — R6-15: nachgestellt; R5-24: Test des Widerlegers `v5/test_r5_24_dokumente.py` rot | bestätigt | Commit 6c60b2d, 839127a |
| P-41 | 1 | niedrig | `verfahren/hinweise.py:135-156` | weiter mit Tab/CR/LF → 500 nach geschriebener Handlung — R1-7: Test des Widerlegers `v1/test_r1_7_weiter_steuerzeichen.py` rot | bestätigt | Commit 4ff5302 |
| P-42 | 1, 2, 5 | niedrig | `verfahren/hinweise.py:60-63` | Neue Hinweise zitieren § 4 Abs 6 (gibt es nicht) und § 4 Abs 2 (Rechte) für die Identität — R1-11: Test des Widerlegers `v1/test_r1_5_11_texte.py::test_r1_11_ausschluss_zitiert_den_richtigen_absatz` rot; R2-11: Test des Widerlegers `v2/test_r2_11_paragraphen_zitate.py` rot; R5-19: Test des Widerlegers `v5/test_r5_19_satzungszitat.py` rot | bestätigt | Commit 0288545 |
| P-43 | 1 | niedrig | `gremien/views.py:568-585` | Sperrtests für geänderte Verwaltungsaktionen fehlen — R1-12: Test des Widerlegers `v1/test_r1_12_sperrtests_verwaltung.py` rot | bestätigt | Commit c1add58 |
| P-44 | 2, 5 | niedrig | `plattform_core/similarity.py:209-226` | Regelverzeichnis Ähnlichkeit: Auswahl nach Maximum, Sonderfall ohne Wortpaare, feste 30/78 statt Registerwert — R2-6: Test des Widerlegers `v2/test_r2_6_aehnlichkeit_regel_offen.py` rot; R5-21: Test des Widerlegers `v5/test_r5_21_nachrechenbar_sonderfall.py` rot; R5-11: Test des Widerlegers `v5/test_r5_11_register_18.py` rot | bestätigt | Commit 91f83ea |
| P-45 | 2, 4, 5 | niedrig | `verfahren/templates/verfahren/einbringen.html:59-62` | Band nach dem Einbringen verspricht „ähnliche Anträge“; neuer Erklärsatz auf Einbringen — R2-14: Test des Widerlegers `v2/test_r2_14_einbringen_band.py` rot; R4-15: Test des Widerlegers `v4/test_r4_15_band_verspricht.py` rot; R5-17: Test des Widerlegers `v5/test_r5_17_band_aehnliche.py` rot | bestätigt | Commit e678862 |
| P-46 | 2 | niedrig | `mitglieder/templates/mitglieder/post/rechtsbezug.txt:17` | KI-Brief „betroffene Gesetze“ ohne Stand — R2-15: Test des Widerlegers `v2/test_r2_15_brief_stand.py` rot | bestätigt | Commit 10fd9fe |
| P-47 | 2, 3 | niedrig | `verfahren/models.py:989` | Schnappschuss von Vertrauens-/Mandatsfrage trägt den Anteil 0,5 der Ordnung — R2-16: Test des Widerlegers `v2/test_r2_16_vf_schnappschuss_anteil.py` rot; R3-14: Test des Widerlegers `v3/test_r3_14_vf_schnappschuss.py` rot | bestätigt | Commit 560f85d |
| P-48 | 3 | niedrig | `ki/warteschlange.py:163-181` | Budget, das mitten im Stapel ausgeht, kostet Versuche — R3-12: Test des Widerlegers `v3/test_r3_11_12_13_15_17_warteschlange.py` rot | bestätigt | Commit b1fbd9d |
| P-49 | 3 | niedrig | `ki/models.py:67-73` | Monatsverbrauch rechnet den Monat nach UTC — R3-13: Test des Widerlegers `v3/test_r3_11_12_13_15_17_warteschlange.py` rot | bestätigt | Commit 96b9691 |
| P-50 | 3 | niedrig | `ki/warteschlange.py:11-12` | Docstring nennt Rückstellung 64 min — R3-17: Test des Widerlegers `v3/test_r3_11_12_13_15_17_warteschlange.py` rot | bestätigt | Commit 376e274 |
| P-51 | 4 | niedrig | `verfahren/static/verfahren/js/app.js:332` | Fokus-Modus am Handy nach Drehen/Verkleinern nicht zu verlassen — R4-10: Test des Widerlegers `v4/e2e/test_r4_sonden.py::test_r4_10a_fokus_nach_verkleinern_nicht_gefangen` rot | bestätigt | Commit 8519ad5 |
| P-52 | 4 | niedrig | `verfahren/static/verfahren/js/app.js:223` | Einpassen des Fächers wirkt der Browser-Vergrößerung entgegen — R4-12: Test des Widerlegers `v4/e2e/test_r4_sonden.py::test_r4_12_einpassen_nur_im_2x2_raster` rot | bestätigt | Commit 4ebfe0e |
| P-53 | 4, 5 | niedrig | `verfahren/templates/verfahren/zukunftswerkstatt.html:126` | Zwei neue Inline-Styles; Feldnamen der Ordnung ohne gettext — R4-13: Test des Widerlegers `v4/test_r4_13_inline_styles.py` rot; R5-26: Test des Widerlegers `v5/test_r5_26_inline_styles.py` rot | bestätigt | Commit 4194c98 |
| P-54 | 4 (H-2) | niedrig | `verfahren/test_app_rahmen.py:321` | Test Feldtausch-Übergang blind für Fächerlinks — R4-14: Test des Widerlegers `v4/test_r4_14_h2_faecherlinks.py` rot | bestätigt | Commit 0b732b8 |
| P-55 | 5 | niedrig | `plattform_core/rollen.py:387` | Rollenmatrix Fassung 6: „FB-I1“ im Nutzertext, „kommt mit offen —“ — R5-14: Test des Widerlegers `v5/test_r5_14_kennungen_rollen.py` rot | bestätigt | Commit 8df74f6 |
| P-56 | 5 | niedrig | `mitglieder/templates/mitglieder/profil.html:60-61` | Profil „Nachrichten“: Liste „Ohne Haken: nur …“ unvollständig — R5-15: Test des Widerlegers `v5/test_r5_15_ohne_haken.py` rot | bestätigt | Commit cb5414f |
| P-57 | 5 | niedrig | `mitglieder/beitraege_views.py:75` | C4/C6-Reste: „Wir prüfen automatisch weiter“, „Danke für die Meldung“ — R5-18: Test des Widerlegers `v5/test_r5_18_c4_c6_reste.py` rot | bestätigt | Commit 73b0e3a |
| P-58 | 5 | niedrig | `docs/adr/ADR-011-aehnlichkeit-einbettungen.md:29` | DDOE_KI_EINBETTUNGSMODELL wird nicht aus der Umgebung gelesen — R5-20: Test des Widerlegers `v5/test_r5_20_einbettungsmodell_env.py` rot | bestätigt | Commit 2fbed0b |
| P-59 | 5 | niedrig | `locale/en/LC_MESSAGES/django.po` | Übersetzung: „touched“, „is not supported“, zwei Namen der Zukunftswerkstatt — R5-25: Test des Widerlegers `v5/test_r5_25_uebersetzung.py` rot | bestätigt | Commit 3cba7ad (Katalog, Schritt 5) |
| P-60 | 5, 6 | niedrig | `mitglieder/templates/mitglieder/verwaltung_mitglied.html:29` | Verwaltung zeigt den Brief „betroffene Gesetze“ als „Ausweis-Vorschau · PDF noch nicht versendet“ — Hinweis des Nachprüfers von K2, mit Test nachgestellt (rot, dann grün) | bestätigt | Commit 8bc42ce |
| P-61 | 5 | niedrig | `uebersicht/templates/uebersicht/uebersicht.html:124` | Übersicht nennt die gespeicherte Tageskennung „flüchtig“ — Widerspruch zur Datenschutzerklärung — Hinweis des Nachprüfers von K5, mit Test nachgestellt (rot, dann grün) | bestätigt | Commit 34dacc8 |
| P-62 | 4 | mittel | `verfahren/static/verfahren/js/app.js:302` | Nach jedem Fächer-Wechsel fällt „Meine Favoriten“ rund eine halbe Sekunde lang auf Deckkraft 0 und blendet neu ein (Eingangsbewegung läuft nach der FLIP-Bewegung neu an) — leeres Bild der Sichtprüfung, im Browser gemessen (Deckkraft 0) und mit Test nachgestellt (rot, dann grün) | bestätigt | Commit d85e150 |

## 4. Hypothesen und Anhang A

- **H-1 (Pause und Beitrittsdatum) — bestätigt.** `status_setzen` überschreibt `Mitglied.beitritt` beim Ende einer Pause (`mitglieder/models.py:255-263`). Leser der Anwartschaft (gewollt): `ist_stimmberechtigt`, `stimmberechtigte_zaehlen` (und damit die Grundgesamtheit der Prozent-Schwelle), `plattform_core/eligibility.py`, `stimmrechts_satz`. Leser der Historie (verfälscht): Mitgliedsausweis „Mitglied seit“ (`mitglieder/ausweis.py:160`), öffentliche QR-Prüfseite (`ausweis_views.py:77` — weicht nach der Pause von der gedruckten Karte ab), Verwaltung „beigetreten“, Verwaltungsliste, Datenexport, Mitgliederkurve auf `/uebersicht/`, Mindestdauer vor der Beitragserinnerung. Nicht verschoben wird über den Umweg Pause → Ausschluss → Reaktivierung; das alte Datum steht in keinem Audit-Eintrag. **Entscheidung des Gründers 29.9.2026: „a“ — das Verschieben bleibt, nichts bauen, kein Feld für Pausentage.** Die Lücken (Umweg über den Ausschluss, fehlende Spur im Audit, Altbestand ohne `status_seit`) stehen als Folgeschritt.
- **H-2 (Test Feldtausch-Übergang) — bestätigt.** Mit Kategorienbaum schlägt `verfahren/test_app_rahmen.py::test_skelette_und_feldtausch_mit_uebergang` an fünf Fächer- und Brotkrumen-Links an; ohne Kategorien prüfte er null Knoten. Behoben als P-54.
- **H-3 (Audit-Hash der Migration 0021) — widerlegt, die Kette ist heil.** Auf PostgreSQL mit einer Datenbank im Stand 0.49 (main-Code, `demo_seed`, Einträge mit Umlauten, Listen, Kommazahl) die Migrationen gefahren und die ganze Kette per SQL (JSONB-Rundreise) mit `plattform_core.hashchain.kette_pruefen` nachgerechnet: 48 bzw. 53 Einträge, `kette_ok True`, `vorgaenger` stimmt. `audit_anhaengen` in 0021/0022 rechnet wie `AuditEintrag.anhaengen` (Zeit im Ereignis, gleiche Serialisierung). Unterschied: keine Wiederholung bei überholtem Kopf — ein Deploy scheitert dann und wird im nächsten nachgeholt, ohne Datenverlust. Ein Test fehlte (P-38).
- **A-1 Tastenkürzel** — Konflikt bestätigt (macOS ⌥2 = „““ verschluckt, Windows-Alt-Codes, Tabwechsel unter Linux überschrieben, Fokusfalle des Menüs umgangen). **Entscheidung des Gründers 29.9.2026: Tastenkürzel samt Tastenhilfe entfernen**, Fokus-Knöpfe und `?fokus=` bleiben (P-23).
- **A-2 Manifest-Symbole** — kein Befund: WhiteNoise liefert `app.webmanifest` als `application/manifest+json` (gehasht `immutable`, ungehasht `max-age=60`), die Symbole ungehasht mit `max-age=60`; `id: "/parlament/"` hält die App-Kennung stabil. Folgeschritt: Manifest über eine View mit `{% static %}`.
- **A-3 Zweck „einschaetzung“ ohne Auftragstext-Datei** — festgestellt, Folgeschritt `ki/auftraege/einschaetzung-v1.md`.
- **A-4 Datenschutz** — die Liste „vom Gründer zu bestätigen“ ging an den Gründer; **freigegeben 29.9.2026** (Verantwortlicher, Anschrift, Registerzahl, Dienstleister bestätigt). Die Sätze, die der Code nicht erfüllt, wurden auf seine Anweisung angeglichen (P-2, P-16, P-17).
- **A-5 Bildschirmtest Zone 2** — fehlte; ergänzt in der Sichtprüfung 0.50.0 (Karte „Betroffene Gesetze“ eingereiht und erledigt, Band nach dem Einbringen).
- **A-6 Warteschlange ohne Anbieter** — in Ordnung: `/zukunftswerkstatt/` sagt „kein Anbieter angeschlossen“, die Karte „Kein Anbieter angeschlossen — es wird nichts gerechnet“, `abarbeiten` reserviert nichts und zählt keinen Versuch.
- **A-7 Regionalpost-Laufzeit** — gemessen: 2 000 Empfänger ≈ 4,7 s und 8 006 Abfragen auf PostgreSQL (10 000 ≈ 22 s); behoben als P-12 (gemessen 0,12 s, 14 Abfragen).
- **A-8 Rollenmatrix Fassung 6, Regelverzeichnis** — Orte der gehobenen Zeilen stimmen; Abweichungen P-44 (Ähnlichkeit), P-55 (Kennungen in Nutzertexten), P-17 f (Cookie-Satz der Gast-Rolle).
- **A-9 Auftragstext `rechtsbezug-v1.md`** — sachlich, „keine Rechtsberatung … Du schlägst vor; entschieden wird von Menschen“, keine Kennungen; kein Befund. Die Datei liegt außerhalb des Sprachregel-Wächters (Protokollwerte `aendern`/`beruehrt` sind JSON-Schlüssel).
- **A-10 bewusst nicht in dieser Welle** — unverändert festgestellt: A3 (Status ↔ Gremien; der Lostopf filtert nur Testkonten), A5 (Übergangsregel live gelesen, beim Einbringen jetzt sofort eingefroren), A6 (Chat-Anzeige), A7 (Audit-Prüfung; die Migrationen schreiben in dieselbe Kette), A8 (Reaktionen werden hart gelöscht; im Diff kein `.delete(`), A9 (CASCADE; neu `AntragsEinbettung.antrag` CASCADE, der Antrag selbst wird nie gelöscht), A10 (Sicherung; die Betriebsdoku führt sie ehrlich als offen), A11 (teilweise behoben: Endzustand der Verfahrenspost, Wiener Kalendertag bei `bewerben`/`demo_seed`; offen: Bestätigungslink reaktiviert Ausgeschlossene, Anmeldelinks per GET, `art` statt `typ`), A14 (Beitragserinnerung an Testkonten behoben; Meldeknopf/Drossel, 180-Tage-Zustimmung, Berichtswesenrat offen), B3 (zwei neue Inline-Styles → P-53), B4 (Skelett-Schimmer flackert bei reduzierter Bewegung — nachstellbar, bewusst nicht in dieser Welle), C7 (bleibt, Gründerentscheid), D4 (Höchstzahl fünf zusätzlich in `hinweise.py`), D5, D6 unverändert.

## 5. Folgeschritte (nicht in diesem Pull Request)

| Befund | Schwere | Inhalt | Aufwand / Weg |
|---|---|---|---|
| R1-8 | niedrig | Feldhinweise sind über fremde Links fälschbar (`/parlament/?hinweis=stimme&feld=wichtig` zeigt „Stimme erfasst“) | Bindung an die Sitzung, ~1 h |
| R1-9 | niedrig | Chat: gesperrtes Konto ohne JavaScript verliert den Entwurf (403-Seite); Formular wird Gesperrten gezeigt | ~1 h |
| R1-10 | niedrig | Kachel der Vertrauensfrage nennt Pausierten den falschen Sperrgrund; Stimmknöpfe bleiben bei Aussetzung | ~1 h |
| R2-13 | niedrig | Ungeprüfte Konten zählen auf Startseite/Übersicht als „Mitglieder“ | Frage an den Gründer |
| R3-11 | niedrig | Tageskontingent „ki-tageslaeufe“ zählt Aufträge statt Anbieteraufrufe (bis ~6× mehr Aufrufe) | Definition durch den Gründer |
| R4-8 | niedrig | Doppelte Landmarken mit gleichem Namen (region in region) | `role=group`, ~30 min |
| R4-9 | niedrig | Esc beendet den Fokus-Modus auch beim Schließen eines Menüs | ~30 min |
| R4-11 | niedrig | Ohne JavaScript verlässt jeder Fächer-/Suchklick den Fokus-Modus | ~30 min |
| R5-22 | niedrig | Cloudflare (laut `render.yaml` im Datenpfad) nicht in der Empfängerliste; KI-Anbieter nur als technischer Schlüssel | Gründer (Datenschutz) |
| R5-23 | niedrig | Die in `render.yaml` vorausgesetzte Einwilligung der Testmitglieder ins US-Hosting holt niemand ein | Gründer |
| R6-6 | niedrig | Neue NOT-NULL-Spalten ohne Datenbank-Vorgabe: die alte Fassung scheitert im Deploy-Fenster (Registrierung, Kontobriefe) | `db_default`, ~1 h; bis dahin kein Rückweg auf 0.49 (Betriebsdoku) |
| R6-9 | niedrig | Migration 0021 legt demo1–5 auch in Entwicklungsdatenbanken still; `demo_seed` reaktiviert sie nicht | frische Entwicklungsdatenbank; ~30 min |
| H-1-Rest | mittel | Pause → Ausschluss → Reaktivierung verschiebt den Beitritt nicht; die Verschiebung steht in keinem Audit-Eintrag; Altbestand ohne `status_seit` | Gründer: „nichts bauen“ — offen für eine spätere Entscheidung |
| Region | — | Die Prozent-Schwelle rechnet auch für Gemeinde-, Bezirks- und Landesanträge mit allen Stimmberechtigten Österreichs | Gründer 29.9.2026: Folgeschritt „Region zählt“, ~halber Tag |
| Zugriffs-Audit | — | Ein Protokoll der Zugriffe auf das Stimmregister (ADR-003 „Zugriffs-Audit“) gibt es nicht; die Texte versprechen es seit dieser Prüfung nicht mehr | ~halber Tag |
| Lauf je Fassung | — | „Betroffene Gesetze“ wird bei einer neuen Fassung (Vorschlag des Expertenrats) nicht neu eingereiht (FB-H6) | ~1 h |
| §-Altbestand | — | „§ 4 Abs 6“ für den Ausschluss im Altbestand (`mitwirkung_ruht.html`, Verwaltung, `mitglieder/models.py`) — die Satzung hat in § 4 nur Abs 1–5 | ~30 min, nach Bestätigung der Satzungsfassung |
| Mitglied n | — | „Mitglied n“/„Ehemaliges Mitglied n“ tragen die Konto-ID, Profil und Austritt versprechen die Mitgliedsnummer (C4-Rest) | Gründer, ~1 h |
| P-6-Rest | niedrig | Der Fristzeitpunkt gilt für alle Wirkungen eines verfristeten Beschlusses: Parametertest und Einführung datieren `geaendert_am` auf die Frist zurück, die Zurückweisung setzt `phase_beginn` auf die Frist, auch wenn der Antrag inzwischen weiter ist (Fenster ≤ ein Takt) | prüfen, ~1 h |
| P-32-Rest | niedrig | Jeder Nachlauf (Beschlüsse, Aussetzungen, Parametertests) arbeitet je Element in einer eigenen Transaktion, wirft aber weiter: Ein Element, das dauerhaft scheitert, hält die nach ihm geordneten Elemente desselben Nachlaufs bei jedem Takt auf (die übrigen Nachläufe und alle Anträge nicht) | Fehlergrenze je Element, ~30 min |
| P-57-Rest | niedrig | Der Handweg der Verwaltung „Beitragseingang vermerkt“ schickt keine Bestätigung per E-Mail; `beitrag.html` sagt „Eingänge werden regelmäßig geprüft“ | ~30 min |
| P-7-Rest | niedrig | Testkonten lassen sich in der Verwaltung reaktivieren (folgenlos); alte Reaktionen von Testkonten im Abstimmungs-Chat zählen in ja/nein | ~30 min |
| P-30-Rest | niedrig | Eine Partner-Instanz, die `DDOE_SYSTEM_ID` nicht setzt, erhält die Bestandseinwilligung der DDÖ | Doku `docs/partner/EINRICHTUNG.md`, ~15 min |
| Datenarten | niedrig | Die Datenschutzerklärung nennt serverseitige Filterprofile, Abos, Favoriten und Lesestände nicht | Text, Freigabe des Gründers |
| Vertrauensfrage geheim | — | § 7 Abs 10 lit e: „Sie ist geheim“ — online läuft sie seit 0.48 pseudonym-offen (❓ D-L6h) | Gründer: Satzungsbaustein oder Präsenz/Brief |

## 6. Widerlegt und unbestätigt

- **R4-7 widerlegt** (als Befund dieser Welle): Der Skelett-Schimmer flackert bei reduzierter Bewegung — nachstellbar, aber Bestandsaufnahme B4, bewusst nicht Teil der Welle.
- **R3-16 widerlegt:** Ein zweiter Stapel der Warteschlange nach Ablauf der 15-Minuten-Sperre rechnet nichts doppelt und überschreitet das Tageskontingent nicht (PostgreSQL-Sonde: 20 Aufträge, 0 doppelt).
- **R4-16 unbestätigt:** Ob Screenreader den Feldhinweis (`role=status`, mit dem Feld getauscht) ansagen, ist ohne Screenreader-Probe nicht belegt — Handprobe des Gründers (NVDA/VoiceOver).
- **R6-16 unbestätigt:** Ob der per API angelegte Render-Dienst die neue Startkette nutzt (render.yaml wirkt dort nicht), ist aus der Prüfumgebung nicht einsehbar — die Betriebsdoku nennt jetzt den Handgriff im Dashboard; der Gründer prüft den Start Command.

## 7. Vom Gründer zu bestätigen

1. **❓ D-L6h — Vertrauensfrage geheim.** § 7 Abs 10 lit e: „Sie ist geheim.“ Online läuft sie seit 0.48 pseudonym-offen wie jede Abstimmung (P-27; ADR-003 und README nennen den Widerspruch). Satzungsbaustein anpassen, oder die Vertrauensfrage über Präsenz und Brief führen?
2. **Betriebsgrenzen als Konstanten.** Die Prüfung hat drei Grenzen der Maschine eingeführt: höchstens acht Sekunden Wartezeit auf den Anbieter beim Einbringen (P-14), höchstens fünf Bedeutungsvergleiche je Konto und Stunde (P-15), Verfahrenspost gibt nach 24 Versuchen auf (P-13). Sie stehen wie `HOECHSTVERSUCHE` der Warteschlange als Konstanten im Code, nicht im Register (FB-J2: „Grenzen der Maschine“). Sollen sie Registerwerte werden?
3. **Tageskontingent der Zukunftswerkstatt** (`ki-tageslaeufe`, 20): Es zählt Aufträge, nicht Anbieteraufrufe; ein Auftrag kann bis zu sechs Aufrufe kosten (R3-11). Welche Zählung ist gemeint?
4. **„Mitglieder“ auf Startseite und Übersicht** zählen ungeprüfte Konten mit (R2-13). Bleibt das so?
5. **Datenschutz, Nachträge:** Cloudflare steht laut `render.yaml` im Datenpfad, aber nicht in der Empfängerliste (R5-22); die in `render.yaml` vorausgesetzte Einwilligung der Testmitglieder ins US-Hosting holt niemand ein (R5-23); der Widerruf von Lichtbild und Fachliste läuft über die Verwaltung (Zusage an den Ablauf, kein Knopf); die Drossel hält die Verbindungsadresse „rund zwei Stunden“ — auf einer ruhigen Instanz länger, weil erst eine neue Zeile aufräumt.
6. **„Mitglied n“** trägt die Konto-Kennung, Profil und Austritt sprechen von der Mitgliedsnummer (C4-Rest).
7. **H-1-Rest:** Pause → Ausschluss → Reaktivierung verschiebt den Beitritt nicht; die Verschiebung steht in keinem Audit-Eintrag; Altbestand ohne `status_seit`. Nach „a“ nichts gebaut — offen für eine spätere Entscheidung.
8. **Render:** Start Command im Dashboard prüfen (R6-16, aus der Prüfumgebung nicht einsehbar).
9. **Screenreader-Probe** des Feldhinweises (`role=status`) mit NVDA oder VoiceOver (R4-16).

## 8. Selbst getroffene Entscheidungen

- **Testkonten gesperrt statt gelöscht.** „Die demokonten können komplett raus“ ist umgesetzt als: in keiner Zählung (Zähler und Nenner, Kennzahlen, Lostopf, Auswahl der Verwaltung), keine Mitwirkung (Hinweis „Testkonto — ohne Mitwirkung.“), stillgelegt; ihre Zeilen bleiben gespeichert (Grundregel 7, CLAUDE.md § 6: keine Löschung von Stimm- und Verfahrensdaten).
- **Beanstanden zielt auf die Einschätzung der Kopfkarte** (P-11, Nachbesserung): Das Formular steht in der Kopfkarte; liegt keine Einschätzung vor, trifft es wie bisher den jüngsten lesbaren Lauf (Rechtsbezug). Ein ausdrückliches Ziel über ein verstecktes Feld wäre genauer, aber größer — nicht gebaut.
- **Wächter: Transaktion je Schritt** (P-5, Nachbesserung): statt einer Transaktion je Antrag, damit ein späterer Fehler einen fälligen früheren Übergang nicht bei jedem Takt zurückrollt — dasselbe Verhalten wie auf der Antragsseite.
- **P-62 behoben**, obwohl erst bei der Sichtprüfung gefunden: ein leeres Bild der Fächer-Bewegung führte auf ein echtes Aufblitzen des Felds nach jedem Wechsel (im Browser gemessen) — mitten in der Bewegung, die der Gründer „flüssig“ wollte.
- **Zwei zusätzliche Befunde der Nachprüfer** behoben, weil sie in dieser Welle entstanden und je eine Zeile groß sind: P-60 (Verwaltungsanzeige der neuen Postart), P-61 („flüchtig“ auf der Übersicht gegen die freigegebene Datenschutzerklärung). Dazu zwei Dokumentvermerke ohne Code: Freigabe der Datenschutzerklärung im Lastenheft (P-17) und Nachtrag „Zugriffs-Audit fehlt“ in ADR-003 (P-2).
- **CLAUDE.md § 5 Punkt 6** nennt jetzt die Status-Checks mit Python-Fassung (P-40); die feste Versionsangabe blieb unberührt.
- **Commit-Zeilen** aus einem Arbeitszweig (K4), die kein Verb trugen, beim Übernehmen in den Imperativ gesetzt; eine verrutschte Testmarkierung (`django_db`) beim Übernehmen zurückgesetzt.
- **Übersetzung:** „Zukunftswerkstatt“ bleibt überall Eigenname (die Einträge mit „future workshop“ angeglichen, die erklärende Klammer auf der Startseite bleibt); „berührt“ → „affected“; „cannot be endorsed“ für den Bestätigungsantrag (P-59).
- **Drosseltest mit fester Uhr** (P-15, Nachbesserung): Der Test zählte gegen die echte Uhr und hätte über einen Stundenwechsel hinweg sehr selten fehlgeschlagen; die Drossel selbst bleibt unverändert.
- **Eine erste Zeile mit 74 Zeichen** (`01b734b`, Vermerk im Lastenheft) bleibt stehen: Sie umzuschreiben bräuchte einen Rebase des Zweigs, den die Regeln dieser Prüfung ausschließen.
- **Nebenzweige:** Arbeitsagenten haben `pruefung/k3a`, `pruefung/k3b`, `pruefung/k4` und `pruefung/k5` nach GitHub gepusht; ihr Inhalt steckt vollständig in diesem Zweig. Das Löschen scheiterte aus der Prüfumgebung (Netzwerk) — der Gründer löscht sie auf GitHub.
- **Sichtprüfung:** Das Bild der Tastenhilfe entfällt mit der Tastenhilfe; die Bewegung des Fächers liegt als Bildfolge aus vier angehaltenen Zeitpunkten der Animation und als GIF vor (deterministisch statt Video). Das Bild der Prozent-Schwelle rechnet mit dem Erstbestand von fünf Prozent.

## 9. Sichtprüfung

Ordner `docs/sichtpruefung/0.50.0/` mit 92 Bildern: der Bestand aus `tests/e2e/test_sichtpruefung.py` (Parlament als Gast und als Mitglied, hell und dunkel, Fächer-Zustände, Handy, Antragsseite, Entwurfsfenster, Anstoß, Beschlüsse, Fachliste …) und dazu die Bilder für das Neue in 0.50.0 (Desktop 1440×900, Handy 390×844):

| Bilder | Was zu sehen ist | Worauf achten |
|---|---|---|
| `parlament-hinweis-im-feld-{desktop-hell,desktop-dunkel,handy,ohne-javascript}` | Unterstützen aus der Feed-Zeile des WeicherFilters | Das Feld bleibt stehen, „Unterstützung erfasst.“ steht im Feldkopf, der Knopf zeigt „Unterstützt“. Ohne JavaScript dasselbe nach einem Seitenwechsel. |
| `parlament-fokus-favoriten-{desktop-hell,desktop-dunkel,ohne-javascript}` | Fokus-Modus: „Meine Favoriten“ füllt das Raster | Die anderen Felder sind weg, der Knopf ⤢ führt zurück. Es gibt keine Tastenhilfe mehr. |
| `faecher-nach-flip-{desktop-hell,desktop-dunkel,handy}` | Der Fächer nach einem Wechsel in einen Lebensbereich | Der Anker steht unten in der Mitte, die Brotkrume steht im Feldkopf, nichts ist abgeschnitten. |
| `faecher-flip-1…4.png`, `faecher-flip.gif` | Die FLIP-Bewegung zu vier Zeitpunkten und als GIF | Die Knoten gleiten von der alten an die neue Stelle, die neuen blenden ein. Die Bewegung soll kurz und gerichtet sein, ohne Sprung. |
| `einbringen-aehnlichkeit-{desktop-hell,desktop-dunkel,handy}` | Ähnlichkeitskarte beim Einbringen (Attrappe statt Anbieter) | „Wortvergleich n % · Bedeutung m %“, „Trotzdem einbringen“ ist gleichwertig. |
| `antrag-neu-band-{desktop,handy}` | Das Band nach dem Einbringen | Es verspricht nur „betroffene Gesetze“ und verweist auf die Einschätzung. |
| `antrag-rechtsbezug-eingereiht-{desktop-hell,desktop-dunkel}` | Karte „Betroffene Gesetze“ in der Warteschlange | Platz in der Schlange, kein falsches Versprechen. |
| `zukunftswerkstatt-warteschlange-{desktop-hell,desktop-dunkel,handy}` | Die öffentliche Warteschlange | Stand, Tageskontingent, versionierte Auftragstexte. |
| `antrag-rechtsbezug-erledigt-{desktop-hell,desktop-dunkel,handy}` | Die Karte mit Ergebnis | Jede Norm trägt „nicht verifiziert“ und hat keinen Link; genannt sind Modell, Auftragsfassung, Stand „zu Fassung 1“ und der Lauf. |
| `datenschutz-{desktop-hell,desktop-dunkel,handy}` | Die freigegebene Datenschutzerklärung | „Stand: 29.9.2026.“ ohne „Entwurf“. Der Text liest sich ruhig, die Karten sind gegliedert. |
| `profil-nachrichten-{desktop,handy-dunkel}` | Die Karte „Nachrichten“ mit dem Haken der Einwilligung | Die Listen „Mit Haken“ und „Ohne Haken“ sind vollständig. |
| `registrieren-einwilligung-{desktop,handy}` | Registrierung mit dem Haken (Voreinstellung nein) | Der Text des Hakens nennt alles, wofür er gilt. |
| `willkommen-stimmrechtssatz-{desktop,handy}` | Willkommensseite | Der Stimmrechtssatz nennt den heutigen Stand statt fester Monatsfristen. |
| `rollen-formular-namen` | Rollen berufen (Verwaltung) | Die Auswahl zeigt Name und Mitgliedsnummer, keine Anmeldeadresse. |
| `parameter-prozentschwelle-{desktop,handy}` | Regelzeile einer Ordnung der Fassung 4 auf der Antragsseite | Die Schwelle steht als Zahl mit Anteil und Grundgesamtheit. |

Das Bild der Tastenhilfe (`parlament-tastenhilfe`) entfällt, weil der Gründer die Tastenhilfe entfernt hat. Die Bewegung liegt als Bildfolge aus der angehaltenen Animation vor, nicht als Video: Die vier Bilder sind auf jedem Rechner gleich.

## 10. Übergabe

**Gebaut und behoben.** Im Zweig liegt die Bauwelle (Teil 1–5, 7, 8, bis `6745178`) und darauf die Prüfung (Teil 6) mit 71 Commits seit diesem Prüfstand. Das sind je ein Commit pro Befund (P-1 … P-62, Tabelle in Abschnitt 3), drei Nachbesserungen (P-5, P-11, P-15), zwei Dokumentvermerke (P-2, P-17), der Katalog, die Fassung 0.50.0 mit Änderungsprotokoll, die Sichtprüfung und dieses Fahrtenbuch mit Bericht. Dazu kommt der Vermerk „Fassung 1.0“ der Gemeinsamen Vision.

**Betroffene Dateien** (seit `6745178`, ohne Bilder): 112 Dateien, am meisten in `verfahren/` und `mitglieder/`. Weiter: `ki/`, `gremien/`, `mandatare/`, `parameter/`, `plattform_core/` (Schema-Export), `uebersicht/`, `locale/en/`, `tests/e2e/`, `gunicorn.conf.py`, `Dockerfile`, `Makefile`, `config/settings.py`, `CLAUDE.md`, `README.md`, `CONTRIBUTING.md` und die Dokumente `docs/SCHEMA.md`, `docs/CONCEPT.md`, `docs/BETRIEB-RENDER.md`, `docs/partner/`, `docs/adr/ADR-003`, `ADR-011`. Die Bilder liegen unter `docs/sichtpruefung/0.50.0/`.

**Selbst getroffene Entscheidungen:** siehe Abschnitt 8.

**Offen:** die Folgeschritte in Abschnitt 5, mit Aufwand. ❓ D-L6h (Vertrauensfrage geheim) steht im Fahrtenbuch, Teil D.

**Vom Gründer zu bestätigen:** siehe Abschnitt 7.

**Am Arbeitsplatz nachzutragen:**
- Memory und Notizen: Teil 6 ist erledigt, die Entscheidungen vom 29.9.2026 sind im Fahrtenbuch eingetragen.
- Den Wortlaut der Anweisungen vom 28.9. aus `DDOE_Original_Anweisungen_A0.txt` in A0-20 nachtragen.
- Sichtprüfung der Bilder unter `docs/sichtpruefung/0.50.0/`.
- Registerwerte nach dem Merge: neue Fassung der Verfahrensordnung mit dem Anteil von 5 %, `aehnlichkeit-schwelle-prozent` auf 30.
- Branch-Schutz auf `main` mit `pruefen (3.11)`, `pruefen (3.12)`, `pruefen_postgres` und `sichtpruefung`.
- Auf Render den Start Command prüfen.
- Die Nebenzweige `pruefung/k3a`, `pruefung/k3b`, `pruefung/k4` und `pruefung/k5` auf GitHub löschen.

**Danach** ist der zweite Prompt an der Reihe: „Restaufgaben aus dem Fahrtenbuch“.
