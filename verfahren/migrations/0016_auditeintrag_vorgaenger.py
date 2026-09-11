"""Der Vorgänger eines Audit-Eintrags wird Datenbank-Tatsache (Befund #9).

Bis 0.44 las `AuditEintrag.anhaengen` den Kettenkopf mit einem gewöhnlichen SELECT und legte
den neuen Eintrag an. Zwei Worker, die den Kopf lasen, bevor der jeweils andere schrieb, hashten
beide gegen denselben Vorgänger — die Kette gabelte sich still. Mit einer eindeutigen Spalte
`vorgaenger` weist die Datenbank den zweiten Schreiber ab, und `anhaengen` liest neu.

In drei Schritten wie die Beschlussnummer (gremien/0006): Spalte ohne Eindeutigkeit anlegen,
aus der bestehenden Kette füllen (der erste Eintrag hängt am Startwert, jeder weitere am Hash
seines Vorgängers nach `lfd`), dann die Eindeutigkeit erzwingen. Die Prüfbarkeit alter
Einträge ändert sich nicht: Ihr Hash bleibt, wie er ist.

Idempotent: Gefüllt wird, was leer ist; rückwärts bleibt die Spalte stehen, bis Django sie mit
dem `AddField` zurücknimmt.
"""

from django.db import migrations, models

from plattform_core.hashchain import vorgaenger_zuordnen


def nachtragen(apps, schema_editor):
    AuditEintrag = apps.get_model("verfahren", "AuditEintrag")
    eintraege = list(AuditEintrag.objects.order_by("lfd").only("lfd", "hash", "vorgaenger"))
    if not eintraege:
        return
    # Wirft KettenFehler, wenn die vorhandene Kette schon gegabelt ist — dann muss ein Mensch
    # hinsehen, statt dass eine Migration die Gabel mit erfundenen Werten zudeckt.
    zuordnung = vorgaenger_zuordnen(e.hash for e in eintraege)
    zu_schreiben = []
    for eintrag, vorgaenger in zip(eintraege, zuordnung, strict=True):
        if eintrag.vorgaenger:
            continue
        eintrag.vorgaenger = vorgaenger
        zu_schreiben.append(eintrag)
    AuditEintrag.objects.bulk_update(zu_schreiben, ["vorgaenger"], batch_size=500)


class Migration(migrations.Migration):
    dependencies = [("verfahren", "0015_hilfetexte_ohne_kennungen")]

    operations = [
        migrations.AddField(
            model_name="auditeintrag",
            name="vorgaenger",
            field=models.CharField(blank=True, default="", editable=False, max_length=64),
        ),
        migrations.RunPython(nachtragen, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="auditeintrag",
            name="vorgaenger",
            field=models.CharField(
                editable=False,
                help_text="Hash des Vorgängers — eindeutig, damit die Kette sich nicht gabeln kann.",
                max_length=64,
                unique=True,
            ),
        ),
    ]
