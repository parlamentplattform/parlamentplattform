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
    Antragsart,
    Kategorie,
    KategorieAbo,
    Verfahrensordnung,
    antrag_einbringen,
    bewerbung_einreichen,
    bewerbung_zustimmen,
    kategorien_zuordnen,
    stimme_abgeben,
    vollzug_fortschreiben,
)


class Command(BaseCommand):
    help = "Erzeugt Demo-Daten für die lokale Entwicklung."

    def handle(self, *args, **opts):
        call_command("gemeinden_laden")
        ordnung, _ = Verfahrensordnung.objects.get_or_create(
            policy_id="sachantrag-standard",
            version=2,
            defaults={
                "regeln": {
                    "id": "sachantrag-standard",
                    "version": 2,
                    "unterstuetzung_schwelle": 3,
                    "unterstuetzung_frist_tage": 60,
                    "beratung_tage": 21,
                    "abstimmung_tage": 28,
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
                "Abgeschlossenes Beispiel: Namenskonvention der Plattform",
                "Die Plattform führt den Namen ParlamentPlattform.",
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
            a3.phase_beginn = timezone.now() - timedelta(days=30)
            a3.save(update_fields=["phase_beginn"])
            a3.fortschreiben()  # -> Ergebnis

            # Umsetzungsregister (F-55): der angenommene Antrag bekommt eine Vollzugsgeschichte
            vollzug_fortschreiben(
                a3,
                leute[0],
                "in_umsetzung",
                "Der Namenszug wird in allen Vorlagen, im Repository und auf der Website "
                "vereinheitlicht; Abschluss bis Monatsende geplant.",
            )
            vollzug_fortschreiben(
                a3,
                leute[0],
                "umgesetzt",
                "Alle Auftritte führen den Namen ParlamentPlattform — Beschluss vollzogen.",
            )

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

        # Mandats-Kandidatur (§ 7 Abs 1, F-70) — eigener Wächter, damit auch
        # bestehende Datenbanken die neue Antragsart als Testlauf bekommen.
        if not Antrag.objects.filter(art=Antragsart.MANDAT).exists():
            k1 = antrag_einbringen(
                leute[0],
                "Testlauf: Listenreihung Gemeinderat St. Marienkirchen an der Polsenz",
                "Reihung des DDÖ-Wahlvorschlags für die nächste Gemeinderatswahl. "
                "Jedes wählbare Mitglied kann sich an diesem Antrag bewerben; die Mitglieder "
                "stimmen den Bewerbungen zu — die meiste Zustimmung führt die Liste an (§ 7 Abs 1).",
                "Das Parlament wird von Anfang an auch für Personenwahlen genutzt (Mandatar-Steuerung).",
                ordnung,
                ebene="gemeinde",
                gebiet="St. Marienkirchen an der Polsenz",
                art=Antragsart.MANDAT,
            )
            bewerbung_einreichen(
                k1, leute[1], "Seit drei Jahren im Gemeindeleben aktiv; ich stehe für offene Sitzungen."
            )
            bewerbung_einreichen(
                k1, leute[2], "Technikerin — ich will die Plattform-Beschlüsse in die Gemeindearbeit tragen."
            )
            for m in leute[:3]:
                k1.unterstuetzungen.create(mitglied=m)
            k1.fortschreiben()  # Schwelle -> Beratung
            k1.phase_beginn = timezone.now() - timedelta(days=22)
            k1.save(update_fields=["phase_beginn"])
            k1.fortschreiben()  # Beratungsfrist um -> Abstimmung
            for waehler, bewerber in ((leute[3], leute[1]), (leute[4], leute[1]), (leute[0], leute[2])):
                bewerbung_zustimmen(k1, waehler, k1.bewerbungen.get(mitglied=bewerber))
            kategorien_zuordnen(k1)
            self.stdout.write(
                self.style.SUCCESS(f"Mandats-Kandidatur bereit: {k1.pk} ({k1.phase}, 2 Bewerbungen).")
            )

        # Gremien-Werkstatt (Ring 0a, F-66) — eigener Wächter: Rollen auf Zeit
        # und ein Entwurfsfenster am Beratungs-Antrag, auch für bestehende Datenbanken.
        from gremien.models import Entwurf, EntwurfsFassung, Gremium, Rolle, standard_ende

        if not Rolle.objects.exists():
            for mitglied, gremium in (
                (leute[1], Gremium.EXPERTENRAT_1),
                (leute[2], Gremium.EXPERTENRAT_1),
                (leute[3], Gremium.EXPERTENRAT_2),
                (leute[0], Gremium.KOORDINATIONSRAT),
            ):
                Rolle.objects.create(
                    mitglied=mitglied, gremium=gremium, endet_am=standard_ende(), bestaetigt=True
                )
            beratung = (
                Antrag.objects.filter(phase="beratung", art=Antragsart.SACHE)
                .exclude(entwurf__isnull=False)
                .first()
            )
            if beratung is not None:
                entwurf = Entwurf.objects.create(antrag=beratung)
                grundlage = beratung.aktueller_text()
                EntwurfsFassung.objects.create(
                    entwurf=entwurf,
                    nummer=1,
                    wortlaut=grundlage.wortlaut if grundlage else "",
                    begruendung="Arbeitsgrundlage: übernommener Antragswortlaut.",
                    verfasst_von=leute[1],
                )
                entwurf.beitraege.create(
                    mitglied=leute[2],
                    text="Vorschlag: den Berichtsrhythmus präzisieren und eine feste Rubrik "
                    "„Was schiefging“ aufnehmen — das greift den Wunsch aus der Beratung auf.",
                )
            self.stdout.write(
                self.style.SUCCESS("Gremien bereit: 2× Gruppe 1, 1× Gruppe 2, 1× Koordinationsrat.")
            )

        # Abstimmungs-Chat (Ring 0a, FB-G6) — eigener Wächter: ein Antrag, dessen Vorschlag
        # den Unterstützern vorliegt, mit „Passt alles", Reaktionen und einer Kritik.
        from verfahren.chat import beitrag_schreiben, passt_alles_anlegen, reaktion_umschalten
        from verfahren.models import Reaktionsart

        if not Antrag.objects.filter(entwurf__status="unterstuetzer").exists():
            a6 = antrag_einbringen(
                leute[2],
                "Testlauf: Vorschlag des Expertenrats zur Fahrradabstellanlage",
                "Vor jedem Amtsgebäude der Gemeinde entsteht eine überdachte Abstellanlage für "
                "mindestens zwanzig Fahrräder.\n\n"
                "Die Anlage wird beleuchtet und ist rund um die Uhr zugänglich.",
                "",
                ordnung,
            )
            for m in leute[:4]:
                a6.unterstuetzungen.create(mitglied=m)
            a6.fortschreiben()  # Schwelle erreicht → Beratung
            a6.refresh_from_db()
            entwurf6 = Entwurf.objects.create(antrag=a6)
            grundlage = a6.aktueller_text()
            EntwurfsFassung.objects.create(
                entwurf=entwurf6,
                nummer=1,
                wortlaut=(grundlage.wortlaut if grundlage else "").replace(
                    "mindestens zwanzig Fahrräder", "mindestens dreißig Fahrräder"
                )
                + "\n\nDie Gemeinde berichtet jährlich über Auslastung und Instandhaltung.",
                begruendung="Der Expertenrat hat die Zahl an den erhobenen Bedarf angepasst und "
                "eine Berichtspflicht ergänzt.",
                verfasst_von=leute[1],
            )
            entwurf6.einreichen()  # ohne Vollzugsbezug: direkt zu den Unterstützern
            passt = passt_alles_anlegen(a6, entwurf6)
            for m in leute[:2]:
                reaktion_umschalten(passt, m, Reaktionsart.ZUSTIMMUNG)
            reaktion_umschalten(passt, leute[3], Reaktionsart.ABLEHNUNG)
            kritik = beitrag_schreiben(
                a6,
                leute[3],
                "Dreißig Stellplätze sind vor dem kleinen Amtshaus zu viel — dort passen "
                "höchstens zwölf, ohne den Gehsteig zu verstellen.",
                ist_kritik=True,
                bezug_absatz=1,
            )
            reaktion_umschalten(kritik, leute[3], Reaktionsart.ZUSTIMMUNG)
            beitrag_schreiben(a6, leute[0], "Die Berichtspflicht finde ich gut — die bleibt hoffentlich drin.")
            self.stdout.write(
                self.style.SUCCESS(f"Abstimmungs-Chat bereit: Antrag {a6.pk} (Vorschlag Runde 1).")
            )

        # Parameterregister (Ring 0b, F-68): Erstbestand sicherstellen — läuft
        # bei jedem Deploy mit, bestehende Werte bleiben unangetastet.
        from parameter.models import erstbestand_sicherstellen

        neu = erstbestand_sicherstellen()
        if neu:
            self.stdout.write(self.style.SUCCESS(f"Parameterregister: {neu} Einträge angelegt."))
