# Die offenen Einreich-Abstimmungen vor 0.45 werden in einen Beschluss übertragen (FB-I4).
#
# § 5 Abs 5: Ein laufendes Verfahren wird nicht mitten im Lauf umgestellt — wer in Runde n schon
# „Ja, einreichen" gesagt hatte, sagt es nach der Umstellung immer noch. Die Stimmen werden mit
# Vermerk übernommen; die alte Tabelle bleibt stehen (Grundregel 7). Rückwärts geschieht nichts:
# Die übertragenen Beschlüsse sind selbst Verfahrensdaten.

from datetime import timedelta

from django.db import migrations
from django.utils import timezone

KUERZEL = {"expertenrat1": "E1"}


def uebertragen(apps, schema_editor):
    Entwurf = apps.get_model("gremien", "Entwurf")
    EinreichStimme = apps.get_model("gremien", "EinreichStimme")
    GremienBeschluss = apps.get_model("gremien", "GremienBeschluss")
    GremienStimme = apps.get_model("gremien", "GremienStimme")
    EntwurfsFassung = apps.get_model("gremien", "EntwurfsFassung")
    jetzt = timezone.now()
    for entwurf in Entwurf.objects.filter(status="in_arbeit"):
        stimmen = list(EinreichStimme.objects.filter(entwurf=entwurf, runde=entwurf.runde).order_by("abgegeben_am"))
        if not stimmen:
            continue
        if GremienBeschluss.objects.filter(entwurf=entwurf, anlass="einreichung").exists():
            continue
        fassung = EntwurfsFassung.objects.filter(entwurf=entwurf).order_by("-nummer").first()
        if fassung is None:
            continue
        praefix = f"{KUERZEL['expertenrat1']}-{jetzt.year}-"
        laufend = GremienBeschluss.objects.filter(gremium="expertenrat1", nummer__startswith=praefix).count() + 1
        titel = entwurf.antrag.titel
        beschluss = GremienBeschluss.objects.create(
            gremium="expertenrat1",
            nummer=f"{praefix}{laufend:02d}",
            anlass="einreichung",
            gegenstand=f"Fassung {fassung.nummer} einreichen: {titel}"[:200],
            beschreibung="Übertragen aus der Einreich-Abstimmung vor 0.45 (Migration 0013).",
            optionen=[{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}],
            frist=jetzt + timedelta(days=7),
            antrag=entwurf.antrag,
            entwurf=entwurf,
            angelegt_von=stimmen[0].mitglied,
            angelegt_am=jetzt,
        )
        for stimme in stimmen:
            GremienStimme.objects.create(
                beschluss=beschluss,
                mitglied=stimme.mitglied,
                option="dafuer" if stimme.einverstanden else "dagegen",
                begruendung="Übernommen aus der Einreich-Abstimmung vor 0.45.",
                abgegeben_am=stimme.abgegeben_am,
            )


class Migration(migrations.Migration):
    dependencies = [
        ("gremien", "0012_koordinationsrat_verweise"),
    ]

    operations = [
        migrations.RunPython(uebertragen, migrations.RunPython.noop),
    ]
