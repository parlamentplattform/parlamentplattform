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

from django.conf import settings
from django.db import models
from django.utils import timezone

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


class Antrag(models.Model):
    """Ein Antrag nach § 5 — mit eingefrorener Policy."""

    titel = models.CharField(max_length=200)
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

    def fortschreiben(self, jetzt=None) -> bool:
        """Prüft fällige Übergänge und wendet sie an (idempotent).
        Rückgabe: True, wenn sich die Phase geändert hat."""
        jetzt = jetzt or timezone.now()
        phase = Phase(self.phase)
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
        self.phase = uebergang.neue_phase.value
        self.phase_beginn = uebergang.wirksam_ab
        felder = ["phase", "phase_beginn"]
        if uebergang.neue_phase is Phase.ABSTIMMUNG and self.stimmberechtigte_anzahl is None:
            # § 4 Abs 4 lit a: Zahl der Stimmberechtigten wird bei Abstimmungsbeginn
            # festgestellt, veröffentlicht und danach nie mehr verändert.
            from django.conf import settings as dj_settings

            from mitglieder.models import stimmberechtigte_zaehlen
            from plattform_core import Gegenstand

            self.stimmberechtigte_anzahl = max(
                1,
                stimmberechtigte_zaehlen(
                    Gegenstand.SACHFRAGE,
                    uebergang.wirksam_ab.date(),
                    uebergang=getattr(dj_settings, "DDOE_UEBERGANGSREGEL", True),
                ),
            )
            felder.append("stimmberechtigte_anzahl")
        self.save(update_fields=felder)
        AuditEintrag.anhaengen(
            {
                "typ": "phasenwechsel",
                "antrag": self.pk,
                "neue_phase": uebergang.neue_phase.value,
                "wirksam_ab": uebergang.wirksam_ab.isoformat(),
                "grund": uebergang.grund,
            }
        )
        return True

    def stimme_zulaessig(self, jetzt=None) -> bool:
        jetzt = jetzt or timezone.now()
        return stimme_zulaessig(Phase(self.phase), self.phase_beginn, jetzt, self.policy())

    def auszaehlen(self):
        stimmen = [(s.pseudonym.hex, s.stimme) for s in self.stimmabgaben.all()]
        return auszaehlen(stimmen, self.stimmberechtigte_anzahl or 1, self.policy())


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
) -> Antrag:
    """Einbringen nach § 5 Abs 2–3: Policy einfrieren, Fassung 1 anlegen, auditieren."""
    policy = ordnung.als_policy()  # validiert die Regeln gegen die Satzungsminima
    antrag = Antrag.objects.create(
        titel=titel,
        eingebracht_von=mitglied,
        policy_snapshot=policy.als_dict(),
        ebene=Ebene(ebene),
        gebiet=gebiet,
    )
    AntragsFassung.objects.create(antrag=antrag, nummer=1, wortlaut=wortlaut, begruendung=begruendung)
    AuditEintrag.anhaengen(
        {
            "typ": "antrag_eingebracht",
            "antrag": antrag.pk,
            "titel": titel,
            "policy": f"{policy.id} v{policy.version}",
        }
    )
    return antrag


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
    """Beitrag zur Beratungsphase (§ 5 Abs 3 lit c). Nur Mitglieder; öffentlich lesbar."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="kommentare")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField(max_length=4000)
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["erstellt_am"]
        verbose_name = "Kommentar"
        verbose_name_plural = "Kommentare"

    def __str__(self) -> str:
        return f"Kommentar von Mitglied {self.mitglied_id} zu Antrag {self.antrag_id}"


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
