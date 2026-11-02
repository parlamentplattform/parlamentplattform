"""Ein einzelnes Dokument aus der benannten Original-XML-Quelle übernehmen."""

from django.core.management.base import BaseCommand, CommandError

from faktenbasis.models import Norm
from faktenbasis.ris import RisFehler
from faktenbasis.volltext import importieren


class Command(BaseCommand):
    help = "Einen amtlichen Dokumenttext zu einem vorhandenen Metadaten-Schnappschuss abrufen."

    def add_arguments(self, parser):
        parser.add_argument("--norm", required=True, type=int, help="ID des Metadaten-Schnappschusses")

    def handle(self, *args, **options):
        try:
            norm = Norm.objects.get(pk=options["norm"])
        except Norm.DoesNotExist as fehler:
            raise CommandError("Metadaten-Schnappschuss nicht gefunden; kein Abruf.") from fehler
        try:
            lauf = importieren(norm)
        except RisFehler as fehler:
            raise CommandError(f"Dokumenttext-Abruf fehlgeschlagen ({fehler.code}); kein Text übernommen.") from fehler
        self.stdout.write(
            f"Abruf {lauf.pk}: Dokumenttext {lauf.inhalt_id}, neu: {lauf.neu}. "
            "Einzeldokument; keine vollständige Rechtsvorschrift oder geprüfte Antragszuordnung."
        )
