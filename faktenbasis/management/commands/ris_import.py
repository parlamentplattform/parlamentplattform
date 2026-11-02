"""Ein ausdrücklich ausgelöster Einzelbezug aus dem RIS."""

from datetime import date

from django.core.management.base import BaseCommand, CommandError

from faktenbasis.importieren import importieren
from faktenbasis.ris import GESETZESNUMMER, RisFehler


class Command(BaseCommand):
    help = "Eine Seite amtlicher Bundesrechts-Metadaten (maximal zehn Dokumente) importieren."

    def add_arguments(self, parser):
        parser.add_argument("--gesetzesnummer", required=True)
        parser.add_argument("--stand", required=True, help="Stichtag YYYY-MM-DD")

    def handle(self, *args, **options):
        nummer = options["gesetzesnummer"]
        if not GESETZESNUMMER.fullmatch(nummer):
            raise CommandError("Gesetzesnummer muss aus acht Ziffern bestehen.")
        try:
            stand = date.fromisoformat(options["stand"])
            if stand.isoformat() != options["stand"]:
                raise ValueError
        except ValueError as fehler:
            raise CommandError("Stichtag muss YYYY-MM-DD entsprechen.") from fehler
        try:
            lauf = importieren(nummer, stand)
        except RisFehler as fehler:
            raise CommandError(f"RIS-Import fehlgeschlagen ({fehler.code}); keine Norm übernommen.") from fehler
        self.stdout.write(
            f"Import {lauf.pk}: {lauf.gelesen} von {lauf.treffer} Dokumenten gelesen, {lauf.neu} neu. "
            "Nur Metadaten; keine vollständige Rechtsvorschrift und keine geprüfte Antragszuordnung."
        )
