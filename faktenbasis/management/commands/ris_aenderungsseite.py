from datetime import date
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from faktenbasis.ris import HOECHSTBYTES, RisFehler
from faktenbasis.ris_historie import Leermeldung, abrufen, importieren


class Command(BaseCommand):
    help = gettext_lazy("Eine ausgewählte RIS-Änderungsseite der Bundesnormen erfassen.")

    def add_arguments(self, parser):
        parser.add_argument("--tag", required=True, type=date.fromisoformat, metavar="JJJJ-MM-TT")
        parser.add_argument("--seite", required=True, type=int)
        quelle = parser.add_mutually_exclusive_group()
        quelle.add_argument("--datei", type=Path)
        quelle.add_argument("--abrufen", action="store_true", help=gettext_lazy("Eine Seite direkt beim RIS abrufen."))
        parser.add_argument("--sha256")

    def handle(self, *args, **options):
        dateipfad, direkt = options["datei"], options["abrufen"]
        if (dateipfad is not None) == direkt:
            raise CommandError(_("Wählen Sie eine lokale Datei oder den RIS-Einzelabruf."))
        try:
            tag, seite, pruefsumme = options["tag"], options["seite"], options["sha256"]
            if direkt:
                stand = abrufen(tag, seite, erwartete_pruefsumme=pruefsumme)
            else:
                with Path(dateipfad).open("rb") as datei:
                    daten = datei.read(HOECHSTBYTES + 1)
                stand = importieren(tag, seite, daten, erwartete_pruefsumme=pruefsumme)
        except OSError as fehler:
            raise CommandError(_("Die RIS-Änderungsdatei ließ sich nicht lesen.")) from fehler
        except RisFehler as fehler:
            raise CommandError(_("RIS-Änderungsseite abgewiesen (%(grund)s).") % {"grund": fehler.code}) from fehler
        if isinstance(stand, Leermeldung):
            meldung = _("RIS meldet für diese Abfrage keine Treffer. SHA-256 %(hash)s.")
        else:
            meldung = _("RIS-Änderungsseite gespeichert. SHA-256 %(hash)s.")
        self.stdout.write(meldung % {"hash": stand.original_sha256})
