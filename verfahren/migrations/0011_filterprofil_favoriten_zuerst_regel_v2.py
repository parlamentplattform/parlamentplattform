# S3 WeicherFilter (FB-B1–B3): Schalter „★ Favoriten zuerst“ je Konfiguration und Übernahme
# der Reglerstände von Regel v1 nach v2 — der richtungslose Regler „gestimmt“ lebt in
# „ja“ und „nein“ weiter (D-B2). Idempotent: bereits übersetzte Profile bleiben unberührt.

from django.db import migrations, models


def regler_nach_v2(apps, schema_editor):
    FilterProfil = apps.get_model("verfahren", "FilterProfil")
    for profil in FilterProfil.objects.all():
        regler = dict(profil.regler or {})
        if "gestimmt" not in regler:
            continue
        wert = regler.pop("gestimmt")
        regler.setdefault("ja", wert)
        regler.setdefault("nein", wert)
        profil.regler = regler
        profil.save(update_fields=["regler"])


class Migration(migrations.Migration):

    dependencies = [
        ("verfahren", "0010_filterprofil"),
    ]

    operations = [
        migrations.AddField(
            model_name="filterprofil",
            name="favoriten_zuerst",
            field=models.BooleanField(
                default=True,
                help_text="★ Favoriten zuerst: Anträge aus abonnierten Lebensbereichen stehen vorn (FB-B1).",
            ),
        ),
        migrations.RunPython(regler_nach_v2, migrations.RunPython.noop),
    ]
