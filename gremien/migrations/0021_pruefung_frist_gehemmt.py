import datetime

from django.db import migrations, models


class Migration(migrations.Migration):
    """GP-008: Die Frist des Koordinationsrats über einen Austauschantrag ruht während einer Zurückweisung.

    Rein additiv; bestehende Prüfungen bekommen die Dauer null, für sie rechnet die Frist wie bisher
    ab dem Urteil. Das Urteilsdatum selbst wird nie verschoben."""

    dependencies = [
        ('gremien', '0020_pruefung_korat_entscheid_ohne_ergebnis'),
    ]

    operations = [
        migrations.AddField(
            model_name='pruefung',
            name='frist_gehemmt',
            field=models.DurationField(
                default=datetime.timedelta,
                help_text='Nur bei Austauschanträgen: die Dauer aufgehobener Zurückweisungen des Antrags, während '
                'deren die Frist des Koordinationsrats ruhte (§ 5 Abs 2). Das Urteilsdatum bleibt, wie es war.',
            ),
        ),
    ]
