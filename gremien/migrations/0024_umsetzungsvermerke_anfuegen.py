import django.db.models.deletion
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models


def vermerke_des_rates_uebertragen(apps, schema_editor):
    """Trägt bestehende Umsetzungsvermerke des Rates in die neue Liste um (GP-025, GP-034).

    Bis 0.114.0 teilten sich der Vermerk der Plattform und der des Rates ein Feld; der des Rates
    ersetzte, was dort stand. Ob ein Text vom Rat stammt, sagt die Audit-Kette: Jedes Schreiben über
    das Formular hat dort einen Eintrag `umsetzungsvermerk`. Hat ein entschiedener Beschluss solche
    Einträge, ist der Text im Feld der zuletzt geschriebene Vermerk des Rates — er wird zum Eintrag
    der Liste, mit der Zuweisung und Frist des Beschlusses, dem Zeitpunkt des letzten Eintrags der
    Kette und dessen Zählung als Nummer (frühere, überschriebene Wortlaute sind nicht erhalten und
    werden nicht erfunden). Das Feld gehört danach der Plattform und ist für diesen Beschluss leer.
    Ohne Eintrag in der Kette bleibt alles, wie es ist.

    Beliebig oft wiederholbar: Ein Beschluss mit Einträgen in der Liste oder leerem Feld wird
    übergangen. Gelesen werden aus der Kette nur `ereignis` und `zeit`, in einem Durchlauf."""
    GremienBeschluss = apps.get_model('gremien', 'GremienBeschluss')
    Umsetzungsvermerk = apps.get_model('gremien', 'Umsetzungsvermerk')
    Rolle = apps.get_model('gremien', 'Rolle')
    AuditEintrag = apps.get_model('verfahren', 'AuditEintrag')
    je_beschluss = {}
    eintraege = (
        AuditEintrag.objects.filter(ereignis__typ='umsetzungsvermerk')
        .order_by('lfd')
        .values_list('ereignis', 'zeit')
    )
    for ereignis, zeit in eintraege.iterator(chunk_size=500):
        kennung = ereignis.get('beschluss')
        if isinstance(kennung, int) and not isinstance(kennung, bool) and 'vermerk_nr' not in ereignis:
            anzahl = je_beschluss.get(kennung, (0, None))[0]
            je_beschluss[kennung] = (anzahl + 1, zeit)
    kennungen = sorted(je_beschluss)
    for anfang in range(0, len(kennungen), 500):
        beschluesse = GremienBeschluss.objects.filter(
            pk__in=kennungen[anfang:anfang + 500], status='entschieden'
        ).exclude(umsetzungsvermerk='')
        for beschluss in beschluesse:
            if Umsetzungsvermerk.objects.filter(beschluss_id=beschluss.pk).exists():
                continue
            anzahl, zeit = je_beschluss[beschluss.pk]
            rolle = None
            if beschluss.umsetzung_durch_id is not None:
                rolle = (
                    Rolle.objects.filter(mitglied_id=beschluss.umsetzung_durch_id, gremium=beschluss.gremium)
                    .order_by('-berufen_am', '-pk')
                    .first()
                )
            Umsetzungsvermerk.objects.create(
                beschluss_id=beschluss.pk,
                nummer=anzahl,
                text=beschluss.umsetzungsvermerk,
                rolle=rolle,
                frist=beschluss.umsetzung_frist,
                erstellt_am=zeit,
            )
            GremienBeschluss.objects.filter(pk=beschluss.pk).update(umsetzungsvermerk='')


def rueckweg_pruefen(apps, schema_editor):
    """Der Rückweg löschte mit der Tabelle jeden Vermerk des Rates — vorwärts wurde das Feld am Beschluss
    geleert, zurückgeschrieben würde nichts. Solange kein Vermerk besteht, verliert er nichts; sonst bricht
    er ab (Gesamtprüfung 0.115.0, Muster verfahren 0025)."""
    from django.db.migrations.exceptions import IrreversibleError

    Umsetzungsvermerk = apps.get_model('gremien', 'Umsetzungsvermerk')
    if Umsetzungsvermerk.objects.using(schema_editor.connection.alias).exists():
        raise IrreversibleError(
            'gremien 0024 lässt sich nicht zurücknehmen: Der Rückweg löschte die Umsetzungsvermerke des Rates. '
            'Vorwärts beheben (docs/BETRIEB-RENDER.md).'
        )


class Migration(migrations.Migration):
    """GP-025, GP-034: Umsetzungsvermerke des Rates werden angefügt, nie ersetzt.

    Additiv: eine neue Tabelle. Das Feld `umsetzungsvermerk` am Beschluss bleibt und gehört künftig
    allein der Plattform (nur der Hilfetext ändert sich); Zuweisung und Frist am Beschluss tragen den
    Stand des jüngsten Vermerks. Bestehende Vermerke des Rates wandern in die Liste, wo die Kette sie
    als solche ausweist."""

    dependencies = [
        ('gremien', '0023_beschluss_auszaehlung_festgehalten'),
        ('verfahren', '0010_filterprofil'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterField(
            model_name='gremienbeschluss',
            name='umsetzung_durch',
            field=models.ForeignKey(
                blank=True,
                help_text='Wer die Umsetzung übernimmt — ein Mitglied des Rates. Stand des jüngsten Vermerks.',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='zugewiesene_umsetzungen',
                to=settings.AUTH_USER_MODEL,
            ),
        ),
        migrations.AlterField(
            model_name='gremienbeschluss',
            name='umsetzung_frist',
            field=models.DateField(blank=True, help_text='Bis wann. Stand des jüngsten Vermerks.', null=True),
        ),
        migrations.AlterField(
            model_name='gremienbeschluss',
            name='umsetzungsvermerk',
            field=models.TextField(
                blank=True,
                help_text='Der Vermerk der Plattform: was der Beschluss bewirkt hat oder warum er ohne Wirkung '
                'blieb. Nur anfügend; die Vermerke des Rates stehen als eigene Einträge daneben.',
                max_length=2000,
            ),
        ),
        migrations.CreateModel(
            name='Umsetzungsvermerk',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nummer', models.PositiveIntegerField(help_text='Je Beschluss fortlaufend.')),
                ('text', models.TextField(max_length=2000)),
                ('frist', models.DateField(blank=True, help_text='Bis wann — freiwillig.', null=True)),
                ('erstellt_am', models.DateTimeField(default=django.utils.timezone.now)),
                (
                    'beschluss',
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name='umsetzungsvermerke',
                        to='gremien.gremienbeschluss',
                    ),
                ),
                (
                    'rolle',
                    models.ForeignKey(
                        blank=True,
                        help_text='Die Rolle des Ratsmitglieds, das die Umsetzung übernimmt — freiwillig.',
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name='umsetzungsvermerke',
                        to='gremien.rolle',
                    ),
                ),
            ],
            options={
                'verbose_name': 'Umsetzungsvermerk',
                'verbose_name_plural': 'Umsetzungsvermerke',
                'ordering': ['-nummer'],
                'unique_together': {('beschluss', 'nummer')},
            },
        ),
        # Der Rückweg bricht ab, sobald ein Vermerk besteht (`rueckweg_pruefen`); nur eine Datenbank ohne
        # Vermerke (leer, Testläufe) lässt sich zurücknehmen. Zurückrollen ist ohnehin ausgeschlossen.
        migrations.RunPython(vermerke_des_rates_uebertragen, rueckweg_pruefen),
    ]
