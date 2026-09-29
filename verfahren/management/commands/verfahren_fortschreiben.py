"""Schreibt alle laufenden Verfahren fort: `python manage.py verfahren_fortschreiben`.

Die Phasenautomatik ist lazy — sie läuft, wenn jemand eine Antragsseite öffnet. Fristen werden
zwar rückwirkend zum Fristzeitpunkt wirksam (`plattform_core.phases`, Befund #33), aber je
länger niemand hinsieht, desto später sieht man das Ergebnis, und Folgefristen können schon
verstrichen sein, bevor sie überhaupt begonnen haben. Ein Cron, der diesen Befehl täglich (oder
öfter) aufruft, hält die Verspätung klein. Der Befehl tut nichts, was ein Seitenaufruf nicht
auch täte — er ist idempotent und schreibt nur, was fällig ist.
"""

import logging

from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from plattform_core import Phase
from verfahren.models import Antrag

log = logging.getLogger(__name__)

LAUFENDE_PHASEN = (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value)


def alles_fortschreiben(jetzt=None) -> dict[str, int]:
    """Fristen, Entwurfsschleife, Gremienbeschlüsse, Aussetzungen und Parametertests auswerten.

    Ein Fehler trifft nur das Verfahren, in dem er entsteht: Jeder Antrag läuft in seiner eigenen
    Transaktion, jeder Nachlauf für sich; der Fehler steht im Protokoll und in `stand["fehler"]`,
    der Lauf geht weiter. Ohne diese Grenze hielt ein einziger werfender Antrag bei jedem Takt
    alle Anträge mit größerer Kennung und sämtliche Nachläufe an."""
    jetzt = jetzt or timezone.now()
    stand = {
        "phasenwechsel": 0,
        "beschluesse": 0,
        "aussetzungen": 0,
        "parametertests": 0,
        "vertrauensfragen": 0,
        "fehler": 0,
    }
    for antrag in Antrag.objects.filter(phase__in=LAUFENDE_PHASEN).order_by("pk"):
        # Einmal je Antrag genügt nicht immer: Wertet die Entwurfsschleife aus, ist danach
        # vielleicht schon der Phasenübergang fällig — so lange fortschreiben, bis nichts mehr passiert.
        wechsel = 0
        try:
            with transaction.atomic():
                for _schritt in range(5):
                    if not antrag.fortschreiben(jetzt):
                        break
                    wechsel += 1
        except Exception:
            log.exception("Fortschreiben von Antrag %s gescheitert", antrag.pk)
            stand["fehler"] += 1
            continue
        stand["phasenwechsel"] += wechsel
    nachlaeufe = []
    if apps.is_installed("gremien"):
        from gremien import models as gremien

        nachlaeufe += [
            ("beschluesse", gremien.GremienBeschluss.faellige_abschliessen),
            ("aussetzungen", gremien.aussetzungen_fortschreiben),
            ("parametertests", gremien.parametertests_fortschreiben),
        ]
    if apps.is_installed("mandatare"):
        from mandatare import models as mandatare

        # Zweite Stufe der Wirkungen einer verlorenen Vertrauensfrage (§ 7 Abs 10 lit f):
        # nach der Anfechtungsfrist enden ruhende Rollen, nach 30 Tagen endet die Vertretung.
        nachlaeufe.append(("vertrauensfragen", mandatare.vertrauensfragen_fortschreiben))
    for schluessel, nachlauf in nachlaeufe:
        try:
            stand[schluessel] = nachlauf(jetzt)
        except Exception:
            log.exception("Nachlauf %s gescheitert", schluessel)
            stand["fehler"] += 1
    return stand


class Command(BaseCommand):
    help = "Wertet fällige Fristen aller laufenden Verfahren aus — für einen Cron; idempotent."

    def handle(self, *args, **opts):
        stand = alles_fortschreiben()
        self.stdout.write(
            self.style.SUCCESS(
                "Fortgeschrieben: {phasenwechsel} Übergänge, {beschluesse} Beschlüsse ausgewertet, "
                "{aussetzungen} Aussetzungen beendet, {parametertests} Parametertests fortgeschrieben, "
                "{vertrauensfragen} Vertrauensfragen fortgeschrieben.".format(**stand)
            )
        )
