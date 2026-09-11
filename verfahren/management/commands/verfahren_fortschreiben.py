"""Schreibt alle laufenden Verfahren fort: `python manage.py verfahren_fortschreiben`.

Die Phasenautomatik ist lazy — sie läuft, wenn jemand eine Antragsseite öffnet. Fristen werden
zwar rückwirkend zum Fristzeitpunkt wirksam (`plattform_core.phases`, Befund #33), aber je
länger niemand hinsieht, desto später sieht man das Ergebnis, und Folgefristen können schon
verstrichen sein, bevor sie überhaupt begonnen haben. Ein Cron, der diesen Befehl täglich (oder
öfter) aufruft, hält die Verspätung klein. Der Befehl tut nichts, was ein Seitenaufruf nicht
auch täte — er ist idempotent und schreibt nur, was fällig ist.
"""

from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils import timezone

from plattform_core import Phase
from verfahren.models import Antrag

LAUFENDE_PHASEN = (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value)


def alles_fortschreiben(jetzt=None) -> dict[str, int]:
    """Fristen, Entwurfsschleife, Gremienbeschlüsse, Aussetzungen und Parametertests auswerten."""
    jetzt = jetzt or timezone.now()
    stand = {"phasenwechsel": 0, "beschluesse": 0, "aussetzungen": 0, "parametertests": 0}
    for antrag in Antrag.objects.filter(phase__in=LAUFENDE_PHASEN).order_by("pk"):
        # Einmal je Antrag genügt nicht immer: Wertet die Entwurfsschleife aus, ist danach
        # vielleicht schon der Phasenübergang fällig — so lange fortschreiben, bis nichts mehr passiert.
        for _schritt in range(5):
            if not antrag.fortschreiben(jetzt):
                break
            stand["phasenwechsel"] += 1
    if apps.is_installed("gremien"):
        from gremien.models import GremienBeschluss, aussetzungen_fortschreiben, parametertests_fortschreiben

        stand["beschluesse"] = GremienBeschluss.faellige_abschliessen(jetzt)
        stand["aussetzungen"] = aussetzungen_fortschreiben(jetzt)
        stand["parametertests"] = parametertests_fortschreiben(jetzt)
    return stand


class Command(BaseCommand):
    help = "Wertet fällige Fristen aller laufenden Verfahren aus — für einen Cron; idempotent."

    def handle(self, *args, **opts):
        stand = alles_fortschreiben()
        self.stdout.write(
            self.style.SUCCESS(
                "Fortgeschrieben: {phasenwechsel} Übergänge, {beschluesse} Beschlüsse ausgewertet, "
                "{aussetzungen} Aussetzungen beendet, {parametertests} Parametertests fortgeschrieben.".format(**stand)
            )
        )
