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
