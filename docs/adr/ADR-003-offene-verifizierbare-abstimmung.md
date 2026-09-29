# ADR-003: Pseudonym-offene, verifizierbare Abstimmung statt kryptografischer Geheimwahl

Status: angenommen · Datum: 2026-08-19

## Kontext
Geheime Online-Abstimmung und Überprüfbarkeit durch Laien schließen einander
nach heutigem Stand aus (Kernargument der LiquidFeedback-Autoren 2012; Maßstab
des VfGH-Erkenntnisses V 85-96/11 zu E-Voting; BVerfG 2 BvC 3/07 zur
Öffentlichkeit der Wahl). Die Satzung verlangt Nachrechenbarkeit ohne
Spezialkenntnisse (§ 5 Abs 8) und verbietet die personenbezogene
Veröffentlichung des Stimmverhaltens (§ 8 Abs 5).

## Entscheidung
Sachabstimmungen laufen pseudonym-offen: Veröffentlicht wird die vollständige
Stimmliste unter Pseudonymen plus Auszählungsskript; jedes Mitglied kann per
persönlichem Prüfcode die eigene Stimme in der Liste verifizieren. Die
Zuordnung Mensch↔Pseudonym liegt getrennt, zugriffsbeschränkt und auditiert
(Modell StimmRegister). Geheime Personenwahlen finden nicht online statt,
sondern per Präsenz/Brief (§ 13 Abs 3), bis Geheimheit und Laien-
Überprüfbarkeit vereinbar sind.

## Konsequenzen
+ Jedes Ergebnis ist von jedem nachrechenbar — das stärkste Vertrauensargument.
+ Ehrlich gegenüber dem Stand der Technik; keine Krypto-Versprechen.
− Der Betreiber der Datenbank KANN theoretisch Stimmen zuordnen. Gegenmaßnahmen:
  getrennte Tabelle, Zugriffs-Audit, Vier-Augen-Prinzip im Betrieb, öffentliche
  Benennung dieser Grenze. Wer mehr verspricht, verspricht zu viel.

## Nachtrag 29.9.2026 — Personenwahlen, die heute online laufen
Die Entscheidung sagt „Geheime Personenwahlen finden nicht online statt“. Seit
0.22 (1.9.2026) läuft die Listenreihung des Wahlvorschlags — die Zustimmungswahl
zu Mandats-Kandidaturen nach § 7 Abs 1 (F-70) — und seit 0.48 (16.9.2026) die
Vertrauensfrage nach § 7 Abs 10 auf der Plattform: beide sind Personenwahlen,
beide laufen **pseudonym-offen** über dasselbe Stimmregister wie Sachabstimmungen,
mit derselben Grenze wie oben (der Betreiber der Datenbank kann zuordnen). Sie
sind damit nicht geheim im Sinne dieses ADR; die Oberfläche sagt seit 0.50
„pseudonym“ statt „geheim“. Präsenz und Brief (§ 13 Abs 3) bleiben der Weg für
Wahlen, die geheim sein müssen — welche das sind, entscheidet die Satzung, nicht
diese Entscheidung.

Für die Vertrauensfrage hat die Satzung es bereits entschieden: **§ 7 Abs 10 lit e
— „Sie ist geheim“.** Die Online-Abstimmung der Vertrauensfrage läuft seit 0.48
pseudonym-offen und erfüllt das nicht. Das ist ein offener Widerspruch zwischen
Code und Satzung; ihn entscheidet der Gründer (Fahrtenbuch Teil D, D-L6h: Satzung
anpassen oder die Vertrauensfrage über Präsenz und Brief führen). Bis dahin läuft
sie unverändert wie beschrieben.

## Nachtrag 29.9.2026 (Prüfung 0.50.0) — Zugriffs-Audit
Das unter „Konsequenzen“ genannte Zugriffs-Audit auf die Zuordnung Pseudonym → Konto ist nicht
gebaut. Startseite, „Meine Stimme“ und Datenschutzerklärung versprechen es seit 0.50.0 nicht mehr;
die übrigen Gegenmaßnahmen (getrennte Tabelle, öffentliche Benennung der Grenze) gelten. Das Audit
ist ein Folgeschritt (Prüfbericht 0.50.0, Abschnitt 5).

## Nachtrag 29.9.2026 — Vertrauensfrage entschieden (D-L6h)
Der Gründer hat den Widerspruch zu § 7 Abs 10 lit e entschieden: „nein, wir sind transparent so
weit es geht.“ Die Vertrauensfrage bleibt eine pseudonym-offene Online-Abstimmung wie jede andere
nach diesem ADR; die Satzung wird an dieser Stelle angepasst (Satzungstexte ändert nur der Gründer,
nicht dieses Repository). Präsenz und Brief bleiben der Weg für Wahlen, die die Satzung weiter
geheim verlangt.
