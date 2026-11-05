"""Ein ausdrücklich ausgelöster Einzelbezug aus dem RIS."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from faktenbasis.importieren import importieren
from faktenbasis.ris import GESETZESNUMMER, RisFehler


class Command(BaseCommand):
    help = gettext_lazy("Eine ausdrücklich gewählte Seite amtlicher Bundesrechts-Metadaten übernehmen; höchstens zehn Dokumente.")

    def add_arguments(self, parser):
        parser.add_argument("--gesetzesnummer", required=True)
        parser.add_argument("--stand", required=True, help="Stichtag YYYY-MM-DD")
        parser.add_argument("--seite", type=int, default=1, help=gettext_lazy("RIS-Seite; ohne Angabe Seite 1."))

    def handle(self, *args, **options):
        nummer = options["gesetzesnummer"]
        if not GESETZESNUMMER.fullmatch(nummer):
            raise CommandError(_("Gesetzesnummer muss aus acht Ziffern bestehen."))
        try:
            stand = date.fromisoformat(options["stand"])
            if stand.isoformat() != options["stand"]:
                raise ValueError
        except ValueError as fehler:
            raise CommandError(_("Stichtag muss YYYY-MM-DD entsprechen.")) from fehler
        try:
            lauf = importieren(nummer, stand, seite=options["seite"])
        except RisFehler as fehler:
            raise CommandError(_("RIS-Import fehlgeschlagen (%(code)s); keine Norm übernommen.") % {"code": fehler.code}) from fehler
        self.stdout.write(
            _("Import %(import)s, RIS-Seite %(seite)s: %(gelesen)s von %(treffer)s Dokumenten gelesen, %(neu)s neu. Nur Metadaten; keine vollständige Rechtsvorschrift und keine geprüfte Antragszuordnung.")
            % {"import": lauf.pk, "seite": lauf.seite, "gelesen": lauf.gelesen, "treffer": lauf.treffer, "neu": lauf.neu}
        )
