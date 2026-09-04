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

import secrets
import uuid
from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
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

    BUND = "bund", "Bund"
    LAND = "land", "Land"
    BEZIRK = "bezirk", "Bezirk"
    GEMEINDE = "gemeinde", "Gemeinde"


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
        help_text="Übergeordnete Kategorie — leer bei Hauptkategorien. Der Baum trägt die Drill-down-Zuordnung (F-45).",
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
        help_text="Schlagwortliste für die automatische Zuordnung (F-47, Stufe 1) — gepflegt in der YAML-Quelle.",
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
    gewinnt, die Zustimmungsreihenfolge ergibt die Reihung des Wahlvorschlags."""

    SACHE = "sache", "Sachantrag"
    MANDAT = "mandat", "Mandats-Kandidatur"


class Antrag(models.Model):
    """Ein Antrag nach § 5 — mit eingefrorener Policy."""

    titel = models.CharField(max_length=200)
    art = models.CharField(
        max_length=12,
        choices=Antragsart.choices,
        default=Antragsart.SACHE,
        help_text="Sachantrag (§ 5) oder Mandats-Kandidatur (§ 7 Abs 1, F-70).",
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
    zurueckweisung_begruendung = models.TextField(
        blank=True,
        help_text="Nur bei formaler Zurückweisung durch den Integritätsrat — wird veröffentlicht (§ 5 Abs 2).",
    )
    ebene = models.CharField(
        max_length=12,
        choices=Ebene.choices,
        default=Ebene.BUND,
        help_text="Territoriale Ebene (§ 14) — regionale Anträge erscheinen im Bereich c des Hauptfensters (F-43).",
    )
    gebiet = models.CharField(
        max_length=120,
        blank=True,
        help_text="Name des Landes, Bezirks bzw. der Gemeinde bei regionalen Anträgen.",
    )
    hervorgehoben = models.BooleanField(
        default=False,
        help_text="Bereich b des Hauptfensters (F-42): wichtige Abstimmung, die alle angeht, aber wenig "
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
        help_text="Lebensbereiche des Antrags (F-45) — automatisch zugeordnet (F-47), "
        "durch den Integritätsrat korrigierbar.",
    )

    class Meta:
        verbose_name = "Antrag"
        verbose_name_plural = "Anträge"
        ordering = ["-eingebracht_am"]

    def __str__(self) -> str:
        return f"#{self.pk} {self.titel} [{self.phase}]"

    # --- Kern-Anbindung -----------------------------------------------------

    def policy(self) -> Policy:
        return Policy.aus_dict(self.policy_snapshot)

    def aktueller_text(self) -> AntragsFassung | None:
        return self.fassungen.order_by("-nummer").first()

    @transaction.atomic
    def fortschreiben(self, jetzt=None) -> bool:
        """Prüft fällige Übergänge und wendet sie an (idempotent).
        Rückgabe: True, wenn sich die Phase geändert hat.

        Atomar, weil ein Phasenwechsel drei Dinge zugleich sind: neue Phase, archivierter Chat
        (FB-G5) und Audit-Eintrag. Bricht eines ab, darf keines stehenbleiben."""
        jetzt = jetzt or timezone.now()
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
        uebergang = naechster_uebergang(
            phase,
            self.phase_beginn,
            jetzt,
            policy,
            unterstuetzungen=self.unterstuetzungen.count(),
            auszaehlung=ausz,
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
            from plattform_core import Gegenstand

            # § 4 Abs 4: Personenwahlen haben eine längere Anwartschaft als Sachfragen.
            gegenstand = (
                Gegenstand.PERSONENWAHL if self.art == Antragsart.MANDAT else Gegenstand.SACHFRAGE
            )
            self.stimmberechtigte_anzahl = max(
                1,
                stimmberechtigte_zaehlen(
                    gegenstand,
                    uebergang.wirksam_ab.date(),
                    uebergang=getattr(dj_settings, "DDOE_UEBERGANGSREGEL", True),
                ),
            )
            felder.append("stimmberechtigte_anzahl")
        self.save(update_fields=felder)
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
        return True

    def chat_archivieren(self, jetzt=None) -> int:
        """FB-G5: Bei jeder Hochstufung wandern die Beiträge der bisherigen Phase ins Archiv.

        Archivieren heißt Sichtbarkeit ändern, nicht entfernen (Grundregel 7): Der laufende
        Chat beginnt leer, die Beiträge bleiben unter ihrer Phase lesbar. Idempotent —
        was schon gestempelt ist, bleibt unberührt. Rückgabe: Zahl der archivierten Beiträge."""
        return self.kommentare.filter(archiviert_am__isnull=True).update(
            archiviert_am=jetzt or timezone.now()
        )

    def stimme_zulaessig(self, jetzt=None) -> bool:
        jetzt = jetzt or timezone.now()
        return stimme_zulaessig(Phase(self.phase), self.phase_beginn, jetzt, self.policy())

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
            for z in BewerbungsZustimmung.objects.filter(
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
    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="unterstuetzungen")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    erklaert_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("antrag", "mitglied")]  # einmal je Mensch
        verbose_name = "Unterstützung"
        verbose_name_plural = "Unterstützungen"

    def __str__(self) -> str:
        return f"Unterstützung Antrag {self.antrag_id} durch Mitglied {self.mitglied_id}"


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

    OFFEN = "offen", "offen"
    IN_UMSETZUNG = "in_umsetzung", "in Umsetzung"
    BLOCKIERT = "blockiert", "blockiert"
    UMGESETZT = "umgesetzt", "umgesetzt"
    ZURUECKGESTELLT = "zurueckgestellt", "zurückgestellt"


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
        help_text="Öffentlicher Vermerk: Stand, Hindernis, nächster Schritt, Termin (F-56-Raster).",
    )
    erstellt_am = models.DateTimeField(default=timezone.now)
    durch = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")

    class Meta:
        ordering = ["-erstellt_am", "-pk"]
        verbose_name = "Vollzugseintrag"
        verbose_name_plural = "Umsetzungsregister"

    def __str__(self) -> str:
        return f"Antrag {self.antrag_id}: {self.status}"


def vollzug_fortschreiben(antrag: Antrag, mitglied, status: str, vermerk: str = "") -> Vollzugseintrag:
    """F-55: den Umsetzungsstand fortschreiben — nur für angenommene Anträge,
    immer als neuer Eintrag, immer auditiert."""
    if antrag.phase != Phase.ANGENOMMEN.value:
        raise ValueError("Das Umsetzungsregister führt nur angenommene Anträge (§ 6 Abs 10).")
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
    und der Admin ist read-only registriert."""

    lfd = models.BigAutoField(primary_key=True)
    zeit = models.DateTimeField(default=timezone.now)
    ereignis = models.JSONField()
    hash = models.CharField(max_length=64, editable=False)

    class Meta:
        verbose_name = "Audit-Eintrag"
        verbose_name_plural = "Audit-Log"
        ordering = ["lfd"]

    def __str__(self) -> str:
        return f"Audit #{self.lfd} {self.ereignis.get('typ', '?')}"

    @classmethod
    def anhaengen(cls, ereignis: dict) -> AuditEintrag:
        letzter = cls.objects.order_by("-lfd").first()
        vorgaenger = letzter.hash if letzter else GENESIS
        return cls.objects.create(ereignis=ereignis, hash=ereignis_hash(vorgaenger, ereignis))


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
        default=True, help_text="★ Favoriten zuerst: Anträge aus abonnierten Lebensbereichen stehen vorn (FB-B1)."
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

    class Meta:
        unique_together = [("bewerbung", "pseudonym")]
        verbose_name = "Bewerbungs-Zustimmung"
        verbose_name_plural = "Bewerbungs-Zustimmungen"

    def __str__(self) -> str:
        return f"Zustimmung {self.pseudonym.hex[:8]}… zu Bewerbung {self.bewerbung_id}"


class BewerbungsFehler(Exception):
    """Bewerbung derzeit nicht möglich (falsche Antragsart oder Phase)."""


def bewerbung_einreichen(antrag: Antrag, mitglied, vorstellung: str) -> Bewerbung:
    """Sich um das Mandat bewerben bzw. die eigene Bewerbung erneuern (§ 7 Abs 1).
    Möglich bis zum Beginn der Abstimmung; ein früherer Rückzug wird aufgehoben."""
    if antrag.art != Antragsart.MANDAT:
        raise BewerbungsFehler("Dieser Antrag ist keine Mandats-Kandidatur.")
    antrag.fortschreiben()
    if antrag.phase not in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value):
        raise BewerbungsFehler("Bewerben ist nur bis zum Beginn der Abstimmung möglich (§ 7 Abs 1).")
    text = (vorstellung or "").strip()[:2000]
    bewerbung, neu = Bewerbung.objects.get_or_create(
        antrag=antrag, mitglied=mitglied, defaults={"vorstellung": text}
    )
    if not neu:
        bewerbung.vorstellung = text or bewerbung.vorstellung
        bewerbung.zurueckgezogen = False
        bewerbung.save(update_fields=["vorstellung", "zurueckgezogen"])
    AuditEintrag.anhaengen(
        {"typ": "bewerbung" if neu else "bewerbung_erneuert", "antrag": antrag.pk, "bewerbung": bewerbung.pk}
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
    if not angelegt:
        zustimmung.delete()
    AuditEintrag.anhaengen(
        {
            "typ": "personenwahl_stimme",
            "antrag": antrag.pk,
            "pseudonym": register.pseudonym.hex,
            # bewusst OHNE Bewerbungs-ID und OHNE Mitglieds-ID: Das Audit-Log ist
            # öffentlich — wem zugestimmt wurde, zeigt erst die Auszählung nach Fristende.
        }
    )
    return angelegt


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

    BEARBEITUNGSFENSTER = timedelta(minutes=5)  # danach ist der Text unveränderlich (FB-G1)

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="kommentare")
    mitglied = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True,
        help_text="Leer beim Systembeitrag der Plattform („Passt alles“, FB-G6) — sonst der Verfasser.",
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
        null=True, blank=True, help_text="Bei Hochstufung gesetzt: der Beitrag wandert ins Archiv (FB-G5)."
    )
    geloescht = models.BooleanField(default=False, help_text="Vom Verfasser entfernt — die Struktur bleibt.")
    ausgeblendet_am = models.DateTimeField(null=True, blank=True)
    ausgeblendet_grund = models.CharField(
        max_length=200, blank=True, help_text="Öffentlicher Grund der Verwaltung (Art 17 DSA)."
    )
    system = models.BooleanField(
        default=False, help_text="Von der Plattform angelegt — der „Passt alles“-Eintrag des Abstimmungs-Chats (FB-G6)."
    )
    ist_kritik = models.BooleanField(
        default=False, help_text="Konkrete Kritik am Vorschlag des Expertenrats — geht bei Rückgabe an ihn (FB-G6)."
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

    def darf_bearbeiten(self, mitglied, jetzt=None) -> bool:
        """Ändern nur durch den Verfasser und nur binnen fünf Minuten (FB-G1)."""
        jetzt = jetzt or timezone.now()
        return (
            mitglied.is_authenticated
            and mitglied.pk == self.mitglied_id
            and not self.geloescht
            and not self.ausgeblendet_am
            and not self.archiviert_am
            and jetzt - self.erstellt_am <= self.BEARBEITUNGSFENSTER
        )


class Reaktionsart(models.TextChoices):
    ZUSTIMMUNG = "zustimmung", "Zustimmung"
    ABLEHNUNG = "ablehnung", "Ablehnung"


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
        BELEIDIGUNG = "beleidigung", "Beleidigung oder Herabwürdigung"
        FALSCH = "falsch", "Nachweislich falsche Tatsachenbehauptung"
        THEMA = "thema", "Kein Bezug zum Antrag"
        RECHT = "recht", "Rechtswidriger Inhalt"
        SONST = "sonst", "Sonstiges"

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
    treffer = zuordnen(text, aktive)
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
