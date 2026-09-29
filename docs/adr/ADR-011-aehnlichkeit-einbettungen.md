# ADR-011: Ähnlichkeit Stufe 2 über Anbieter-Einbettungen am Modell-Steckplatz

Status: angenommen zur Umsetzung der Gründeranweisung vom 28.9.2026 („Wenn ich zwei
verschiedene Anträge eingebe wird auch bei keiner inhaltlichen Übereinstimmung eine
Übereinstimmung angezeigt. Diese Funktion muss besser werden. Wird das über Mistral gemacht?“).
Fahrtenbuch FB-H2, ergänzt ADR-006.

## Ausgangslage

Die Ähnlichkeitsprüfung beim Einbringen (§ 5 Abs 10 lit d) verglich Dreizeichenfolgen mit dem
Jaccard-Koeffizienten (`plattform_core/similarity.py`, Fassung 1). Sie zählte die Floskeln mit,
die fast jeder Antrag trägt — „Die Bundesregierung wird aufgefordert, dem Nationalrat einen
Gesetzesentwurf vorzulegen“ —, und meldete für zwei Anträge ohne jede inhaltliche Nähe
(Holzschneidebretter in der Gastronomie; Börsennotierung von Rüstungs- und Pharmaunternehmen)
29 Prozent Übereinstimmung bei einer Schwelle von 18.

## Entscheidung

Zwei Stufen, beide gekennzeichnet, keine entscheidet:

1. **Stufe 1b — Wortvergleich, ohne Modell** (`similarity.py`, Fassung 2): Stoppwörter und
   Antragsfloskeln fallen weg, Wörter werden auf eine einfache Stammform gekürzt, Titelwörter
   zählen doppelt; der Wert ist zu zwei Dritteln der gewichtete Jaccard der Wortmengen und zu
   einem Drittel der Jaccard der Wortpaare. Schwelle 30 Prozent (Register
   `aehnlichkeit-schwelle-prozent`). Mit Papier und Bleistift nachrechenbar; das Regelverzeichnis
   trägt die Fassung.
2. **Stufe 2 — Bedeutung über den Modell-Steckplatz**: Textvektoren („Embeddings“) des
   eingestellten Anbieters (`ki/anbieter.py`, `einbetten`; für Mistral `POST /v1/embeddings`,
   Modell aus `DDOE_KI_EINBETTUNGSMODELL`, Standard `mistral-embed`; die Attrappe liefert
   deterministische Vektoren für Tests). Der Vektor je Antragsfassung liegt in
   `verfahren.AntragsEinbettung`; die Nähe ist der Kosinus (`similarity.kosinus`), Schwelle 78
   Prozent (`aehnlichkeit-bedeutung-schwelle-prozent`). Beim Einbringen genügt **ein** Aufruf: der
   neue Text plus höchstens `aehnlichkeit-einbettungen-je-aufruf` offene Anträge ohne Vektor. Der
   Vektor des neuen Antrags wird gespeichert, ohne zweiten Aufruf; nach „Trotzdem einbringen“
   holt ihn die Warteschlange nach. Jeder Aufruf läuft über `ki.models.einbettung_ausfuehren`
   (Budget, Archiv, Fehlerpfad) — Zweck `aehnlichkeit` im Lauf-Archiv.

Treffer sind die Vereinigung beider Stufen, sortiert nach dem höheren Wert; die Karte zeigt
beide Werte („Wortvergleich 31 % · Bedeutung 72 %“), den Modellnamen und „Vorschlag, keine
Hürde“. Ohne Anbieter, bei erschöpftem Budget oder Anbieterfehler fällt die Prüfung still auf den
Wortvergleich zurück und sagt das in der Karte.

## Alternativen

- **Lokales Modell mit `sentence-transformers`** (etwa `multilingual-e5-small`, CPU): kein Text
  verlässt die Plattform, aber eine neue Abhängigkeit mit PyTorch (> 500 MB) auf einem
  Render-Dienst mit 512 MB Arbeitsspeicher; der Web-Worker würde beim Laden des Modells den
  Speicher sprengen oder eine eigene Instanz brauchen. Verworfen für den Alpha-Betrieb; bleibt
  die Option, sobald die Plattform auf eigener Infrastruktur läuft (dann nur der Anbieter im
  Steckplatz wechselt — die Schnittstelle `einbetten(texte)` bleibt).
- **Anbieter-Einbettung über den Steckplatz** (gewählt): Titel und Wortlaut verlassen die
  Plattform an den eingestellten Anbieter. Bei den laufenden Anträgen sind sie öffentlich (§ 5 Abs 3);
  beim neuen Text ist es der Entwurf, noch vor der Einbringung — also vor der Veröffentlichung,
  auch wenn das Mitglied nach dem Hinweis nicht einbringt. Begründung, Chat und Personenbezug werden
  nicht übertragen. Kein neues Paket, keine neue Instanz.
- **Nur Stufe 1b**: reicht gegen Floskel-Treffer, erkennt aber keine Umformulierung mit anderen
  Wörtern. Bleibt als Rückfall und Zweitmeinung.

## Folgen

- Text verlässt die Plattform nur an den Anbieter, der im Steckplatz eingestellt ist: Titel und
  Wortlaut der laufenden Anträge und — beim Absenden auf „Antrag einbringen“ — Titel und Wortlaut
  des Entwurfs, bevor er veröffentlicht ist. Der Lauf steht mit dem Entwurf und dem anfordernden
  Konto im Lauf-Archiv (`KILauf.eingabe`, append-only), auch wenn der Antrag nie eingebracht wird.
  Datenschutzerklärung und Einbringen-Seite sagen das, sobald ein Anbieter angeschlossen ist
  (Entscheidung des Gründers vom 29.9.2026: das Verhalten bleibt, die Texte werden ehrlich).
- Budget: `mistral-embed` rechnet rund 1 Token je 4 Zeichen; ein Einbringen mit 20 nachgezogenen
  Anträgen à 2 000 Zeichen kostet ~10 000 Tokens am Monatsbudget (`ki-monatstokens`). Der Vektor
  je Fassung wird einmal gerechnet; ein Modellwechsel rechnet neu (anderer Schlüssel), alte Zeilen
  bleiben stehen.
- Die Warteschlange (`ki/warteschlange.py`, Tageskontingent `ki-tageslaeufe`) trägt neben den
  betroffenen Gesetzen auch das Nachziehen von Vektoren.
- Grundregel 5 bleibt: Der Bedeutungswert ist ein Vorschlag mit Modellnamen. Er blockiert nicht,
  reiht nichts außerhalb der Karte und schreibt in keine Faktenbasis.
