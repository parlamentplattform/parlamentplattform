# Befunde #1 und #2 (F-51, § 5 Abs 3): Die verwaltungsseitige Änderung der Anmeldeadresse
# wird ein eigener Vorgang mit Einspruchslink, Wartefrist und zweitem Admin.

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mitglieder", "0011_geprueft_seit_nachtragen"),
    ]

    operations = [
        migrations.CreateModel(
            name="Adresswechsel",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("neue_email", models.EmailField(max_length=254)),
                ("beantragt_am", models.DateTimeField(auto_now_add=True)),
                ("frist_bis", models.DateTimeField()),
                ("bestaetigt_am", models.DateTimeField(blank=True, null=True)),
                ("einspruch_hash", models.CharField(max_length=64, unique=True)),
                (
                    "status",
                    models.CharField(
                        choices=[("offen", "offen"), ("wirksam", "wirksam"), ("widerrufen", "widerrufen")],
                        default="offen",
                        max_length=12,
                    ),
                ),
                ("erledigt_am", models.DateTimeField(blank=True, null=True)),
                (
                    "beantragt_von",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="beantragte_adresswechsel",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "bestaetigt_von",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="bestaetigte_adresswechsel",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "mitglied",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="adresswechsel",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "verbose_name": "Adresswechsel",
                "verbose_name_plural": "Adresswechsel",
                "ordering": ["-beantragt_am"],
            },
        ),
    ]
