# Gegenüberstellung beim Einbringen: vorbereitete Verträge

Dieser Stand enthält noch keinen angeschlossenen Modellweg und keine neue
Bedienhandlung. Der bestehende Wort-/Vektorvergleich und die menschliche Wahl
bleiben unverändert. Die Vorbereitung ist keine Abnahme des gesamten Schritts.

Der private Rahmen `ki.vergleichskontext` Fassung 1 bindet das signierte Angebot
an Konto und vollständiges Formular. Nur die angebotenen öffentlichen aktuellen
Sachantragsfassungen werden gelesen. Geänderte Titel, Fassungen, fehlende Texte
oder inzwischen nicht mehr offene Anträge verlangen ein neues Angebot. Interne
Gremienentwürfe werden nicht gelesen. Titel und Wortlaute werden vollständig oder
gar nicht übernommen; die Gesamtgrenze wird nicht durch stilles Kürzen umgangen.

Die spätere Anbieterprojektion enthält nur den eigenen Titel/Wortlaut sowie
öffentliche Antrags-/Fassungsreferenzen, Titel, Wortlaute und Textprüfsummen.
Konto, E-Mail, Begründung, Gebiet und Vergleichsprozente werden nicht beigefügt.
Der Fingerabdruck normalisiert Formularzeilenenden wie der bestehende Prüfstand;
gespeicherte öffentliche Wortlaute bleiben genau erhalten. Spätere Nachlese
rekonstruiert denselben Input ohne aktuelle Datenbanktexte nachzuladen.

Ein signiertes Angebot für eine zufällige Anforderungskennung speichert selbst
noch keinen Entwurf. Erst eine ausdrückliche Anforderung darf später eine private
`Vergleichsanfrage` anlegen. Konto, Texte, Prüfsummen und Erstellzeit bleiben
über gewöhnliche ORM-Wege unveränderlich. Ein bedingtes UPDATE reserviert die
Kennung einmalig. Doppel-POST, Reload oder ein zurückgesetztes Statusfeld können
sie nicht erneut starten; begonnen_am bleibt maßgeblich. Ein Prozessabbruch löst
keine zeitgesteuerte zweite Anbieterausführung aus. Ein neuer Versuch benötigt
eine neue ausdrückliche Anforderung. Keine Provider- oder Budgetwirkung bisher.

Die additive Migration legt nur die neue Tabelle an. Der eigene Datenexport
enthält ausschließlich die eigenen privaten Anforderungen; öffentliche
Antragsarchive enthalten diese unveröffentlichten Texte nicht.

Der reine Antwortvertrag `plattform_core.gegenueberstellung` Fassung 1 prüft
genau die angebotenen IDs/Fassungen und ihre Reihenfolge, je einen begrenzten
Textteil für Gemeinsamkeit und Unterschied. Er erkennt keine juristische oder
inhaltliche Richtigkeit und ersetzt keine menschliche Entscheidung. Keine
Teilantwort wird bei fehlerhaften Paaren als brauchbar ausgegeben.
