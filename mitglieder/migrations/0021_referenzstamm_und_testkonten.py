"""Fester Beitragsreferenz-Stamm und Stilllegung der Demo-Konten (Bestandsaufnahme 28.9.2026).

1. `beitragsreferenz_stamm`: Der Stamm der persönlichen Beitragsreferenz (F-38) hing bis 0.49 am
   Anmeldenamen; ein Adresswechsel (F-51) änderte ihn still, und gedruckte QR-Codes oder
   Daueraufträge wurden unzuordenbar (Befund A12). Der heute gültige Stamm wird für jedes Konto
   festgeschrieben — Bestandsreferenzen bleiben damit exakt gleich.
2. Die Demo-Konten des Aufbaus (demo1…demo5, example.org) werden stillgelegt: Testkonto, nicht
   anmeldbar, Rollen beendet, Fachlisteneintrag gestrichen. Ihre Beiträge zu Verfahren bleiben
   stehen (Grundregel 7: nichts wird gelöscht, was Verfahren betrifft); der Gründer hat die
   Stilllegung am 28.9.2026 freigegeben („Die Testkonten dürfen gelöscht werden“). Idempotent.

Ohne Rückweg: Er löschte den eingefrorenen Stamm, und ein erneutes Vorwärts leitete ihn aus dem
dann gültigen Anmeldenamen neu ab — nach einem Adresswechsel ein anderer als der gedruckte.
"""

import hashlib

from django.db import migrations, models
from django.utils import timezone

DEMO_NAMEN = [f"demo{i}" for i in range(1, 6)]


def stamm(pk: int, username: str) -> str:
    return hashlib.sha256(f"ddoe-beitrag-{pk}-{username}".encode()).hexdigest()[:6].upper()


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


def vorwaerts(apps, schema_editor):
    Mitglied = apps.get_model("mitglieder", "Mitglied")
    Rolle = apps.get_model("gremien", "Rolle")
    Fachliste = apps.get_model("gremien", "Fachliste")
    db = schema_editor.connection.alias
    mitglieder = Mitglied.objects.using(db)

    for m in mitglieder.filter(beitragsreferenz_stamm="").order_by("pk").iterator():
        mitglieder.filter(pk=m.pk).update(beitragsreferenz_stamm=stamm(m.pk, m.username))

    heute = timezone.localdate()
    demos = list(
        mitglieder.filter(username__in=DEMO_NAMEN, email__iendswith="@example.org")
        .filter(models.Q(testkonto=False) | models.Q(is_active=True))
        .order_by("pk")
    )
    if not demos:
        return
    pks = [m.pk for m in demos]
    mitglieder.filter(pk__in=pks).update(testkonto=True, is_active=False)
    # Welche Rollen enden und welche Fachlisteneinträge gestrichen werden, steht im Sammeleintrag —
    # nur IDs, keine Namen.
    rollen = Rolle.objects.using(db).filter(mitglied_id__in=pks, beendet_grund="")
    rollen_ids = list(rollen.order_by("pk").values_list("pk", flat=True))
    rollen.update(beendet_grund="Testkonto stillgelegt (28.9.2026)")
    fachliste = Fachliste.objects.using(db).filter(mitglied_id__in=pks, gestrichen_am__isnull=True)
    fachliste_ids = list(fachliste.order_by("pk").values_list("pk", flat=True))
    fachliste.update(gestrichen_am=heute, gestrichen_grund="Testkonto stillgelegt (28.9.2026)")
    audit_anhaengen(apps, db, {
        "typ": "testkonten_stillgelegt", "konten": pks, "rollen": rollen_ids, "fachliste": fachliste_ids,
        "anlass": "Bestandsaufnahme 28.9.2026",
    })


class Migration(migrations.Migration):
    dependencies = [
        ("mitglieder", "0020_nummern_bestand"),
        ("gremien", "0017_rolle_ruht_anlass_vertrauensfrage_sperre"),
        ("verfahren", "0022_antragsart_vertrauensfrage_rueckgabezusage"),
    ]
    operations = [
        migrations.AddField(
            model_name="mitglied",
            name="beitragsreferenz_stamm",
            field=models.CharField(
                blank=True,
                default="",
                editable=False,
                help_text="Einmal vergebener Stamm der persönlichen Beitragsreferenz (F-38). Er bleibt bei jedem Adresswechsel gleich, damit Daueraufträge und gedruckte QR-Codes weiter zugeordnet werden.",
                max_length=6,
            ),
        ),
        migrations.AlterField(
            model_name="mitglied",
            name="testkonto",
            field=models.BooleanField(
                default=False,
                editable=False,
                help_text="Testkonto des Aufbaus (Demo-Daten, Konten vor dem Gründerkonto): keine Nummer, kein Ausweis, keine Post — und nie im Nenner der Stimmberechtigten oder in einer Mitgliederzahl (§ 4 Abs 4 lit a).",
            ),
        ),
        migrations.RunPython(vorwaerts),  # ohne Rückweg — siehe Docstring
    ]
