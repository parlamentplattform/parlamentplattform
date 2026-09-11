# Befund #25 (§ 4 Abs 4 lit a): Freischaltung und Status tragen ihr Datum, damit die
# Stimmberechtigung am Stichtag geprüft werden kann. Befund #15: das Label der Stufe
# „geprüft“ sagt, was sie heute bedeutet (Beitragseingang), keine Datenänderung.

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("mitglieder", "0009_hilfetexte_ohne_kennungen"),
    ]

    operations = [
        migrations.AddField(
            model_name="mitglied",
            name="geprueft_seit",
            field=models.DateField(
                blank=True,
                help_text="Tag, seit dem das Konto nicht mehr „ungeprüft“ ist — Stichtagsprüfung der "
                "Stimmberechtigung (§ 4 Abs 4 lit a): Zähler und Nenner folgen demselben Tag.",
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="mitglied",
            name="status_seit",
            field=models.DateField(
                blank=True,
                help_text="Tag, seit dem der aktuelle Status gilt (leer = seit jeher) — Stichtagsprüfung "
                "der Stimmberechtigung (§ 4 Abs 4 lit a).",
                null=True,
            ),
        ),
        migrations.AlterField(
            model_name="mitglied",
            name="identitaetsstufe",
            field=models.CharField(
                choices=[
                    ("ungeprueft", "ungeprüft"),
                    ("geprueft", "geprüft (Beitragseingang verbucht)"),
                    ("praesenz", "Präsenz-Identitätsfeststellung (§ 13 Abs 2)"),
                    ("eid", "elektronischer Identitätsnachweis (§ 2 Abs 4)"),
                ],
                default="ungeprueft",
                max_length=20,
            ),
        ),
    ]
