"""Der Entwurf merkt sich, welche Fassung eingereicht wurde (Befund #5).

Bis 0.44 nahm die Endabstimmung nach einer verstrichenen Überarbeitungsfrist die höchste
Entwurfsfassung — auch einen Arbeitsstand, den Gruppe 1 nach der Rückgabe angehängt hatte und
den kein Organ freigegeben hatte. Jetzt hält `eingereichte_fassung` fest, was vorgelegt war.

Für bestehende Entwürfe wird die Nummer nachgetragen: die höchste Fassung, die es zum
Zeitpunkt der Einreichung schon gab (danach war die Werkstatt gesperrt, bis der Vorschlag
zurückkam). Idempotent — gefüllt wird nur, was leer ist; rückwärts bleibt alles stehen.
"""

from django.db import migrations, models


def nachtragen(apps, schema_editor):
    Entwurf = apps.get_model("gremien", "Entwurf")
    for entwurf in Entwurf.objects.filter(eingereicht_am__isnull=False, eingereichte_fassung__isnull=True):
        fassung = (
            entwurf.fassungen.filter(erstellt_am__lte=entwurf.eingereicht_am).order_by("-nummer").first()
            or entwurf.fassungen.order_by("-nummer").first()
        )
        if fassung is None:
            continue
        entwurf.eingereichte_fassung = fassung.nummer
        entwurf.save(update_fields=["eingereichte_fassung"])


class Migration(migrations.Migration):
    dependencies = [("gremien", "0013_einreichstimmen_uebertragen")]

    operations = [
        migrations.AddField(
            model_name="entwurf",
            name="eingereichte_fassung",
            field=models.PositiveIntegerField(
                blank=True,
                help_text="Nummer der Entwurfsfassung, die zuletzt eingereicht wurde — nur sie geht zur "
                "Endabstimmung. Ein später angehängter Arbeitsstand hat kein Organ freigegeben (§ 5 Abs 12).",
                null=True,
            ),
        ),
        migrations.RunPython(nachtragen, migrations.RunPython.noop),
    ]
