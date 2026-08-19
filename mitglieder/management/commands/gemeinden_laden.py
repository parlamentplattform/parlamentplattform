"""Importiert das amtliche Gemeindeverzeichnis aus daten/gemeinden.csv (idempotent)."""

import csv

from django.conf import settings
from django.core.management.base import BaseCommand

from mitglieder.models import Bundesland, Gemeinde

LAND_ZU_CODE = {wert.label: wert.value for wert in Bundesland}


class Command(BaseCommand):
    help = "Importiert bzw. aktualisiert das amtliche Gemeindeverzeichnis."

    def handle(self, *args, **opts):
        pfad = settings.BASE_DIR / "daten" / "gemeinden.csv"
        neu = geaendert = 0
        with open(pfad, encoding="utf-8") as f:
            zeilen = [z for z in f if not z.startswith("#")]
        for reihe in csv.DictReader(zeilen, delimiter=";"):
            _, erstellt = Gemeinde.objects.update_or_create(
                kennziffer=reihe["kennziffer"],
                defaults={
                    "name": reihe["name"],
                    "bezirk": reihe["bezirk"],
                    "bundesland": LAND_ZU_CODE[reihe["bundesland"]],
                },
            )
            neu += int(erstellt)
            geaendert += int(not erstellt)
        self.stdout.write(self.style.SUCCESS(f"Gemeindeverzeichnis: {neu} neu, {geaendert} aktualisiert."))
