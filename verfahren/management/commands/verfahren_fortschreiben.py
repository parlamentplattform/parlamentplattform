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


def einzeln_fortzuschreiben(antraege, jetzt, faellige_beschluesse=None) -> set[int]:
    """Die Kennungen der Anträge, an denen in diesem Lauf etwas fällig sein KANN (Gesamtprüfung GP-163).

    Der Wächter schrieb jeden laufenden Antrag einzeln fort — rund neun Abfragen je Antrag und Takt,
    auch wenn nichts fällig war. Hier wird mit wenigen Sammelabfragen ausgewählt; nur die Auswahl
    geht den bisherigen Weg (`Antrag.fortschreiben`), unverändert. Im Zweifel einzeln — ein Antrag
    bleibt nur liegen, wenn feststeht, dass seine Fortschreibung nichts täte:

    - kein fälliger offener Gremienbeschluss zu ihm (sonst reiht `fortschreiben` ihn ein, GP-004),
    - keine Aussetzung, weder laufend noch beendet (sonst rechnet der Phasenbeginn anders, § 6 Abs 3 lit d),
    - in der Beratung kein Entwurf (die Schleife hat eigene Fristen, § 5 Abs 12),
    - keine Vertrauensfrage (sie hält das Erreichen der Schwelle eigens fest, § 7 Abs 10 lit c),
    - und der Kern (`naechster_uebergang`) nennt mit dem gespeicherten Phasenbeginn und der gezählten
      Unterstützung keinen Übergang. Dieselbe Funktion entscheidet auch in `fortschreiben`; die
      Unterstützungen aller Anträge zählt hier EINE Abfrage, mit demselben Filter wie dort.

    Lässt sich ein Antrag nicht beurteilen (etwa ein Schnappschuss der Regeln, den dieser Stand nicht
    lesen kann), geht er einzeln — dort steht der Fehler wie bisher im Protokoll."""
    from django.db.models import Count

    from plattform_core import naechster_uebergang
    from verfahren.models import Antragsart, Unterstuetzung

    einzeln: set[int] = set()
    if apps.is_installed("gremien"):
        from gremien.models import Aussetzung, Entwurf

        if faellige_beschluesse is not None:
            einzeln |= set(faellige_beschluesse.exclude(antrag_id=None).values_list("antrag_id", flat=True))
        einzeln |= set(Aussetzung.objects.filter(antrag__phase__in=LAUFENDE_PHASEN).values_list("antrag_id", flat=True))
        einzeln |= set(Entwurf.objects.filter(antrag__phase=Phase.BERATUNG.value).values_list("antrag_id", flat=True))
    unterstuetzungen = dict(
        Unterstuetzung.objects.filter(
            antrag__phase=Phase.UNTERSTUETZUNG.value, zurueckgezogen_am__isnull=True, mitglied__testkonto=False
        )
        .order_by()
        .values_list("antrag_id")
        .annotate(n=Count("id"))
    )
    for antrag in antraege:
        if antrag.pk in einzeln:
            continue
        if antrag.art == Antragsart.VERTRAUENSFRAGE:
            einzeln.add(antrag.pk)
            continue
        try:
            uebergang = naechster_uebergang(
                Phase(antrag.phase),
                antrag.phase_beginn,
                jetzt,
                antrag.policy(),
                unterstuetzungen=unterstuetzungen.get(antrag.pk, 0),
            )
        except Exception:
            # Abstimmungsfrist erreicht (der Kern verlangt dann die Auszählung) oder nicht zu beurteilen.
            einzeln.add(antrag.pk)
            continue
        if uebergang is not None:
            einzeln.add(antrag.pk)
    return einzeln


def alles_fortschreiben(jetzt=None, *, jeden_einzeln: bool = False) -> dict[str, int]:
    """Fristen, Entwurfsschleife, Gremienbeschlüsse, Aussetzungen und Parametertests auswerten.

    Ein Fehler trifft nur das Verfahren, in dem er entsteht: Jeder Schritt eines Antrags läuft in
    seiner eigenen Transaktion, jeder Nachlauf für sich; der Fehler steht im Protokoll und in
    `stand["fehler"]`, der Lauf geht weiter. Ohne diese Grenze hielt ein einziger werfender Antrag
    bei jedem Takt alle Anträge mit größerer Kennung und sämtliche Nachläufe an.

    Fällige Beschlüsse zu einem laufenden Antrag wertet schon dessen Fortschreibung aus, nach ihrer
    Frist zwischen die Phasenfristen gereiht (Gesamtprüfung GP-004); der Nachlauf schließt, was keinen
    laufenden Antrag hat. `stand["beschluesse"]` zählt beides.

    Einzeln fortgeschrieben wird nur, woran etwas fällig sein kann (`einzeln_fortzuschreiben`, GP-163);
    die Reihenfolge bleibt die der Kennungen. Jede Fortschreibung schloss nebenbei die von selbst
    abgelaufenen Aussetzungen ALLER Anträge — das geschieht für die übersprungenen Anträge weiter an
    derselben Stelle der Reihenfolge, aber einmal statt je Antrag. `jeden_einzeln` fährt den Lauf wie
    früher (jeder Antrag einzeln); der Endzustand ist derselbe, das hält ein Test fest."""
    jetzt = jetzt or timezone.now()
    stand = {
        "phasenwechsel": 0,
        "beschluesse": 0,
        "aussetzungen": 0,
        "parametertests": 0,
        "vertrauensfragen": 0,
        "fehler": 0,
    }
    faellige_beschluesse = None
    if apps.is_installed("gremien"):
        from gremien.models import BeschlussStatus, GremienBeschluss

        faellige_beschluesse = GremienBeschluss.objects.filter(status=BeschlussStatus.OFFEN, frist__lte=jetzt)
        faellig_vorher = faellige_beschluesse.count()
    antraege = list(Antrag.objects.filter(phase__in=LAUFENDE_PHASEN).order_by("pk"))
    einzeln = None if jeden_einzeln else einzeln_fortzuschreiben(antraege, jetzt, faellige_beschluesse)
    # Ob die abgelaufenen Aussetzungen zum Stand `jetzt` schon geschlossen sind. Jede Fortschreibung
    # eines Antrags tut das zuerst; danach kann sie selbst neue Lagen geschaffen haben.
    aussetzungen_geschlossen = False
    for antrag in antraege:
        if einzeln is not None and antrag.pk not in einzeln:
            # Nichts fällig. Was die Fortschreibung dieses Antrags sonst noch getan hätte, geschieht
            # hier einmal für alle Übersprungenen in Folge: abgelaufene Aussetzungen schließen.
            if not aussetzungen_geschlossen and apps.is_installed("gremien"):
                from gremien.models import aussetzungen_fortschreiben

                try:
                    with transaction.atomic():
                        aussetzungen_fortschreiben(jetzt)
                    aussetzungen_geschlossen = True
                except Exception:
                    log.exception("Schließen abgelaufener Aussetzungen gescheitert")
                    stand["fehler"] += 1
            continue
        aussetzungen_geschlossen = False
        # Einmal je Antrag genügt nicht immer: Wertet die Entwurfsschleife aus, ist danach
        # vielleicht schon der Phasenübergang fällig — so lange fortschreiben, bis nichts mehr passiert.
        # Jeder Schritt in seiner eigenen Transaktion, wie auf der Antragsseite: Scheitert ein
        # späterer Schritt, bleibt ein früherer, fälliger Übergang geschrieben.
        try:
            for _schritt in range(5):
                with transaction.atomic():
                    weiter = antrag.fortschreiben(jetzt)
                if not weiter:
                    break
                stand["phasenwechsel"] += 1
        except Exception:
            log.exception("Fortschreiben von Antrag %s gescheitert", antrag.pk)
            stand["fehler"] += 1
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
        if schluessel == "aussetzungen" and aussetzungen_geschlossen:
            # Zum Stand `jetzt` schon geschlossen, und seither hat nichts eine neue Lage geschaffen:
            # Der Nachlauf fände nichts (GP-163 — eine Abfrage auf Aussetzungen je Ruhelauf, nicht zwei).
            continue
        try:
            stand[schluessel] = nachlauf(jetzt)
            if stand[schluessel]:
                aussetzungen_geschlossen = False  # ein Nachlauf hat etwas bewirkt — neu hinsehen
        except Exception:
            log.exception("Nachlauf %s gescheitert", schluessel)
            stand["fehler"] += 1
            aussetzungen_geschlossen = False
    if faellige_beschluesse is not None:
        stand["beschluesse"] = max(stand["beschluesse"], faellig_vorher - faellige_beschluesse.count())
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
