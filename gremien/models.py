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

Offene Parameter: Seit F-68 liest die Schleife ihre Fristen und Runden aus
dem öffentlichen Parameterregister (/parameter/); die Konstanten unten sind
die eingebauten Zielwerte und bleiben der ehrliche Rückfall."""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone

from verfahren.models import Antrag, AntragsFassung, AuditEintrag

REVIEW_TAGE = 14
UEBERARBEITUNG_TAGE = 14
HOECHSTRUNDEN = 3
ROLLEN_DAUER_TAGE = 730  # zwei Jahre, § 6 Abs 8
BESCHLUSS_TAGE = 7  # Rückfall für die Frist eines internen Beschlusses (§ 6 Abs 2 lit e)
PRUEFUNG_TAGE = 7  # Rückfall für die Frist der Prüfung durch Gruppe 2 (§ 6 Abs 7)


def _registerzahl(schluessel: str, standard: int) -> int:
    """Seit F-68 liest die Schleife ihre Fristen aus dem offenen
    Parameterregister — die Konstanten oben bleiben die Zielwerte/Fallbacks."""
    from parameter.models import zahl

    return zahl(schluessel, standard)


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
    return timezone.localdate() + timedelta(days=_registerzahl("gremien-rollen-dauer-tage", ROLLEN_DAUER_TAGE))


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
            self.review_frist = jetzt + timedelta(days=_registerzahl("gremien-review-tage", REVIEW_TAGE))
        self.ueberarbeitung_frist = None
        self.save()
        if self.status == EntwurfsStatus.PRUEFUNG:
            self.pruefbeschluss_anlegen(jetzt)
        if self.status == EntwurfsStatus.UNTERSTUETZER:
            self.abstimmungschat_eroeffnen(jetzt)
        AuditEintrag.anhaengen(
            {
                "typ": "vorschlag_eingereicht",
                "antrag": self.antrag_id,
                "runde": self.runde,
                "weg": "pruefung" if self.vollzugsbezug else "unterstuetzer",
            }
        )

    def pruefbeschluss_anlegen(self, jetzt=None):
        """Legt die interne Abstimmung der Gruppe 2 zu diesem Vorschlag an (FB-I3).

        Ohne aktive Rolle in Gruppe 2 entsteht keine Abstimmung — dann bliebe der Vorschlag
        liegen, bis jemand berufen ist. Das ist der einzige Fall, in dem hier nichts geschieht;
        die Ansicht sagt es dann auch so, statt eine leere Abstimmung zu zeigen."""
        jetzt = jetzt or timezone.now()
        if self.beschluesse.filter(gremium=Gremium.EXPERTENRAT_2, status=BeschlussStatus.OFFEN).exists():
            return None
        angelegt_von = Rolle.aktive(Gremium.EXPERTENRAT_2).select_related("mitglied").first()
        if angelegt_von is None:
            return None
        return GremienBeschluss.objects.create(
            gremium=Gremium.EXPERTENRAT_2,
            anlass=Anlass.PRUEFUNG,
            gegenstand=f"Prüfung: {self.antrag.titel}"[:200],
            beschreibung=(
                "Vorschlag der Gruppe 1 mit Vollzugs- oder Beschaffungsbezug (§ 6 Abs 7). "
                "Zu prüfen sind Interessenbindungen, Bieterkreis, Schwellenwerte und "
                "Vergleichsangebote; jede Stimme wird mit Begründung veröffentlicht."
            ),
            optionen=PRUEFOPTIONEN,
            frist=jetzt + timedelta(days=_registerzahl("gremien-pruefung-tage", PRUEFUNG_TAGE)),
            antrag=self.antrag,
            entwurf=self,
            angelegt_von=angelegt_von.mitglied,
            angelegt_am=jetzt,
        )

    def zu_den_unterstuetzern(self, jetzt=None) -> None:
        jetzt = jetzt or timezone.now()
        self.status = EntwurfsStatus.UNTERSTUETZER
        self.review_frist = jetzt + timedelta(days=_registerzahl("gremien-review-tage", REVIEW_TAGE))
        self.save(update_fields=["status", "review_frist"])
        self.abstimmungschat_eroeffnen(jetzt)

    @transaction.atomic
    def abstimmungschat_eroeffnen(self, jetzt=None) -> None:
        """Der Vorschlag liegt vor — Zone 3 beginnt als Abstimmungs-Chat (FB-G6).

        Die Beiträge der Beratung wandern ins Archiv (FB-G5: Beginn der Vorschlagsberatung
        ist eine Hochstufung), und die Plattform legt den „Passt alles“-Beitrag an, auf den
        sich die Auswertung bezieht. Idempotent — ein zweiter Aufruf ändert nichts."""
        from verfahren.chat import passt_alles_anlegen

        jetzt = jetzt or timezone.now()
        archiviert = self.antrag.chat_archivieren(jetzt)
        passt_alles_anlegen(self.antrag, self, jetzt)
        AuditEintrag.anhaengen(
            {
                "typ": "abstimmungschat_eroeffnet",
                "antrag": self.antrag_id,
                "runde": self.runde,
                "wirksam_ab": jetzt.isoformat(),
                "chat_archiviert": archiviert,
            }
        )

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
            self.ueberarbeitung_frist = jetzt + timedelta(
                days=_registerzahl("gremien-ueberarbeitung-tage", UEBERARBEITUNG_TAGE)
            )
        elif frist_erneuern and self.runde > 1:
            self.ueberarbeitung_frist = jetzt + timedelta(
                days=_registerzahl("gremien-ueberarbeitung-tage", UEBERARBEITUNG_TAGE)
            )
        self.save()
        AuditEintrag.anhaengen(
            {"typ": "vorschlag_zurueckgegeben", "antrag": self.antrag_id, "runde": self.runde, "grund": grund}
        )

    @transaction.atomic
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
        from plattform_core import Phase

        if antrag.phase in (Phase.ZURUECKGEWIESEN.value, Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value):
            # Ein zurückgewiesener oder entschiedener Antrag bekommt keine Endabstimmung mehr.
            # Ohne dieses Tor öffnete die Schleife sie auch dann, wenn der Integritätsrat den
            # Antrag inzwischen zurückgewiesen hat (§ 5 Abs 2).
            return
        self.status = EntwurfsStatus.ANGENOMMEN
        self.save(update_fields=["status"])
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
        archiviert = antrag.chat_archivieren(jetzt)  # FB-G5: Hochstufung räumt den Chat
        AuditEintrag.anhaengen(
            {
                "typ": "phasenwechsel",
                "antrag": antrag.pk,
                "neue_phase": Phase.ABSTIMMUNG.value,
                "wirksam_ab": jetzt.isoformat(),
                "grund": grund,
                "chat_archiviert": archiviert,
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
        if self.status == EntwurfsStatus.PRUEFUNG:
            if self.pruefungen.filter(
                ergebnis=Pruefung.Ergebnis.AUSTAUSCH, korat_entscheid=""
            ).exists():
                return False  # der Koordinationsrat ist am Zug, nicht Gruppe 2
            offene = list(
                self.beschluesse.filter(
                    gremium=Gremium.EXPERTENRAT_2, status=BeschlussStatus.OFFEN
                )
            )
            if not offene:
                # Erst hier, nicht schon beim Einreichen: Beim Einreichen ist manchmal noch
                # niemand in Gruppe 2 berufen, und die Frist einer Gruppe kann nicht laufen,
                # bevor es die Gruppe gibt.
                self.pruefbeschluss_anlegen(jetzt)
                return False
            # Die Prüfung der Gruppe 2 hat ihre eigene Frist (FB-I3). Läuft sie ab, wertet der
            # Beschluss aus — sonst hinge ein Beschaffungsantrag an der Aufmerksamkeit eines
            # einzelnen Rates, und genau das soll die Frist verhindern (§ 5 Abs 12).
            for beschluss in offene:
                if beschluss.abschliessen(jetzt):
                    self.refresh_from_db()
                    return True
            return False
        if self.status == EntwurfsStatus.UNTERSTUETZER:
            # FB-G6: Ausgewertet wird nach Fristablauf — bis dahin sind Reaktionen umschaltbar
            if self.review_frist is None or jetzt < self.review_frist:
                return False
            from verfahren.chat import abstimmung_stand

            stand = abstimmung_stand(antrag, self)
            rechnung = (
                f"„Passt alles“ {stand['ja']}:{stand['nein']} = {stand['prozent']} % "
                f"(Schwelle {round(stand['schwelle'] * 100)} %), "
                f"{'an erster Stelle' if stand['oben'] else 'nicht an erster Stelle'}, "
                f"Regel {stand['reihung']}"
            )
            if not stand["angenommen"] and self.runde < _registerzahl(
                "gremien-hoechstrunden", HOECHSTRUNDEN
            ):
                self.zurueck_an_gruppe_1(
                    f"Der Abstimmungs-Chat gibt zurück: {rechnung}. "
                    f"{len(stand['kritik'])} Kritik-Beiträge gehen als Wünsche an den Expertenrat.",
                    jetzt,
                    neue_runde=True,
                )
                antrag.chat_archivieren(jetzt)  # die Runde ist vorbei — ihre Beiträge ins Archiv (FB-G5)
                return True
            self._endabstimmung_oeffnen(
                antrag,
                f"Vorschlag des Expertenrats angenommen ({rechnung}, Runde {self.runde}, § 5 Abs 12).",
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
    """Interne Beratung der Gruppe 1 — dokumentiert (§ 6 Abs 9). Ein Beitrag
    mit gesetztem ki_lauf ist eine KI-Einschätzung aus dem Modell-Steckplatz
    (F-60) — deutlich gekennzeichnet: Sie schlägt vor, sie entscheidet nie."""

    entwurf = models.ForeignKey(Entwurf, on_delete=models.CASCADE, related_name="beitraege")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    text = models.TextField(max_length=4000)
    ki_lauf = models.ForeignKey(
        "ki.KILauf", null=True, blank=True, on_delete=models.PROTECT, related_name="beitraege"
    )
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
    durch = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        help_text="Leer, wenn das Gremium gemeinsam entschieden hat — dann steht alles am Beschluss.",
    )
    beschluss = models.OneToOneField(
        "gremien.GremienBeschluss",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="pruefung",
        help_text="Die interne Abstimmung, aus der dieses Urteil hervorging (§ 6 Abs 2 lit e).",
    )
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


class Anlass(models.TextChoices):
    """Wozu ein Beschluss gefasst wird — und damit, was er auslöst (FB-I4).

    Ein Feld, nicht vier Sonderbedingungen: Die Wirkungstabelle am Ende des Moduls verzweigt
    ausschließlich hierüber. Neue Anlässe kommen erst, wenn ihre Wirkung gebaut ist — ein Anlass
    ohne Wirkung wäre ein Knopf, der schweigend nichts tut."""

    INTERN = "intern", "innere Angelegenheit des Rates"
    PRUEFUNG = "pruefung", "Prüfung eines Vorschlags (§ 6 Abs 7)"
    HERVORHEBUNG = "hervorhebung", "Hervorhebung eines Antrags (§ 5 Abs 10 lit b)"
    HERVORHEBUNG_AUFHEBEN = "hervorhebung_aufheben", "Hervorhebung aufheben (§ 5 Abs 10 lit b)"
    ZURUECKWEISUNG = "zurueckweisung", "Zurückweisung eines Antrags (§ 5 Abs 2)"
    ZURUECKWEISUNG_AUFHEBEN = "zurueckweisung_aufheben", "Zurückweisung aufheben (§ 5 Abs 2)"


#: Die Regelfrage eines Rates an sich selbst. Zwei Optionen, keine Enthaltung: Wer sich nicht
#: entscheiden will, stimmt nicht ab — dann fehlt er in der Beschlussfähigkeit, und genau das
#: soll er auch, statt eine dritte Farbe ins Ergebnis zu tragen.
JA_NEIN = [{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}]

#: § 6 Abs 3 lit a: „Er besteht aus drei bis sieben Mitgliedern." Ein Rat unter dieser Grenze
#: ist kein Integritätsrat, und ein Beschluss mit Außenwirkung — Hervorhebung, Zurückweisung —
#: darf ihm nicht gelingen. Satzungsfest, deshalb im Code und nicht im Register: Als Stellgröße
#: könnte die Verwaltung die Aufsicht über sich selbst kleinrechnen.
SATZUNG_MIN_INTEGRITAETSRAT = 3


#: Kürzel der Gremien in der Beschlussnummer. Kurz, weil die Nummer zitiert wird — in
#: Begründungen, in Anträgen, im Gespräch.
GREMIUMSKUERZEL = {
    "expertenrat1": "E1",
    "expertenrat2": "E2",
    "koordinationsrat": "KR",
    "integritaetsrat": "IR",
}


def beschlussnummer(gremium: str, jahr: int, laufend: int) -> str:
    """Die zitierfähige Kennung eines Beschlusses, z. B. „IR-2026-04“.

    Je Gremium und Jahr fortlaufend. Zwei Stellen sind kein Limit — die Nummer wächst mit,
    sie beginnt nur nicht bei „1“, damit „IR-2026-04“ und „IR-2026-12“ gleich lang aussehen."""
    return f"{GREMIUMSKUERZEL.get(gremium, 'GR')}-{jahr}-{laufend:02d}"


class BeschlussStatus(models.TextChoices):
    """Wo ein interner Beschluss steht (FB-I4)."""

    OFFEN = "offen", "offen"
    ENTSCHIEDEN = "entschieden", "entschieden"
    OHNE_ERGEBNIS = "ohne_ergebnis", "ohne Ergebnis (Frist abgelaufen)"


class GremienBeschluss(models.Model):
    """Eine interne Abstimmung eines Rates (§ 6 Abs 2 lit e, § 6 Abs 9).

    Generisch, weil jedes Gremium dieselbe Art zu entscheiden braucht: Gruppe 2 über eine
    Prüfung, der Koordinationsrat über einen Austauschantrag oder einen Parametertest, der
    Integritätsrat über eine Hervorhebung. Ein eigenes Modell je Anlass hätte vier Oberflächen
    und vier Auszählungen ergeben — und irgendwann vier verschiedene Mehrheitsregeln.

    Öffentlich mit Namen (§ 6 Abs 9): Wer in einem Rat sitzt, entscheidet über andere; das
    geschieht sichtbar. Gelöscht wird nichts (Grundregel 7) — auch ein Beschluss ohne Ergebnis
    bleibt stehen, denn dass ein Gremium nicht beschlussfähig war, ist selbst eine Auskunft."""

    gremium = models.CharField(max_length=20, choices=Gremium.choices)
    nummer = models.CharField(
        max_length=20, unique=True, blank=True,
        help_text="Zitierfähige Kennung, je Gremium und Jahr fortlaufend — z. B. „IR-2026-04“.",
    )
    anlass = models.CharField(
        max_length=30, choices=Anlass.choices, default=Anlass.INTERN,
        help_text="Wozu der Beschluss gefasst wird; die Wirkungstabelle verzweigt hierüber.",
    )
    gegenstand = models.CharField(max_length=200)
    beschreibung = models.TextField(max_length=4000, blank=True)
    optionen = models.JSONField(
        help_text="Liste aus {„wert“, „name“} — „wert“ zählt die Regel, „name“ liest der Mensch."
    )
    frist = models.DateTimeField(
        null=True, blank=True, help_text="Danach wird mit den vorliegenden Stimmen ausgewertet."
    )
    status = models.CharField(max_length=16, choices=BeschlussStatus.choices, default=BeschlussStatus.OFFEN)
    ergebnis = models.CharField(max_length=40, blank=True)
    regel_version = models.PositiveIntegerField(
        default=0, help_text="Fassung der Auszählregel, mit der entschieden wurde."
    )
    umsetzungsvermerk = models.TextField(
        max_length=2000, blank=True, help_text="Was wie umgesetzt wird — nach der Entscheidung."
    )
    zustand_vorher = models.JSONField(
        null=True,
        blank=True,
        help_text="Was der Beschluss überschrieben hat — damit eine Aufhebung den alten Stand "
        "wiederherstellen kann, statt ihn zu erraten (§ 5 Abs 2: die Zurückweisung ist beim "
        "Parteischiedsgericht bekämpfbar).",
    )

    antrag = models.ForeignKey(
        Antrag, on_delete=models.CASCADE, null=True, blank=True, related_name="gremienbeschluesse"
    )
    entwurf = models.ForeignKey(
        "gremien.Entwurf", on_delete=models.CASCADE, null=True, blank=True, related_name="beschluesse"
    )
    angelegt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="angelegte_beschluesse"
    )
    angelegt_am = models.DateTimeField(default=timezone.now)
    entschieden_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-angelegt_am"]
        verbose_name = "Gremienbeschluss"
        verbose_name_plural = "Gremienbeschlüsse"

    def __str__(self) -> str:
        return f"{self.nummer or self.get_gremium_display()}: {self.gegenstand}"

    def save(self, *args, **kwargs):
        """Vergibt beim ersten Speichern die Beschlussnummer.

        In einer Transaktion und mit `unique=True` abgesichert: Zwei gleichzeitig angelegte
        Beschlüsse desselben Rates bekämen sonst dieselbe Nummer, und eine Nummer, die zweimal
        vorkommt, ist keine."""
        if not self.nummer:
            with transaction.atomic():
                jahr = (self.angelegt_am or timezone.now()).year
                bisher = (
                    GremienBeschluss.objects.select_for_update()
                    .filter(gremium=self.gremium, nummer__startswith=f"{GREMIUMSKUERZEL.get(self.gremium, 'GR')}-{jahr}-")
                    .count()
                )
                self.nummer = beschlussnummer(self.gremium, jahr, bisher + 1)
                return super().save(*args, **kwargs)
        return super().save(*args, **kwargs)

    @property
    def offen(self) -> bool:
        return self.status == BeschlussStatus.OFFEN

    def optionswerte(self) -> list[str]:
        return [eintrag["wert"] for eintrag in self.optionen]

    def name_von(self, wert: str) -> str:
        for eintrag in self.optionen:
            if eintrag["wert"] == wert:
                return eintrag.get("name", wert)
        return wert

    def aktive_rollen(self) -> int:
        return Rolle.aktive(self.gremium).count()

    def auswertung(self):
        """Der Stand nach der offenen Regel — jederzeit abrufbar, auch während der Frist."""
        from plattform_core.gremienbeschluss import auswerten

        return auswerten(
            [stimme.option for stimme in self.stimmen.all()], self.optionswerte(), self.aktive_rollen()
        )

    def alle_haben_gestimmt(self) -> bool:
        aktive = self.aktive_rollen()
        return aktive > 0 and self.stimmen.count() >= aktive

    @transaction.atomic
    def abschliessen(self, jetzt=None) -> bool:
        """Wertet aus und schreibt das Ergebnis fest. Gibt zurück, ob sich etwas geändert hat.

        Ein Beschluss schließt aus zwei Gründen: Alle haben gestimmt, oder die Frist ist um.
        Der zweite Fall ist der wichtigere — sonst könnte ein einzelner Rat durch Schweigen
        alles aufhalten, und „Untätigkeit hemmt nie" gälte im Verfahren, aber nicht im Gremium."""
        if self.status != BeschlussStatus.OFFEN:
            return False
        jetzt = jetzt or timezone.now()
        frist_um = self.frist is not None and jetzt >= self.frist
        if not (frist_um or self.alle_haben_gestimmt()):
            return False
        ergebnis = self.auswertung()
        self.regel_version = ergebnis.version
        self.entschieden_am = jetzt
        if ergebnis.ergebnis is not None:
            self.status = BeschlussStatus.ENTSCHIEDEN
            self.ergebnis = ergebnis.ergebnis
        else:
            self.status = BeschlussStatus.OHNE_ERGEBNIS
            self.ergebnis = ""
        self.save(update_fields=["status", "ergebnis", "regel_version", "entschieden_am"])
        # Die Wirkungstabelle steht am Ende des Moduls. Sie hier auszulösen und nicht bei den
        # Aufrufern ist Absicht: Ein Aufrufer, der sie vergisst, hinterließe einen Beschluss,
        # der entschieden aussieht und nichts bewirkt hat.
        wirkung_anwenden(self, jetzt)
        AuditEintrag.anhaengen(
            {
                "typ": "gremienbeschluss_ausgewertet",
                "gremium": self.gremium,
                "beschluss": self.pk,
                "status": self.status,
                "ergebnis": self.ergebnis,
                "zaehlung": ergebnis.zaehlung,
                "abgegeben": ergebnis.abgegeben,
                "noetig": ergebnis.noetig,
                "regel_version": ergebnis.version,
            }
        )
        return True

    @classmethod
    def faellige_abschliessen(cls, jetzt=None) -> int:
        """Schließt alle Beschlüsse, deren Frist um ist (lazy, wie die Phasenautomatik)."""
        jetzt = jetzt or timezone.now()
        geschlossen = 0
        for beschluss in cls.objects.filter(status=BeschlussStatus.OFFEN, frist__lte=jetzt):
            geschlossen += int(beschluss.abschliessen(jetzt))
        return geschlossen


class GremienStimme(models.Model):
    """Eine Stimme in einer internen Abstimmung — mit Namen und Begründung (§ 6 Abs 9).

    Nur aktive Rollen dürfen stimmen; geprüft wird beim Abgeben, nicht erst beim Zählen, damit
    niemand eine Stimme abgibt, die später stillschweigend verfällt."""

    beschluss = models.ForeignKey(GremienBeschluss, on_delete=models.CASCADE, related_name="stimmen")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    option = models.CharField(max_length=40)
    begruendung = models.TextField(max_length=4000, blank=True)
    abgegeben_am = models.DateTimeField(default=timezone.now)
    geaendert_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [("beschluss", "mitglied")]
        ordering = ["abgegeben_am"]
        verbose_name = "Stimme im Gremium"
        verbose_name_plural = "Stimmen im Gremium"

    def __str__(self) -> str:
        return f"{self.mitglied_id} → {self.option}"


def beschluss_frist(tage_schluessel: str = "gremien-beschluss-tage", standard: int = BESCHLUSS_TAGE):
    """Wann ein neu angelegter Beschluss ausgewertet wird."""
    return timezone.now() + timedelta(days=_registerzahl(tage_schluessel, standard))


#: Die drei Wege der Gruppe 2 (§ 6 Abs 7). Der Wert steht im Code, der Name auf dem Knopf.
PRUEFOPTIONEN = [
    {"wert": "validiert", "name": "validieren"},
    {"wert": "zurueck", "name": "mit Begründung zurückgeben"},
    {"wert": "austausch", "name": "Austausch bei Gruppe 1 beantragen"},
]

#: Die Prüfpunkte der Gruppe 2 (§ 6 Abs 7). Abgehakte Punkte wandern in die Begründung —
#: eine Liste, die niemand sieht, prüft nichts.
PRUEFPUNKTE = [
    ("interessen", "Interessenbindungen der Gruppe 1 offengelegt und unauffällig"),
    ("bieter", "Bieterkreis nachvollziehbar, keine Häufung derselben Anbieter"),
    ("schwellen", "Schwellenwerte des Vergaberechts beachtet"),
    ("vergleich", "Vergleichsangebote oder eine Begründung, warum es keine gibt"),
]


def pruefbeschluss_wirkung(beschluss, jetzt=None) -> None:
    """Setzt das Ergebnis einer Gruppe-2-Abstimmung ins Verfahren um (FB-I3).

    Kein Ergebnis heißt hier **nicht** „validiert": Gruppe 2 ist eine Korruptionsprüfung, und
    Schweigen darf nicht als Unbedenklichkeitsbescheinigung gelten. Es heißt aber auch nicht
    „zurück" — sonst könnte ein Rat durch Nichtstun jeden Beschaffungsantrag aufhalten
    (§ 5 Abs 12: Untätigkeit hemmt nie). Der Vorschlag geht deshalb weiter an die Unterstützer,
    und der offengelegte Vermerk sagt, dass die Prüfung ohne Ergebnis blieb — die Unterstützer
    entscheiden dann in Kenntnis dieser Tatsache."""
    entwurf = beschluss.entwurf
    if entwurf is None or entwurf.status != EntwurfsStatus.PRUEFUNG:
        return
    jetzt = jetzt or timezone.now()
    auswertung = beschluss.auswertung()
    stimmen = list(beschluss.stimmen.select_related("mitglied"))
    if beschluss.ergebnis:
        ergebnis = beschluss.ergebnis
        begruendung = "\n\n".join(
            f"{stimme.mitglied.anzeigename}: {beschluss.name_von(stimme.option)} — {stimme.begruendung}"
            for stimme in stimmen
            if stimme.begruendung
        )
    else:
        ergebnis = Pruefung.Ergebnis.VALIDIERT
        begruendung = (
            "Die Prüfung der Gruppe 2 blieb ohne Ergebnis: "
            + (
                "Gleichstand der Stimmen."
                if auswertung.gleichstand
                else f"{auswertung.abgegeben} von {auswertung.noetig} nötigen Stimmen bis zum Fristende."
            )
            + " Der Vorschlag geht weiter an die Unterstützer, ohne dass Gruppe 2 ihn validiert hat "
            "(§ 5 Abs 12: Untätigkeit hemmt nie)."
        )
    Pruefung.objects.create(
        entwurf=entwurf,
        runde=entwurf.runde,
        ergebnis=ergebnis,
        begruendung=begruendung[:4000],
        durch=None,
        beschluss=beschluss,
        erstellt_am=jetzt,
    )
    AuditEintrag.anhaengen(
        {
            "typ": "vorschlag_geprueft",
            "antrag": entwurf.antrag_id,
            "runde": entwurf.runde,
            "ergebnis": ergebnis,
            "beschluss": beschluss.pk,
            "ohne_ergebnis": not beschluss.ergebnis,
        }
    )
    if ergebnis == Pruefung.Ergebnis.VALIDIERT:
        entwurf.zu_den_unterstuetzern(jetzt)
    elif ergebnis == Pruefung.Ergebnis.ZURUECK:
        entwurf.zurueck_an_gruppe_1(f"Gruppe 2: {begruendung[:160]}", frist_erneuern=True)



def _integritaetsrat_beschlussfaehig(beschluss) -> bool:
    """Ein Beschluss mit Außenwirkung gelingt nur einem satzungsgemäß besetzten Rat.

    § 6 Abs 3 lit a verlangt drei bis sieben Mitglieder. Sinkt die Besetzung darunter, ist das
    kein Grund, die laufende Abstimmung zu verwerfen — wohl aber einer, ihr die Wirkung zu
    versagen: Ein Rat aus zwei Menschen soll keinen Antrag zurückweisen können."""
    return Rolle.aktive(Gremium.INTEGRITAETSRAT).count() >= SATZUNG_MIN_INTEGRITAETSRAT


def _vermerken(beschluss, text: str) -> None:
    """Hält am Beschluss fest, warum eine Wirkung ausblieb — statt sie stumm zu unterlassen."""
    beschluss.umsetzungsvermerk = (beschluss.umsetzungsvermerk + " " + text).strip()[:2000]
    beschluss.save(update_fields=["umsetzungsvermerk"])


def hervorhebung_wirkung(beschluss, jetzt=None, aufheben: bool = False) -> None:
    """Setzt oder nimmt die Hervorhebung eines Antrags (§ 5 Abs 10 lit b).

    „Sie erfolgt niemals durch einen Algorithmus" — und ebenso wenig durch einen Haken in der
    Verwaltung. Die Begründung, die am Antrag erscheint, ist die des Beschlusses und trägt seine
    Nummer: Wer die goldene Zeile sieht, kann nachlesen, wer das wann und warum beschlossen hat."""
    antrag = beschluss.antrag
    if antrag is None or beschluss.ergebnis != "dafuer":
        return
    if not _integritaetsrat_beschlussfaehig(beschluss):
        _vermerken(beschluss, "Ohne Wirkung: Der Integritätsrat war nicht satzungsgemäß besetzt (§ 6 Abs 3 lit a).")
        return
    jetzt = jetzt or timezone.now()
    if aufheben:
        antrag.hervorgehoben = False
        antrag.hervorhebung_begruendung = ""
    else:
        antrag.hervorgehoben = True
        antrag.hervorhebung_begruendung = (
            f"Beschluss {beschluss.nummer} vom {timezone.localtime(jetzt).strftime('%d.%m.%Y')}: "
            f"{beschluss.beschreibung}".strip()
        )
    antrag.save(update_fields=["hervorgehoben", "hervorhebung_begruendung"])
    AuditEintrag.anhaengen(
        {
            "typ": "hervorhebung_aufgehoben" if aufheben else "hervorhebung_beschlossen",
            "antrag": antrag.pk,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
        }
    )


def zurueckweisung_wirkung(beschluss, jetzt=None) -> None:
    """Weist einen Antrag zurück (§ 5 Abs 2) — und hält fest, was dabei überschrieben wurde.

    Die Zurückweisung ist beim Parteischiedsgericht bekämpfbar. Ein Verfahren, das sie nicht
    zurücknehmen kann, macht dieses Recht wertlos; deshalb merkt sich der Beschluss Phase und
    Phasenbeginn. Laufende Entwurfsschleifen und offene Beschlüsse zu diesem Antrag werden
    geschlossen: Ein zurückgewiesener Antrag darf nicht weiter durch die Automatik wandern."""
    from plattform_core import Phase

    antrag = beschluss.antrag
    if antrag is None or beschluss.ergebnis != "dafuer":
        return
    if antrag.phase == Phase.ZURUECKGEWIESEN.value:
        return
    if not _integritaetsrat_beschlussfaehig(beschluss):
        _vermerken(beschluss, "Ohne Wirkung: Der Integritätsrat war nicht satzungsgemäß besetzt (§ 6 Abs 3 lit a).")
        return
    jetzt = jetzt or timezone.now()
    beschluss.zustand_vorher = {
        "phase": antrag.phase,
        "phase_beginn": antrag.phase_beginn.isoformat(),
        "zurueckgewiesen_am": jetzt.isoformat(),
    }
    beschluss.save(update_fields=["zustand_vorher"])
    antrag.phase = Phase.ZURUECKGEWIESEN.value
    antrag.phase_beginn = jetzt
    antrag.zurueckweisung_begruendung = (
        f"Beschluss {beschluss.nummer} vom {timezone.localtime(jetzt).strftime('%d.%m.%Y')}: "
        f"{beschluss.beschreibung}".strip()
    )
    antrag.save(update_fields=["phase", "phase_beginn", "zurueckweisung_begruendung"])
    entwurf = getattr(antrag, "entwurf", None)
    if entwurf is not None and entwurf.status != EntwurfsStatus.ANGENOMMEN:
        entwurf.status = EntwurfsStatus.ANGENOMMEN  # die Schleife ruht; nichts wird gelöscht
        entwurf.review_frist = None
        entwurf.ueberarbeitung_frist = None
        entwurf.save(update_fields=["status", "review_frist", "ueberarbeitung_frist"])
    GremienBeschluss.objects.filter(
        antrag=antrag, status=BeschlussStatus.OFFEN
    ).exclude(pk=beschluss.pk).update(
        status=BeschlussStatus.OHNE_ERGEBNIS, entschieden_am=jetzt
    )
    AuditEintrag.anhaengen(
        {
            "typ": "antrag_zurueckgewiesen",
            "antrag": antrag.pk,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
            "vorherige_phase": beschluss.zustand_vorher["phase"],
        }
    )


def zurueckweisung_aufheben_wirkung(beschluss, jetzt=None) -> None:
    """Nimmt eine Zurückweisung zurück und gibt dem Antrag seine Restfrist (§ 5 Abs 2).

    Der Antrag darf durch das Verfahren, das ihn zu Unrecht gestoppt hat, keine Zeit verlieren:
    Der Phasenbeginn rückt um die Dauer der Zurückweisung nach hinten, die Restfrist ist damit
    dieselbe wie vorher."""
    from datetime import datetime

    from plattform_core import Phase

    antrag = beschluss.antrag
    if antrag is None or beschluss.ergebnis != "dafuer":
        return
    if antrag.phase != Phase.ZURUECKGEWIESEN.value:
        return
    frueher = (
        GremienBeschluss.objects.filter(
            antrag=antrag, anlass=Anlass.ZURUECKWEISUNG, status=BeschlussStatus.ENTSCHIEDEN
        )
        .exclude(zustand_vorher=None)
        .order_by("-entschieden_am")
        .first()
    )
    if frueher is None:
        _vermerken(beschluss, "Ohne Wirkung: Zu diesem Antrag ist keine Zurückweisung verzeichnet.")
        return
    jetzt = jetzt or timezone.now()
    seit = datetime.fromisoformat(frueher.zustand_vorher["zurueckgewiesen_am"])
    antrag.phase = frueher.zustand_vorher["phase"]
    antrag.phase_beginn = datetime.fromisoformat(frueher.zustand_vorher["phase_beginn"]) + (jetzt - seit)
    antrag.zurueckweisung_begruendung = ""
    antrag.save(update_fields=["phase", "phase_beginn", "zurueckweisung_begruendung"])
    AuditEintrag.anhaengen(
        {
            "typ": "zurueckweisung_aufgehoben",
            "antrag": antrag.pk,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
            "wieder_in_phase": antrag.phase,
            "gehemmt_sekunden": int((jetzt - seit).total_seconds()),
        }
    )

#: Was ein ausgewerteter Beschluss im Verfahren auslöst — die ganze Tabelle auf einen Blick.
#: Sie wächst mit den Gremien: heute die Prüfung der Gruppe 2, später Hervorhebung und
#: Zurückweisung des Integritätsrats und die Parametertests des Koordinationsrats.
WIRKUNGEN = {
    Anlass.PRUEFUNG: lambda beschluss, jetzt: pruefbeschluss_wirkung(beschluss, jetzt),
    Anlass.HERVORHEBUNG: lambda beschluss, jetzt: hervorhebung_wirkung(beschluss, jetzt),
    Anlass.HERVORHEBUNG_AUFHEBEN: lambda beschluss, jetzt: hervorhebung_wirkung(
        beschluss, jetzt, aufheben=True
    ),
    Anlass.ZURUECKWEISUNG: lambda beschluss, jetzt: zurueckweisung_wirkung(beschluss, jetzt),
    Anlass.ZURUECKWEISUNG_AUFHEBEN: lambda beschluss, jetzt: zurueckweisung_aufheben_wirkung(
        beschluss, jetzt
    ),
}


def wirkung_anwenden(beschluss, jetzt=None) -> None:
    """Setzt die Wirkung eines ausgewerteten Beschlusses um.

    Verzweigt allein über den **Anlass**, nicht über Gremium und Fremdschlüssel: Die alte
    Bedingung (`gremium == EXPERTENRAT_2 and entwurf_id`) hätte beim zweiten Anlass desselben
    Rates schon nicht mehr getragen. Ein Anlass ohne Eintrag bewirkt nichts außer sich selbst —
    das ist der Normalfall für innere Angelegenheiten und keine Lücke."""
    wirkung = WIRKUNGEN.get(beschluss.anlass)
    if wirkung is not None:
        wirkung(beschluss, jetzt)
