# S3 WeicherFilter (FB-B1): der Schalter „★ Favoriten zuerst“ für die neutrale Voreinstellung.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mitglieder", "0007_bankkopplung_alter_mitglied_beitrag_zuletzt_am_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="mitglied",
            name="favoriten_zuerst",
            field=models.BooleanField(
                default=True,
                help_text="WeicherFilter in der Voreinstellung: ★ Favoriten zuerst (FB-B1). Gilt, solange kein Profil aktiv ist.",
            ),
        ),
    ]
