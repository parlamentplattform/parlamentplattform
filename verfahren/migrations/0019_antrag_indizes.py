"""Indizes auf den Listenfeldern des Antrags (Befund #81).

Jede Listenansicht filtert auf die Phase und reiht nach Phasenbeginn; die Hervorhebung sucht
drei Anträge aus allen. Heute nicht messbar — der billigste Schritt, der beim Wachsen als
Nächstes fehlt. Der Teilindex auf `hervorgehoben` läuft auf SQLite ≥ 3.8 und PostgreSQL.
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("verfahren", "0018_ruecknahmen_dokumentiert")]

    operations = [
        migrations.AddIndex(
            model_name="antrag",
            index=models.Index(fields=["phase", "phase_beginn"], name="antrag_phase_beginn_idx"),
        ),
        migrations.AddIndex(
            model_name="antrag",
            index=models.Index(
                condition=models.Q(("hervorgehoben", True)),
                fields=["hervorgehoben"],
                name="antrag_hervorgehoben_idx",
            ),
        ),
    ]
