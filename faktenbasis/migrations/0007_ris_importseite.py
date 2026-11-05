import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("faktenbasis", "0006_personalressorts")]

    operations = [migrations.AddField(
        model_name="risimport", name="seite",
        field=models.PositiveIntegerField(default=1, validators=[
            django.core.validators.MinValueValidator(1),
            django.core.validators.MaxValueValidator(2147483647),
        ]),
    )]
