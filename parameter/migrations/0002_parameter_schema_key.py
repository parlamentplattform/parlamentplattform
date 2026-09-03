# S14a (FB-M5, § 12 Abs 5): sprachneutrale Schema-Kennung je Stellgröße — die Brücke zwischen
# den Landesinstanzen. Idempotent: bestehende Kennungen bleiben, fehlende werden nachgetragen.

from django.db import migrations, models


def kennungen_nachtragen(apps, schema_editor):
    from plattform_core.schema import schema_key

    Parameter = apps.get_model("parameter", "Parameter")
    for parameter in Parameter.objects.all():
        kennung = schema_key(parameter.schluessel)
        if kennung and parameter.schema_key != kennung:
            parameter.schema_key = kennung
            parameter.save(update_fields=["schema_key"])


class Migration(migrations.Migration):

    dependencies = [
        ("parameter", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="parameter",
            name="schema_key",
            field=models.CharField(
                blank=True,
                default="",
                help_text="Sprachneutrale Kennung im gemeinsamen Schema (docs/SCHEMA.md), z. B. „draft_loop.review_days“; leer = nur lokal.",
                max_length=80,
            ),
        ),
        migrations.RunPython(kennungen_nachtragen, migrations.RunPython.noop),
    ]
