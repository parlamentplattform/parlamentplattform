"""Fällige Postaufträge bearbeiten (auch als unabhängiger Wartungslauf)."""
from django.core.management.base import BaseCommand

from mitglieder.postausgang import offene_zustellen


class Command(BaseCommand):
    def handle(self, *args, **options):
        self.stdout.write(str(offene_zustellen()))
