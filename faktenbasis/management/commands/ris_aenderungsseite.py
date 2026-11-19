from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from faktenbasis.ris import HOECHSTBYTES, RisFehler
from faktenbasis.ris_historie import importieren


class Command(BaseCommand):
    help = gettext_lazy("Eine einzelne lokale RIS-Änderungsseite der Bundesnormen archivieren.")

    def add_arguments(self, parser):
        parser.add_argument("--tag", required=True, type=date.fromisoformat, metavar="JJJJ-MM-TT")
        parser.add_argument("--seite", required=True, type=int)
        parser.add_argument("--datei", required=True, type=Path)
        parser.add_argument("--sha256")

    def handle(self, *args, **options):
        try:
            with Path(options["datei"]).open("rb") as datei:
                daten = datei.read(HOECHSTBYTES + 1)
            stand = importieren(options["tag"], options["seite"], daten, erwartete_pruefsumme=options["sha256"])
        except OSError as fehler:
            raise CommandError(_("Die RIS-Änderungsdatei ließ sich nicht lesen.")) from fehler
        except RisFehler as fehler:
            raise CommandError(_("RIS-Änderungsseite abgewiesen (%(grund)s).") % {"grund": fehler.code}) from fehler
        self.stdout.write(_("RIS-Änderungsseite gespeichert. SHA-256 %(hash)s.") % {"hash": stand.original_sha256})
