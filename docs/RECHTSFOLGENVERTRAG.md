# Vorbereiteter Rechtsfolgen-Antwortvertrag

Der reine Vertrag `plattform_core.rechtsfolgen`, Fassung 1, ist noch nicht an
einen Modellaufruf, eine Warteschlange oder Bedienhandlung angeschlossen. Er
bereitet die Struktur des eigenen späteren Rechtsfolgenauftrags vor. Dieser
Stand ist keine S11-Abnahme oder neue Softwarefreigabe.

Die Antwort enthält genau `normen`, `judikatur`, `exekutive`, `personal`,
`unsicherheit` und `quellen`. Normen sind begrenzte Behauptungen mit Kennung,
Titel, Änderung und Begründung. Ihre Existenz, Betroffenheit oder juristische
Richtigkeit wird durch eine passende Form nicht bestätigt. Judikatur und
Exekutive haben je einen begrenzten Textabschnitt. Eine fehlerhafte Antwort
liefert keine als brauchbar ausgegebene Teilmenge.

Quellenreferenzen müssen aus dem tatsächlichen Angebot stammen, ohne Duplikate
und in dessen Reihenfolge. Erlaubte Referenzräume sind `norm:<id>`,
`personal_aggregat:<id>` und `personal_ressorts:<id>`. Diese formale Bindung sagt
nichts darüber aus, ob eine Quelle die Deutung tatsächlich trägt. Unbekannte
Normkennungen bleiben unbestätigte Behauptungen; daraus entsteht kein Link.

Der vorbereitete Personalrahmen belegt Bestände, keine Stellenfolgen. Deshalb
müssen `beamte_delta_min`, `beamte_delta_max`, `vb_delta_min` und `vb_delta_max`
in dieser ersten Vertragsfassung immer `null` sein. Auch die Zahl 0 wäre eine
unbelegte Nullbedarfsbehauptung. Nur angebotene Personalbereiche oder
`unbestimmt` dürfen referenziert werden. Es werden keine Mengen aus der Prosa
extrahiert oder Grafiken mit Scheinspannen erzeugt. Quantitative Abnahmen bleiben
offen, bis dafür eine tatsächlich belegte Grundlage besteht.

Technischer Verarbeitungsrahmen: höchstens 100000 Antwortzeichen, acht Normen,
sechzehn Personalbereiche und zweiundzwanzig angebotene Quellen. JSON muss ohne
Markdown, doppelte Schlüssel, nichtendliche Zahlen oder ungültiges UTF-8 lesbar
sein. Ergebnis nennt die Vertragsfassung und den Hash der unveränderten Antwort;
`inhaltlich_geprueft` bleibt stets `false`.
