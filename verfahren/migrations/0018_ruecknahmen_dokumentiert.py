"""Rücknahmen bleiben als Zeile stehen (Befund #27, Grundregel 7).

Eine zurückgenommene Personenwahl-Zustimmung wurde bis 0.44 hart gelöscht, und das Audit trug
für beide Richtungen denselben Typ — aus Datenbank und Audit war nicht mehr rekonstruierbar, ob
ein Pseudonym zugestimmt oder zurückgenommen hatte. Jetzt trägt die Zeile einen Stempel
(`zurueckgenommen_am`) und zählt nicht mehr. Für Unterstützungen bekommt die Zeile denselben
Stempel (`zurueckgezogen_am`); die Umstellung des Rückzugs vom Löschen auf den Stempel liegt in
der Ansicht (siehe NOTIZEN_C.md). Beide Felder sind leer für alles Bestehende — nichts ändert sich
rückwirkend.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("verfahren", "0017_antrag_stimmberechtigung_stichtag")]

    operations = [
        migrations.AddField(
            model_name="bewerbungszustimmung",
            name="zurueckgenommen_am",
            field=models.DateTimeField(
                blank=True,
                help_text="Gesetzt, wenn die Zustimmung zurückgenommen wurde — Stimmdaten werden nie gelöscht "
                "(Grundregel 7); gezählt wird sie dann nicht mehr.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="unterstuetzung",
            name="zurueckgezogen_am",
            field=models.DateTimeField(
                blank=True,
                help_text="Gesetzt, wenn die Unterstützung zurückgezogen wurde — die Zeile bleibt, gezählt wird sie nicht mehr.",
                null=True,
            ),
        ),
    ]
