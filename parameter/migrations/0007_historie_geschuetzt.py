"""Die Historie des Registers hängt mit PROTECT am Parameter (Gesamtprüfung GP-130).

Bisher nahm ein gelöschter Parameter seine Änderungen und Tests still mit (CASCADE), und der Wert entstand
beim nächsten Aufruf ohne Geschichte neu. Die Migration ändert nur die Löschregel der beiden
Fremdschlüssel: keine Datenänderung, keine neue Spalte. Die Löschregel führt Django, nicht die Datenbank —
der Schritt läuft auf SQLite wie auf PostgreSQL ohne SQL, auf einer leeren wie auf einer großen Datenbank."""

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("parameter", "0006_gruppe_mandatare"),
    ]

    operations = [
        migrations.AlterField(
            model_name="aenderung",
            name="parameter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="historie", to="parameter.parameter"
            ),
        ),
        migrations.AlterField(
            model_name="parametertest",
            name="parameter",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="tests", to="parameter.parameter"
            ),
        ),
    ]
