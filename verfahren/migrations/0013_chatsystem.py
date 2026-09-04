# S6 Chatsystem (FB-G1, G2, G5): Der Kommentar wird zum Chat-Beitrag — Faden (antwort_auf),
# Phase beim Schreiben, Archivierung bei Hochstufung, Bearbeitungsfenster, Entfernen durch den
# Verfasser und Ausblenden durch die Verwaltung. Dazu Reaktion, Lesestand und Meldung.
# Bestehende Beiträge bekommen rückwirkend die Phase ihres Antrags, damit die Archivierung
# beim nächsten Phasenwechsel greift; nichts wird gelöscht (Grundregel 7).

import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def phase_nachtragen(apps, schema_editor):
    """Ohne Phase wäre jeder Altbeitrag bei der nächsten Hochstufung nicht zuzuordnen."""
    Kommentar = apps.get_model("verfahren", "Kommentar")
    for kommentar in Kommentar.objects.select_related("antrag").filter(phase=""):
        kommentar.phase = kommentar.antrag.phase
        kommentar.save(update_fields=["phase"])


class Migration(migrations.Migration):

    dependencies = [
        ('verfahren', '0012_beanstandung'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Lesestand',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('gelesen_bis', models.DateTimeField(default=django.utils.timezone.now, help_text='Zeitpunkt des zuletzt gelesenen Beitrags.')),
            ],
            options={
                'verbose_name': 'Lesestand',
                'verbose_name_plural': 'Lesestände',
            },
        ),
        migrations.CreateModel(
            name='Meldung',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('grund', models.CharField(choices=[('beleidigung', 'Beleidigung oder Herabwürdigung'), ('falsch', 'Nachweislich falsche Tatsachenbehauptung'), ('thema', 'Kein Bezug zum Antrag'), ('recht', 'Rechtswidriger Inhalt'), ('sonst', 'Sonstiges')], max_length=20)),
                ('erlaeuterung', models.CharField(blank=True, max_length=500)),
                ('erstellt_am', models.DateTimeField(default=django.utils.timezone.now)),
                ('erledigt_am', models.DateTimeField(blank=True, null=True)),
                ('entscheidung', models.CharField(blank=True, max_length=200)),
            ],
            options={
                'verbose_name': 'Meldung',
                'verbose_name_plural': 'Meldungen',
                'ordering': ['-erstellt_am'],
            },
        ),
        migrations.CreateModel(
            name='Reaktion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('art', models.CharField(choices=[('zustimmung', 'Zustimmung'), ('ablehnung', 'Ablehnung')], default='zustimmung', max_length=12)),
                ('erstellt_am', models.DateTimeField(default=django.utils.timezone.now)),
            ],
            options={
                'verbose_name': 'Reaktion',
                'verbose_name_plural': 'Reaktionen',
            },
        ),
        migrations.AddField(
            model_name='kommentar',
            name='antwort_auf',
            field=models.ForeignKey(blank=True, help_text='Wurzelbeitrag dieses Fadens — leer bei einem eigenen Faden.', null=True, on_delete=django.db.models.deletion.CASCADE, related_name='antworten', to='verfahren.kommentar'),
        ),
        migrations.AddField(
            model_name='kommentar',
            name='archiviert_am',
            field=models.DateTimeField(blank=True, help_text='Bei Hochstufung gesetzt: der Beitrag wandert ins Archiv (FB-G5).', null=True),
        ),
        migrations.AddField(
            model_name='kommentar',
            name='ausgeblendet_am',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='kommentar',
            name='ausgeblendet_grund',
            field=models.CharField(blank=True, help_text='Öffentlicher Grund der Verwaltung (Art 17 DSA).', max_length=200),
        ),
        migrations.AddField(
            model_name='kommentar',
            name='bearbeitet_am',
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name='kommentar',
            name='geloescht',
            field=models.BooleanField(default=False, help_text='Vom Verfasser entfernt — die Struktur bleibt.'),
        ),
        migrations.AddField(
            model_name='kommentar',
            name='phase',
            field=models.CharField(blank=True, help_text='Phase des Antrags beim Schreiben — die Grundlage der Archivierung bei Hochstufung.', max_length=20),
        ),
        migrations.AddIndex(
            model_name='kommentar',
            index=models.Index(fields=['antrag', 'archiviert_am', 'erstellt_am'], name='verfahren_k_antrag__be9638_idx'),
        ),
        migrations.AddField(
            model_name='lesestand',
            name='antrag',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lesestaende', to='verfahren.antrag'),
        ),
        migrations.AddField(
            model_name='lesestand',
            name='mitglied',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='lesestaende', to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='meldung',
            name='kommentar',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='meldungen', to='verfahren.kommentar'),
        ),
        migrations.AddField(
            model_name='meldung',
            name='mitglied',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AddField(
            model_name='reaktion',
            name='kommentar',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='reaktionen', to='verfahren.kommentar'),
        ),
        migrations.AddField(
            model_name='reaktion',
            name='mitglied',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterUniqueTogether(
            name='lesestand',
            unique_together={('mitglied', 'antrag')},
        ),
        migrations.AlterUniqueTogether(
            name='meldung',
            unique_together={('kommentar', 'mitglied')},
        ),
        migrations.AlterUniqueTogether(
            name='reaktion',
            unique_together={('kommentar', 'mitglied')},
        ),
        migrations.RunPython(phase_nachtragen, migrations.RunPython.noop),
    ]
