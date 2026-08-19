"""Lädt den Kategorienbaum aus policies/kategorien-v*.yaml in die Datenbank.

Idempotent: vorhandene Kategorien (per Slug) werden aktualisiert, neue angelegt,
nicht mehr geführte deaktiviert (nie gelöscht — Zuordnungen bleiben erhalten).
Der Baum (Haupt- → Unter- → Detailkategorien) wird rekursiv importiert.
Aufruf: `python manage.py kategorien_laden` (nimmt die höchste Version)."""

from pathlib import Path

import yaml
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from verfahren.models import Kategorie


class Command(BaseCommand):
    help = "Importiert bzw. aktualisiert den Kategorienbaum aus policies/kategorien-v*.yaml."

    def add_arguments(self, parser):
        parser.add_argument("--datei", default=None, help="Pfad zu einer bestimmten Kategorien-Datei.")

    def handle(self, *args, **opts):
        if opts["datei"]:
            pfad = Path(opts["datei"])
        else:
            kandidaten = sorted((settings.BASE_DIR / "policies").glob("kategorien-v*.yaml"))
            if not kandidaten:
                raise CommandError("Keine policies/kategorien-v*.yaml gefunden.")
            pfad = kandidaten[-1]
        daten = yaml.safe_load(pfad.read_text(encoding="utf-8"))

        gesehen: set[str] = set()
        zaehler = {"neu": 0, "geaendert": 0}
        platznummer = {"n": 0}

        def importieren(eintrag: dict, eltern: Kategorie | None):
            platznummer["n"] += 1
            gesehen.add(eintrag["slug"])
            kategorie, erstellt = Kategorie.objects.update_or_create(
                slug=eintrag["slug"],
                defaults={
                    "name": eintrag["name"],
                    "eltern": eltern,
                    "beschreibung": eintrag.get("beschreibung", ""),
                    "eurovoc": "; ".join(eintrag.get("eurovoc", [])),
                    "schlagworte": eintrag.get("schlagworte", []),
                    "reihenfolge": platznummer["n"],
                    "aktiv": True,
                },
            )
            zaehler["neu" if erstellt else "geaendert"] += 1
            for kind in eintrag.get("unterkategorien", []):
                importieren(kind, kategorie)

        for eintrag in daten["lebensbereiche"]:
            importieren(eintrag, None)

        deaktiviert = Kategorie.objects.exclude(slug__in=gesehen).filter(aktiv=True).update(aktiv=False)
        self.stdout.write(
            self.style.SUCCESS(
                f"Kategorienbaum aus {pfad.name} (Version {daten.get('version')}): "
                f"{zaehler['neu']} neu, {zaehler['geaendert']} aktualisiert, {deaktiviert} deaktiviert."
            )
        )
