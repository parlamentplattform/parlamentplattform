# NEUE TEXTE Cluster C — für `locale/en/LC_MESSAGES/django.po` (Cluster D)

Je Zeile: deutsche msgid → englischer Vorschlag. Quelle in Klammern.

## Befund #14/#37 (gremien/templates/gremien/fachliste.html, gremien/views.py)

- blocktranslate (fachliste.html, ersetzt die bisherige msgid „Eine Gruppe des Expertenrats hat mindestens %(m)s Mitglieder (§ 6 Abs 8); für einen Antrag mit Vollzugs- oder Beschaffungsbezug werden zwei unabhängige Gruppen gezogen.“):
  „Eine Gruppe des Expertenrats hat mindestens %(m)s Mitglieder (§ 6 Abs 8); stellt Gruppe 1 einen Vollzugs- oder Beschaffungsbezug fest, wird eine zweite, unabhängig besetzte Gruppe nachgelost.“
  → "A group of the expert council has at least %(m)s members (§ 6 para 8); if group 1 finds an enforcement or procurement aspect, a second, independently staffed group is drawn afterwards."
- gettext (gremien/views.py, fenster_aktion „vollzugsbezug“):
  „Gruppe 2 wurde für diesen Antrag aus der Fachliste gelost.“
  → "Group 2 has been drawn from the expert register for this motion."
