import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('verfahren', '0029_korrekturlauf'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='antrag', name='teilnahmegebiet',
            field=models.JSONField(blank=True, default=None, editable=False, null=True),
        ),
        migrations.AddField(
            model_name='antrag', name='teilnehmerkreis_am',
            field=models.DateTimeField(blank=True, editable=False, null=True),
        ),
        migrations.CreateModel(
            name='OertlicheTeilnahme',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('antrag', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                            related_name='oertlicher_kreis', to='verfahren.antrag')),
                ('mitglied', models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                              related_name='oertliche_verfahrenskreise', to=settings.AUTH_USER_MODEL)),
            ],
            options={'constraints': [models.UniqueConstraint(fields=('antrag', 'mitglied'),
                                                            name='oertlicher_kreis_eindeutig')]},
        ),
    ]
