"""Demo-Daten für die lokale Entwicklung: `python manage.py demo_seed`.

Erzeugt eine aktive Verfahrensordnung, fünf geprüfte Mitglieder und drei
Anträge in verschiedenen Phasen — genug, um jede Ansicht und den kompletten
Durchlauf zu sehen. Läuft nur auf leerer Datenbank sinnvoll; idempotent genug
für den Alltag (get_or_create).
"""

from datetime import date, timedelta

from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from mitglieder.models import Gemeinde, Identitaetsstufe, Mitglied
from verfahren.models import (
    Antrag,
    Kategorie,
    KategorieAbo,
    Verfahrensordnung,
    antrag_einbringen,
    kategorien_zuordnen,
    stimme_abgeben,
)


class Command(BaseCommand):
    help = "Erzeugt Demo-Daten für die lokale Entwicklung."

    def handle(self, *args, **opts):
        call_command("gemeinden_laden")
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
                    "email": f"demo{i}@example.org",
                    "beitritt": date.today() - timedelta(days=200),
                    "identitaetsstufe": Identitaetsstufe.GEPRUEFT,
                    "pseudonym_oeffentlich": f"Mitglied {i}",
                    "gemeinde": "St. Marienkirchen an der Polsenz",
                    "bundesland": "oberoesterreich",
                },
            )
            if neu:
                m.wohnsitz = Gemeinde.finden(m.gemeinde)[0]
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

            # a4: laufende Abstimmung, vom Integritätsrat hervorgehoben (Bereich b)
            a4 = antrag_einbringen(
                leute[3],
                "Jede Ratssitzung als Livestream mit Archiv",
                "Alle Sitzungen der Parteigremien werden live übertragen und dauerhaft archiviert. "
                "Ausnahmen nur bei Personaldebatten mit Persönlichkeitsrechten.",
                "Wer Transparenz verspricht, zeigt sich bei der Arbeit.",
                ordnung,
            )
            for m in leute[:3]:
                a4.unterstuetzungen.create(mitglied=m)
            a4.fortschreiben()
            a4.phase_beginn = timezone.now() - timedelta(days=22)
            a4.save(update_fields=["phase_beginn"])
            a4.fortschreiben()  # -> Abstimmung
            a4.hervorgehoben = True
            a4.hervorhebung_begruendung = (
                "Betrifft alle Gremien dauerhaft, hat aber bisher wenig Beteiligung. "
                "Beschluss IR-2026-03 vom 12.08.2026."
            )
            a4.save(update_fields=["hervorgehoben", "hervorhebung_begruendung"])
            stimme_abgeben(a4, leute[1], "ja")
            stimme_abgeben(a4, leute[2], "nein")

            # a5: regionaler Antrag (Bereich c)
            a5 = antrag_einbringen(
                leute[4],
                "Photovoltaik auf dem Dach des Gemeindeamts",
                "Die DDÖ-Mitglieder der Gemeinde sprechen sich dafür aus, das Dach des "
                "Gemeindeamts mit einer Photovoltaikanlage auszustatten und den Ertrag "
                "öffentlich auszuweisen.",
                "Kleine, sichtbare Projekte bauen Vertrauen in direkte Entscheidungen auf.",
                ordnung,
                ebene="gemeinde",
                gebiet="St. Marienkirchen an der Polsenz",
            )

            # Favoriten für das Demo-Mitglied 1 (Bereich a)
            a4.favoriten.create(mitglied=leute[0])
            a2.favoriten.create(mitglied=leute[0])

            # Lebensbereiche automatisch zuordnen (F-47) und abonnieren (F-46)
            call_command("kategorien_laden")
            for antrag in (a1, a2, a3, a4, a5):
                kategorien_zuordnen(antrag)
            for slug in ["energie", "umwelt-klima"]:
                KategorieAbo.objects.get_or_create(
                    kategorie=Kategorie.objects.get(slug=slug), mitglied=leute[0]
                )

            self.stdout.write(
                self.style.SUCCESS(
                    f"Demo bereit: {a1.pk} (Unterstützung), {a2.pk} (Beratung), {a3.pk} ({a3.phase}), "
                    f"{a4.pk} (Abstimmung, hervorgehoben), {a5.pk} (regional)."
                )
            )
        else:
            self.stdout.write("Anträge existieren bereits — nichts zu tun.")
