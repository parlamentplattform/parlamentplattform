# NEUE_TEXTE_A2 — neue und geänderte Nutzertexte (deutsch → englischer Vorschlag)

Für Cluster D zum Nachziehen von `locale/en/LC_MESSAGES/django.po`. Bereits vorhandene msgids
(„Personenwahl", „Tendenz verdeckt bis Fristende", „Beteiligung", „Umsetzungsregister", „Parlament",
„Zugriff nicht möglich", „Zum Parlament", „Neu anmelden", „Zurück ins Parlament") sind nicht aufgeführt.

## uebersicht/templates/uebersicht/uebersicht.html (Befund #4, #13, #43, #71) — neu

- `%(abgegeben)s von %(berechtigte)s Stimmberechtigten` → `%(abgegeben)s of %(berechtigte)s eligible voters`
- `Gewählt: %(name)s mit %(n)s Zustimmungen` → `Elected: %(name)s with %(n)s approvals`
- `Keine Bewerbung gilt als gewählt.` → `No candidacy counts as elected.`
- Plural: `Eine ältere Entscheidung ist hier nicht mehr aufgeführt.` / `%(n)s ältere Entscheidungen sind hier nicht mehr aufgeführt.` → `One older decision is no longer listed here.` / `%(n)s older decisions are no longer listed here.`
- `Vollständig:` → `Complete list:`

## verfahren/views_aktionen.py (Befund #20, #26, #35, #53)

- geändert: `Ihre Beanstandung ist öffentlich vermerkt — die Zukunftswerkstatt rechnet den Punkt nach.` → neu: `Ihre Beanstandung ist öffentlich vermerkt und bleibt stehen. Ein Korrekturlauf der Zukunftswerkstatt ist noch nicht gebaut.` → `Your objection is publicly recorded and stays. A correction run by the Future Workshop is not built yet.`
- neu: `Ein Rückzug ist nur bis zum Beginn der Abstimmung möglich (§ 7 Abs 1).` → `Withdrawal is possible only until voting begins (§ 7 para. 1).`

## verfahren/templates/verfahren/_zone_einschaetzung.html (Befund #53)

- geändert: `Ihr Vermerk ist öffentlich und bleibt stehen; die Werkstatt rechnet den Punkt nach (§ 6 Abs 11 lit b).` → neu: `Ihr Vermerk ist öffentlich und bleibt stehen (§ 6 Abs 11 lit b). Ein Korrekturlauf der Werkstatt ist noch nicht gebaut.` → `Your note is public and stays (§ 6 para. 11 lit. b). A correction run by the Workshop is not built yet.`

## verfahren/templates/verfahren/zukunftswerkstatt.html (Befund #53, #56)

- geändert (Hinweis unter dem Ablauf): alt `Die Schritte 1 bis 3 und 5 bis 6 entsprechen dem Satzungsentwurf 2.5;\n  die Unterstützer-Schleife in Schritt 4 ist gebaut — für sie liegt ein eigener Satzungsbaustein zur Beschlussfassung vor.` → neu: `Alle sechs Schritte entsprechen dem Satzungsentwurf 2.5 (Schritt 4: § 5 Abs 12 und 13).\n  Geltend ist bis zum Beschluss der Mitglieder die Satzung 1.3.` → `All six steps follow draft statute 2.5 (step 4: § 5 paras. 12 and 13).\n  Until the members decide, statute 1.3 remains in force.`
- geändert (Absatz „Wer wacht worüber", nur das Ende des blocktranslate-Blocks): alt `… kann jede Einschätzung öffentlich beanstanden — die Antwort ist ein Korrekturlauf\n  mit Vermerk, nie ein stilles Ändern.` → neu `… kann jede Einschätzung öffentlich beanstanden; der Vermerk bleibt stehen. Die\n  Antwort darauf wird ein Korrekturlauf mit Vermerk sein, nie ein stilles Ändern — dieser Korrekturlauf ist noch\n  nicht gebaut.` → `… may publicly object to any assessment; the note stays. The answer will be a correction run with a note, never a silent change — that correction run is not built yet.` (Der übrige Absatz — Koordinationsrat, Integritätsrat, Expertenrat — ist unverändert; msgid als Ganzes neu aufnehmen.)

## verfahren/templates/403_csrf.html (Befund #47) — neu

- `Formular nicht angenommen` → `Form not accepted`
- `Das Formular kam nicht durch` → `The form did not get through`
- `Wahrscheinlich lag das Formular zu lange offen oder Sie haben sich inzwischen in einem anderen\nFenster neu angemeldet. Gehen Sie zurück, laden Sie die Seite neu und schicken Sie das Formular noch einmal ab —\neingegebene Texte gehen dabei leider verloren.` → `Most likely the form was open for too long, or you signed in again in another window in the meantime. Go back, reload the page and send the form once more — text you entered is unfortunately lost.`

## verfahren/templates/500.html (Befund #17, #52)

- geändert: alt `Der Fehler liegt bei uns, nicht bei Ihnen. Er ist protokolliert und wird angesehen.\nNichts von dem, was bereits abgestimmt oder eingebracht wurde, geht dabei verloren.` → neu `Der Fehler liegt bei uns, nicht bei Ihnen. Nichts von dem, was bereits abgestimmt oder\neingebracht wurde, geht dabei verloren.` → `The fault is ours, not yours. Nothing that has already been voted on or submitted is lost.`

## mandatare/templates/mandatare/liste.html (Befund #87)

- unverändert, aber jetzt nur noch unter `{% if kandidaturen %}`: `Ehrlich gesagt: Genau dafür bauen wir — und die Wahl unserer Kandidaten läuft bereits, hier auf der ParlamentPlattform (nicht im österreichischen Parlament: Die DDÖ reiht ihre eigenen Wahlvorschläge).` (msgid bleibt)
- neu: `Ehrlich gesagt: Genau dafür bauen wir. Die Kandidaten wählen die Mitglieder hier auf der ParlamentPlattform (nicht im österreichischen Parlament: Die DDÖ reiht ihre eigenen Wahlvorschläge) — derzeit läuft keine Kandidatur; jedes Mitglied kann eine einbringen.` → `Honestly: this is exactly what we are building for. The members elect the candidates here on the ParlamentPlattform (not in the Austrian parliament: the DDÖ ranks its own electoral lists) — no candidacy is running at the moment; any member can start one.`
