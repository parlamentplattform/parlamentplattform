"""Ein Austauschantrag kann verfristen (Befund #8).

Entscheidet der Koordinationsrat binnen der Prüffrist nicht, geht der Vorschlag weiter an die
Unterstützer (§ 5 Abs 12: Untätigkeit hemmt nie) — und die Prüfung trägt den Vermerk
`verfristet` statt einer Entscheidung, die nie fiel. Nur die Auswahl des Feldes ändert sich.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("gremien", "0014_entwurf_eingereichte_fassung")]

    operations = [
        migrations.AlterField(
            model_name="pruefung",
            name="korat_entscheid",
            field=models.CharField(
                blank=True,
                choices=[
                    ("stattgegeben", "stattgegeben"),
                    ("abgelehnt", "abgelehnt"),
                    ("verfristet", "keine Entscheidung binnen der Frist"),
                ],
                help_text="Nur bei Austauschanträgen: die Entscheidung des Koordinationsrats — oder der "
                "Vermerk, dass sie binnen der Prüffrist ausblieb.",
                max_length=12,
            ),
        ),
    ]
