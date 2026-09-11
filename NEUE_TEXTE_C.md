# NEUE TEXTE Cluster C — für `locale/en/LC_MESSAGES/django.po` (Cluster D)

Je Zeile: deutsche msgid → englischer Vorschlag. Quelle in Klammern.

## Befund #14/#37 (gremien/templates/gremien/fachliste.html, gremien/views.py)

- blocktranslate (fachliste.html, ersetzt die bisherige msgid „Eine Gruppe des Expertenrats hat mindestens %(m)s Mitglieder (§ 6 Abs 8); für einen Antrag mit Vollzugs- oder Beschaffungsbezug werden zwei unabhängige Gruppen gezogen.“):
  „Eine Gruppe des Expertenrats hat mindestens %(m)s Mitglieder (§ 6 Abs 8); stellt Gruppe 1 einen Vollzugs- oder Beschaffungsbezug fest, wird eine zweite, unabhängig besetzte Gruppe nachgelost.“
  → "A group of the expert council has at least %(m)s members (§ 6 para 8); if group 1 finds an enforcement or procurement aspect, a second, independently staffed group is drawn afterwards."
- gettext (gremien/views.py, fenster_aktion „vollzugsbezug“):
  „Gruppe 2 wurde für diesen Antrag aus der Fachliste gelost.“
  → "Group 2 has been drawn from the expert register for this motion."

## Befund #31 (gremien/views.py, integritaet_beschluss)

- gettext: „Aussetzen lässt sich nur eine laufende Abstimmung oder der Vollzug eines Beschlusses (§ 6 Abs 3 lit d).“
  → "Only a running vote or the implementation of a resolution can be suspended (§ 6 para 3 lit d)."

## Befund #64 — Auswahl-Beschriftungen (gettext_lazy in den Modellen)

gremien/models.py:
- „Expertenrat — Gruppe 1 (Entwurf)“ → "Expert council — group 1 (drafting)"
- „Expertenrat — Gruppe 2 (Prüfung)“ → "Expert council — group 2 (review)"
- „Koordinationsrat“ → (schon im Katalog) · „Integritätsrat“ → (schon im Katalog)
- „Integrations- und Berichtswesenrat“ → "Integration and reporting council"
- „Technischer Entwicklungsrat“ → "Technical development council"
- „innere Angelegenheit des Rates“ → "internal matter of the council"
- „Prüfung eines Vorschlags (§ 6 Abs 7)“ → "Review of a proposal (§ 6 para 7)"
- „Hervorhebung eines Antrags (§ 5 Abs 10 lit b)“ → "Highlighting a motion (§ 5 para 10 lit b)"
- „Hervorhebung aufheben (§ 5 Abs 10 lit b)“ → "Remove highlighting (§ 5 para 10 lit b)"
- „Zurückweisung eines Antrags (§ 5 Abs 2)“ → "Rejection of a motion (§ 5 para 2)"
- „Zurückweisung aufheben (§ 5 Abs 2)“ → "Revoke rejection (§ 5 para 2)"
- „Abstimmung oder Vollzug aussetzen (§ 6 Abs 3 lit d)“ → "Suspend a vote or an implementation (§ 6 para 3 lit d)"
- „Aussetzung aufheben (§ 6 Abs 3 lit d)“ → "Lift suspension (§ 6 para 3 lit d)"
- „Jährliche Prüfung der automatisierten Regeln (§ 2 Abs 6)“ → "Annual review of the automated rules (§ 2 para 6)"
- „Einreichung eines Vorschlags (§ 5 Abs 12)“ → "Submission of a proposal (§ 5 para 12)"
- „Austausch der Gruppe 1 (§ 6 Abs 7)“ → "Replacement of group 1 (§ 6 para 7)"
- „Hervorhebung beim Integritätsrat beantragen (§ 5 Abs 10 lit b)“ → "Request highlighting from the integrity council (§ 5 para 10 lit b)"
- „Vorschlag zu einer Überlastungsmeldung (§ 6 Abs 10)“ → "Proposal on an overload report (§ 6 para 10)"
- „Test eines Registerwerts anordnen (§ 6 Abs 11 lit c)“ → "Order a test of a register value (§ 6 para 11 lit c)"
- „Einführung eines Registerwerts (§ 6 Abs 11 lit c)“ → "Adoption of a register value (§ 6 para 11 lit c)"
- „offen“ → (schon im Katalog: "open") · „entschieden“ → "decided" · „ohne Ergebnis (Frist abgelaufen)“ → "no result (deadline passed)"
- „laufende Abstimmung“ → "running vote" · „Vollzug eines Beschlusses“ → "implementation of a resolution"
- „geprüft, keine Beanstandung“ → "reviewed, no objection" · „beanstandet“ → "objected"
- „Auswertung eines Parametertests“ → "Evaluation of a parameter test" · „Kandidat für Hervorhebung“ → "Candidate for highlighting" · „Muster-Bericht“ → "Pattern report" · „Lastwarnung“ → "Load warning"
- „Beschluss angelegt“ → "Resolution created" · „verworfen“ → "discarded" · „zur Kenntnis genommen“ → "noted"
- „stattgegeben“ → "granted" · „abgelehnt“ → "refused" · „keine Entscheidung binnen der Frist“ → "no decision within the deadline"

verfahren/models.py:
- „Beleidigung oder Herabwürdigung“ → "Insult or degradation" · „Nachweislich falsche Tatsachenbehauptung“ → "Demonstrably false statement of fact" · „Kein Bezug zum Antrag“ → "Unrelated to the motion" · „Rechtswidriger Inhalt“ → "Unlawful content" · „Sonstiges“ → "Other"
- „in Umsetzung“ → "in implementation" · „blockiert“ → "blocked" · „umgesetzt“ → "implemented" · „zurückgestellt“ → "deferred"
- „Zustimmung“ → "Approval" · „Ablehnung“ → "Disapproval"

ki/models.py: „Einschätzung für die Gremien-Werkstatt“ → "Assessment for the council workshop" · „Vorschlag der Zukunftswerkstatt zu einem Parametertest“ → "Future workshop proposal for a parameter test"
parameter/models.py: „gültig“ → "in force" · „im Test“ → "under test" · „vorgeschlagen“ → "proposed"
mandatare/models.py: „laufend“ → "in progress" · „erledigt“ → "done"
gremien/templates/gremien/integritaet.html (`{% translate name %}` der IR_ANLAESSE): „Antrag hervorheben“ → "Highlight motion" · „Hervorhebung aufheben“ → "Remove highlighting" · „Antrag zurückweisen“ → "Reject motion" · „Zurückweisung aufheben“ → "Revoke rejection" · „Aussetzen“ → "Suspend" · „Aussetzung aufheben“ → "Lift suspension"

Noch nicht umhüllt (siehe NOTIZEN, Abhängigkeit A1 `archiv.py`), msgids für später:
- „Bund“ → "Federal level" · „Sachantrag“ → "Substantive motion" · „Mandats-Kandidatur“ → "Candidacy for a mandate"
- „in Arbeit (Expertenrat)“ → "in progress (expert council)" · „in Prüfung (Gruppe 2)“ → "under review (group 2)" · „liegt den Unterstützern vor“ → "before the supporters" · „zur Endabstimmung übergeben“ → "handed over to the final vote"
- „validiert“ → "validated" · „mit Begründung zurückgegeben“ → "returned with reasons" · „Austausch bei Gruppe 1 beantragt“ → "replacement of group 1 requested"
