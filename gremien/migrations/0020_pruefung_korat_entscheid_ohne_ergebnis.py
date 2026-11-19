from django.db import migrations, models


class Migration(migrations.Migration):
    """GP-040: Ein Austauschbeschluss ohne Ergebnis ist keine Ablehnung — eigener Wert „ergebnislos“.

    Nur die Auswahlliste des Feldes wächst; die Spalte und alle bestehenden Werte bleiben, wie sie sind."""

    dependencies = [
        ('gremien', '0019_interessenbindung_anfuegen_statt_ersetzen'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pruefung',
            name='korat_entscheid',
            field=models.CharField(
                blank=True,
                choices=[
                    ('stattgegeben', 'stattgegeben'),
                    ('abgelehnt', 'abgelehnt'),
                    ('verfristet', 'keine Entscheidung binnen der Frist'),
                    ('ergebnislos', 'ohne Ergebnis'),
                ],
                help_text='Nur bei Austauschanträgen: die Entscheidung des Koordinationsrats — oder der Vermerk, '
                'dass sie binnen der Prüffrist ausblieb.',
                max_length=12,
            ),
        ),
    ]
