"""Reaktionen append-only und die Übergangsregel in der Ordnung (Schritt 1 der Restaufgaben, 0.51.0).

1. `Reaktion.zurueckgenommen_am` (Bestandsaufnahme A8): Zurücknehmen und Wechseln stempeln die Zeile,
   nichts wird gelöscht; ein Teilindex lässt höchstens eine geltende Reaktion je Mitglied und Beitrag
   zu. Der Bestand ist vollständig geltend und schon eindeutig — kein Datenverlust.
2. Übergangsregel (§ 4 Abs 4 lit d, Bestandsaufnahme A5): Seit Fassung 5 der Ordnungsregeln trägt jeder
   Schnappschuss `uebergangsregel`. Ältere Schnappschüsse ohne das Feld lesen die Vorgabe „gilt“ — den
   Standard der Einstellung und den Wert jeder bekannten Instanz. Nur eine Instanz, die heute mit
   `DDOE_UEBERGANGSREGEL=0` läuft, bekommt den Wert „gilt nicht“ in die älteren Schnappschüsse
   geschrieben, mit einem Audit-Eintrag ohne Personenbezug (Entscheidung E4 zum Bauplan 0.51.0: die
   unveränderliche Kopie nur anfassen, wo die Vorgabe falsch wäre). Idempotent: Schnappschüsse mit dem
   Feld bleiben unberührt. Rückweg: nichts zurückzunehmen (noop) — ein zurückgenommener Wert wäre eine
   Behauptung über die Vergangenheit, die niemand prüfen kann.
"""

from django.conf import settings
from django.db import migrations, models
from django.utils import timezone


def audit_anhaengen(apps, db, ereignis: dict) -> None:
    """Ein Audit-Eintrag aus der Migration heraus — dieselbe Kette, derselbe Hash (ADR-005)."""
    from plattform_core.hashchain import GENESIS, ereignis_hash

    AuditEintrag = apps.get_model("verfahren", "AuditEintrag")
    jetzt = timezone.now()
    versiegelt = {**ereignis, "zeit": jetzt.isoformat()}
    letzter = AuditEintrag.objects.using(db).order_by("-lfd").only("hash").first()
    vorgaenger = letzter.hash if letzter else GENESIS
    AuditEintrag.objects.using(db).create(
        zeit=jetzt, ereignis=versiegelt, vorgaenger=vorgaenger, hash=ereignis_hash(vorgaenger, versiegelt)
    )


def uebergangsregel_nachtragen(apps, schema_editor) -> int:
    """Schreibt „gilt nicht“ in Schnappschüsse ohne das Feld — nur auf einer Instanz mit
    `DDOE_UEBERGANGSREGEL=0`. Gibt die Zahl der geänderten Anträge zurück (beim zweiten Lauf null)."""
    if getattr(settings, "DDOE_UEBERGANGSREGEL", True):
        return 0  # die Vorgabe „gilt“ stimmt schon — keine Kopie wird angefasst
    Antrag = apps.get_model("verfahren", "Antrag")
    db = schema_editor.connection.alias
    anzahl = 0
    for antrag in Antrag.objects.using(db).only("pk", "policy_snapshot").iterator():
        schnappschuss = antrag.policy_snapshot or {}
        if "uebergangsregel" in schnappschuss:
            continue
        antrag.policy_snapshot = {**schnappschuss, "uebergangsregel": False}
        antrag.save(update_fields=["policy_snapshot"])
        anzahl += 1
    if anzahl:
        audit_anhaengen(
            apps, db, {"typ": "uebergangsregel_nachgetragen", "wert": False, "antraege": anzahl, "stand": "Einstellung am Tag der Migration"}
        )
    return anzahl


class Migration(migrations.Migration):

    dependencies = [
        ("verfahren", "0024_antragseinbettung"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AlterUniqueTogether(
            name="reaktion",
            unique_together=set(),
        ),
        migrations.AddField(
            model_name="reaktion",
            name="zurueckgenommen_am",
            field=models.DateTimeField(
                blank=True,
                help_text="Gesetzt, wenn die Reaktion zurückgenommen oder gewechselt wurde — die Zeile bleibt (Grundregel 7), gezählt wird sie nicht mehr.",
                null=True,
            ),
        ),
        migrations.AddConstraint(
            model_name="reaktion",
            constraint=models.UniqueConstraint(
                condition=models.Q(("zurueckgenommen_am__isnull", True)),
                fields=("kommentar", "mitglied"),
                name="reaktion_eine_aktive_je_mitglied",
            ),
        ),
        migrations.RunPython(uebergangsregel_nachtragen, migrations.RunPython.noop),
    ]
