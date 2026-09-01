# Verfahrensordnung Version 2 (Vorschlag des Parteigründers, 1.9.2026):
# Unterstützung 2 Monate, Beratung 3 Wochen, Endabstimmung 4 Wochen.
#
# Wichtig (§ 5 Abs 5, L2): Laufende Verfahren behalten die Regeln, unter denen
# sie begannen — diese Migration legt eine NEUE Version an und deaktiviert die
# alte; sie ändert keinen einzigen bestehenden Antrag. Die Fristen sind
# Parameter im Sinne des Parameterregisters (F-68): beschlossen, versioniert,
# lernbar. Idempotent — existiert Version 2 bereits, passiert nichts.

from django.db import migrations

NEUE_WERTE = {"version": 2, "unterstuetzung_frist_tage": 60, "beratung_tage": 21, "abstimmung_tage": 28}


def v2_anlegen(apps, schema_editor):
    Verfahrensordnung = apps.get_model("verfahren", "Verfahrensordnung")
    if Verfahrensordnung.objects.filter(policy_id="sachantrag-standard", version=2).exists():
        return
    v1 = Verfahrensordnung.objects.filter(policy_id="sachantrag-standard", version=1).first()
    if v1 is None:
        return  # frische Datenbank: demo_seed legt direkt Version 2 an
    regeln = dict(v1.regeln)
    regeln.update(NEUE_WERTE)
    Verfahrensordnung.objects.filter(policy_id="sachantrag-standard", aktiv=True).update(aktiv=False)
    Verfahrensordnung.objects.create(policy_id="sachantrag-standard", version=2, regeln=regeln, aktiv=True)


def v2_entfernen(apps, schema_editor):
    Verfahrensordnung = apps.get_model("verfahren", "Verfahrensordnung")
    Verfahrensordnung.objects.filter(policy_id="sachantrag-standard", version=2).delete()
    Verfahrensordnung.objects.filter(policy_id="sachantrag-standard", version=1).update(aktiv=True)


class Migration(migrations.Migration):
    dependencies = [("verfahren", "0007_vollzugseintrag")]
    operations = [migrations.RunPython(v2_anlegen, v2_entfernen)]
