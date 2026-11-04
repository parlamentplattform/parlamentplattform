"""Ausdrücklicher Einzelbezug; keine automatische Sammlung des Landesrechts."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from faktenbasis.importieren import importieren
from faktenbasis.landesrecht import BUNDESLAENDER
from faktenbasis.ris import RisFehler


class Command(BaseCommand):
    help = gettext_lazy("Eine Seite Landesrechts-Metadaten zu genau einem Bundesland übernehmen; höchstens zehn Dokumente.")

    def add_arguments(self, parser):
        parser.add_argument("--bundesland", required=True, choices=list(BUNDESLAENDER))
        parser.add_argument("--gesetzesnummer", required=True)
        parser.add_argument("--stand", required=True)
        parser.add_argument("--seite", type=int, default=1, help=gettext_lazy("RIS-Seite; ohne Angabe Seite 1."))

    def handle(self, *args, **options):
        try:
            stand = date.fromisoformat(options["stand"])
            if stand.isoformat() != options["stand"]:
                raise ValueError
        except ValueError as fehler:
            raise CommandError(_("Bitte einen Stichtag im Format JJJJ-MM-TT angeben.")) from fehler
        try:
            lauf = importieren(options["gesetzesnummer"], stand, bundesland=options["bundesland"], seite=options["seite"])
        except RisFehler as fehler:
            raise CommandError(_("Landesrechts-Import fehlgeschlagen (%(code)s); keine neuen Metadaten übernommen.")
                               % {"code": fehler.code}) from fehler
        self.stdout.write(_("Landesrechts-Import %(import)s, RIS-Seite %(seite)s: %(gelesen)s von %(treffer)s Dokumenten gelesen, %(neu)s neu.")
                          % {"import": lauf.pk, "seite": lauf.seite, "gelesen": lauf.gelesen, "treffer": lauf.treffer, "neu": lauf.neu})
