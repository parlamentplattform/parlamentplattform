"""Demo-Daten für die lokale Entwicklung: `python manage.py demo_seed`.

Erzeugt eine aktive Verfahrensordnung, fünf geprüfte Mitglieder und drei
Anträge in verschiedenen Phasen — genug, um jede Ansicht und den kompletten
Durchlauf zu sehen. Läuft nur auf leerer Datenbank sinnvoll; idempotent genug
für den Alltag (get_or_create).
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from mitglieder.models import Identitaetsstufe, Mitglied
from verfahren.models import Antrag, Verfahrensordnung, antrag_einbringen, stimme_abgeben


class Command(BaseCommand):
    help = "Erzeugt Demo-Daten für die lokale Entwicklung."

    def handle(self, *args, **opts):
        ordnung, _ = Verfahrensordnung.objects.get_or_create(
            policy_id="sachantrag-standard",
            version=1,
            defaults={
                "regeln": {
                    "id": "sachantrag-standard",
                    "version": 1,
                    "unterstuetzung_schwelle": 3,
                    "unterstuetzung_frist_tage": 14,
                    "beratung_tage": 21,
                    "abstimmung_tage": 7,
                    "mindestbeteiligung": 0.05,
                    "mehrheitsbasis": "ja_nein",
                    "wiedereinbringung_sperre_monate": 6,
                },
                "aktiv": True,
            },
        )
        leute = []
        for i in range(1, 6):
            m, neu = Mitglied.objects.get_or_create(
                username=f"demo{i}",
                defaults={
                    "beitritt": date.today() - timedelta(days=200),
                    "identitaetsstufe": Identitaetsstufe.GEPRUEFT,
                    "pseudonym_oeffentlich": f"Mitglied {i}",
                },
            )
            if neu:
                m.set_unusable_password()
                m.save()
            leute.append(m)

        if not Antrag.objects.exists():
            a1 = antrag_einbringen(
                leute[0],
                "Sitzungsprotokolle binnen 48 Stunden veröffentlichen",
                "Die DDÖ veröffentlicht Protokolle aller Ratssitzungen binnen 48 Stunden auf der Plattform.",
                "Transparenz ist unser Kerngeschäft — sie beginnt bei uns selbst.",
                ordnung,
            )
            a2 = antrag_einbringen(
                leute[1],
                "Testlauf: monatlicher öffentlicher Entwicklungsbericht",
                "Das Entwicklungsteam berichtet monatlich öffentlich über Fortschritt, Probleme und nächste Schritte.",
                "",
                ordnung,
            )
            for m in leute[:4]:
                a2.unterstuetzungen.create(mitglied=m)
            a2.fortschreiben()  # Schwelle 3 erreicht -> Beratung
            a2.kommentare.create(
                mitglied=leute[2],
                text="Guter Vorschlag — ich würde den Bericht um eine feste Rubrik "
                "„Was schiefging“ ergänzen. Ehrlichkeit über Fehler schafft mehr "
                "Vertrauen als jede Erfolgsmeldung.",
            )
            a2.kommentare.create(
                mitglied=leute[3],
                text="Einverstanden, aber bitte als leichtgewichtiges Format: eine Seite, "
                "immer gleiche Struktur, damit der Aufwand klein bleibt und der "
                "Bericht wirklich jeden Monat erscheint.",
            )

            a3 = antrag_einbringen(
                leute[2],
                "Abgeschlossenes Beispiel: Namenskonvention des Prototyps",
                "Der Prototyp führt den Namen ParlamentPlattform.",
                "",
                ordnung,
            )
            for m in leute[:4]:
                a3.unterstuetzungen.create(mitglied=m)
            # Verfahren im Zeitraffer durchspielen (kontrollierte Uhr, keine Wartezeit):
            a3.fortschreiben()
            a3.phase_beginn = timezone.now() - timedelta(days=22)
            a3.save(update_fields=["phase_beginn"])
            a3.fortschreiben()  # -> Abstimmung (stellt die Stimmberechtigten automatisch fest)
            for m, wahl in zip(leute, ["ja", "ja", "ja", "nein", "enthaltung"], strict=True):
                stimme_abgeben(a3, m, wahl)
            a3.phase_beginn = timezone.now() - timedelta(days=8)
            a3.save(update_fields=["phase_beginn"])
            a3.fortschreiben()  # -> Ergebnis
            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo bereit: {a1.pk} (Unterstützung), {a2.pk} (Beratung), {a3.pk} ({a3.phase})."
                )
            )
        else:
            self.stdout.write("Anträge existieren bereits — nichts zu tun.")
