"""E-Mail-Einwilligung im Profil und Postaufträge je Anlass (Anweisung des Gründers 28.9.2026).

1. `Mitglied.post_einwilligung`: Darf die Plattform dem Mitglied E-Mails über das Verfahren schicken
   (neue Anträge aus der eigenen Region, Beitragserinnerungen)? Neue Konten entscheiden das bei der
   Registrierung (Voreinstellung: nein). Der Bestand wird auf „ja“ gesetzt — Gründer: „Die bisherigen
   Mitglieder haben bereits zugestimmt.“ Idempotent: Wer schon „ja“ trägt, bleibt unberührt; ein
   Audit-Eintrag ohne Personenbezug hält die Zahl der umgestellten Konten fest.
2. `Postauftrag.bezug` und `Postauftrag.antrag`: Der Schlüssel eines Auftrags ist nun (Mitglied, Art,
   Bezug) — leer bei den Kontobriefen, `antrag:<pk>` bei „Neuer Antrag in Ihrer Region“, `jahr:<Jahr>`
   bei der Beitragserinnerung. Bestehende Zeilen behalten den leeren Bezug.

Ohne Rückweg: Er löschte die Spalte `post_einwilligung` mit jeder seither getroffenen Entscheidung,
und das erneute Vorwärts machte aus jedem Nein ein Ja. Dazu scheiterte die alte Eindeutigkeit
(Mitglied, Art) am zweiten Auftrag je Anlass. Die Bestandseinwilligung läuft deshalb auch nur einmal:
Steht ihr Audit-Eintrag schon in der Kette, setzt sie nichts mehr.
"""

import django.db.models.deletion
from django.db import migrations, models
from django.utils import timezone

ANLASS = "Anweisung des Gründers 28.9.2026"


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


def bestand_einwilligen(apps, schema_editor) -> int:
    """Alle Konten, die vor dieser Migration bestanden, gelten als eingewilligt. Gibt die Zahl der
    umgestellten Konten zurück; beim zweiten Lauf null (idempotent) — auch dann, wenn seither jemand
    ohne Haken registriert oder im Profil abbestellt hat: Der Audit-Eintrag des ersten Laufs sperrt."""
    Mitglied = apps.get_model("mitglieder", "Mitglied")
    AuditEintrag = apps.get_model("verfahren", "AuditEintrag")
    db = schema_editor.connection.alias
    if AuditEintrag.objects.using(db).filter(ereignis__typ="post_einwilligung_bestand").exists():
        return 0
    anzahl = Mitglied.objects.using(db).filter(post_einwilligung=False).update(post_einwilligung=True)
    if anzahl:
        audit_anhaengen(apps, db, {"typ": "post_einwilligung_bestand", "konten": anzahl, "anlass": ANLASS})
    return anzahl


class Migration(migrations.Migration):
    dependencies = [
        ("mitglieder", "0021_referenzstamm_und_testkonten"),
        ("verfahren", "0023_hintergrundlauf"),
    ]
    operations = [
        migrations.AddField(
            model_name="mitglied",
            name="post_einwilligung",
            field=models.BooleanField(
                default=False,
                help_text="Darf die Plattform diesem Mitglied E-Mails über das Verfahren schicken — neue Anträge aus der eigenen Region, Beitragserinnerungen? Anmelde-, Bestätigungs-, Willkommens-, Freischaltungs- und Ausweisnachrichten gehen unabhängig davon (sie gehören zum Konto). Die Registrierung fragt den Haken ab (Voreinstellung: nein); der Bestand vor 0.50 hat laut Gründer bereits zugestimmt.",
            ),
        ),
        migrations.RunPython(bestand_einwilligen),  # ohne Rückweg — siehe Docstring
        migrations.AddField(
            model_name="postauftrag",
            name="bezug",
            field=models.CharField(blank=True, default="", max_length=40),
        ),
        migrations.AddField(
            model_name="postauftrag",
            name="antrag",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="postauftraege",
                to="verfahren.antrag",
            ),
        ),
        migrations.RemoveConstraint(model_name="postauftrag", name="postauftrag_einmal"),
        migrations.AddConstraint(
            model_name="postauftrag",
            constraint=models.UniqueConstraint(
                fields=("mitglied", "art", "bezug"), name="postauftrag_einmal_je_bezug"
            ),
        ),
    ]
