from django.db import migrations, models


class Migration(migrations.Migration):
    """GP-001: Die Entwurfsschleife hält fest, wann sie die Beratung freigegeben hat.

    Rein additiv; bestehende Entwürfe bleiben ohne Wert, für sie rechnet der Regelübergang wie bisher."""

    dependencies = [
        ('gremien', '0017_rolle_ruht_anlass_vertrauensfrage_sperre'),
    ]

    operations = [
        migrations.AddField(
            model_name='entwurf',
            name='beratung_freigegeben_am',
            field=models.DateTimeField(
                blank=True,
                help_text='Zeitpunkt, zu dem die Schleife die Beratung zuletzt freigegeben hat, ohne selbst '
                'die Endabstimmung zu öffnen (Rückgabe der Gruppe 2 oder Austausch ohne Überarbeitungsfrist). '
                'Der Regelübergang in die Abstimmung wirkt nie vor diesem Zeitpunkt.',
                null=True,
            ),
        ),
    ]
