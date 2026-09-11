# Neue und geänderte Nutzertexte — Cluster B (Mitglieder und Schutz)

Je Zeile: deutsche msgid → englischer Vorschlag. Die .po pflegt Cluster D.
Bei `blocktranslate`-Blöcken steht der Wortlaut so, wie er im Template steht (Zeilenumbrüche des
Templates werden von makemessages zusammengezogen).

## Befunde #1/#2 — Adresswechsel (mitglieder/verwaltung.py, verwaltung_mitglied.html, adresswechsel_einspruch.html)

- „Vorname" → "First name" (Label, jetzt gettext_lazy — bereits im Katalog aus mitglieder/views.py)
- „Nachname" → "Last name" (bereits im Katalog)
- „E-Mail-Adresse" → "Email address" (bereits im Katalog)
- „Öffentlicher Anzeigename (leer = Klarname)" → "Public display name (empty = real name)"
- „Wohnsitz-Gemeinde (leer = keine Angabe)" → "Municipality of residence (empty = not stated)"
- „Identitätsstufe" → "Identity level"
- „Letzter Beitragseingang" → "Last contribution received"
- „Die Adresse des satzungsgebenden Erstzugangs wird hier nicht geändert (F-51)." → "The address of the founding administrator account cannot be changed here (F-51)."
- „Diese Adresse ist dem satzungsgebenden Erstzugang vorbehalten (F-51)." → "This address is reserved for the founding administrator account (F-51)."
- „Diese Adresse gehört bereits zu einem anderen Konto." → "This address already belongs to another account."
- „Für dieses Konto läuft bereits eine Adressänderung — zuerst abbrechen oder abwarten." → "An address change is already pending for this account — cancel it first or wait for it to complete."
- „Mehrdeutig — bitte präzisieren: %(optionen)s." → "Ambiguous — please be more specific: %(optionen)s."
- „Steht nicht im amtlichen Gemeindeverzeichnis." → "Not listed in the official register of municipalities."
- „Ihre Anmeldeadresse soll geändert werden — ParlamentPlattform" → "Your login address is about to be changed — ParlamentPlattform"
- Mailtext: „Guten Tag,\n\ndie Verwaltung hat beantragt, die Anmeldeadresse Ihres Kontos auf eine andere E-Mail-Adresse zu ändern. Wirksam wird das frühestens am %(frist)s und nur, wenn ein zweiter Admin die Änderung bestätigt.\n\nWenn Sie das NICHT veranlasst haben, widersprechen Sie bitte mit diesem Link — die Änderung wird dann verworfen:\n\n%(link)s\n\nBis dahin bleibt diese Adresse Ihre Anmeldeadresse.\n\nDirekte Demokratie Österreich — Wir sind das Werkzeug." → "Hello,\n\nthe administration has requested to change the login address of your account to a different email address. This will take effect no earlier than %(frist)s and only if a second administrator confirms it.\n\nIf you did NOT request this, please object using this link — the change will then be discarded:\n\n%(link)s\n\nUntil then, this address remains your login address.\n\nDirekte Demokratie Österreich — We are the tool."
- „Die Adressänderung wurde nicht vorgemerkt: Die Nachricht an die bisherige Adresse ließ sich nicht versenden." → "The address change was not recorded: the notification to the current address could not be sent."
- „Adressänderung vorgemerkt: Die bisherige Adresse wurde benachrichtigt; wirksam wird sie frühestens am %(frist)s, sobald ein zweiter Admin bestätigt hat." → "Address change recorded: the current address has been notified; it takes effect no earlier than %(frist)s, once a second administrator has confirmed."
- „Stammdaten gespeichert." → "Master data saved."
- „Keine Änderungen." → "No changes."
- „Für dieses Konto läuft keine Adressänderung." → "No address change is pending for this account."
- „Bestätigt. Nach Ablauf der Frist wird die neue Adresse zur Anmeldeadresse — sofern kein Einspruch kommt." → "Confirmed. Once the waiting period has passed, the new address becomes the login address — unless an objection is raised."
- „Die Bestätigung braucht einen zweiten Admin — nicht den, der die Änderung beantragt hat." → "Confirmation requires a second administrator — not the one who requested the change."
- „Adressänderung abgebrochen — die bisherige Adresse bleibt." → "Address change cancelled — the current address remains."
- „Der satzungsgebende Erstzugang ist unantastbar (F-51)." → "The founding administrator account is untouchable (F-51)."
- „Diese Aktion können nur andere Admins auf Ihr Konto anwenden." → "Only other administrators can apply this action to your account."
- „Bitte eine Begründung angeben — sie wird im Audit-Log veröffentlicht." → "Please give a reason — it will be published in the audit log."
- „Mitgliedschaft pausiert — Mitwirkungsrechte ruhen bis zum Beitragseingang." → "Membership paused — participation rights are suspended until the contribution is received."
- „Mitglied ausgeschlossen und Konto deaktiviert." → "Member excluded and account deactivated."
- „Mitgliedschaft ist wieder aktiv." → "Membership is active again."
- „Beitragseingang vermerkt — die Pause ist damit aufgehoben." → "Contribution recorded — the pause is lifted."
- „Beitragseingang vermerkt." → "Contribution recorded."
- „%(name)s hat jetzt Zugang zur Verwaltung." → "%(name)s now has access to the administration."
- „Adminrechte entzogen." → "Administrator rights revoked."
- „Unbekannte Aktion." → "Unknown action."
- „Adressänderung vorgemerkt" → "Address change pending"
- „Neue Anmeldeadresse <strong>%(neu)s</strong> — beantragt am %(seit)s, Einspruchsfrist bis %(frist)s. Bis dahin bleibt die bisherige Adresse Anmeldeadresse; die bisherige Adresse wurde mit Einspruchslink benachrichtigt." → "New login address <strong>%(neu)s</strong> — requested on %(seit)s, objection period until %(frist)s. Until then the current address remains the login address; it has been notified with an objection link."
- „Bestätigt von Admin #%(pk)s — wird nach der Frist wirksam." → "Confirmed by administrator #%(pk)s — takes effect after the waiting period."
- „Noch nicht von einem zweiten Admin bestätigt." → "Not yet confirmed by a second administrator."
- „Als zweiter Admin bestätigen" → "Confirm as second administrator"
- „Adressänderung abbrechen" → "Cancel address change"
- „Bezirk und Bundesland folgen automatisch dem Gemeindeverzeichnis. Die Änderung wird (ohne Werte) im Audit-Log vermerkt. Eine neue E-Mail-Adresse wird nicht sofort wirksam: Die bisherige Adresse erhält einen Einspruchslink, danach braucht es die Frist und einen zweiten Admin." → "District and federal state follow the register of municipalities automatically. The change is recorded (without values) in the audit log. A new email address does not take effect immediately: the current address receives an objection link, after which the waiting period and a second administrator are required." (geändert; alte msgid „Bezirk und Bundesland folgen automatisch dem Gemeindeverzeichnis. Die Änderung wird (ohne Werte) im Audit-Log vermerkt." entfällt)
- „Änderung der Anmeldeadresse" → "Change of login address"
- „Änderung Ihrer Anmeldeadresse" → "Change of your login address"
- „Die Verwaltung hat beantragt, die Anmeldeadresse Ihres Kontos zu ändern. Wenn Sie das nicht veranlasst haben, verwerfen Sie die Änderung hier — Ihre bisherige Adresse bleibt dann Ihre Anmeldeadresse." → "The administration has requested to change the login address of your account. If you did not request this, discard the change here — your current address will then remain your login address."
- „Änderung verwerfen — meine Adresse bleibt" → "Discard change — keep my address"
- „Haben Sie die Änderung selbst gewünscht, müssen Sie nichts tun: Sie wird nach Ablauf der Frist wirksam, sobald ein zweiter Admin sie bestätigt hat." → "If you requested the change yourself, no action is needed: it takes effect after the waiting period, once a second administrator has confirmed it."
- „Die Änderung ist verworfen." → "The change has been discarded."
- „Ihre bisherige Adresse bleibt Ihre Anmeldeadresse. Der Vorgang steht ohne Adresswerte im öffentlichen Audit-Log." → "Your current address remains your login address. The event is recorded in the public audit log without address values."
- „Diese Änderung ist bereits wirksam. Wenn Sie sie nicht veranlasst haben, schreiben Sie bitte umgehend an didide@ddoe.at." → "This change has already taken effect. If you did not request it, please write to didide@ddoe.at immediately."

## Befunde #15/#51/#55 — mitgliedschaft.html (geänderte blocktranslate-Blöcke)

- „Mindestens 21 Tage öffentliche Erörterung; der Expertenrat erarbeitet einen Vorschlag, den die Unterstützer annehmen oder zurückgeben. Die Durchrechnung in der <a href="/zukunftswerkstatt/">Zukunftswerkstatt</a> (berührte Gesetze, Aufwand) ist im Aufbau — wie weit, steht auf der Werkstatt-Seite." → "At least 21 days of public deliberation; the expert council prepares a proposal, which the supporters accept or return. The analysis in the <a href="/zukunftswerkstatt/">Future Workshop</a> (affected laws, effort) is under construction — how far along, see the workshop page." (ersetzt die msgid „Mindestens 21 Tage öffentliche Erörterung. Die <a href=…>Zukunftswerkstatt</a> rechnet durch, …")
- „Heute: ein Konto je E-Mail-Adresse, Bestätigungslink, Beitragseingang schaltet die Mitwirkung frei. Der Identitätsnachweis nach § 2 Abs 4 (ID Austria oder Präsenzstelle) ist geplant — bis dahin ist die Ein-Mensch-eine-Stimme-Regel eine Frage des Vertrauens. Öffentlich treten Sie unter einem beständigen Pseudonym auf, wenn Sie möchten; Ihre Stimme bleibt bei Abstimmungen pseudonym." → "Today: one account per email address, confirmation link, a received contribution unlocks participation. Identity verification under § 2 (4) (ID Austria or in-person office) is planned — until then the one-person-one-vote rule is a matter of trust. Publicly you may appear under a persistent pseudonym if you wish; your vote remains pseudonymous in ballots." (ersetzt „Ein Konto je Person, mit geprüfter Identität — das schützt vor gekauften Mehrheiten. …")
- „Regionale Anträge sind nach Gemeinde, Bezirk und Land sortiert und erscheinen in Ihrem Bereich „Meine Region“. Abstimmen dürfen bei jedem Antrag alle stimmberechtigten Mitglieder — die Satzung schließt niemanden von einer Abstimmung aus (§ 5 Abs 6). Ob Betroffene bei Sachfragen besonders berücksichtigt werden, entscheidet eine Verfahrensordnung, die die Mitglieder erst beschließen müssen. Ihre Lebensbereiche wählen Sie als Favoriten — Neues daraus erscheint direkt in Ihrem Parlament." → "Regional motions are sorted by municipality, district and state and appear in your “My region” area. On every motion, all eligible members may vote — the statutes exclude no one from a ballot (§ 5 (6)). Whether those affected receive special consideration on substantive questions is decided by rules of procedure the members have yet to adopt. You choose your areas of life as favourites — new items from them appear directly in your parliament." (ersetzt „Regionale Anträge entscheidet, wen sie betreffen: …")
- „Zielbild: Zu jedem Antrag soll die Zukunftswerkstatt — mit der StaatsSimulation als Rechenkern — eine mit amtlichen Quellen belegte Einschätzung liefern: berührte Gesetze, Aufwand für den Staatsapparat, Ausschreibungspflichten, realistische Dauer. Sie berät alle und entscheidet nie — Entscheidungen treffen die Mitglieder. Wie weit der Aufbau ist, steht auf der Werkstatt-Seite." → "Target: for every motion, the Future Workshop — with the StaatsSimulation as its computational core — is to deliver an assessment backed by official sources: affected laws, effort for the state apparatus, procurement obligations, realistic duration. It advises everyone and never decides — decisions are made by the members. How far along the build is, see the workshop page." (ersetzt „Zu jedem Antrag liefert die Zukunftswerkstatt — …")
