# Befund #25: Altbestand — wer schon vor dieser Fassung nicht mehr „ungeprüft“ war, gilt
# als seit dem Beitritt freigeschaltet (ein früheres Datum ist nicht überliefert; der
# Beitritt ist die konservative Wahl: Er verändert keine bisherige Stimmberechtigung).
# Idempotent: Nur leere Felder werden befüllt. Rückwärts nichts zu tun.

from django.db import migrations
from django.db.models import F


def geprueft_seit_nachtragen(apps, schema_editor):
    Mitglied = apps.get_model("mitglieder", "Mitglied")
    Mitglied.objects.filter(geprueft_seit__isnull=True, beitritt__isnull=False).exclude(
        identitaetsstufe="ungeprueft"
    ).update(geprueft_seit=F("beitritt"))


class Migration(migrations.Migration):

    dependencies = [
        ("mitglieder", "0010_mitglied_geprueft_seit_status_seit"),
    ]

    operations = [
        migrations.RunPython(geprueft_seit_nachtragen, migrations.RunPython.noop),
    ]
