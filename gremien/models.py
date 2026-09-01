"""Die Gremien-Werkstatt, Ring 0a (F-66, § 6): Rollen auf Zeit, Entwurfsfenster,
interne dokumentierte Abstimmungen und die Übergabe-Handlungen des Verfahrens.

Bausteine:
- **Rolle** — befristete Berufung in ein Gremium (§ 6 Abs 8: zwei Jahre,
  Bestätigung durch die Mitgliederversammlung, automatisches Erlöschen).
- **Entwurf** — das Entwurfsfenster des Expertenrats (Gruppe 1) je Antrag in
  der Beratung: append-only-Fassungen, interne Beiträge, die interne
  Einreich-Abstimmung und der Zustand der Entwurfsschleife (§ 5 Abs 12).
- **Pruefung** — die Korruptions-Redundanz der Gruppe 2 bei Vorschlägen mit
  Vollzugs- oder Beschaffungsbezug (§ 6 Abs 7): validieren, begründet
  zurückgeben oder beim Koordinationsrat den Austausch beantragen.
- **UnterstuetzerVotum** — die Schleife selbst: Die Unterstützer des Antrags
  nehmen den Vorschlag an oder geben ihn mit Wünschen zurück.

Fristlogik ohne Blockademacht (F-67, § 5 Abs 12 „Untätigkeit hemmt nie"):
Bleiben Stimmen aus, wertet der Fristablauf aus; bleibt eine Überarbeitung
aus, geht die zuletzt vorgelegte Fassung zur Endabstimmung. Die Beratung
eines Antrags bleibt nur offen, solange die Schleife tatsächlich arbeitet.

Offene Parameter (Zielwerte des Fahrplans, wandern mit F-68 ins Register):
REVIEW_TAGE = 14 (Unterstützer), UEBERARBEITUNG_TAGE = 14 (Expertenrat),
HOECHSTRUNDEN = 3 (Rundenzahl der Schleife, „per Verfahrensordnung")."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

from verfahren.models import Antrag, AntragsFassung, AuditEintrag

REVIEW_TAGE = 14
UEBERARBEITUNG_TAGE = 14
HOECHSTRUNDEN = 3


class Gremium(models.TextChoices):
    EXPERTENRAT_1 = "expertenrat1", "Expertenrat — Gruppe 1 (Entwurf)"
    EXPERTENRAT_2 = "expertenrat2", "Expertenrat — Gruppe 2 (Prüfung)"
    KOORDINATIONSRAT = "koordinationsrat", "Koordinationsrat"
    INTEGRITAETSRAT = "integritaetsrat", "Integritätsrat"


class Rolle(models.Model):
    """Eine befristete Berufung (§ 6 Abs 8): zwei Jahre, öffentlich, auditiert.
    Erlöschen geschieht automatisch über das Ablaufdatum; eine vorzeitige
    Beendigung (Abberufung, Austausch) bleibt mit Grund dokumentiert."""

    mitglied = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="rollen"
    )
    gremium = models.CharField(max_length=20, choices=Gremium.choices)
    berufen_am = models.DateField(default=timezone.localdate)
    endet_am = models.DateField(help_text="Automatisches Erlöschen — Rollen sind Rollen auf Zeit (§ 6 Abs 8).")
    bestaetigt = models.BooleanField(
        default=False, help_text="Bestätigung der Bestellung durch die Mitgliederversammlung (§ 6 Abs 8)."
    )
    beendet_grund = models.CharField(max_length=200, blank=True)

    class Meta:
        ordering = ["gremium", "berufen_am"]
        verbose_name = "Rolle"
        verbose_name_plural = "Rollen"

    def __str__(self) -> str:
        return f"{self.get_gremium_display()}: Mitglied {self.mitglied_id}"

    @property
    def aktiv(self) -> bool:
        return not self.beendet_grund and self.endet_am >= timezone.localdate()

    @classmethod
    def aktive(cls, gremium: str):
        return cls.objects.filter(
            gremium=gremium, beendet_grund="", endet_am__gte=timezone.localdate()
        )

    @classmethod
    def hat(cls, mitglied, *gremien: str) -> bool:
        if not getattr(mitglied, "is_authenticated", False):
            return False
        return cls.objects.filter(
            mitglied=mitglied,
            gremium__in=gremien,
            beendet_grund="",
            endet_am__gte=timezone.localdate(),
        ).exists()


def standard_ende():
    return timezone.localdate() + timedelta(days=730)  # zwei Jahre, § 6 Abs 8


class EntwurfsStatus(models.TextChoices):
    IN_ARBEIT = "in_arbeit", "in Arbeit (Expertenrat)"
    PRUEFUNG = "pruefung", "in Prüfung (Gruppe 2)"
    UNTERSTUETZER = "unterstuetzer", "liegt den Unterstützern vor"
    ANGENOMMEN = "angenommen", "zur Endabstimmung übergeben"


class Entwurf(models.Model):
    """Das Entwurfsfenster je Antrag (F-66/F-67): hier entsteht der Vorschlag
    des Expertenrats (Terminus: immer „Vorschlag"), der über die
    Entwurfsschleife (§ 5 Abs 12) zur Endabstimmung hochgestuft wird."""

    antrag = models.OneToOneField(Antrag, on_delete=models.CASCADE, related_name="entwurf")
    status = models.CharField(
        max_length=16, choices=EntwurfsStatus.choices, default=EntwurfsStatus.IN_ARBEIT
    )
    runde = models.PositiveIntegerField(default=1)
    vollzugsbezug = models.BooleanField(
        default=False,
        help_text="Unmittelbarer Vollzugs- oder Beschaffungsbezug — dann prüft Gruppe 2 (§ 6 Abs 7).",
    )
    eingereicht_am = models.DateTimeField(null=True, blank=True)
    review_frist = models.DateTimeField(null=True, blank=True)
    ueberarbeitung_frist = models.DateTimeField(null=True, blank=True)
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Entwurf"
        verbose_name_plural = "Entwürfe"

    def __str__(self) -> str:
        return f"Entwurf zu Antrag {self.antrag_id} (Runde {self.runde}, {self.get_status_display()})"

    # ── Lesehilfen ────────────────────────────────────────────────────────────

    def aktuelle_fassung(self):
        return self.fassungen.order_by("-nummer").first()

    def einreich_stand(self) -> dict:
        """Interne Abstimmung der Gruppe 1 (dokumentiert, § 6 Abs 8/9):
        einreichbar bei einfacher Mehrheit und mindestens der Hälfte der
        aktiven Rollen als Zustimmung (Beschlussfähigkeit)."""
        stimmen = list(self.einreich_stimmen.filter(runde=self.runde))
        ja = sum(1 for s in stimmen if s.einverstanden)
        nein = len(stimmen) - ja
        aktive = Rolle.aktive(Gremium.EXPERTENRAT_1).count()
        noetig = max(1, (aktive + 1) // 2)
        return {
            "ja": ja,
            "nein": nein,
            "aktive": aktive,
            "noetig": noetig,
            "einreichbar": ja >= noetig and ja > nein and self.aktuelle_fassung() is not None,
        }

    def votum_stand(self) -> dict:
        voten = list(self.unterstuetzer_voten.filter(runde=self.runde))
        annahmen = sum(1 for v in voten if v.annehmen)
        rueckgaben = len(voten) - annahmen
        unterstuetzer = self.antrag.unterstuetzungen.count()
        return {"annahmen": annahmen, "rueckgaben": rueckgaben, "unterstuetzer": unterstuetzer}

    def haelt_beratung_offen(self, jetzt=None) -> bool:
        """Die Beratung bleibt NUR offen, solange die Schleife arbeitet — nie
        durch bloßes Bestehen eines unfertigen Entwurfs (keine Blockademacht):
        eingereicht/in Prüfung/im Review, oder eine laufende Überarbeitung."""
        jetzt = jetzt or timezone.now()
        if self.status in (EntwurfsStatus.PRUEFUNG, EntwurfsStatus.UNTERSTUETZER):
            return True
        return (
            self.status == EntwurfsStatus.IN_ARBEIT
            and self.runde > 1
            and self.ueberarbeitung_frist is not None
            and jetzt < self.ueberarbeitung_frist
        )

    # ── Übergabe-Handlungen ──────────────────────────────────────────────────

    def einreichen(self, jetzt=None) -> None:
        """Gruppe 1 reicht den Vorschlag ein: mit Vollzugsbezug zuerst zur
        Prüfung der Gruppe 2, sonst direkt an die Unterstützer (§ 5 Abs 12)."""
        jetzt = jetzt or timezone.now()
        self.eingereicht_am = jetzt
        if self.vollzugsbezug:
            self.status = EntwurfsStatus.PRUEFUNG
        else:
            self.status = EntwurfsStatus.UNTERSTUETZER
            self.review_frist = jetzt + timedelta(days=REVIEW_TAGE)
        self.ueberarbeitung_frist = None
        self.save()
        AuditEintrag.anhaengen(
            {
                "typ": "vorschlag_eingereicht",
                "antrag": self.antrag_id,
                "runde": self.runde,
                "weg": "pruefung" if self.vollzugsbezug else "unterstuetzer",
            }
        )

    def zu_den_unterstuetzern(self, jetzt=None) -> None:
        jetzt = jetzt or timezone.now()
        self.status = EntwurfsStatus.UNTERSTUETZER
        self.review_frist = jetzt + timedelta(days=REVIEW_TAGE)
        self.save(update_fields=["status", "review_frist"])

    def zurueck_an_gruppe_1(
        self, grund: str, jetzt=None, neue_runde: bool = False, frist_erneuern: bool = False
    ) -> None:
        """Zurück in die Werkstatt: mit neuer Runde (Unterstützer-Rückgabe) oder
        ohne (Gruppe 2, § 6 Abs 7). frist_erneuern gibt einer laufenden
        Überarbeitung (Runde > 1) frische Zeit, ohne die Runden zu zählen."""
        jetzt = jetzt or timezone.now()
        self.status = EntwurfsStatus.IN_ARBEIT
        if neue_runde:
            self.runde += 1
            self.ueberarbeitung_frist = jetzt + timedelta(days=UEBERARBEITUNG_TAGE)
        elif frist_erneuern and self.runde > 1:
            self.ueberarbeitung_frist = jetzt + timedelta(days=UEBERARBEITUNG_TAGE)
        self.save()
        AuditEintrag.anhaengen(
            {"typ": "vorschlag_zurueckgegeben", "antrag": self.antrag_id, "runde": self.runde, "grund": grund}
        )

    def _endabstimmung_oeffnen(self, antrag: Antrag, grund: str, jetzt) -> None:
        """§ 5 Abs 3 lit d: Abgestimmt wird über den zustande gekommenen
        Vorschlag — er wird die neue, letzte Antragsfassung."""
        fassung = self.aktuelle_fassung()
        letzte = antrag.aktueller_text()
        nummer = (letzte.nummer if letzte else 0) + 1
        AntragsFassung.objects.create(
            antrag=antrag,
            nummer=nummer,
            wortlaut=fassung.wortlaut,
            begruendung=f"Vorschlag des Expertenrats, Runde {self.runde} (§ 5 Abs 12). {fassung.begruendung}".strip(),
        )
        self.status = EntwurfsStatus.ANGENOMMEN
        self.save(update_fields=["status"])
        from plattform_core import Phase

        antrag.phase = Phase.ABSTIMMUNG.value
        antrag.phase_beginn = jetzt
        felder = ["phase", "phase_beginn"]
        if antrag.stimmberechtigte_anzahl is None:
            from django.conf import settings as dj_settings

            from mitglieder.models import stimmberechtigte_zaehlen
            from plattform_core import Gegenstand

            antrag.stimmberechtigte_anzahl = max(
                1,
                stimmberechtigte_zaehlen(
                    Gegenstand.SACHFRAGE,
                    jetzt.date(),
                    uebergang=getattr(dj_settings, "DDOE_UEBERGANGSREGEL", True),
                ),
            )
            felder.append("stimmberechtigte_anzahl")
        antrag.save(update_fields=felder)
        AuditEintrag.anhaengen(
            {
                "typ": "phasenwechsel",
                "antrag": antrag.pk,
                "neue_phase": Phase.ABSTIMMUNG.value,
                "wirksam_ab": jetzt.isoformat(),
                "grund": grund,
            }
        )

    def fortschreiben(self, antrag: Antrag, jetzt=None) -> bool:
        """Fristen der Schleife auswerten (idempotent, ohne Blockademacht):

        - Liegt der Vorschlag den Unterstützern vor und ist die Frist um (oder
          haben alle Unterstützer gestimmt): Mehrheit für Rückgabe UND Runden
          übrig → zurück an Gruppe 1 mit den Wünschen; sonst → Endabstimmung
          über den Vorschlag (auch bei Stille — Untätigkeit hemmt nie).
        - Verstreicht eine Überarbeitungsfrist ohne neue Einreichung → die
          zuletzt vorgelegte Fassung geht zur Endabstimmung."""
        jetzt = jetzt or timezone.now()
        if self.status == EntwurfsStatus.UNTERSTUETZER:
            stand = self.votum_stand()
            alle_da = stand["unterstuetzer"] > 0 and (
                stand["annahmen"] + stand["rueckgaben"] >= stand["unterstuetzer"]
            )
            if not alle_da and (self.review_frist is None or jetzt < self.review_frist):
                return False
            if stand["rueckgaben"] > stand["annahmen"] and self.runde < HOECHSTRUNDEN:
                self.zurueck_an_gruppe_1(
                    f"Unterstützer-Mehrheit gibt zurück ({stand['rueckgaben']}:{stand['annahmen']}).",
                    jetzt,
                    neue_runde=True,
                )
                return True
            self._endabstimmung_oeffnen(
                antrag,
                "Vorschlag des Expertenrats angenommen "
                f"({stand['annahmen']}:{stand['rueckgaben']}, Runde {self.runde}, § 5 Abs 12).",
                jetzt,
            )
            return True
        if (
            self.status == EntwurfsStatus.IN_ARBEIT
            and self.runde > 1
            and self.ueberarbeitung_frist is not None
            and jetzt >= self.ueberarbeitung_frist
        ):
            self._endabstimmung_oeffnen(
                antrag,
                "Überarbeitungsfrist verstrichen — die zuletzt vorgelegte Fassung geht zur "
                "Endabstimmung (§ 5 Abs 12: Untätigkeit hemmt nie).",
                jetzt,
            )
            return True
        return False


class EntwurfsFassung(models.Model):
    """Append-only: Jede Arbeitsfassung des Vorschlags bleibt erhalten (F-66)."""

    entwurf = models.ForeignKey(Entwurf, on_delete=models.CASCADE, related_name="fassungen")
    nummer = models.PositiveIntegerField()
    wortlaut = models.TextField()
    begruendung = models.TextField(blank=True)
    verfasst_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("entwurf", "nummer")]
        ordering = ["nummer"]
        verbose_name = "Entwurfsfassung"
        verbose_name_plural = "Entwurfsfassungen"

    def __str__(self) -> str:
        return f"Fassung {self.nummer} zu Entwurf {self.entwurf_id}"


class EntwurfsBeitrag(models.Model):
    """Interne Beratung der Gruppe 1 — dokumentiert (§ 6 Abs 9)."""

    entwurf = models.ForeignKey(Entwurf, on_delete=models.CASCADE, related_name="beitraege")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField(max_length=4000)
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["erstellt_am"]

    def __str__(self) -> str:
        return f"Beitrag von Mitglied {self.mitglied_id} zu Entwurf {self.entwurf_id}"


class EinreichStimme(models.Model):
    """Die interne, dokumentierte Abstimmung der Gruppe 1: einreichen? (F-66)"""

    entwurf = models.ForeignKey(Entwurf, on_delete=models.CASCADE, related_name="einreich_stimmen")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    runde = models.PositiveIntegerField()
    einverstanden = models.BooleanField()
    abgegeben_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("entwurf", "mitglied", "runde")]

    def __str__(self) -> str:
        return f"Einreich-Stimme von Mitglied {self.mitglied_id} (Runde {self.runde})"


class Pruefung(models.Model):
    """Das Urteil der Gruppe 2 (§ 6 Abs 7) — mit veröffentlichter Begründung."""

    class Ergebnis(models.TextChoices):
        VALIDIERT = "validiert", "validiert"
        ZURUECK = "zurueck", "mit Begründung zurückgegeben"
        AUSTAUSCH = "austausch", "Austausch bei Gruppe 1 beantragt"

    entwurf = models.ForeignKey(Entwurf, on_delete=models.CASCADE, related_name="pruefungen")
    runde = models.PositiveIntegerField()
    ergebnis = models.CharField(max_length=12, choices=Ergebnis.choices)
    begruendung = models.TextField(max_length=4000)
    durch = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    erstellt_am = models.DateTimeField(default=timezone.now)
    korat_entscheid = models.CharField(
        max_length=12,
        blank=True,
        choices=[("stattgegeben", "stattgegeben"), ("abgelehnt", "abgelehnt")],
        help_text="Nur bei Austauschanträgen: die Entscheidung des Koordinationsrats.",
    )
    korat_begruendung = models.TextField(max_length=2000, blank=True)

    class Meta:
        ordering = ["-erstellt_am"]
        verbose_name = "Prüfung (Gruppe 2)"
        verbose_name_plural = "Prüfungen (Gruppe 2)"

    def __str__(self) -> str:
        return f"Prüfung zu Entwurf {self.entwurf_id}: {self.get_ergebnis_display()}"


class UnterstuetzerVotum(models.Model):
    """Die Entwurfsschleife (§ 5 Abs 12): Unterstützer nehmen den Vorschlag an
    oder geben ihn mit einem konkreten Wunsch zurück. Offen geführt — wer den
    Antrag öffentlich unterstützt, entscheidet hier sichtbar über seinen Weg."""

    entwurf = models.ForeignKey(Entwurf, on_delete=models.CASCADE, related_name="unterstuetzer_voten")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    runde = models.PositiveIntegerField()
    annehmen = models.BooleanField()
    wunsch = models.TextField(max_length=2000, blank=True)
    abgegeben_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("entwurf", "mitglied", "runde")]
        ordering = ["abgegeben_am"]

    def __str__(self) -> str:
        return f"Votum von Mitglied {self.mitglied_id} zu Entwurf {self.entwurf_id} (Runde {self.runde})"
