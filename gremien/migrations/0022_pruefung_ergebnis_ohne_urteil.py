from django.db import migrations, models


def urteile_ohne_pruefung_berichtigen(apps, schema_editor):
    """Nennt Urteile, die keine waren, bei ihrem Namen (GP-032).

    Bis 0.114.0 stand „validiert“ am Urteil, wenn der Prüfbeschluss ohne Ergebnis blieb oder Gruppe 2
    unbesetzt war. Beides lässt sich am Bestand sicher erkennen: am Beschluss ohne Ergebnis und am
    Vermerk der Plattform ohne Beschluss und ohne Person. Ein Urteil, das wirklich jemand gefällt hat,
    bleibt stehen. Zwei Anweisungen, beliebig oft wiederholbar; die Begründungen bleiben unberührt."""
    Pruefung = apps.get_model('gremien', 'Pruefung')
    GremienBeschluss = apps.get_model('gremien', 'GremienBeschluss')
    ohne_ergebnis = GremienBeschluss.objects.filter(status='ohne_ergebnis', ergebnis='').values('pk')
    Pruefung.objects.filter(ergebnis='validiert', beschluss_id__in=ohne_ergebnis).update(ergebnis='ergebnislos')
    Pruefung.objects.filter(
        ergebnis='validiert',
        beschluss__isnull=True,
        durch__isnull=True,
        begruendung__startswith='Die Prüfung blieb aus',
    ).update(ergebnis='ungeprueft')


class Migration(migrations.Migration):
    """GP-032: Eine Prüfung ohne Ergebnis oder ohne Gruppe 2 heißt nicht „validiert“.

    Die Auswahlliste des Feldes wächst um zwei Werte; die Spalte bleibt, wie sie ist. Der Altbestand
    wird berichtigt, wo der Fall eindeutig ist. Die Audit-Kette bleibt unverändert: Ältere Einträge
    `vorschlag_geprueft` tragen weiter „validiert“ zusammen mit `ohne_ergebnis: true`."""

    dependencies = [
        ('gremien', '0021_pruefung_frist_gehemmt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='pruefung',
            name='ergebnis',
            field=models.CharField(
                choices=[
                    ('validiert', 'validiert'),
                    ('zurueck', 'mit Begründung zurückgegeben'),
                    ('austausch', 'Austausch bei Gruppe 1 beantragt'),
                    ('ergebnislos', 'ohne Ergebnis — nicht validiert'),
                    ('ungeprueft', 'nicht geprüft — Gruppe 2 unbesetzt'),
                ],
                max_length=12,
            ),
        ),
        migrations.RunPython(urteile_ohne_pruefung_berichtigen, migrations.RunPython.noop),
    ]
