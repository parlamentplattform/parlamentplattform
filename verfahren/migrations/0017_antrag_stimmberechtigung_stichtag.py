"""Der Stichtag der Stimmberechtigung wird am Antrag gespeichert (Befund #32).

Bis 0.44 bildete jede Stelle den Stichtag selbst aus `phase_beginn.date()` — dem UTC-Datum.
Zwischen 0 und 2 Uhr Wiener Zeit lag er damit einen Tag vor dem Abstimmungsbeginn, den die
Seite zeigte. Jetzt wird der Wiener Kalendertag beim Übergang in die Abstimmung festgestellt und
gespeichert; Zählung und Einzelprüfung lesen dieselbe Zahl (§ 4 Abs 4 lit a).

Für Anträge, die gerade abgestimmt werden, wird der Tag nachgetragen, mit dem damals wirklich
gezählt wurde — das UTC-Datum des Phasenbeginns. Ihn nachträglich auf den Wiener Tag zu setzen,
änderte die veröffentlichte Feststellung („danach nie mehr verändert“). Abgeschlossene Verfahren
bleiben leer; für sie liest `stichtag_der_stimmberechtigung()` den Rückfall.
"""

from django.db import migrations, models


def nachtragen(apps, schema_editor):
    Antrag = apps.get_model("verfahren", "Antrag")
    for antrag in Antrag.objects.filter(
        phase="abstimmung", stimmberechtigte_anzahl__isnull=False, stimmberechtigung_stichtag__isnull=True
    ):
        antrag.stimmberechtigung_stichtag = antrag.phase_beginn.date()
        antrag.save(update_fields=["stimmberechtigung_stichtag"])


class Migration(migrations.Migration):
    dependencies = [("verfahren", "0016_auditeintrag_vorgaenger")]

    operations = [
        migrations.AddField(
            model_name="antrag",
            name="stimmberechtigung_stichtag",
            field=models.DateField(
                blank=True,
                help_text="Der Kalendertag (Wiener Zeit), an dem die Stimmberechtigung festgestellt wurde — "
                "dieselbe Zahl für Zählung und Einzelprüfung (§ 4 Abs 4 lit a).",
                null=True,
            ),
        ),
        migrations.RunPython(nachtragen, migrations.RunPython.noop),
    ]
