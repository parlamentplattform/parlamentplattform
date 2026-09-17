from django.db import migrations


def bestand(apps, schema_editor):
    Mitglied = apps.get_model("mitglieder", "Mitglied")
    Kreis = apps.get_model("mitglieder", "Mitgliedsnummernkreis")
    db = schema_editor.connection.alias
    mitglieder = Mitglied.objects.using(db)
    # Expliziter Gründerauftrag A0-15: vorherige Konten sind Testmitgliedschaften.
    gruender = mitglieder.filter(email__iexact="didide@ddoe.at").first()
    if gruender:
        mitglieder.filter(pk__lt=gruender.pk).update(testkonto=True)
    nummer = 1
    for m in mitglieder.filter(testkonto=False).order_by("pk").iterator():
        mitglieder.filter(pk=m.pk).update(mitgliedsnummer=nummer)
        nummer += 1
    Kreis.objects.using(db).update_or_create(pk=1, defaults={"naechste": nummer})


class Migration(migrations.Migration):
    dependencies = [("mitglieder", "0019_mitgliedsnummer")]
    operations = [migrations.RunPython(bestand, migrations.RunPython.noop)]
