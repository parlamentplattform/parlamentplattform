# NEUE TEXTE Cluster D — bereits in `locale/en/LC_MESSAGES/django.po` eingetragen und kompiliert

Cluster D pflegt den Katalog selbst; diese Liste dient der Hauptarbeit nur zur Übersicht.

## Neue oder geänderte Nutzertexte aus Cluster-D-Dateien

- „An diesen Stellschrauben lernt das System: … Stellgrößen liest der Code von hier; fehlt ein Eintrag, gilt der
  eingebaute Zielwert. Einträge mit der Einheit „Regelfassung“ sind Versionsschilder einer Regel — sie beschreiben
  ihren Stand und stellen nichts ein. …" (parameter/liste.html, Befund #45)
  → „These are the dials the system learns at: … The code reads its settings from here; if an entry is missing,
  the built-in target value applies. Entries with the unit “Regelfassung” are version labels of a rule — they
  describe its state and set nothing. …"
- „Die Einträge dieser Seite liegen derzeit nur auf Deutsch vor; Überschriften und Erklärungen sind übersetzt."
  (rollen.html, regeln.html, liste.html, Befund #90)
  → „The entries on this page are currently available in German only; headings and explanations are translated."
- Stand der Rollenmatrix: „teilweise" → „partly", „geplant" → „planned" (rollen.py, Befund #90)
- Wirkungen des Regelverzeichnisses: „entscheidet" → „decides", „reiht" → „orders", „ordnet zu" → „assigns",
  „rechnet" → „calculates", „stellt dar" → „presents", je mit Erklärungssatz (regelwerk.py, Befund #90)
- Einheiten des Erstbestands: Einträge, Ereignisse, Gespräche, Minuten, Monate, Personen, Profile, Prozent,
  Regelfassung, Runden, Sekunden, Tage, Tokens, Tokens/Monat, Treffer, Zeichen, Äste → Entries, Events,
  Conversations, Minutes, Months, Persons, Profiles, Percent, Rule version, Rounds, Seconds, Days, Tokens,
  Tokens/month, Hits, Characters, Branches (parameter/models.py, Befund #90)

## Nachgetragene Einträge zu bestehenden Texten anderer Dateien (Befunde #60, #61, #62, #63, #88)

198 Einträge im Abschnitt „0.45: Koordinationsrat, Parameterverfahren, Räte, Export (Nachtrag Cluster D)"
am Ende der .po — Beschluss-, Aussetzungs-, Regelprüfungs- und Parametertest-Meldungen aus gremien/views.py,
die Vorlagen koordination.html, fenster.html, _beschluesse.html, integritaet_bericht.html, rat.html,
expertenrat.html, pruefung.html, _rollenband.html, umsetzung.html, parameter/bericht.html, parameter.html,
der Auslosungshinweis (antrag.html), der Fristring (_ring.html: „%(wert)s %% der Frist verstrichen"), das
Bot-Schutz-Bild (botschutz.py) und die zwölf Beschriftungen des Markdown-Exports (archiv.py).
Fünf `count`-Blöcke als Pluralpaare (msgid/msgid_plural): „Ein Test/%(n)s Tests", „Eine Änderung/%(n)s Änderungen",
„Eine aktive Rolle/%(n)s aktive Rollen", „Ein Vollzugsbericht zur Kenntnis/%(n)s Vollzugsberichte zur Kenntnis",
„noch ein Tag bis zur 30-Tage-Frist/noch %(t)s Tage bis zur 30-Tage-Frist".

## Vorgemerkt, noch ohne englische Fassung (Befund #90, Datenpflege)

Die langen Texte aus plattform_core/rollen.py (Rollen, Fähigkeiten, Wege hinein), plattform_core/regelwerk.py
(Titel, Zweck, Begründung, Nachrechnen, Lücke) und die Beschreibungen des ERSTBESTAND sind markiert und laufen
per `{% translate variable %}` durch den Katalog; ihre Übersetzung fehlt noch. `tests/test_katalog.py` listet sie
nicht als Fehlbestand (Präfix „vorgemerkt:"). Sobald sie eingetragen sind, den Seitenkopf-Hinweis entfernen.
