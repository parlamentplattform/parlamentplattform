"""Verfahrensdaten: Anträge, Unterstützungen, Stimmen, Audit-Log.

Die fachliche Logik (Phasen, Fristen, Auszählung) liegt NICHT hier, sondern in
plattform_core — diese Modelle speichern Zustand und rufen den Kern auf.
Zwei bewusste Designentscheidungen:

1. `policy_snapshot`: Beim Einbringen wird die gültige Policy als JSON-Kopie
   gespeichert (§ 5 Abs 5). Alle späteren Berechnungen lesen ausschließlich
   diese Kopie.

2. Stimmen sind zweigeteilt (F-25): `Stimmabgabe` enthält Pseudonym und Stimme
   (und wird veröffentlicht), `StimmRegister` enthält die Zuordnung
   Mitglied ↔ Pseudonym je Antrag (zugriffsbeschränkt, nie veröffentlicht).
   Die Verbindung beider Tabellen ist der einzige Weg vom Menschen zur Stimme —
   und genau dieser Zugriff ist protokollierungspflichtig.
"""

from __future__ import annotations

import dataclasses
import math
import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, models, transaction
from django.db.models.fields.json import KeyTransform
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from plattform_core import (
    GENESIS,
    Phase,
    Policy,
    auszaehlen,
    ereignis_hash,
    naechster_uebergang,
)
from plattform_core import (
    Stimme as KernStimme,
)
from plattform_core.phases import stimme_zulaessig


class Verfahrensordnung(models.Model):
    """Eine Version der maschinenlesbaren Verfahrensregeln (Quelle: policies/*.yaml,
    beschlossen von der Mitgliederversammlung)."""

    policy_id = models.SlugField(max_length=60)
    version = models.PositiveIntegerField()
    regeln = models.JSONField(help_text="Serialisierte Policy — validiert gegen plattform_core.Policy.")
    beschlossen_am = models.DateTimeField(null=True, blank=True)
    aktiv = models.BooleanField(default=False)

    class Meta:
        unique_together = [("policy_id", "version")]
        verbose_name = "Verfahrensordnung"
        verbose_name_plural = "Verfahrensordnungen"

    def __str__(self) -> str:
        return f"{self.policy_id} v{self.version}{' (aktiv)' if self.aktiv else ''}"

    def als_policy(self) -> Policy:
        return Policy.aus_dict(self.regeln)


class Ebene(models.TextChoices):
    """Territoriale Ebene eines Antrags (§ 14; Bereich c des Hauptfensters, F-43)."""

    BUND = "bund", _("Bund")
    LAND = "land", _("Land")
    BEZIRK = "bezirk", _("Bezirk")
    GEMEINDE = "gemeinde", _("Gemeinde")


class Kategorie(models.Model):
    """Ein Lebensbereich des Kategoriesystems (F-45, ADR-007).

    Quelle ist policies/kategorien-v*.yaml (versioniert, per Management-Befehl
    `kategorien_laden` importiert). Slugs sind stabil über Versionen hinweg;
    nicht mehr geführte Bereiche werden deaktiviert, nie gelöscht — bestehende
    Zuordnungen bleiben nachvollziehbar."""

    slug = models.SlugField(max_length=60, unique=True)
    name = models.CharField(max_length=120)
    eltern = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="kinder",
        help_text="Übergeordnete Kategorie — leer bei Hauptkategorien. Der Baum trägt die Drill-down-Zuordnung.",
    )
    beschreibung = models.CharField(max_length=300, blank=True)
    eurovoc = models.CharField(
        max_length=300,
        blank=True,
        help_text="Zugeordnete EuroVoc-Domänen (Ebene 2, für Feinverschlagwortung und RIS/EUR-Lex-Anschluss).",
    )
    schlagworte = models.JSONField(
        default=list,
        blank=True,
        help_text="Schlagwortliste für die automatische Zuordnung — gepflegt in der YAML-Quelle.",
    )
    reihenfolge = models.PositiveIntegerField(default=0)
    aktiv = models.BooleanField(default=True)

    class Meta:
        ordering = ["reihenfolge", "slug"]
        verbose_name = "Kategorie"
        verbose_name_plural = "Kategorien"

    def __str__(self) -> str:
        return self.name

    @property
    def pfad(self) -> str:
        """Voller Pfad von der Wurzel, z. B. „Das gesellschaftliche Zusammenleben › … › Installateur“."""
        teile, knoten = [], self
        while knoten is not None:
            teile.append(knoten.name)
            knoten = knoten.eltern
        return " › ".join(reversed(teile))

    @property
    def pfad_kurz(self) -> str:
        """Die letzten drei Ebenen — genug Kontext für Chips und Meldungen,
        ohne die ganze Säulen-Kette auszuschreiben (F-45)."""
        return " › ".join(self.pfad.split(" › ")[-3:])

    def vorfahren(self) -> list[Kategorie]:
        """Stamm von der Wurzel bis zum Elternknoten (für die Brotkrume der Fokus-Ansicht)."""
        kette, knoten = [], self.eltern
        while knoten is not None:
            kette.append(knoten)
            knoten = knoten.eltern
        return list(reversed(kette))

    @property
    def tiefe(self) -> int:
        t, knoten = 0, self.eltern
        while knoten is not None:
            t += 1
            knoten = knoten.eltern
        return t

    def nachfahren_ids(self) -> set[int]:
        """IDs dieses Knotens und aller Unterkategorien (Abo eines Astes gilt für den ganzen Ast)."""
        ids, rand = {self.pk}, [self.pk]
        while rand:
            kinder = list(Kategorie.objects.filter(eltern_id__in=rand).values_list("id", flat=True))
            rand = [k for k in kinder if k not in ids]
            ids.update(kinder)
        return ids


class Antragsart(models.TextChoices):
    """§ 7 Abs 1 (E-2.5): Mandats-Kandidaturen laufen als eigene Antragsart —
    Bewerbungen statt Ja/Nein, Zustimmung je Bewerbung, die meiste Zustimmung
    gewinnt, die Zustimmungsreihenfolge ergibt die Reihung des Wahlvorschlags.

    § 7 Abs 9: Die Mandatsfrage ist die Ja-Nein-Frage, die ein Mandatar aus einem
    Instant-Report heraus stellt — ohne Unterstützungs- und Beratungsphase direkt
    in der Abstimmung (`mandatsfrage_eroeffnen`); ausgezählt wie ein Sachantrag.

    § 7 Abs 10: Die Vertrauensfrage ist der Antrag eines Mitglieds, einem Mandatsträger
    das Vertrauen zu versagen — Unterstützung durch fünf Prozent der für Personenwahlen
    Stimmberechtigten, keine Beratungsphase, Abstimmung als Personenwahl
    (`vertrauensfrage_einbringen`); ausgezählt wie ein Sachantrag, „angenommen“ heißt
    „verloren“. Dieselbe Art trägt den Bestätigungsantrag nach lit f Z 3."""

    SACHE = "sache", _("Sachantrag")
    MANDAT = "mandat", _("Mandats-Kandidatur")
    MANDATSFRAGE = "mandatsfrage", _("Mandatsfrage")
    VERTRAUENSFRAGE = "vertrauensfrage", _("Vertrauensfrage")


class Rueckgabezusage(models.TextChoices):
    """§ 7 Abs 3: die freiwillige, nicht einklagbare Erklärung, das Mandat nach einer verlorenen
    Vertrauensfrage binnen der Frist zurückzulegen — abgegeben oder nicht abgegeben, öffentlich.
    Leer heißt „unbekannt“: Bewerbungen aus der Zeit vor 0.48 tragen keine Erklärung."""

    UNBEKANNT = "", _("keine Angabe")
    ABGEGEBEN = "abgegeben", _("abgegeben")
    NICHT_ABGEGEBEN = "nicht_abgegeben", _("nicht abgegeben")


def gegenstand_fuer(antrag):
    """Der Gegenstand nach § 4 Abs 4 für die Stimmberechtigung eines Antrags: Kandidatur und
    Vertrauensfrage sind Personenwahlen (zwölf Monate Anwartschaft), alles andere Sachfrage.
    Die eine Stelle, die Zählung (`fortschreiben`), Einzelprüfung (`abstimmen`) und Unterstützung
    (`unterstuetzen`) gemeinsam lesen — sonst zählte der Nenner anders als der Zähler."""
    from plattform_core import Gegenstand

    if antrag.art in (Antragsart.MANDAT, Antragsart.VERTRAUENSFRAGE):
        return Gegenstand.PERSONENWAHL
    return Gegenstand.SACHFRAGE


class Antrag(models.Model):
    """Ein Antrag nach § 5 — mit eingefrorener Policy."""

    titel = models.CharField(max_length=200)
    art = models.CharField(
        max_length=20,
        choices=Antragsart.choices,
        default=Antragsart.SACHE,
        help_text="Sachantrag (§ 5), Mandats-Kandidatur (§ 7 Abs 1), Mandatsfrage eines Mandatars (§ 7 Abs 9) "
        "oder Vertrauensfrage zu einem Mandatsträger (§ 7 Abs 10).",
    )
    eingebracht_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="antraege"
    )
    eingebracht_am = models.DateTimeField(default=timezone.now)
    phase = models.CharField(
        max_length=20, choices=[(p.value, p.value) for p in Phase], default=Phase.UNTERSTUETZUNG.value
    )
    phase_beginn = models.DateTimeField(default=timezone.now)
    policy_snapshot = models.JSONField(
        help_text="Unveränderliche Kopie der Policy zum Einbringungszeitpunkt (§ 5 Abs 5)."
    )
    stimmberechtigte_anzahl = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Zahl der Stimmberechtigten, festgestellt und veröffentlicht bei Abstimmungsbeginn (§ 4 Abs 4 lit a).",
    )
    stimmberechtigung_stichtag = models.DateField(
        null=True,
        blank=True,
        help_text="Der Kalendertag (Wiener Zeit), an dem die Stimmberechtigung festgestellt wurde — "
        "dieselbe Zahl für Zählung und Einzelprüfung (§ 4 Abs 4 lit a).",
    )
    zurueckweisung_begruendung = models.TextField(
        blank=True,
        help_text="Nur bei formaler Zurückweisung durch den Integritätsrat — wird veröffentlicht (§ 5 Abs 2).",
    )
    ebene = models.CharField(
        max_length=12,
        choices=Ebene.choices,
        default=Ebene.BUND,
        help_text="Territoriale Ebene (§ 14) — regionale Anträge erscheinen im Bereich c des Hauptfensters.",
    )
    gebiet = models.CharField(
        max_length=120,
        blank=True,
        help_text="Name des Landes, Bezirks bzw. der Gemeinde bei regionalen Anträgen.",
    )
    hervorgehoben = models.BooleanField(
        default=False,
        help_text="Bereich b des Hauptfensters: wichtige Abstimmung, die alle angeht, aber wenig "
        "Aufmerksamkeit bekommt — oder bei der Beeinflussungsrisiko besteht. Entscheidung des "
        "Integritätsrats, nie eines Algorithmus.",
    )
    hervorhebung_begruendung = models.TextField(
        blank=True,
        help_text="Öffentliche Begründung der Hervorhebung — Transparenz ist Bedingung (§ 2 Abs 5).",
    )
    kategorien = models.ManyToManyField(
        Kategorie,
        blank=True,
        related_name="antraege",
        help_text="Lebensbereiche des Antrags — automatisch zugeordnet, "
        "durch den Integritätsrat korrigierbar.",
    )

    class Meta:
        verbose_name = "Antrag"
        verbose_name_plural = "Anträge"
        ordering = ["-eingebracht_am"]
        # Jede Listenansicht filtert auf die Phase und reiht nach Phasenbeginn; die Hervorhebung
        # sucht drei aus allen (Befund #81). Heute nicht messbar — der billigste Schritt, der beim
        # Wachsen als Nächstes fehlt.
        indexes = [
            models.Index(fields=["phase", "phase_beginn"], name="antrag_phase_beginn_idx"),
            models.Index(fields=["hervorgehoben"], condition=models.Q(hervorgehoben=True), name="antrag_hervorgehoben_idx"),
        ]

    def __str__(self) -> str:
        return f"#{self.pk} {self.titel} [{self.phase}]"

    # --- Kern-Anbindung -----------------------------------------------------

    def policy(self) -> Policy:
        return Policy.aus_dict(self.policy_snapshot)

    def stichtag_der_stimmberechtigung(self):
        """Der Kalendertag, gegen den eine Stimmberechtigung geprüft wird (§ 4 Abs 4 lit a).

        Gespeichert beim Übergang in die Abstimmung; für ältere Verfahren der Wiener Kalendertag
        des Phasenbeginns. Nie `phase_beginn.date()`: Das wäre das UTC-Datum, und zwischen 0 und
        2 Uhr läge es einen Tag vor dem, was die Seite als Abstimmungsbeginn zeigt (Befund #32)."""
        return self.stimmberechtigung_stichtag or timezone.localdate(self.phase_beginn)

    def aktueller_text(self) -> AntragsFassung | None:
        return self.fassungen.order_by("-nummer").first()

    @transaction.atomic
    def fortschreiben(self, jetzt=None) -> bool:
        """Prüft fällige Übergänge und wendet sie an (idempotent).
        Rückgabe: True, wenn sich die Phase geändert hat.

        Atomar, weil ein Phasenwechsel drei Dinge zugleich sind: neue Phase, archivierter Chat
        (FB-G5) und Audit-Eintrag. Bricht eines ab, darf keines stehenbleiben.

        Die eigene Zeile wird zuerst gesperrt und die Phasenfelder werden daraus gelesen: Zwei
        gleichzeitige Fortschreibungen desselben Antrags (zwei Unterstützungen an der Schwelle,
        zwei erste Aufrufe am Ergebnis) serialisieren sich so auf Postgres, und die zweite sieht
        den gesetzten Stempel bzw. die neue Phase — statt zweier Audit-Einträge „schwelle_erreicht“
        mit zwei Zeitpunkten und zweier Hinweise im Posteingang (Befund B26; § 7 Abs 10 lit c: das
        Erreichen der Schwelle hat EINEN Zeitpunkt). SQLite kennt keine Zeilensperre und
        serialisiert ohnehin; ein veraltetes Objekt im Speicher liest so aber auch dort die
        Datenbank, bevor es einen zweiten Übergang anwendet."""
        jetzt = jetzt or timezone.now()
        frisch = (
            type(self)
            .objects.select_for_update()
            .only("phase", "phase_beginn", "stimmberechtigte_anzahl", "stimmberechtigung_stichtag")
            .get(pk=self.pk)
        )
        self.phase, self.phase_beginn = frisch.phase, frisch.phase_beginn
        self.stimmberechtigte_anzahl, self.stimmberechtigung_stichtag = (
            frisch.stimmberechtigte_anzahl,
            frisch.stimmberechtigung_stichtag,
        )
        phase = Phase(self.phase)
        # Entwurfsfenster der Gremien-Werkstatt (F-66/F-67, § 5 Abs 12): Die Schleife
        # wertet ihre eigenen Fristen zuerst aus — sie kann selbst die Endabstimmung
        # über den Vorschlag öffnen. Verfahren ohne Entwurf laufen unverändert (§ 5 Abs 5).
        # Frische Abfrage statt Related-Cache: Der Descriptor merkt sich „kein Entwurf"
        # und übersähe ein später geöffnetes Fenster. Lazy geladen — verfahren bleibt
        # unabhängig von gremien, solange die App fehlt.
        entwurf = None
        if phase is Phase.BERATUNG:
            from django.apps import apps

            if apps.is_installed("gremien"):
                entwurf = (
                    apps.get_model("gremien", "Entwurf").objects.filter(antrag_id=self.pk).first()
                )
        if entwurf is not None and entwurf.fortschreiben(self, jetzt):
            return True
        policy = self.policy()
        ausz = None
        if phase is Phase.ABSTIMMUNG:
            ausz = self.auszaehlen()
        # Abgelaufene Aussetzungen zuerst schließen: Sie enden von selbst (§ 6 Abs 3 lit d),
        # und eine, die nur noch formal offen steht, hemmte sonst weiter.
        from django.apps import apps

        if apps.is_installed("gremien"):
            from gremien.models import aussetzungen_fortschreiben

            aussetzungen_fortschreiben(jetzt)
        unterstuetzungen = self.unterstuetzungen.filter(zurueckgezogen_am__isnull=True).count()
        vf = self._vertrauensfrage()
        if vf is not None and phase is Phase.UNTERSTUETZUNG and vf.schwelle_erreicht_am is None:
            # § 7 Abs 10 lit c: Das Erreichen der Schwelle wird veröffentlicht — der Zeitpunkt ist der
            # der Zählung, die es zuerst sieht (die Unterstützung ruft sie sofort auf), nicht der einer
            # späteren Verarbeitung. Der Kern rechnet damit den Abstimmungsbeginn (lit e).
            from plattform_core.phases import unterstuetzung_frist_ende

            if unterstuetzungen >= policy.unterstuetzung_schwelle and jetzt <= unterstuetzung_frist_ende(
                self.wirksamer_phase_beginn(jetzt), policy
            ):
                vf.schwelle_erreicht_am = jetzt
                vf.save(update_fields=["schwelle_erreicht_am"])
                AuditEintrag.anhaengen(
                    {
                        "typ": "schwelle_erreicht",
                        "antrag": self.pk,
                        "unterstuetzungen": unterstuetzungen,
                        "schwelle": policy.unterstuetzung_schwelle,
                        "am": jetzt.isoformat(),
                    }
                )
        uebergang = naechster_uebergang(
            phase,
            self.wirksamer_phase_beginn(jetzt),
            jetzt,
            policy,
            unterstuetzungen=unterstuetzungen,
            auszaehlung=ausz,
            schwelle_erreicht_am=vf.schwelle_erreicht_am if vf is not None else None,
        )
        if uebergang is None:
            return False
        if (
            entwurf is not None
            and phase is Phase.BERATUNG
            and uebergang.neue_phase is Phase.ABSTIMMUNG
            and entwurf.haelt_beratung_offen(jetzt)
        ):
            # Die Entwurfsschleife arbeitet gerade (eingereicht, in Prüfung, im Review
            # oder in laufender Überarbeitung) — der Regelübergang wartet auf sie.
            # Ein bloß offenes, nie eingereichtes Fenster hält dagegen nichts auf.
            return False
        self.phase = uebergang.neue_phase.value
        self.phase_beginn = uebergang.wirksam_ab
        felder = ["phase", "phase_beginn"]
        if uebergang.neue_phase is Phase.ABSTIMMUNG and self.stimmberechtigte_anzahl is None:
            # § 4 Abs 4 lit a: Zahl der Stimmberechtigten wird bei Abstimmungsbeginn
            # festgestellt, veröffentlicht und danach nie mehr verändert.
            from django.conf import settings as dj_settings

            from mitglieder.models import stimmberechtigte_zaehlen

            # § 4 Abs 4: Personenwahlen haben eine längere Anwartschaft als Sachfragen.
            gegenstand = gegenstand_fuer(self)
            # § 4 Abs 4 lit a rechnet in Kalendertagen — im Wiener Kalender, nicht im UTC-Datum:
            # Zwischen 0 und 2 Uhr läge der Stichtag sonst einen Tag zu früh (Befund #32). Der Tag
            # wird gespeichert, damit Zählung und Einzelprüfung dieselbe Zahl lesen.
            self.stimmberechtigung_stichtag = timezone.localdate(uebergang.wirksam_ab)
            self.stimmberechtigte_anzahl = max(
                1,
                stimmberechtigte_zaehlen(
                    gegenstand,
                    self.stimmberechtigung_stichtag,
                    uebergang=getattr(dj_settings, "DDOE_UEBERGANGSREGEL", True),
                ),
            )
            felder += ["stimmberechtigte_anzahl", "stimmberechtigung_stichtag"]
        self.save(update_fields=felder)
        if uebergang.neue_phase is Phase.BERATUNG and apps.is_installed("gremien"):
            # § 6 Abs 7: Der Expertenrat wird für DIESEN Antrag aus der Fachliste gelost —
            # erst jetzt, denn erst jetzt steht fest, dass beraten wird. Der Anker ist der
            # Kopf der Audit-Kette in diesem Augenblick: vorher von niemandem auszurechnen.
            from gremien.models import auslosen

            auslosen(self, jetzt=uebergang.wirksam_ab)
        archiviert = self.chat_archivieren(uebergang.wirksam_ab)
        AuditEintrag.anhaengen(
            {
                "typ": "phasenwechsel",
                "antrag": self.pk,
                "neue_phase": uebergang.neue_phase.value,
                "wirksam_ab": uebergang.wirksam_ab.isoformat(),
                "grund": uebergang.grund,
                "chat_archiviert": archiviert,
            }
        )
        if vf is not None and uebergang.neue_phase in (Phase.ANGENOMMEN, Phase.ABGELEHNT):
            # § 7 Abs 10 lit e und f: „angenommen“ heißt verloren — die Wirkungen treten mit der
            # Veröffentlichung des Ergebnisses ein, also zum Fristzeitpunkt, nicht zum Jobzeitpunkt.
            from mandatare.models import vertrauensfrage_ergebnis

            vertrauensfrage_ergebnis(vf, uebergang.wirksam_ab)
        return True

    def _vertrauensfrage(self):
        """Die Fachdaten der Vertrauensfrage zu diesem Antrag — None bei jeder anderen Antragsart.
        Frische Abfrage statt Related-Cache, lazy geladen: `verfahren` bleibt unabhängig von
        `mandatare`, solange die App fehlt."""
        if self.art != Antragsart.VERTRAUENSFRAGE:
            return None
        from django.apps import apps

        if not apps.is_installed("mandatare"):
            return None  # pragma: no cover
        return apps.get_model("mandatare", "Vertrauensfrage").objects.filter(antrag_id=self.pk).first()

    def chat_archivieren(self, jetzt=None) -> int:
        """FB-G5: Bei jeder Hochstufung wandern die Beiträge der bisherigen Phase ins Archiv.

        Archivieren heißt Sichtbarkeit ändern, nicht entfernen (Grundregel 7): Der laufende
        Chat beginnt leer, die Beiträge bleiben unter ihrer Phase lesbar. Idempotent —
        was schon gestempelt ist, bleibt unberührt. Rückgabe: Zahl der archivierten Beiträge."""
        return self.kommentare.filter(archiviert_am__isnull=True).update(
            archiviert_am=jetzt or timezone.now()
        )

    def _aussetzungs_abschnitte(self) -> list[tuple]:
        """Die Zeiträume, in denen dieses Verfahren nach § 6 Abs 3 lit d stillstand.

        Lazy geladen: `verfahren` bleibt unabhängig von `gremien`, solange die App fehlt."""
        from django.apps import apps

        if not apps.is_installed("gremien"):
            return []
        modell = apps.get_model("gremien", "Aussetzung")
        return [a.abschnitt() for a in modell.objects.filter(antrag_id=self.pk)]

    def aussetzung_laeuft(self, jetzt=None, gegenstand: str | None = None) -> bool:
        """Ob gerade eine Aussetzung wirkt — dann ruht das Verfahren vollständig.

        `gegenstand` („abstimmung“ oder „vollzug“) schränkt auf eine Art ein."""
        from django.apps import apps

        if not apps.is_installed("gremien"):
            return False
        jetzt = jetzt or timezone.now()
        modell = apps.get_model("gremien", "Aussetzung")
        laufende = modell.objects.filter(antrag_id=self.pk, beendet_am__isnull=True)
        if gegenstand is not None:
            laufende = laufende.filter(gegenstand=gegenstand)
        return any(a.laeuft(jetzt) for a in laufende)

    def wirksamer_phase_beginn(self, jetzt=None):
        """Der Phasenbeginn, mit dem gerechnet wird — um die Stillstandszeit nach hinten gerückt.

        Der gespeicherte Beginn bleibt unangetastet, damit die Historie lesbar bleibt; gerechnet
        wird mit diesem hier (§ 6 Abs 3 lit d: die Aussetzung darf dem Antrag keine Zeit nehmen)."""
        from plattform_core.aussetzung import wirksamer_beginn

        abschnitte = self._aussetzungs_abschnitte()
        if not abschnitte:
            return self.phase_beginn
        return wirksamer_beginn(self.phase_beginn, abschnitte, jetzt or timezone.now())

    def stimme_zulaessig(self, jetzt=None) -> bool:
        jetzt = jetzt or timezone.now()
        if self.aussetzung_laeuft(jetzt):
            return False  # § 6 Abs 3 lit d: die Abstimmung ist ausgesetzt
        return stimme_zulaessig(
            Phase(self.phase), self.wirksamer_phase_beginn(jetzt), jetzt, self.policy()
        )

    def auszaehlen(self):
        if self.art == Antragsart.MANDAT:
            return self.kandidatur_auszaehlen()
        stimmen = [(s.pseudonym.hex, s.stimme) for s in self.stimmabgaben.all()]
        return auszaehlen(stimmen, self.stimmberechtigte_anzahl or 1, self.policy())

    def kandidatur_auszaehlen(self):
        """§ 7 Abs 1 (E-2.5): Zustimmungswahl über die wählbaren Bewerbungen —
        gerechnet im framework-freien Kern (plattform_core.tally)."""
        from plattform_core.tally import personenwahl_auszaehlen

        waehlbar = list(
            self.bewerbungen.filter(zurueckgezogen=False)
            .order_by("erstellt_am", "pk")
            .values_list("pk", flat=True)
        )
        zustimmungen = [
            (z.pseudonym.hex, z.bewerbung_id)
            for z in BewerbungsZustimmung.gueltige().filter(
                bewerbung__antrag=self, bewerbung__zurueckgezogen=False
            )
        ]
        return personenwahl_auszaehlen(
            zustimmungen, waehlbar, self.stimmberechtigte_anzahl or 1, self.policy()
        )

    def vollzugsstand(self):
        """Jüngster Eintrag im Umsetzungsregister (F-55) — None, solange keiner existiert
        (ein angenommener Antrag ohne Eintrag gilt als „offen")."""
        return self.vollzug.first()


class AntragsFassung(models.Model):
    """Vollständige Versionshistorie des Wortlauts (§ 5 Abs 3 — abgestimmt wird
    über die zuletzt veröffentlichte Fassung)."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="fassungen")
    nummer = models.PositiveIntegerField()
    wortlaut = models.TextField()
    begruendung = models.TextField(blank=True)
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("antrag", "nummer")]
        verbose_name = "Antragsfassung"
        verbose_name_plural = "Antragsfassungen"

    def __str__(self) -> str:
        return f"Antrag {self.antrag_id}, Fassung {self.nummer}"


class Unterstuetzung(models.Model):
    """Eine öffentliche Unterstützung (§ 5 Abs 3 lit b). Sie bestimmt den Phasenübergang und den
    Kreis der Stimmberechtigten im Abstimmungs-Chat (§ 5 Abs 12) — deshalb bleibt ein Rückzug
    als Zeile stehen (`zurueckgezogen_am`, Grundregel 7) statt gelöscht zu werden (Befund #27).
    Gezählt wird nur, was nicht zurückgezogen ist: `gueltige()`."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="unterstuetzungen")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    erklaert_am = models.DateTimeField(default=timezone.now)
    zurueckgezogen_am = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Gesetzt, wenn die Unterstützung zurückgezogen wurde — die Zeile bleibt, gezählt wird sie nicht mehr.",
    )

    class Meta:
        unique_together = [("antrag", "mitglied")]  # einmal je Mensch
        verbose_name = "Unterstützung"
        verbose_name_plural = "Unterstützungen"

    def __str__(self) -> str:
        return f"Unterstützung Antrag {self.antrag_id} durch Mitglied {self.mitglied_id}"

    @classmethod
    def gueltige(cls):
        """Die Unterstützungen, die zählen — ohne die zurückgezogenen."""
        return cls.objects.filter(zurueckgezogen_am__isnull=True)


class Stimmabgabe(models.Model):
    """Die veröffentlichte Seite einer Stimme: Pseudonym + Wert. KEIN Personenbezug."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="stimmabgaben")
    pseudonym = models.UUIDField(default=uuid.uuid4, editable=False)
    stimme = models.CharField(max_length=12, choices=[(s.value, s.value) for s in KernStimme])
    abgegeben_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("antrag", "pseudonym")]
        verbose_name = "Stimmabgabe"
        verbose_name_plural = "Stimmabgaben"

    def __str__(self) -> str:
        return f"Stimme {self.pseudonym.hex[:8]}… zu Antrag {self.antrag_id}"


class StimmRegister(models.Model):
    """Die geschützte Seite: Mitglied ↔ Pseudonym je Antrag (F-25, § 8 Abs 5).
    Zugriff nur für den Systembetrieb im Störfall; jeder Zugriff wird auditiert.
    Der Prüfcode erlaubt dem Mitglied, die eigene Stimme in der veröffentlichten
    Liste wiederzufinden, ohne dass Dritte das können."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="stimmregister")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    pseudonym = models.UUIDField()
    pruefcode = models.CharField(max_length=32, default="", editable=False)

    class Meta:
        unique_together = [("antrag", "mitglied")]  # eine Stimme je Mensch je Antrag
        verbose_name = "Stimmregister-Eintrag (geschützt)"
        verbose_name_plural = "Stimmregister (geschützt)"

    def __str__(self) -> str:
        return f"Registereintrag Antrag {self.antrag_id} (geschützt)"

    def save(self, *args, **kwargs):
        if not self.pruefcode:
            self.pruefcode = secrets.token_hex(8)
        super().save(*args, **kwargs)


class KategorieAbo(models.Model):
    """Abonnement eines Lebensbereichs (F-46): erscheint im Bereich a des
    Hauptfensters; künftig Grundlage der Benachrichtigungen (F-30)."""

    kategorie = models.ForeignKey(Kategorie, on_delete=models.CASCADE, related_name="abos")
    mitglied = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="kategorie_abos"
    )
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("kategorie", "mitglied")]
        verbose_name = "Kategorie-Abo"
        verbose_name_plural = "Kategorie-Abos"

    def __str__(self) -> str:
        return f"Abo {self.kategorie_id} von Mitglied {self.mitglied_id}"


class Favorit(models.Model):
    """Bereich a des Hauptfensters (§ 5 Abs 10 lit a, F-41): ein Mitglied merkt
    sich einen Antrag. Rein persönlich — Favoriten beeinflussen niemals
    Reihung, Schwellen oder Ergebnis (F-31)."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="favoriten")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="favoriten")
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("antrag", "mitglied")]
        verbose_name = "Favorit"
        verbose_name_plural = "Favoriten"

    def __str__(self) -> str:
        return f"Favorit Antrag {self.antrag_id} von Mitglied {self.mitglied_id}"


class Vollzugsstatus(models.TextChoices):
    """Stand der Umsetzung eines angenommenen Antrags (F-55, § 6 Abs 10)."""

    OFFEN = "offen", _("offen")
    IN_UMSETZUNG = "in_umsetzung", _("in Umsetzung")
    BLOCKIERT = "blockiert", _("blockiert")
    UMGESETZT = "umgesetzt", _("umgesetzt")
    ZURUECKGESTELLT = "zurueckgestellt", _("zurückgestellt")


class Vollzugseintrag(models.Model):
    """Ein Schritt im öffentlichen Umsetzungsregister (F-55, § 6 Abs 10).

    Append-only wie das Audit-Log: Der aktuelle Stand ist stets der jüngste
    Eintrag; frühere Einträge werden nie geändert oder gelöscht — die
    Geschichte der Umsetzung bleibt vollständig nachlesbar. Bis das
    Rollensystem (F-05) den Integrations- und Berichtswesenrat technisch
    abbildet, schreiben die Admins der Mitgliederverwaltung fort."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="vollzug")
    status = models.CharField(max_length=20, choices=Vollzugsstatus.choices)
    vermerk = models.TextField(
        blank=True,
        max_length=2000,
        help_text="Öffentlicher Vermerk: Stand, Hindernis, nächster Schritt, Termin.",
    )
    erstellt_am = models.DateTimeField(default=timezone.now)
    durch = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-erstellt_am", "-pk"]
        verbose_name = "Vollzugseintrag"
        verbose_name_plural = "Umsetzungsregister"

    def __str__(self) -> str:
        return f"Antrag {self.antrag_id}: {self.status}"


class VollzugAusgesetzt(ValueError):
    """Der Vollzug ist durch den Integritätsrat ausgesetzt (§ 6 Abs 3 lit d)."""


def vollzug_fortschreiben(antrag: Antrag, mitglied, status: str, vermerk: str = "") -> Vollzugseintrag:
    """F-55: den Umsetzungsstand fortschreiben — nur für angenommene Anträge,
    immer als neuer Eintrag, immer auditiert. Ein ausgesetzter Vollzug wird nicht
    fortgeschrieben (§ 6 Abs 3 lit d) — sonst hinderte die Aussetzung das Register nicht (Befund #31)."""
    if antrag.phase != Phase.ANGENOMMEN.value:
        raise ValueError("Das Umsetzungsregister führt nur angenommene Anträge (§ 6 Abs 10).")
    if antrag.aussetzung_laeuft(gegenstand="vollzug"):
        raise VollzugAusgesetzt(
            "Der Vollzug dieses Beschlusses ist durch den Integritätsrat ausgesetzt (§ 6 Abs 3 lit d) — "
            "solange die Aussetzung läuft, wird das Umsetzungsregister nicht fortgeschrieben."
        )
    eintrag = Vollzugseintrag.objects.create(
        antrag=antrag, status=Vollzugsstatus(status), vermerk=vermerk.strip(), durch=mitglied
    )
    AuditEintrag.anhaengen(
        {"typ": "vollzug", "antrag": antrag.pk, "status": eintrag.status, "durch": mitglied.pk}
    )
    return eintrag


class AuditEintrag(models.Model):
    """Append-only-Audit-Log mit Hash-Kette (F-22, ADR-005).
    Einträge werden nie geändert oder gelöscht — dafür gibt es keinen Code-Pfad,
    und der Admin ist read-only registriert.

    `vorgaenger` ist eindeutig: Zwei Einträge können nie am selben Kopf hängen. Ohne diese
    Bedingung konnten zwei gleichzeitige Schreiber (zwei Worker, READ COMMITTED) denselben Kopf
    lesen und beide dagegen hashen — die Kette gabelte sich still und war ab dort für jeden
    Nachprüfer von einer Manipulation nicht zu unterscheiden (Befund #9)."""

    lfd = models.BigAutoField(primary_key=True)
    zeit = models.DateTimeField(default=timezone.now)
    ereignis = models.JSONField()
    vorgaenger = models.CharField(
        max_length=64,
        unique=True,
        editable=False,
        help_text="Hash des Vorgängers — eindeutig, damit die Kette sich nicht gabeln kann.",
    )
    hash = models.CharField(max_length=64, editable=False)

    class Meta:
        verbose_name = "Audit-Eintrag"
        verbose_name_plural = "Audit-Log"
        ordering = ["lfd"]
        indexes = [
            # Befund #41: Die Audit-Spur eines Antrags wird in der Datenbank gefiltert
            # (ereignis -> 'antrag'); ohne Ausdrucksindex bliebe das ein Lauf über das ganze Log.
            models.Index(KeyTransform("antrag", "ereignis"), name="audit_antrag_idx"),
        ]

    def __str__(self) -> str:
        return f"Audit #{self.lfd} {self.ereignis.get('typ', '?')}"

    #: Wie oft `anhaengen` einen überholten Kopf neu liest, bevor es aufgibt.
    VERSUCHE = 3

    @classmethod
    def _kopf(cls) -> str:
        letzter = cls.objects.order_by("-lfd").only("hash").first()
        return letzter.hash if letzter else GENESIS

    @classmethod
    def anhaengen(cls, ereignis: dict) -> AuditEintrag:
        """Hängt ein Ereignis an die Kette — mit versiegeltem Zeitstempel und ohne Gabelung.

        Der Zeitpunkt steht im Ereignis selbst (`zeit`), damit er unter dem Hash liegt: Die
        Spalte `zeit` allein könnte jemand mit Datenbankzugriff ändern, ohne dass die Kette es
        bemerkt (Befund #75). Ältere Einträge ohne diesen Schlüssel bleiben prüfbar.

        Überholt ein zweiter Schreiber den gelesenen Kopf, weist die Eindeutigkeit von
        `vorgaenger` den Eintrag ab; dann wird der Kopf neu gelesen und noch einmal versucht.
        Der Fehler wird AUSSERHALB des inneren `atomic` gefangen — nur so bleibt eine äußere
        Transaktion (etwa `Antrag.fortschreiben`) auf PostgreSQL benutzbar."""
        jetzt = timezone.now()
        versiegelt = {**ereignis, "zeit": jetzt.isoformat()}
        for _versuch in range(cls.VERSUCHE):
            vorgaenger = cls._kopf()
            try:
                with transaction.atomic():
                    return cls.objects.create(
                        zeit=jetzt,
                        ereignis=versiegelt,
                        vorgaenger=vorgaenger,
                        hash=ereignis_hash(vorgaenger, versiegelt),
                    )
            except IntegrityError:
                continue
        raise IntegrityError(
            f"Audit-Kette: Der Kopf wurde {cls.VERSUCHE}-mal hintereinander überholt — Eintrag nicht angehängt."
        )


# --- Fachoperationen (die einzigen Schreibwege) -------------------------------


def antrag_einbringen(
    mitglied,
    titel: str,
    wortlaut: str,
    begruendung: str,
    ordnung: Verfahrensordnung,
    ebene: str = Ebene.BUND,
    gebiet: str = "",
    art: str = Antragsart.SACHE,
) -> Antrag:
    """Einbringen nach § 5 Abs 2–3: Policy einfrieren, Fassung 1 anlegen, auditieren.
    `art` unterscheidet Sachantrag und Mandats-Kandidatur (§ 7 Abs 1, F-70)."""
    policy = ordnung.als_policy()  # validiert die Regeln gegen die Satzungsminima
    antrag = Antrag.objects.create(
        titel=titel,
        eingebracht_von=mitglied,
        policy_snapshot=policy.als_dict(),
        ebene=Ebene(ebene),
        gebiet=gebiet,
        art=Antragsart(art),
    )
    AntragsFassung.objects.create(antrag=antrag, nummer=1, wortlaut=wortlaut, begruendung=begruendung)
    AuditEintrag.anhaengen(
        {
            "typ": "antrag_eingebracht",
            "antrag": antrag.pk,
            "titel": titel,
            "art": str(antrag.art),
            "policy": f"{policy.id} v{policy.version}",
        }
    )
    return antrag


class MandatsfrageFehler(ValueError):
    """Eine Mandatsfrage kann so nicht eröffnet werden — die Meldung sagt dem Mandatar, warum."""


@transaction.atomic
def mandatsfrage_eroeffnen(mandat, aufgabe, titel: str, wortlaut: str, ordnung: Verfahrensordnung, jetzt=None) -> Antrag:
    """§ 7 Abs 9: Aus einem Instant-Report wird eine Abstimmung — direkt in der Abstimmungsphase,
    ohne Unterstützungs- und Beratungsphase.

    Die Dauer kommt aus der Stellgröße `mandatsfrage-abstimmung-tage`, nie unter dem
    Satzungsminimum (§ 5 Abs 3 lit d), und wird in die eingefrorene Ordnung des Antrags
    geschrieben (§ 5 Abs 5): Eine spätere Registeränderung ändert laufende Mandatsfragen nicht.
    Der Registerwert ist bewusst kein Ordnungsschlüssel der Verfahrensordnung — so bleibt er
    nach D-J3g befristet testbar.

    Tore: Die Frist der Aufgabe muss die ganze Abstimmung fassen (sonst bleibt es beim
    Kurzbericht ohne Abstimmung), die Aufgabe hat noch keine Abstimmung, das Mandat ist offen,
    die Aufgabe gehört zum Mandat — und nach einer verlorenen Vertrauensfrage ruht die Befugnis,
    Abstimmungen zu betreuen (§ 7 Abs 10 lit f Z 6: ab der Veröffentlichung des Ergebnisses; eine
    Aufhebung durch das Parteischiedsgericht leert `vertrauen_entzogen_am` und belebt sie wieder,
    eine Bestätigung nach Z 3 nicht). Laufende Mandatsfragen werden zu Ende geführt und bleiben
    Beschlusslage — sie sind nicht berührt. Die Zahl der Stimmberechtigten wird hier festgestellt
    (§ 4 Abs 4 lit a) — `fortschreiben()` täte es für einen direkt in der Abstimmung
    angelegten Antrag nie. Gegenstand ist die Sachfrage (drei Monate Anwartschaft,
    Mindestbeteiligung wie beim Sachantrag)."""
    from django.conf import settings as dj_settings

    from mitglieder.models import stimmberechtigte_zaehlen
    from parameter.models import zahl
    from plattform_core import Gegenstand
    from plattform_core.policy import SATZUNG_MIN_ABSTIMMUNG_TAGE

    jetzt = jetzt or timezone.now()
    if not mandat.aktiv:
        raise MandatsfrageFehler(_("Das Mandat ist beendet — es kann keine Mandatsfrage mehr stellen."))
    if mandat.vertrauen_entzogen_am is not None:
        raise MandatsfrageFehler(
            _("Nach einer verlorenen Vertrauensfrage ruht die Befugnis, Abstimmungen zu betreuen (§ 7 Abs 10 lit f Z 6).")
        )
    if aufgabe.mandat_id != mandat.pk:
        raise MandatsfrageFehler(_("Der Report gehört nicht zu diesem Mandat."))
    if aufgabe.antrag_id is not None:
        raise MandatsfrageFehler(_("Zu diesem Report läuft bereits eine Abstimmung."))
    dauer = max(SATZUNG_MIN_ABSTIMMUNG_TAGE, zahl("mandatsfrage-abstimmung-tage", 7))
    if aufgabe.frist is None or aufgabe.frist < jetzt + timedelta(days=dauer):
        raise MandatsfrageFehler(
            _("Die Frist liegt zu nah: Eine Abstimmung dauert mindestens %(tage)s Tage (§ 5 Abs 3 lit d).")
            % {"tage": dauer}
        )
    policy = dataclasses.replace(ordnung.als_policy(), abstimmung_tage=dauer)
    stichtag = timezone.localdate(jetzt)
    antrag = Antrag.objects.create(
        titel=titel,
        art=Antragsart.MANDATSFRAGE,
        eingebracht_von=mandat.mitglied,
        eingebracht_am=jetzt,
        phase=Phase.ABSTIMMUNG.value,
        phase_beginn=jetzt,
        policy_snapshot=policy.als_dict(),
        stimmberechtigung_stichtag=stichtag,
        stimmberechtigte_anzahl=max(
            1,
            stimmberechtigte_zaehlen(
                Gegenstand.SACHFRAGE, stichtag, uebergang=getattr(dj_settings, "DDOE_UEBERGANGSREGEL", True)
            ),
        ),
        ebene=Ebene(mandat.ebene),
        gebiet=mandat.gebiet,
    )
    frist_lokal = timezone.localtime(aufgabe.frist)
    begruendung = (
        f"Mandatsfrage nach § 7 Abs 9 aus dem Instant-Report „{aufgabe.titel}“ "
        f"({'Sitzungstag' if aufgabe.sitzungstag else 'Frist'} {frist_lokal:%d.%m.%Y %H:%M}). "
        f"Die Abstimmung dauert {dauer} Tage und endet vor dieser Frist."
    )
    AntragsFassung.objects.create(antrag=antrag, nummer=1, wortlaut=wortlaut, begruendung=begruendung)
    kategorien_zuordnen(antrag)
    aufgabe.antrag = antrag
    aufgabe.save(update_fields=["antrag", "aktualisiert_am"])
    AuditEintrag.anhaengen(
        {
            "typ": "mandatsfrage_eroeffnet",
            "antrag": antrag.pk,
            "mandat": mandat.pk,
            "aufgabe": aufgabe.pk,
            "frist_ende": (jetzt + timedelta(days=dauer)).isoformat(),
            "policy": f"{policy.id} v{policy.version}",
        }
    )
    AuditEintrag.anhaengen(
        {
            "typ": "phasenwechsel",
            "antrag": antrag.pk,
            "neue_phase": Phase.ABSTIMMUNG.value,
            "wirksam_ab": jetzt.isoformat(),
            "grund": "Mandatsfrage nach § 7 Abs 9 — ohne Unterstützungs- und Beratungsphase",
        }
    )
    return antrag


@transaction.atomic
def vertrauensfrage_einbringen(
    mitglied,
    mandat,
    begruendung: str,
    anlaesse,
    ausstaende,
    ordnung: Verfahrensordnung,
    jetzt=None,
    art: str = "vertrauensfrage",
) -> Antrag:
    """§ 7 Abs 10: Die Vertrauensfrage zu einem Mandatsträger einbringen — oder, mit `art="bestaetigung"`,
    den Bestätigungsantrag der betroffenen Person selbst (lit f Z 3).

    Die Ordnung des Antrags entsteht aus der geltenden Verfahrensordnung, überschrieben mit den
    Satzungswerten des Absatzes 10 und eingefroren (§ 5 Abs 5): Schwelle fünf Prozent der für
    Personenwahlen Stimmberechtigten am Einbringungstag (aufgerundet, mindestens 1), Sammelfrist aus
    `vertrauensfrage-unterstuetzung-tage` (nie über 30), keine Beratungsphase, Abstimmung frühestens
    am siebten Tag nach Einbringung und spätestens am dritten Tag nach Erreichen der Schwelle, Dauer
    aus `vertrauensfrage-abstimmung-tage` (nie unter 7). Die Zahlen werden mit dem Antrag veröffentlicht.

    Formerfordernis (lit b): mindestens ein Anlass — ein Eintrag des Rechenschaftsregisters mit
    Abweichung (`anlaesse`: Rechenschaft-Objekte dieses Mandats mit `weicht_ab`) oder ein seit mehr
    als 30 Tagen ausgewiesener Ausstand (`ausstaende`: Kennungen aus `Mandat.anlass_ausstaende`).
    Ohne Anlass gibt es keinen Antrag (`VertrauensfrageFehler`) — das ist kein Zurückweisen im
    Sinne des § 5 Abs 2, sondern ein Formular ohne Pflichtfeld.

    Sperren nach lit g prüft `mandatare.models.sperren_pruefen` — das Ergebnis steht als Klartext
    am Antrag (`sperrhinweis`) und wird dem Integritätsrat vorgelegt; **abgewiesen wird nicht**
    (§ 2 Abs 6). Der Mandatar wird verständigt (Brief ohne Inhalt, nur Link).

    Bestätigungsantrag: nur die betroffene Person, nur nach entzogenem Vertrauen ohne Bestätigung,
    frühestens sechs Monate nach dem Ergebnis oder der letzten Ablehnung; ohne Anlass, ohne Sperren,
    Schwelle 0 (gilt mit dem Einbringen als erreicht), Abstimmung am siebten Tag."""
    from django.conf import settings as dj_settings

    from mandatare.models import (
        VERTRAUENSFRAGE_LAUFEND,
        Vertrauensfrage,
        VertrauensfrageArt,
        VertrauensfrageFehler,
        bestaetigung_zulaessig_ab,
        bis_zum_stand_fortschreiben,
        sperren_pruefen,
    )
    from mitglieder.models import stimmberechtigte_zaehlen
    from parameter.models import zahl
    from plattform_core import Gegenstand
    from plattform_core.policy import (
        SATZUNG_MAX_VERTRAUENSFRAGE_SAMMELFRIST_TAGE,
        SATZUNG_MIN_ABSTIMMUNG_TAGE,
        SATZUNG_VERTRAUENSFRAGE_ANTEIL,
        VERTRAUENSFRAGE_FRUEHESTENS_TAGE,
        VERTRAUENSFRAGE_SPAETESTENS_TAGE,
    )

    jetzt = jetzt or timezone.now()
    art = VertrauensfrageArt(art)
    bestaetigung = art == VertrauensfrageArt.BESTAETIGUNG
    anlaesse = list(anlaesse or ())
    ausstaende_kennungen = [str(k) for k in (ausstaende or ())]
    begruendung = (begruendung or "").strip()
    if bestaetigung:
        if mitglied.pk != mandat.mitglied_id:
            raise VertrauensfrageFehler(_("Die Bestätigung kann nur die betroffene Person selbst beantragen (§ 7 Abs 10 lit f Z 3)."))
        if not mandat.kandidatursperre:
            raise VertrauensfrageFehler(_("Es gibt keine verlorene Vertrauensfrage, die zu bestätigen wäre."))
        # Phasen sind lazy: Ein an der Frist abgelaufener, nie aufgerufener Bestätigungsantrag darf den
        # nächsten nicht sperren — erst fortschreiben, dann prüfen (Befund B25).
        for alt in Vertrauensfrage.objects.filter(
            mandat=mandat, art=VertrauensfrageArt.BESTAETIGUNG, antrag__phase__in=VERTRAUENSFRAGE_LAUFEND
        ).select_related("antrag"):
            bis_zum_stand_fortschreiben(alt.antrag, jetzt)
        if Vertrauensfrage.objects.filter(
            mandat=mandat, art=VertrauensfrageArt.BESTAETIGUNG, antrag__phase__in=VERTRAUENSFRAGE_LAUFEND
        ).exists():
            raise VertrauensfrageFehler(_("Ein Bestätigungsantrag läuft bereits."))
        frei_ab = bestaetigung_zulaessig_ab(mandat)
        if frei_ab is not None and timezone.localdate(jetzt) < frei_ab:
            raise VertrauensfrageFehler(
                _("Die Bestätigung kann frühestens ab %(datum)s beantragt werden (§ 7 Abs 10 lit f Z 3).")
                % {"datum": frei_ab.strftime("%d.%m.%Y")}
            )
        anlaesse, ausstaende_kennungen, gewaehlte = [], [], []
    else:
        for r in anlaesse:
            if r.mandat_id != mandat.pk:
                raise VertrauensfrageFehler(_("Der gewählte Anlass gehört nicht zu diesem Mandat."))
            if not r.weicht_ab:
                raise VertrauensfrageFehler(
                    _("Anlass ist nur ein Eintrag, in dem das Stimmverhalten vom Beschluss der Plattform abweicht (§ 7 Abs 10 lit b).")
                )
        moeglich = {a["kennung"]: a for a in mandat.anlass_ausstaende(timezone.localdate(jetzt))}
        unbekannt = [k for k in ausstaende_kennungen if k not in moeglich]
        if unbekannt:
            raise VertrauensfrageFehler(
                _("Ein gewählter Ausstand ist nicht (mehr) seit über 30 Tagen ausgewiesen (§ 7 Abs 10 lit b).")
            )
        gewaehlte = [
            {**moeglich[k], "seit": moeglich[k]["seit"].isoformat()} for k in dict.fromkeys(ausstaende_kennungen)
        ]
        if not anlaesse and not gewaehlte:
            raise VertrauensfrageFehler(
                _("Eine Vertrauensfrage braucht mindestens einen Anlass: einen Eintrag des Rechenschaftsregisters mit "
                  "Abweichung oder einen seit mehr als 30 Tagen ausständigen Bericht (§ 7 Abs 10 lit b).")
            )
        if not begruendung:
            raise VertrauensfrageFehler(_("Die Begründung fehlt."))

    stichtag = timezone.localdate(jetzt)
    uebergang = getattr(dj_settings, "DDOE_UEBERGANGSREGEL", True)
    n_partei = stimmberechtigte_zaehlen(Gegenstand.PERSONENWAHL, stichtag, uebergang=uebergang)
    schwelle = 0 if bestaetigung else max(1, math.ceil(SATZUNG_VERTRAUENSFRAGE_ANTEIL * n_partei))
    sammelfrist = max(
        1, min(SATZUNG_MAX_VERTRAUENSFRAGE_SAMMELFRIST_TAGE, zahl("vertrauensfrage-unterstuetzung-tage", 30))
    )
    dauer = max(SATZUNG_MIN_ABSTIMMUNG_TAGE, zahl("vertrauensfrage-abstimmung-tage", 7))
    policy = dataclasses.replace(
        ordnung.als_policy(),
        unterstuetzung_schwelle=schwelle,
        unterstuetzung_frist_tage=sammelfrist,
        beratung_entfaellt=True,
        abstimmung_fruehestens_tage=VERTRAUENSFRAGE_FRUEHESTENS_TAGE,
        abstimmung_spaetestens_tage_nach_schwelle=(
            VERTRAUENSFRAGE_FRUEHESTENS_TAGE if bestaetigung else VERTRAUENSFRAGE_SPAETESTENS_TAGE
        ),
        abstimmung_tage=dauer,
    )
    ort = mandat.gebiet or mandat.get_ebene_display()
    if bestaetigung:
        titel = f"Bestätigung nach § 7 Abs 10: {mandat.bezeichnung}, {ort}"
        wortlaut = (
            f"Die Mitgliederversammlung bestätigt {mandat.mitglied.anzeigename} als Mandatsträger "
            f"({mandat.bezeichnung}, {ort}) nach § 7 Abs 10 lit f Z 3."
            + (f"\n\n{begruendung}" if begruendung else "")
        )
        fassung_begruendung = (
            "Bestätigungsantrag der betroffenen Person nach § 7 Abs 10 lit f Z 3 — ohne Unterstützungs- und "
            f"Beratungsphase; die Abstimmung beginnt am {VERTRAUENSFRAGE_FRUEHESTENS_TAGE}. Tag nach Einbringung "
            f"und dauert {dauer} Tage. Zugrunde liegt das Rechenschaftsregister seit dem Ergebnis."
        )
    else:
        titel = f"Vertrauensfrage: {mandat.bezeichnung}, {ort}"
        zeilen = [
            f"Der Antrag lautet auf Versagung des Vertrauens gegenüber {mandat.mitglied.anzeigename} "
            f"({mandat.bezeichnung}, {ort}) nach § 7 Abs 10 lit b.",
            "",
            begruendung,
            "",
            "Anlässe:",
        ]
        for r in anlaesse:
            zeilen.append(
                f"- Rechenschaft vom {r.sitzung_am:%d.%m.%Y}: {r.gegenstand} — Beschluss der Plattform "
                f"{r.get_beschluss_plattform_display()}, Stimme {r.get_stimme_display()}"
            )
        for a in gewaehlte:
            zeilen.append(f"- {a['art'].capitalize()} {a['bezug']} ausständig seit {a['tage']} Tagen (Frist {a['seit']})")
        wortlaut = "\n".join(zeilen)
        fassung_begruendung = (
            f"Vertrauensfrage nach § 7 Abs 10. Für Personenwahlen stimmberechtigte Mitglieder am Einbringungstag: "
            f"{n_partei}; Unterstützungsschwelle: {schwelle} (fünf Prozent, lit c); Sammelfrist {sammelfrist} Tage; "
            f"keine Beratungsphase; Abstimmung frühestens am {VERTRAUENSFRAGE_FRUEHESTENS_TAGE}. Tag nach Einbringung, "
            f"spätestens am {VERTRAUENSFRAGE_SPAETESTENS_TAGE}. Tag nach Erreichen der Schwelle, Dauer {dauer} Tage."
        )
    antrag = Antrag.objects.create(
        titel=titel[:200],
        art=Antragsart.VERTRAUENSFRAGE,
        eingebracht_von=mitglied,
        eingebracht_am=jetzt,
        phase=Phase.UNTERSTUETZUNG.value,
        phase_beginn=jetzt,
        policy_snapshot=policy.als_dict(),
        ebene=Ebene(mandat.ebene),
        gebiet=mandat.gebiet,
    )
    AntragsFassung.objects.create(antrag=antrag, nummer=1, wortlaut=wortlaut, begruendung=fassung_begruendung)
    sperrhinweis = "" if bestaetigung else sperren_pruefen(mandat, jetzt, anlaesse=anlaesse, ausstaende=gewaehlte)
    vf = Vertrauensfrage.objects.create(
        antrag=antrag,
        mandat=mandat,
        art=art,
        anlass_ausstaende=gewaehlte,
        stimmberechtigte_partei_am_einbringungstag=n_partei,
        schwelle_partei=schwelle,
        schwelle_erreicht_am=jetzt if bestaetigung else None,
        sperrhinweis=sperrhinweis,
    )
    if anlaesse:
        vf.anlaesse.set(anlaesse)
    kategorien_zuordnen(antrag)
    AuditEintrag.anhaengen(
        {
            "typ": "vertrauensfrage_eingebracht",
            "antrag": antrag.pk,
            "mandat": mandat.pk,
            "art": str(art),
            "anlaesse": [r.pk for r in anlaesse],
            "ausstaende": len(gewaehlte),
            "stimmberechtigte": n_partei,
            "schwelle": schwelle,
            "sperrhinweis": bool(sperrhinweis),
            "policy": f"{policy.id} v{policy.version}",
        }
    )
    if not bestaetigung:
        from mitglieder.post import vertrauensfrage_senden

        vertrauensfrage_senden(mandat, antrag)
    return antrag


class FilterProfil(models.Model):
    """Ein gespeichertes Regler-Profil des WeicherFilters (P5, § 5 Abs 10 lit d).

    Profile liegen serverseitig beim Mitglied; höchstens fünf (durchgesetzt in
    der Ansicht), genau eines ist aktiv. Sie wirken ausschließlich auf die
    EIGENE Ansicht des Mitglieds — nie auf gemeinsame Reihung, Schwellen oder
    Ergebnisse (§ 2 Abs 6 letzter Satz: mitgliedereigene Reihung ist keine
    Sortierung durch die Partei; die Voreinstellung bleibt neutral)."""

    HOECHSTZAHL = 5

    mitglied = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="filterprofile"
    )
    name = models.CharField(max_length=40)
    regler = models.JSONField(default=dict, help_text="Reglerstellungen 0–100 je Regel (plattform_core.weicherfilter).")
    favoriten_zuerst = models.BooleanField(
        default=True, help_text="★ Favoriten zuerst: Anträge aus abonnierten Lebensbereichen stehen vorn."
    )
    aktiv = models.BooleanField(default=False)
    geaendert_am = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [("mitglied", "name")]
        ordering = ["pk"]
        verbose_name = "WeicherFilter-Profil"
        verbose_name_plural = "WeicherFilter-Profile"

    def __str__(self) -> str:
        return f"{self.name}{' (aktiv)' if self.aktiv else ''}"


class Bewerbung(models.Model):
    """Eine Bewerbung um das Mandat eines Kandidatur-Antrags (§ 7 Abs 1 E-2.5).

    Bewerben ist bis zum Beginn der Abstimmung möglich — wer sich beteiligt,
    wird im Antragsfenster als wählbar geführt. Anders als das Stimmverhalten
    ist die Bewerbung offen: Wer gewählt werden will, tritt sichtbar an.
    Ein Rückzug bleibt dokumentiert; die Bewerbung zählt dann nicht mehr."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="bewerbungen")
    mitglied = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="bewerbungen"
    )
    vorstellung = models.TextField(
        max_length=2000, blank=True, help_text="Wer bin ich, wofür stehe ich — öffentlich sichtbar."
    )
    rueckgabezusage = models.CharField(
        max_length=20,
        choices=Rueckgabezusage.choices,
        blank=True,
        default=Rueckgabezusage.UNBEKANNT,
        help_text="Erklärung nach § 7 Abs 3, ob die Rückgabezusage abgegeben wird — mit der Bewerbung "
        "abgegeben, beim Kandidatur-Antrag ausgewiesen; leer bei Bewerbungen aus der Zeit vor 0.48.",
    )
    erstellt_am = models.DateTimeField(default=timezone.now)
    zurueckgezogen = models.BooleanField(default=False)

    class Meta:
        unique_together = [("antrag", "mitglied")]  # eine Bewerbung je Mensch je Mandat
        ordering = ["erstellt_am", "pk"]
        verbose_name = "Bewerbung"
        verbose_name_plural = "Bewerbungen"

    def __str__(self) -> str:
        return f"Bewerbung von Mitglied {self.mitglied_id} für Antrag {self.antrag_id}"


class BewerbungsZustimmung(models.Model):
    """Die veröffentlichte Seite einer Personenwahl-Stimme: Pseudonym + Bewerbung.

    Zustimmungswahl (§ 7 Abs 1 E-2.5): Jedes Mitglied kann mehreren Bewerbungen
    zustimmen — jeder aber nur einmal — und jede Zustimmung bis Fristende wieder
    zurücknehmen. Das Pseudonym kommt aus demselben Stimmregister wie bei
    Sachfragen (F-25): geheim für Dritte, nachrechenbar für alle, auffindbar
    für das eigene Mitglied über den Prüfcode. KEIN Personenbezug."""

    bewerbung = models.ForeignKey(Bewerbung, on_delete=models.CASCADE, related_name="zustimmungen")
    pseudonym = models.UUIDField()
    abgegeben_am = models.DateTimeField(default=timezone.now)
    zurueckgenommen_am = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Gesetzt, wenn die Zustimmung zurückgenommen wurde — Stimmdaten werden nie gelöscht "
        "(Grundregel 7); gezählt wird sie dann nicht mehr.",
    )

    class Meta:
        unique_together = [("bewerbung", "pseudonym")]
        verbose_name = "Bewerbungs-Zustimmung"
        verbose_name_plural = "Bewerbungs-Zustimmungen"

    def __str__(self) -> str:
        return f"Zustimmung {self.pseudonym.hex[:8]}… zu Bewerbung {self.bewerbung_id}"

    @classmethod
    def gueltige(cls):
        """Die Zustimmungen, die zählen — ohne die zurückgenommenen (Befund #27)."""
        return cls.objects.filter(zurueckgenommen_am__isnull=True)


class BewerbungsFehler(Exception):
    """Bewerbung derzeit nicht möglich (falsche Antragsart oder Phase)."""


def kandidatursperre(mitglied) -> bool:
    """§ 7 Abs 10 lit f Z 3: Wer eine Vertrauensfrage verloren hat, kandidiert erst wieder nach einer
    Bestätigung durch die Mitgliederversammlung (`Mandat.kandidatursperre`). Lazy geladen —
    `verfahren` bleibt unabhängig von `mandatare`, solange die App fehlt."""
    from django.apps import apps

    if not apps.is_installed("mandatare") or not getattr(mitglied, "pk", None):
        return False  # pragma: no cover
    return (
        apps.get_model("mandatare", "Mandat")
        .objects.filter(mitglied=mitglied, vertrauen_entzogen_am__isnull=False, bestaetigt_am__isnull=True)
        .exists()
    )


def bewerbung_einreichen(antrag: Antrag, mitglied, vorstellung: str, rueckgabezusage: str = "") -> Bewerbung:
    """Sich um das Mandat bewerben bzw. die eigene Bewerbung erneuern (§ 7 Abs 1).
    Möglich bis zum Beginn der Abstimmung; ein früherer Rückzug wird aufgehoben.

    `rueckgabezusage` ist die Erklärung nach § 7 Abs 3 („abgegeben“ / „nicht_abgegeben“), die mit der
    Bewerbung abgegeben wird; das Formular verlangt sie als Pflichtangabe, hier bleibt „“ (unbekannt)
    zulässig, weil Altbewerbungen und der Demo-Bestand ohne sie entstanden sind. Wer nach einer
    verlorenen Vertrauensfrage noch nicht bestätigt ist, wird abgewiesen (§ 7 Abs 10 lit f Z 3)."""
    if antrag.art != Antragsart.MANDAT:
        raise BewerbungsFehler("Dieser Antrag ist keine Mandats-Kandidatur.")
    if kandidatursperre(mitglied):
        raise BewerbungsFehler(
            str(
                _("Nach einer verlorenen Vertrauensfrage ist eine Kandidatur erst nach einer Bestätigung durch die "
                  "Mitgliederversammlung möglich (§ 7 Abs 10 lit f Z 3).")
            )
        )
    antrag.fortschreiben()
    if antrag.phase not in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value):
        raise BewerbungsFehler("Bewerben ist nur bis zum Beginn der Abstimmung möglich (§ 7 Abs 1).")
    text = (vorstellung or "").strip()[:2000]
    zusage = Rueckgabezusage(rueckgabezusage or "")
    bewerbung, neu = Bewerbung.objects.get_or_create(
        antrag=antrag, mitglied=mitglied, defaults={"vorstellung": text, "rueckgabezusage": zusage}
    )
    if not neu:
        bewerbung.vorstellung = text or bewerbung.vorstellung
        bewerbung.zurueckgezogen = False
        if zusage != Rueckgabezusage.UNBEKANNT:
            bewerbung.rueckgabezusage = zusage
        bewerbung.save(update_fields=["vorstellung", "zurueckgezogen", "rueckgabezusage"])
    AuditEintrag.anhaengen(
        {
            "typ": "bewerbung" if neu else "bewerbung_erneuert",
            "antrag": antrag.pk,
            "bewerbung": bewerbung.pk,
            "rueckgabezusage": str(bewerbung.rueckgabezusage),
        }
    )
    return bewerbung


def bewerbung_zustimmen(antrag: Antrag, mitglied, bewerbung: Bewerbung, jetzt=None) -> bool:
    """Zustimmung zu einer Bewerbung geben oder zurücknehmen (Umschalter).
    Rückgabe: True = zugestimmt, False = zurückgenommen. Läuft über das
    Stimmregister des Antrags — geheim und nachrechenbar wie jede Stimme."""
    jetzt = jetzt or timezone.now()
    if antrag.art != Antragsart.MANDAT or bewerbung.antrag_id != antrag.pk:
        raise StimmabgabeFehler("Diese Bewerbung gehört nicht zu dieser Kandidatur.")
    if bewerbung.zurueckgezogen:
        raise StimmabgabeFehler("Diese Bewerbung wurde zurückgezogen und ist nicht wählbar.")
    if not antrag.stimme_zulaessig(jetzt):
        raise StimmabgabeFehler("Für diese Kandidatur läuft derzeit keine Abstimmung.")
    register, _neu = StimmRegister.objects.get_or_create(
        antrag=antrag, mitglied=mitglied, defaults={"pseudonym": uuid.uuid4()}
    )
    zustimmung, angelegt = BewerbungsZustimmung.objects.get_or_create(
        bewerbung=bewerbung, pseudonym=register.pseudonym, defaults={"abgegeben_am": jetzt}
    )
    # Zurücknehmen löscht nicht (Grundregel 7, Befund #27): Die Zeile bekommt einen Stempel, und
    # das Audit unterscheidet die Richtung — sonst sähe, wer Audit und Export gegeneinander
    # prüft, zwei Stimmereignisse und keine Stimme, ohne eine verlorene von einer
    # zurückgenommenen unterscheiden zu können.
    if angelegt or zustimmung.zurueckgenommen_am is not None:
        if not angelegt:
            zustimmung.zurueckgenommen_am = None
            zustimmung.abgegeben_am = jetzt
            zustimmung.save(update_fields=["zurueckgenommen_am", "abgegeben_am"])
        dazu, typ = True, "personenwahl_stimme"
    else:
        zustimmung.zurueckgenommen_am = jetzt
        zustimmung.save(update_fields=["zurueckgenommen_am"])
        dazu, typ = False, "personenwahl_stimme_zurueckgenommen"
    AuditEintrag.anhaengen(
        {
            "typ": typ,
            "antrag": antrag.pk,
            "pseudonym": register.pseudonym.hex,
            # bewusst OHNE Bewerbungs-ID und OHNE Mitglieds-ID: Das Audit-Log ist
            # öffentlich — wem zugestimmt wurde, zeigt erst die Auszählung nach Fristende.
        }
    )
    return dazu


class StimmabgabeFehler(Exception):
    pass


def stimme_abgeben(antrag: Antrag, mitglied, stimme: str, jetzt=None) -> Stimmabgabe:
    """Stimmabgabe bzw. -änderung während laufender Abstimmung (§ 5 Abs 3 lit d)."""
    jetzt = jetzt or timezone.now()
    if not antrag.stimme_zulaessig(jetzt):
        raise StimmabgabeFehler("Für diesen Antrag läuft derzeit keine Abstimmung.")
    stimme = KernStimme(stimme).value
    register, neu = StimmRegister.objects.get_or_create(
        antrag=antrag, mitglied=mitglied, defaults={"pseudonym": uuid.uuid4()}
    )
    abgabe, _ = Stimmabgabe.objects.update_or_create(
        antrag=antrag,
        pseudonym=register.pseudonym,
        defaults={"stimme": stimme, "abgegeben_am": jetzt},
    )
    AuditEintrag.anhaengen(
        {
            "typ": "stimme" if neu else "stimme_geaendert",
            "antrag": antrag.pk,
            "pseudonym": register.pseudonym.hex,
            # bewusst OHNE Stimmwert und OHNE Mitglieds-ID: Das Audit-Log ist öffentlich.
        }
    )
    return abgabe


class Kommentar(models.Model):
    """Ein Beitrag im Chat eines Antrags (§ 5 Abs 3 lit c, FB-G1). Nur Mitglieder schreiben,
    alle lesen mit.

    Der Faden ist eine Ebene tief: `antwort_auf` zeigt auf den Wurzelbeitrag; eine Antwort auf
    eine Antwort hängt sich an denselben Wurzelbeitrag (`wurzel()`), damit der Faden lesbar
    bleibt. Jeder Beitrag merkt sich die `phase`, in der er geschrieben wurde — bei jeder
    Hochstufung werden die Beiträge der bisherigen Phase mit `archiviert_am` gestempelt und
    verschwinden aus dem laufenden Chat, ohne gelöscht zu werden (FB-G5, Grundregel 7).
    Auch das Entfernen durch den Verfasser und das Ausblenden durch die Verwaltung lassen den
    Beitrag stehen; nur sein Text weicht einem Vermerk."""

    #: Rückfallwert in Minuten; der gültige steht im Register unter „chat-bearbeitungsfenster-minuten".
    BEARBEITUNGSFENSTER_MINUTEN = 5

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="kommentare")
    mitglied = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        help_text="Leer beim Systembeitrag der Plattform („Passt alles“) — sonst der Verfasser.",
    )
    text = models.TextField(max_length=4000)
    antwort_auf = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="antworten",
        help_text="Wurzelbeitrag dieses Fadens — leer bei einem eigenen Faden.",
    )
    phase = models.CharField(
        max_length=20, blank=True,
        help_text="Phase des Antrags beim Schreiben — die Grundlage der Archivierung bei Hochstufung.",
    )
    erstellt_am = models.DateTimeField(default=timezone.now)
    bearbeitet_am = models.DateTimeField(null=True, blank=True)
    archiviert_am = models.DateTimeField(
        null=True, blank=True, help_text="Bei Hochstufung gesetzt: der Beitrag wandert ins Archiv."
    )
    geloescht = models.BooleanField(default=False, help_text="Vom Verfasser entfernt — die Struktur bleibt.")
    ausgeblendet_am = models.DateTimeField(null=True, blank=True)
    ausgeblendet_grund = models.CharField(
        max_length=200, blank=True, help_text="Öffentlicher Grund der Verwaltung (Art 17 DSA)."
    )
    system = models.BooleanField(
        default=False, help_text="Von der Plattform angelegt — der „Passt alles“-Eintrag des Abstimmungs-Chats."
    )
    ist_kritik = models.BooleanField(
        default=False, help_text="Konkrete Kritik am Vorschlag des Expertenrats — geht bei Rückgabe an ihn."
    )
    bezug_absatz = models.PositiveIntegerField(
        null=True, blank=True, help_text="Absatz des Vorschlags, auf den sich die Kritik bezieht (ab 1)."
    )

    class Meta:
        ordering = ["erstellt_am"]
        verbose_name = "Kommentar"
        verbose_name_plural = "Kommentare"
        indexes = [models.Index(fields=["antrag", "archiviert_am", "erstellt_am"])]

    def __str__(self) -> str:
        return f"Kommentar von Mitglied {self.mitglied_id} zu Antrag {self.antrag_id}"

    def wurzel(self) -> Kommentar:
        """Der Beitrag, unter dem dieser Faden hängt — bei Wurzelbeiträgen er selbst."""
        return self.antwort_auf or self

    def sichtbarer_text(self) -> str:
        if self.ausgeblendet_am:
            return str(_("[von der Verwaltung ausgeblendet: %s]") % (self.ausgeblendet_grund or _("kein Grund angegeben")))
        if self.geloescht:
            return str(_("[vom Verfasser entfernt]"))
        return self.text

    @classmethod
    def bearbeitungsfenster_minuten(cls) -> int:
        """Wie lange ein Beitrag änderbar bleibt — aus dem Register (FB-G1, Befund #69).

        Bis 0.44 stand hier eine harte Konstante, während das öffentliche Register denselben
        Wert als Stellgröße führte und die Verwaltung ihn ändern konnte, ohne dass etwas geschah."""
        from parameter.models import zahl

        return zahl("chat-bearbeitungsfenster-minuten", cls.BEARBEITUNGSFENSTER_MINUTEN)

    def darf_bearbeiten(self, mitglied, jetzt=None) -> bool:
        """Ändern nur durch den Verfasser und nur binnen des Bearbeitungsfensters (FB-G1)."""
        jetzt = jetzt or timezone.now()
        return (
            mitglied.is_authenticated
            and mitglied.pk == self.mitglied_id
            and not self.geloescht
            and not self.ausgeblendet_am
            and not self.archiviert_am
            and jetzt - self.erstellt_am <= timedelta(minutes=self.bearbeitungsfenster_minuten())
        )


class Reaktionsart(models.TextChoices):
    ZUSTIMMUNG = "zustimmung", _("Zustimmung")
    ABLEHNUNG = "ablehnung", _("Ablehnung")


class Reaktion(models.Model):
    """Zustimmung oder Ablehnung zu einem Beitrag (FB-G1, FB-G6).

    Außerhalb des Abstimmungs-Chats nur Zustimmung, rein informativ — sie wirkt nie auf die
    Reihung (D-G1, Grundregel 6). Im Abstimmungs-Chat des Expertenrats-Vorschlags (S7) ist sie
    das Votum der Unterstützer. Eine Reaktion je Mitglied und Beitrag, umschaltbar."""

    kommentar = models.ForeignKey(Kommentar, on_delete=models.CASCADE, related_name="reaktionen")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    art = models.CharField(max_length=12, choices=Reaktionsart.choices, default=Reaktionsart.ZUSTIMMUNG)
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("kommentar", "mitglied")]
        verbose_name = "Reaktion"
        verbose_name_plural = "Reaktionen"

    def __str__(self) -> str:
        return f"{self.get_art_display()} von Mitglied {self.mitglied_id} zu Beitrag {self.kommentar_id}"


class Lesestand(models.Model):
    """Wie weit ein Mitglied den Chat eines Antrags gelesen hat (FB-G2).

    Geräteübergreifend und serverseitig — daraus entsteht die Trennlinie „n neue Beiträge"
    und der Ungelesen-Punkt im Gesprächs-Panel. Die genaue Scrollstelle merkt sich zusätzlich
    das Gerät selbst (localStorage); dieser Stand hier ist die gemeinsame Wahrheit."""

    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesestaende")
    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="lesestaende")
    gelesen_bis = models.DateTimeField(default=timezone.now, help_text="Zeitpunkt des zuletzt gelesenen Beitrags.")

    class Meta:
        unique_together = [("mitglied", "antrag")]
        verbose_name = "Lesestand"
        verbose_name_plural = "Lesestände"

    def __str__(self) -> str:
        return f"Lesestand von Mitglied {self.mitglied_id} zu Antrag {self.antrag_id}"


class Meldung(models.Model):
    """Meldung eines Beitrags durch ein Mitglied (Art 16 DSA, § 5 Abs 2, FB-G1).

    Die Meldung geht an die Verwaltung; sie kann den Beitrag mit öffentlichem Grund ausblenden.
    Meldungen werden nie gelöscht — auch die Entscheidung bleibt nachlesbar."""

    class Grund(models.TextChoices):
        BELEIDIGUNG = "beleidigung", _("Beleidigung oder Herabwürdigung")
        FALSCH = "falsch", _("Nachweislich falsche Tatsachenbehauptung")
        THEMA = "thema", _("Kein Bezug zum Antrag")
        RECHT = "recht", _("Rechtswidriger Inhalt")
        SONST = "sonst", _("Sonstiges")

    kommentar = models.ForeignKey(Kommentar, on_delete=models.CASCADE, related_name="meldungen")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    grund = models.CharField(max_length=20, choices=Grund.choices)
    erlaeuterung = models.CharField(max_length=500, blank=True)
    erstellt_am = models.DateTimeField(default=timezone.now)
    erledigt_am = models.DateTimeField(null=True, blank=True)
    entscheidung = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["-erstellt_am"]
        unique_together = [("kommentar", "mitglied")]
        verbose_name = "Meldung"
        verbose_name_plural = "Meldungen"

    def __str__(self) -> str:
        return f"Meldung ({self.grund}) zu Beitrag {self.kommentar_id}"


class Beanstandung(models.Model):
    """Beanstandung einer Einschätzung der Zukunftswerkstatt (§ 6 Abs 11 lit b, FB-F2).

    Die Modellrechnung schlägt vor, sie entscheidet nie (Grundregel 5) — und sie kann irren.
    Wer einen Fehler sieht, hält ihn hier fest: öffentlich, mit Namen, append-only. Der Eintrag
    ist zugleich die Anforderung eines Korrekturlaufs; die Antwort der Werkstatt kommt als
    `erledigt_vermerk` dazu, der Text selbst wird nie geändert (Grundregel 7)."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="beanstandungen")
    lauf = models.ForeignKey(
        "ki.KILauf", null=True, blank=True, on_delete=models.SET_NULL, related_name="beanstandungen",
        help_text="Der beanstandete Lauf — leer, wenn die Einschätzung inzwischen ersetzt wurde.",
    )
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField(max_length=2000, help_text="Was ist falsch? Sachlich, mit Beleg wenn möglich.")
    erstellt_am = models.DateTimeField(default=timezone.now)
    erledigt_am = models.DateTimeField(null=True, blank=True)
    erledigt_vermerk = models.TextField(max_length=2000, blank=True)

    class Meta:
        ordering = ["-erstellt_am"]
        verbose_name = "Beanstandung einer Einschätzung"
        verbose_name_plural = "Beanstandungen von Einschätzungen"

    def __str__(self) -> str:
        return f"Beanstandung von Mitglied {self.mitglied_id} zu Antrag {self.antrag_id}"


def kategorien_zuordnen(antrag: Antrag) -> list[Kategorie]:
    """F-47 Stufe 1: automatische Zuordnung zu Lebensbereichen — deterministisch,
    nachrechenbar (plattform_core.klassifikation), auditiert. Die Zuordnung ist
    Vorschlag ohne Sperrwirkung; der Integritätsrat kann sie korrigieren."""
    from plattform_core.klassifikation import zuordnen

    fassung = antrag.aktueller_text()
    text = " ".join(
        [antrag.titel, fassung.wortlaut if fassung else "", fassung.begruendung if fassung else ""]
    )
    aktive = list(Kategorie.objects.filter(aktiv=True).values_list("id", "eltern_id", "schlagworte"))
    from parameter.models import zahl

    treffer = zuordnen(text, aktive, limit=zahl("kategorien-je-antrag", 3))
    kategorien = list(Kategorie.objects.filter(id__in=[kid for kid, _ in treffer]))
    kategorien.sort(key=lambda k: [kid for kid, _ in treffer].index(k.pk))
    antrag.kategorien.set(kategorien)
    AuditEintrag.anhaengen(
        {
            "typ": "kategorien_zugeordnet",
            "antrag": antrag.pk,
            "kategorien": [k.slug for k in kategorien],
            "methode": "schlagworte-v1",
        }
    )
    return kategorien
