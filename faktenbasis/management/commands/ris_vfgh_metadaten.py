from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from faktenbasis.ris import HOECHSTBYTES, RisFehler
from faktenbasis.vfgh_import import importieren


class Command(BaseCommand):
    help = gettext_lazy("Eine einzelne lokale RIS-Metadatendatei zu einem VfGH-Entscheidungstext einlesen.")

    def add_arguments(self, parser):
        parser.add_argument("--dokumentnummer", required=True)
        parser.add_argument("--datei", required=True, type=Path)
        parser.add_argument("--sha256")

    def handle(self, *args, **options):
        try:
            with Path(options["datei"]).open("rb") as datei:
                daten = datei.read(HOECHSTBYTES + 1)
            stand = importieren(options["dokumentnummer"], daten, erwartete_pruefsumme=options["sha256"])
        except OSError as exc:
            raise CommandError(_("Die RIS-Metadatendatei ließ sich nicht lesen.")) from exc
        except RisFehler as exc:
            raise CommandError(_("VfGH-Metadaten abgewiesen (%(grund)s).") % {"grund": exc.code}) from exc
        self.stdout.write(_("VfGH-Beleg %(nummer)s gespeichert. SHA-256 %(hash)s.") % {
            "nummer": stand.dokumentnummer, "hash": stand.original_sha256,
        })
