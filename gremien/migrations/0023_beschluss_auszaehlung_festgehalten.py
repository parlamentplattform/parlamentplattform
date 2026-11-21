from django.db import migrations, models


def _ganzzahl(wert) -> bool:
    return isinstance(wert, int) and not isinstance(wert, bool) and wert >= 0


def auszaehlung_aus_dem_audit_nachtragen(apps, schema_editor):
    """Trägt geschlossenen Beschlüssen die Zahlen ihres Audit-Eintrags nach (GP-035).

    Quelle ist allein der Eintrag `gremienbeschluss_ausgewertet` (abgegeben, nötig, Zählung je
    Option). Die Zahl der aktiven Rollen trug er vor dieser Fassung nicht — sie bleibt dann offen
    und wird nicht aus der heutigen Besetzung errechnet. Ein Beschluss ohne solchen Eintrag bleibt
    ohne festgehaltene Zahl; die Seiten sagen das. Beliebig oft wiederholbar: Geschrieben wird
    nur, wo noch nichts steht. Gelesen wird die Kette in einem Durchlauf, nur die Spalte `ereignis`."""
    GremienBeschluss = apps.get_model('gremien', 'GremienBeschluss')
    AuditEintrag = apps.get_model('verfahren', 'AuditEintrag')
    offen = set(
        GremienBeschluss.objects.exclude(status='offen').filter(festgehalten__isnull=True).values_list('pk', flat=True)
    )
    if not offen:
        return
    eintraege = (
        AuditEintrag.objects.filter(ereignis__typ='gremienbeschluss_ausgewertet')
        .order_by('lfd')
        .values_list('ereignis', flat=True)
    )
    for ereignis in eintraege.iterator(chunk_size=500):
        kennung = ereignis.get('beschluss')
        if kennung not in offen:
            continue
        abgegeben, noetig, zaehlung = ereignis.get('abgegeben'), ereignis.get('noetig'), ereignis.get('zaehlung')
        if not (_ganzzahl(abgegeben) and _ganzzahl(noetig) and isinstance(zaehlung, dict)):
            continue
        fest = {'abgegeben': abgegeben, 'noetig': noetig, 'zaehlung': zaehlung, 'quelle': 'audit'}
        if _ganzzahl(ereignis.get('aktive')):
            fest['aktive'] = ereignis['aktive']
        GremienBeschluss.objects.filter(pk=kennung, festgehalten__isnull=True).update(festgehalten=fest)
        offen.discard(kennung)  # der erste Eintrag je Beschluss gilt
        if not offen:
            break


class Migration(migrations.Migration):
    """GP-035: Ein geschlossener Beschluss zeigt die Zahlen seines Beschlusszeitpunkts.

    Rein additiv: ein leeres Feld für die Auszählung. Der Altbestand bekommt nachgetragen, was die
    Audit-Kette trägt — nichts sonst."""

    dependencies = [
        ('gremien', '0022_pruefung_ergebnis_ohne_urteil'),
        ('verfahren', '0010_filterprofil'),
    ]

    operations = [
        migrations.AddField(
            model_name='gremienbeschluss',
            name='festgehalten',
            field=models.JSONField(
                blank=True,
                null=True,
                help_text='Die Auszählung zum Beschlusszeitpunkt: abgegebene und nötige Stimmen, aktive Rollen, '
                'Zählung je Option. Ein geschlossener Beschluss zeigt nur diese Zahlen. Leer, solange er offen '
                'ist, und wenn er ohne Auswertung geschlossen wurde.',
            ),
        ),
        migrations.RunPython(auszaehlung_aus_dem_audit_nachtragen, migrations.RunPython.noop),
    ]
