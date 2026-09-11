# NEUE_TEXTE Cluster A1 — deutsche msgid → englischer Vorschlag

Format je Zeile: `msgid` → `msgstr`. Plural-Einträge mit `{% blocktranslate count %}` sind als Paar notiert.
Kontext in Klammern: Datei.

## Neu

- `Werkstatt` → `Workshop` (_leiste.html, Kurzform von „Zukunftswerkstatt“ zwischen 1024 und 1279 px; `Umsetzung` als Kurzform von „Umsetzungsregister“ ist im Katalog schon vorhanden)
- `Ausgesetzt seit %(seit)s durch Beschluss %(nummer)s des Integritätsrats — die Frist ruht (§ 6 Abs 3 lit d).` → `Suspended since %(seit)s by resolution %(nummer)s of the Integrity Council — the deadline is paused (§ 6 para 3 lit d).` (antrag.html)
- `Zum Beschluss` → `To the resolution` (antrag.html)
- `Zu den neuesten Beiträgen` → `To the newest posts` (_chat.html)
- `Zum Anfang der Reihung` → `To the top of the ranking` (_chat.html)
- `Einen älteren Beitrag zeigen` / `%(n)s ältere Beiträge zeigen` → `Show one older post` / `Show %(n)s older posts` (_chat_mehr.html)
- `Einen weiteren Beitrag zeigen` / `%(n)s weitere Beiträge zeigen` → `Show one more post` / `Show %(n)s more posts` (_chat_mehr.html)
- `Den Beitrag zeigen` / `Alle %(n)s Beiträge zeigen` → `Show the post` / `Show all %(n)s posts` (_zone_archiv.html)
- `— sie stehen auch oben im Chat` → `— they are also shown in the chat above` (_zone_archiv.html)

## Geändert

- `zurück mit Wünschen · höchstens 3 Runden` **entfällt**; neu: `zurück mit Wünschen · höchstens %(n)s Runden` → `back with requests · at most %(n)s rounds` (index.html, blocktranslate with n=fristen.runden)

## Unverändert, aber verschoben

- `Umsetzungsregister`, `Zukunftswerkstatt` stehen in _leiste.html jetzt zusätzlich als `title`-Attribut und in `<span class="lang">` — dieselben msgids.
