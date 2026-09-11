# Notizen — Cluster B (Mitglieder und Schutz)

Änderungsvorschläge für Dateien anderer Cluster, Abweichungen vom Vorschlag und Hinweise für die
Zusammenführung.

## Befund #1 — Sperre von Stimmabgabe und Registereinsicht während eines laufenden Adresswechsels

Datei: `verfahren/views_aktionen.py` (Cluster A2). `Mitglied.adresswechsel_offen` (mitglieder/models.py)
liefert `True`, solange ein `Adresswechsel` mit Status „offen" existiert. Vorschlag:

```python
# abstimmen(), nach der Stimmberechtigungsprüfung (Z. ~421) — und ebenso in kandidatur_zustimmen() (Z. ~675):
if request.user.adresswechsel_offen:
    messages.error(
        request,
        _("Für Ihr Konto läuft eine Änderung der Anmeldeadresse — bis sie entschieden ist, ruht die Stimmabgabe (F-51)."),
    )
    return redirect("verfahren:antrag", pk=pk)

# eigene_stimme(), nach dem Login-Check (Z. ~742):
if request.user.adresswechsel_offen:
    return render(request, "verfahren/eigene_stimme.html", {"antrag": antrag, "eintrag": None, "gesperrt": True})
```

In `verfahren/templates/verfahren/eigene_stimme.html` (A2) bei `gesperrt`: „Für Ihr Konto läuft eine Änderung
der Anmeldeadresse. Bis sie entschieden ist, zeigt die Plattform Ihren Registereintrag nicht an (F-51)."
Kein AuditEintrag in `eigene_stimme` (Beteiligungs-Leak im öffentlichen Log — so der Nachprüfer).

## Befund #1 — Registerschlüssel `adresswechsel-wartefrist-stunden`

`Adresswechsel.wartefrist_stunden()` liest `parameter.zahl("adresswechsel-wartefrist-stunden", 72)`.
Der Erstbestand steht in `parameter/models.py` (nicht Cluster B). Vorschlag für ERSTBESTAND:

```python
{
    "schluessel": "adresswechsel-wartefrist-stunden",
    "wert": "72",
    "einheit": "Stunden",
    "gruppe": "schutz",
    "beschreibung": "Wie lange eine verwaltungsseitige Änderung der Anmeldeadresse wartet, bevor sie "
    "wirksam wird. In dieser Zeit kann die bisherige Adresse widersprechen; zusätzlich braucht es "
    "einen zweiten Admin. Der Login läuft passwortlos über die Adresse — ohne Frist wäre eine "
    "Änderung eine Kontoübernahme.",
    "quelle": "§ 5 Abs 3 · F-51",
},
```

Ohne Eintrag gilt der eingebaute Zielwert 72 (ehrlicher Rückfall von `zahl`).

## Befund #55 — über den Vorschlag hinaus

Die Karte „Die Zukunftswerkstatt" weiter unten auf mitgliedschaft.html behauptete dasselbe wie Station 3
(„Zu jedem Antrag liefert die Zukunftswerkstatt … eine mit amtlichen Quellen belegte Einschätzung"). Sie ist
jetzt als Zielbild gekennzeichnet („soll … liefern", Verweis auf den Stand der Werkstatt-Seite) — Regel 3
(öffentliche Texte müssen wahr sein), nicht Teil des Nachprüfer-Vorschlags, deshalb hier vermerkt.

## Befunde #19/#66 — Einstellung und Deploy (Cluster D: config/settings.py, render.yaml, docs)

`mitglieder/botschutz.klienten_ip` liest `getattr(settings, "DDOE_CLIENT_IP_KOPFZEILE", "")`; X-Forwarded-For
wird nie mehr gelesen. Vorschlag für `config/settings.py` (neben DDOE_FIX_ADMIN):

```python
# F-49/F-52: Welche Kopfzeile die Adresse der Verbindung trägt, wenn ein vertrauenswürdiger Proxy
# davorsteht — in META-Schreibweise, einwertig (Render hinter Cloudflare: HTTP_CF_CONNECTING_IP).
# Unbesetzt zählt ausschließlich REMOTE_ADDR; X-Forwarded-For wird nie gelesen, weil sein erster
# Eintrag vom Client frei wählbar ist und Cloudflare wie Render nur anhängen.
DDOE_CLIENT_IP_KOPFZEILE = os.environ.get("DDOE_CLIENT_IP_KOPFZEILE", "")
```

`render.yaml` (envVars): `- key: DDOE_CLIENT_IP_KOPFZEILE` / `value: HTTP_CF_CONNECTING_IP`.
Vor dem Scharfstellen einmalig prüfen, dass Render die Kopfzeile durchreicht (der Nachprüfer belegt es über
den arcjet-Faden; ein Blick ins Serverlog mit `request.META.get("HTTP_CF_CONNECTING_IP")` genügt). Die
Partner-Anleitung (`docs/partner/instanz/`) sollte den Schlüssel erwähnen: ohne Proxy leer lassen.

Drossel-Zähler: Statt Django-DatabaseCache (bräuchte CACHES in settings.py und `createcachetable` im
dockerCommand) ein eigenes Modell `mitglieder.Drosselzaehler` (Migration 0013) — ebenfalls in der Datenbank,
also über Worker und Neustarts hinweg, aber ohne Eingriff in Dateien anderer Cluster und ohne zusätzlichen
Deploy-Schritt. Zeilen älter als zwei Stunden räumt `drossel_zuviel` selbst ab (keine Verfahrensdaten).

Botschutz-Aufgaben liegen jetzt in der Sitzung (Befund #68) — Gäste, die ein Formular öffnen, erzeugen eine
Sitzungszeile. Deshalb (auch für Befund #67) in `render.yaml` in die dockerCommand-Kette vor gunicorn:
`&& python manage.py clearsessions`. Das räumt nur abgelaufene Sitzungen (Standard 14 Tage).
