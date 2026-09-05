"""Anlass und Beschlussnummer (FB-I4).

Die Nummer wird in drei Schritten eingezogen: Feld ohne Eindeutigkeit anlegen, bestehende
Beschlüsse durchnummerieren, dann die Eindeutigkeit erzwingen. Der bequeme Weg — Feld gleich
mit `unique=True` — ginge nur auf einer leeren Tabelle gut; auf einer gefüllten bekämen alle
Zeilen denselben Leerwert und die Migration bräche mitten im Deploy ab.

Der Anlass wird für bestehende Prüfbeschlüsse nachgetragen: Sie sind daran erkennbar, dass sie
der Gruppe 2 gehören und an einem Entwurf hängen — genau die Bedingung, über die die
Wirkungstabelle bis eben verzweigt hat.
"""

from django.db import migrations, models

KUERZEL = {
    "expertenrat1": "E1",
    "expertenrat2": "E2",
    "koordinationsrat": "KR",
    "integritaetsrat": "IR",
}


def nachtragen(apps, schema_editor):
    Beschluss = apps.get_model("gremien", "GremienBeschluss")
    Beschluss.objects.filter(gremium="expertenrat2", entwurf__isnull=False).update(anlass="pruefung")
    gezaehlt: dict[tuple[str, int], int] = {}
    for beschluss in Beschluss.objects.order_by("angelegt_am", "pk"):
        jahr = beschluss.angelegt_am.year
        schluessel = (beschluss.gremium, jahr)
        gezaehlt[schluessel] = gezaehlt.get(schluessel, 0) + 1
        beschluss.nummer = f"{KUERZEL.get(beschluss.gremium, 'GR')}-{jahr}-{gezaehlt[schluessel]:02d}"
        beschluss.save(update_fields=["nummer"])


def zurueck(apps, schema_editor):
    """Die Nummern wieder leeren — die Spalte selbst nimmt Django zurück."""
    apps.get_model("gremien", "GremienBeschluss").objects.update(nummer="")


class Migration(migrations.Migration):
    dependencies = [("gremien", "0005_pruefung_als_beschluss")]

    operations = [
        migrations.AddField(
            model_name="gremienbeschluss",
            name="anlass",
            field=models.CharField(
                choices=[
                    ("intern", "innere Angelegenheit des Rates"),
                    ("pruefung", "Prüfung eines Vorschlags (§ 6 Abs 7)"),
                ],
                default="intern",
                help_text="Wozu der Beschluss gefasst wird; die Wirkungstabelle verzweigt hierüber.",
                max_length=30,
            ),
        ),
        migrations.AddField(
            model_name="gremienbeschluss",
            name="nummer",
            field=models.CharField(blank=True, default="", max_length=20),
        ),
        migrations.RunPython(nachtragen, zurueck),
        migrations.AlterField(
            model_name="gremienbeschluss",
            name="nummer",
            field=models.CharField(
                blank=True,
                help_text="Zitierfähige Kennung, je Gremium und Jahr fortlaufend — z. B. „IR-2026-04“.",
                max_length=20,
                unique=True,
            ),
        ),
    ]
