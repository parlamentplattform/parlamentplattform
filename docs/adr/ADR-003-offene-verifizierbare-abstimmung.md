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
