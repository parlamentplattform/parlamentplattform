"""Indizes für `faellige_abschliessen` (Status, Frist) und die Sortierung der Fachliste (Befund #81)."""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("gremien", "0015_pruefung_korat_verfristet")]

    operations = [
        migrations.AddIndex(
            model_name="gremienbeschluss",
            index=models.Index(fields=["status", "frist"], name="beschluss_status_frist_idx"),
        ),
        migrations.AddIndex(
            model_name="fachliste",
            index=models.Index(fields=["gestrichen_am"], name="fachliste_gestrichen_idx"),
        ),
    ]
