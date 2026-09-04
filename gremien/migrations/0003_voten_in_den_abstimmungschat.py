"""Die Voten der Unterstützer wandern in den Abstimmungs-Chat (FB-G6).

Bisher entschieden die Unterstützer über ein Formular (annehmen / zurückgeben mit
Wunsch). Ab jetzt entscheiden sie im Chat: Zustimmung und Ablehnung zum Beitrag
„Passt alles", Wünsche als Kritik-Beiträge. Diese Migration überführt, was da ist —
gelöscht wird nichts (Grundregel 7): Die Voten bleiben als Nachweis stehen, sie
bekommen nur ihre Entsprechung im Chat.

Idempotent: Wo der Systembeitrag oder die Reaktion schon existiert, geschieht nichts.
"""

from django.db import migrations

PASST_ALLES = "✓ Passt alles — der Vorschlag kann so zur Endabstimmung."


def voten_uebernehmen(apps, schema_editor):
    Entwurf = apps.get_model("gremien", "Entwurf")
    Kommentar = apps.get_model("verfahren", "Kommentar")
    Reaktion = apps.get_model("verfahren", "Reaktion")

    for entwurf in Entwurf.objects.filter(status="unterstuetzer").select_related("antrag"):
        phase = f"vorschlag-r{entwurf.runde}"
        system = Kommentar.objects.filter(
            antrag=entwurf.antrag, system=True, phase=phase, archiviert_am__isnull=True
        ).first()
        if system is None:
            system = Kommentar.objects.create(
                antrag=entwurf.antrag, mitglied=None, text=PASST_ALLES, phase=phase, system=True
            )
        for votum in entwurf.unterstuetzer_voten.filter(runde=entwurf.runde):
            Reaktion.objects.get_or_create(
                kommentar=system,
                mitglied_id=votum.mitglied_id,
                defaults={
                    "art": "zustimmung" if votum.annehmen else "ablehnung",
                    "erstellt_am": votum.abgegeben_am,
                },
            )
            wunsch = (votum.wunsch or "").strip()
            if not wunsch:
                continue
            schon_da = Kommentar.objects.filter(
                antrag=entwurf.antrag, mitglied_id=votum.mitglied_id, phase=phase, ist_kritik=True, text=wunsch
            ).exists()
            if not schon_da:
                Kommentar.objects.create(
                    antrag=entwurf.antrag,
                    mitglied_id=votum.mitglied_id,
                    text=wunsch[:4000],
                    phase=phase,
                    ist_kritik=True,
                    bezug_absatz=1,  # der alte Wunsch trug keinen Textstellenbezug
                    erstellt_am=votum.abgegeben_am,
                )


def zurueck(apps, schema_editor):
    """Die Übernahme lässt sich zurücknehmen, ohne die Voten anzutasten."""
    Kommentar = apps.get_model("verfahren", "Kommentar")
    Kommentar.objects.filter(system=True).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("gremien", "0002_entwurfsbeitrag_ki_lauf"),
        ("verfahren", "0014_abstimmungschat"),
    ]

    operations = [migrations.RunPython(voten_uebernehmen, zurueck)]
