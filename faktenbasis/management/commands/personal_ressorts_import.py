from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from faktenbasis.ressortimport import amtlich_importieren, datei_importieren


class Command(BaseCommand):
    help = gettext_lazy("Die bekannte amtliche Personal-Ressorttabelle ausdrücklich übernehmen, keine Kapazitätsprognose.")

    def add_arguments(self, parser):
        quelle = parser.add_mutually_exclusive_group(required=True)
        quelle.add_argument("--datei", type=Path)
        quelle.add_argument("--amtliche-quelle", action="store_true")

    def handle(self, *args, **options):
        try:
            if options["datei"]:
                from faktenbasis.personalbeleg import HOECHSTBYTES

                with options["datei"].open("rb") as datei:
                    daten = datei.read(HOECHSTBYTES + 1)
                lauf = datei_importieren(daten)
            else:
                lauf = amtlich_importieren()
        except (ValueError, OSError) as fehler:
            raise CommandError(_("Die bekannte amtliche Personal-Ressorttabelle konnte nicht übernommen werden.")) from fehler
        self.stdout.write(_("Ressorttabelle übernommen; Abruf %(abruf)s, Tabellenstand %(inhalt)s, neu %(neu)s.") % {
            "abruf": lauf.pk, "inhalt": lauf.inhalt_id, "neu": lauf.neu,
        })
