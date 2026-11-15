from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from faktenbasis.kundmachung import zuordnen
from faktenbasis.ris import HOECHSTBYTES, RisFehler


class Command(BaseCommand):
    help = gettext_lazy("Eine einzelne lokale RIS-Kundmachungsdatei dem gespeicherten Normstand zuordnen.")

    def add_arguments(self, parser):
        parser.add_argument("--norm", required=True, type=int)
        parser.add_argument("--datei", required=True, type=Path)
        parser.add_argument("--sha256")

    def handle(self, *args, **options):
        try:
            with Path(options["datei"]).open("rb") as datei:
                daten = datei.read(HOECHSTBYTES + 1)
            beleg = zuordnen(options["norm"], daten, erwartete_pruefsumme=options["sha256"])
        except OSError as exc:
            raise CommandError(_("Die RIS-Kundmachungsdatei ließ sich nicht lesen.")) from exc
        except RisFehler as exc:
            raise CommandError(_("Kundmachungsbeleg abgewiesen (%(grund)s).") % {"grund": exc.code}) from exc
        self.stdout.write(_("Kundmachungsbeleg %(nummer)s gespeichert. SHA-256 %(hash)s.") % {
            "nummer": beleg.dokumentnummer, "hash": beleg.original_sha256,
        })
