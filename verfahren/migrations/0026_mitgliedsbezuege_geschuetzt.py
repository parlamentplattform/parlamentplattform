"""Verfahrensbezüge überleben jede Kontoänderung (Bestandsaufnahme A10, Schritt 2 · 0.52.0).

Unterstützung, StimmRegister (Brücke Mitglied ↔ Pseudonym) und Reaktion hängen jetzt mit PROTECT am
Konto wie alle übrigen Verfahrensbezüge. Nur die Löschregel ändert sich, keine Zeile.
"""

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("verfahren", "0025_reaktion_zurueckgenommen_und_uebergangsregel"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name="reaktion",
            name="mitglied",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AlterField(
            model_name="stimmregister",
            name="mitglied",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL
            ),
        ),
        migrations.AlterField(
            model_name="unterstuetzung",
            name="mitglied",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL
            ),
        ),
    ]
