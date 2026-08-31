"""Kontoabgleich von Hand oder aus einem Zeitplan: `python manage.py beitraege_abrufen`.

Dünn um `bank.abgleich_ausfuehren()` — dieselbe Logik wie „Ich habe überwiesen"
und der nachholende Abgleich der Verwaltung. Gedacht für einen späteren
Zeitplan-Dienst; bis dahin genügen die anlassbezogenen Abrufe im Betrieb.
"""

from django.core.management.base import BaseCommand

from mitglieder import bank


class Command(BaseCommand):
    help = "Ruft die Umsätze des Vereinskontos ab und verbucht Beitragseingänge (F-59)."

    def handle(self, *args, **opts):
        neu, meldung = bank.abgleich_ausfuehren(erzwungen=True)
        if meldung == "ok":
            self.stdout.write(self.style.SUCCESS(f"Abgleich ok — {neu} neue(r) Eingang/Eingänge."))
        else:
            self.stdout.write(f"Kein Abgleich: {meldung}")
