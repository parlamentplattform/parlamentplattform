from django.db import migrations


class Migration(migrations.Migration):
    """GP-002: Die Offenlegung der Interessenbindung wird angefügt, nie überschrieben.

    Die Eindeutigkeit je Antrag, Person und Runde fällt weg — sie erzwang das Überschreiben.
    Bestehende Zeilen bleiben unverändert; es wird nichts gelöscht und nichts umgeschrieben."""

    dependencies = [
        ('gremien', '0018_entwurf_beratung_freigegeben_am'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='interessenbindung',
            options={
                'ordering': ['erklaert_am', 'pk'],
                'verbose_name': 'Interessenbindung',
                'verbose_name_plural': 'Interessenbindungen',
            },
        ),
        migrations.AlterUniqueTogether(
            name='interessenbindung',
            unique_together=set(),
        ),
    ]
