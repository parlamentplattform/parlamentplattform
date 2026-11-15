import json
from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from faktenbasis.ris_historie import tag_pruefen
from plattform_core.faktenbestand import BestandsFehler
from plattform_core.ris_historie import TagesabgleichFehler


class Command(BaseCommand):
    help = gettext_lazy("Einen ausdrücklich gewählten Satz archivierter RIS-Änderungsseiten abgleichen.")

    def add_arguments(self, parser):
        parser.add_argument("--tag", required=True, type=date.fromisoformat, metavar="JJJJ-MM-TT")
        parser.add_argument("--beleg", required=True, action="append", type=int, metavar="DATENSATZ")
        parser.add_argument("--normbestand", action="store_true", help=gettext_lazy("Passende lokale Bundes-Normstände mit ausgeben."))
        parser.add_argument(
            "--originale-pruefen", action="store_true",
            help=gettext_lazy("Archivierte Originaldateien und gespeicherte Verweise abgleichen."),
        )

    def handle(self, *args, **options):
        try:
            ergebnis = tag_pruefen(
                options["tag"], options["beleg"], mit_normbestand=options["normbestand"],
                mit_originalen=options["originale_pruefen"],
            )
        except (TagesabgleichFehler, BestandsFehler) as fehler:
            raise CommandError(_("RIS-Seitensatz abgewiesen (%(grund)s).") % {"grund": str(fehler)}) from fehler
        self.stdout.write(json.dumps(ergebnis, ensure_ascii=False, sort_keys=True))
