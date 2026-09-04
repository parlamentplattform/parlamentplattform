# S5 (FB-F2, § 6 Abs 11 lit b): Beanstandung einer Einschätzung der Zukunftswerkstatt —
# öffentlich, append-only, zugleich Anforderung eines Korrekturlaufs.

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("verfahren", "0011_filterprofil_favoriten_zuerst_regel_v2"),
        ("ki", "0001_initial"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Beanstandung",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("text", models.TextField(help_text="Was ist falsch? Sachlich, mit Beleg wenn möglich.", max_length=2000)),
                ("erstellt_am", models.DateTimeField(default=django.utils.timezone.now)),
                ("erledigt_am", models.DateTimeField(blank=True, null=True)),
                ("erledigt_vermerk", models.TextField(blank=True, max_length=2000)),
                (
                    "antrag",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="beanstandungen",
                        to="verfahren.antrag",
                    ),
                ),
                (
                    "lauf",
                    models.ForeignKey(
                        blank=True,
                        help_text="Der beanstandete Lauf — leer, wenn die Einschätzung inzwischen ersetzt wurde.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="beanstandungen",
                        to="ki.kilauf",
                    ),
                ),
                (
                    "mitglied",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
                ),
            ],
            options={
                "verbose_name": "Beanstandung einer Einschätzung",
                "verbose_name_plural": "Beanstandungen von Einschätzungen",
                "ordering": ["-erstellt_am"],
            },
        ),
    ]
