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

from parameter.models import Aenderung, ParameterTest, Status, TestStatus
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
    BERICHTSWESENRAT = "berichtswesenrat", "Integrations- und Berichtswesenrat"
    ENTWICKLUNGSRAT = "entwicklungsrat", "Technischer Entwicklungsrat"


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
    antrag = models.ForeignKey(
        Antrag,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="gremienrollen",
        help_text="Gesetzt, wenn die Rolle für einen einzelnen Antrag gelost wurde (§ 6 Abs 7). "
        "Leer heißt parteiweit — so waren alle Rollen vor der Auslosung.",
    )
    auslosung = models.ForeignKey(
        "gremien.Auslosung",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="rollen",
    )

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
        """Ob jemand in einem dieser Gremien überhaupt eine aktive Rolle hat.

        Das öffnet den Bereich. Ob dort auch geschrieben werden darf, entscheidet `hat_fuer`:
        Wer für einen Antrag gelost wurde, sieht die Werkstatt — schreiben darf er nur an
        seinem eigenen."""
        if not getattr(mitglied, "is_authenticated", False):
            return False
        return cls.objects.filter(
            mitglied=mitglied,
            gremium__in=gremien,
            beendet_grund="",
            endet_am__gte=timezone.localdate(),
        ).exists()

    @classmethod
    def letzte(cls, mitglied, *gremien: str):
        """Die jüngste Rolle in einem dieser Gremien, ob aktiv oder nicht — oder None.

        Wer eine Rolle hatte, liest den Bereich weiter (mit Band); schreiben darf nur, wer
        eine aktive hat. Ohne diesen Lesezugang verschwände mit dem Ablaufdatum auch die
        Möglichkeit, das eigene Wirken nachzulesen."""
        if not getattr(mitglied, "is_authenticated", False):
            return None
        return cls.objects.filter(mitglied=mitglied, gremium__in=gremien).order_by("-endet_am").first()

    @classmethod
    def fuer_antrag(cls, gremium: str, antrag):
        """Die aktiven Rollen, die für DIESEN Antrag gelten (§ 6 Abs 7).

        Gibt es eine Auslosung, sind es genau die gelosten. Gibt es keine — alle Verfahren, die
        vor der Auslosung begonnen haben —, gelten die parteiweiten Rollen weiter: Ein laufendes
        Verfahren wird nicht mitten im Lauf umgestellt (§ 5 Abs 5)."""
        gelost = cls.aktive(gremium).filter(antrag=antrag)
        if gelost.exists():
            return gelost
        return cls.aktive(gremium).filter(antrag__isnull=True)

    @classmethod
    def hat_fuer(cls, mitglied, gremium: str, antrag) -> bool:
        """Ob jemand an DIESEM Antrag schreiben darf.

        Ohne diese Prüfung könnte eine für Antrag A geloste Fachkraft an Antrag B mitschreiben
        und mitstimmen — und die Auslosung wäre eine Anzeige statt einer Zuständigkeit."""
        if not getattr(mitglied, "is_authenticated", False):
            return False
        if antrag is None:
            return cls.hat(mitglied, gremium)
        return cls.fuer_antrag(gremium, antrag).filter(mitglied=mitglied).exists()


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

    def einreichungsbeschluss(self):
        """Der offene Beschluss der Gruppe 1 über die Einreichung — oder None."""
        return self.beschluesse.filter(anlass=Anlass.EINREICHUNG, status=BeschlussStatus.OFFEN).first()

    def einreichungsbeschluss_anlegen(self, von, jetzt=None):
        """Stellt der Gruppe 1 die Frage, ob die aktuelle Fassung eingereicht wird (FB-I4).

        Bis 0.44 war das eine eigene Abstimmung mit eigener Zählung (`EinreichStimme`). Jetzt
        ist es ein Beschluss wie jeder andere: Quorum nach § 6 Abs 2 lit e, Frist aus dem
        Register, jede Stimme öffentlich mit Namen (§ 6 Abs 9). Der Nenner sind die für
        DIESEN Antrag gelosten Rollen (§ 6 Abs 7). Solange der Beschluss läuft, ruht die
        Fassung — sonst stimmte man über einen Text ab, der sich unter der Hand ändert."""
        fassung = self.aktuelle_fassung()
        if fassung is None or self.status != EntwurfsStatus.IN_ARBEIT:
            return None
        if self.einreichungsbeschluss() is not None:
            return None
        beschluss = GremienBeschluss.objects.create(
            gremium=Gremium.EXPERTENRAT_1,
            anlass=Anlass.EINREICHUNG,
            gegenstand=f"Fassung {fassung.nummer} einreichen: {self.antrag.titel}"[:200],
            beschreibung=(fassung.begruendung or "")[:4000],
            optionen=JA_NEIN,
            frist=beschluss_frist(),
            antrag=self.antrag,
            entwurf=self,
            angelegt_von=von,
            angelegt_am=jetzt or timezone.now(),
        )
        AuditEintrag.anhaengen(
            {
                "typ": "gremienbeschluss_angelegt",
                "gremium": Gremium.EXPERTENRAT_1.value,
                "anlass": Anlass.EINREICHUNG.value,
                "antrag": self.antrag_id,
                "fassung": fassung.nummer,
                "beschluss": beschluss.pk,
                "nummer": beschluss.nummer,
            }
        )
        return beschluss

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
        angelegt_von = (
            Rolle.fuer_antrag(Gremium.EXPERTENRAT_2, self.antrag).select_related("mitglied").first()
        )
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
    absatz = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Gesetzt, wenn der Beitrag an einen Absatz der aktuellen Fassung gebunden ist (FB-I2).",
    )
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["erstellt_am"]

    def __str__(self) -> str:
        return f"Beitrag von Mitglied {self.mitglied_id} zu Entwurf {self.entwurf_id}"


class EinreichStimme(models.Model):
    """Die interne Einreich-Abstimmung der Gruppe 1 bis 0.44 (F-66) — **nur noch Archiv**.

    Seit 0.45 ist die Einreichung ein Beschluss (`Anlass.EINREICHUNG`); offene Abstimmungen
    wurden bei der Umstellung in einen solchen übertragen (Migration 0011). Die Tabelle
    bleibt, weil sie Verfahren betrifft (Grundregel 7) — geschrieben wird sie nicht mehr."""

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
    korat_beschluss = models.ForeignKey(
        "gremien.GremienBeschluss",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="pruefungen_austausch",
        help_text="Der Beschluss des Koordinationsrats über den Austauschantrag (§ 6 Abs 7).",
    )

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
    AUSSETZUNG = "aussetzung", "Abstimmung oder Vollzug aussetzen (§ 6 Abs 3 lit d)"
    AUSSETZUNG_AUFHEBEN = "aussetzung_aufheben", "Aussetzung aufheben (§ 6 Abs 3 lit d)"
    REGELPRUEFUNG = "regelpruefung", "Jährliche Prüfung der automatisierten Regeln (§ 2 Abs 6)"
    EINREICHUNG = "einreichung", "Einreichung eines Vorschlags (§ 5 Abs 12)"
    AUSTAUSCH = "austausch", "Austausch der Gruppe 1 (§ 6 Abs 7)"
    HERVORHEBUNG_ANREGEN = "hervorhebung_anregen", "Hervorhebung beim Integritätsrat beantragen (§ 5 Abs 10 lit b)"
    UEBERLASTUNG = "ueberlastung", "Vorschlag zu einer Überlastungsmeldung (§ 6 Abs 10)"
    PARAMETERTEST = "parametertest", "Test eines Registerwerts anordnen (§ 6 Abs 11 lit c)"
    PARAMETER_EINFUEHRUNG = "parameter_einfuehrung", "Einführung eines Registerwerts (§ 6 Abs 11 lit c)"


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
    "berichtswesenrat": "IB",
    "entwicklungsrat": "TE",
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
    umsetzung_durch = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="zugewiesene_umsetzungen",
        help_text="Wer die Umsetzung übernimmt — ein Mitglied des Rates.",
    )
    umsetzung_frist = models.DateField(null=True, blank=True, help_text="Bis wann.")
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
        """Der Nenner des Quorums — für einen Beschluss zu einem Antrag die gelosten Rollen.

        Ohne diese Bindung zählte ein Beschluss zu Antrag A alle Rollen der Partei, auch die,
        die für ganz andere Anträge gelost wurden — und wäre nie beschlussfähig."""
        if self.antrag_id:
            return Rolle.fuer_antrag(self.gremium, self.antrag).count()
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


class Aussetzung(models.Model):
    """Eine ausgesetzte Abstimmung oder ein ausgesetzter Vollzug (§ 6 Abs 3 lit d).

    Sie braucht ein eigenes Modell, weil sie einen laufenden Zustand hat: Sie beginnt mit dem
    Beschluss, muss binnen sieben Tagen durch Antrag an das Parteischiedsgericht bestätigt
    werden — und endet sonst **von selbst**. Ein Zustand, der nur durch Handeln endet, wäre eine
    Blockademacht auf Vorrat; die Satzung will das Gegenteil.

    Gelöscht wird nichts (Grundregel 7): Eine beendete Aussetzung bleibt stehen, denn sie hat
    die Fristen des Antrags verschoben, und wer das Verfahren nachrechnet, muss sie finden."""

    class Gegenstand(models.TextChoices):
        ABSTIMMUNG = "abstimmung", "laufende Abstimmung"
        VOLLZUG = "vollzug", "Vollzug eines Beschlusses"

    antrag = models.ForeignKey(Antrag, on_delete=models.PROTECT, related_name="aussetzungen")
    gegenstand = models.CharField(max_length=12, choices=Gegenstand.choices)
    beschluss = models.OneToOneField(
        "gremien.GremienBeschluss", on_delete=models.PROTECT, related_name="aussetzung"
    )
    begruendung = models.TextField(max_length=4000, help_text="Zu begründen und zu veröffentlichen.")
    beginn = models.DateTimeField(default=timezone.now)
    schiedsgericht_am = models.DateTimeField(
        null=True, blank=True, help_text="Wann der Antrag an das Parteischiedsgericht gestellt wurde."
    )
    schiedsgericht_kennung = models.CharField(max_length=60, blank=True)
    beendet_am = models.DateTimeField(null=True, blank=True)
    beendet_grund = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ["-beginn"]
        verbose_name = "Aussetzung"
        verbose_name_plural = "Aussetzungen"

    def __str__(self) -> str:
        return f"Aussetzung {self.beschluss.nummer}: {self.get_gegenstand_display()}"

    @property
    def frist(self):
        from plattform_core.aussetzung import frist_ende

        return frist_ende(self.beginn)

    def laeuft(self, jetzt=None) -> bool:
        from plattform_core.aussetzung import laeuft

        return laeuft(self.beginn, jetzt or timezone.now(), self.schiedsgericht_am, self.beendet_am)

    def stand(self, jetzt=None) -> str:
        from plattform_core.aussetzung import grund_des_endes

        jetzt = jetzt or timezone.now()
        return grund_des_endes(self.beginn, jetzt, self.schiedsgericht_am, self.beendet_am)

    def abschnitt(self):
        """Der Zeitraum, den diese Aussetzung hemmt — offenes Ende, solange sie läuft."""
        from plattform_core.aussetzung import ende_von

        return (self.beginn, ende_von(self.beginn, self.schiedsgericht_am, self.beendet_am))


class Regelpruefung(models.Model):
    """Die jährliche Prüfung der automatisierten Regeln (§ 2 Abs 6 letzter Halbsatz).

    Der Vermerk „geprüft am …" wäre ohne die Liste, auf die er sich bezieht, wertlos: Regeln
    ändern sich, und ein Jahr später wüsste niemand mehr, was geprüft worden ist. Deshalb friert
    die Prüfung das Verzeichnis ein, wie es zum Zeitpunkt des Beschlusses stand."""

    class Ergebnis(models.TextChoices):
        GEPRUEFT = "geprueft", "geprüft, keine Beanstandung"
        BEANSTANDET = "beanstandet", "beanstandet"

    jahr = models.PositiveIntegerField()
    beschluss = models.OneToOneField(
        "gremien.GremienBeschluss", on_delete=models.PROTECT, related_name="regelpruefung"
    )
    stand = models.JSONField(help_text="Das Regelverzeichnis, wie es bei der Prüfung stand.")
    verzeichnis_fassung = models.PositiveIntegerField(default=0)
    ergebnis = models.CharField(max_length=12, choices=Ergebnis.choices, blank=True)
    vermerk = models.TextField(max_length=4000, blank=True)
    geprueft_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-jahr", "-pk"]
        verbose_name = "Regelprüfung"
        verbose_name_plural = "Regelprüfungen"

    def __str__(self) -> str:
        return f"Regelprüfung {self.jahr} ({self.beschluss.nummer})"


def aussetzung_wirkung(beschluss, jetzt=None) -> None:
    """Setzt eine Abstimmung oder einen Vollzug aus (§ 6 Abs 3 lit d)."""
    antrag = beschluss.antrag
    if antrag is None or beschluss.ergebnis != "dafuer":
        return
    if not _integritaetsrat_beschlussfaehig(beschluss):
        _vermerken(beschluss, "Ohne Wirkung: Der Integritätsrat war nicht satzungsgemäß besetzt (§ 6 Abs 3 lit a).")
        return
    if Aussetzung.objects.filter(antrag=antrag, beendet_am__isnull=True).exists():
        _vermerken(beschluss, "Ohne Wirkung: Zu diesem Antrag läuft bereits eine Aussetzung.")
        return
    jetzt = jetzt or timezone.now()
    from plattform_core import Phase

    aussetzung = Aussetzung.objects.create(
        antrag=antrag,
        gegenstand=(
            Aussetzung.Gegenstand.ABSTIMMUNG
            if antrag.phase == Phase.ABSTIMMUNG.value
            else Aussetzung.Gegenstand.VOLLZUG
        ),
        beschluss=beschluss,
        begruendung=beschluss.beschreibung,
        beginn=jetzt,
    )
    AuditEintrag.anhaengen(
        {
            "typ": "aussetzung_beschlossen",
            "antrag": antrag.pk,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
            "gegenstand": aussetzung.gegenstand,
            "frist": aussetzung.frist.isoformat(),
        }
    )


def aussetzung_aufheben_wirkung(beschluss, jetzt=None) -> None:
    """Hebt eine laufende Aussetzung auf — der Antrag läuft mit seiner Restfrist weiter."""
    antrag = beschluss.antrag
    if antrag is None or beschluss.ergebnis != "dafuer":
        return
    jetzt = jetzt or timezone.now()
    laufende = [a for a in Aussetzung.objects.filter(antrag=antrag) if a.laeuft(jetzt)]
    if not laufende:
        _vermerken(beschluss, "Ohne Wirkung: Zu diesem Antrag läuft keine Aussetzung.")
        return
    for aussetzung in laufende:
        aussetzung.beendet_am = jetzt
        aussetzung.beendet_grund = f"Aufgehoben durch Beschluss {beschluss.nummer}."
        aussetzung.save(update_fields=["beendet_am", "beendet_grund"])
        AuditEintrag.anhaengen(
            {
                "typ": "aussetzung_aufgehoben",
                "antrag": antrag.pk,
                "aussetzung": aussetzung.pk,
                "beschluss": beschluss.pk,
                "nummer": beschluss.nummer,
            }
        )


def regelpruefung_wirkung(beschluss, jetzt=None) -> None:
    """Hält das Ergebnis der jährlichen Regelprüfung fest (§ 2 Abs 6)."""
    pruefung = getattr(beschluss, "regelpruefung", None)
    if pruefung is None or not beschluss.ergebnis:
        return
    jetzt = jetzt or timezone.now()
    pruefung.ergebnis = beschluss.ergebnis
    pruefung.vermerk = beschluss.beschreibung
    pruefung.geprueft_am = jetzt
    pruefung.save(update_fields=["ergebnis", "vermerk", "geprueft_am"])
    AuditEintrag.anhaengen(
        {
            "typ": "regelpruefung_abgeschlossen",
            "jahr": pruefung.jahr,
            "beschluss": beschluss.pk,
            "nummer": beschluss.nummer,
            "ergebnis": pruefung.ergebnis,
            "regeln": len(pruefung.stand),
        }
    )


def aussetzungen_fortschreiben(jetzt=None) -> int:
    """Schließt Aussetzungen, die von selbst geendet haben (§ 6 Abs 3 lit d).

    Ohne diesen Schritt bliebe eine abgelaufene Aussetzung als offener Zustand stehen und hemmte
    weiter — obwohl die Satzung sagt, sie ende von selbst."""
    jetzt = jetzt or timezone.now()
    geschlossen = 0
    for aussetzung in Aussetzung.objects.filter(beendet_am__isnull=True):
        if aussetzung.laeuft(jetzt):
            continue
        # Den Grund VOR dem Setzen von beendet_am holen: Danach meldete `stand` „durch
        # Beschluss aufgehoben" — und das wäre bei einer Aussetzung, die von selbst endete,
        # genau die falsche Auskunft.
        grund = aussetzung.stand(jetzt)
        aussetzung.beendet_am = min(aussetzung.frist, jetzt)
        aussetzung.beendet_grund = grund
        aussetzung.save(update_fields=["beendet_am", "beendet_grund"])
        AuditEintrag.anhaengen(
            {
                "typ": "aussetzung_beendet",
                "antrag": aussetzung.antrag_id,
                "aussetzung": aussetzung.pk,
                "grund": aussetzung.beendet_grund,
            }
        )
        geschlossen += 1
    return geschlossen


class Fachliste(models.Model):
    """Ein Eintrag in der öffentlich geführten Liste der Fachleute (§ 6 Abs 7).

    Aus dieser Liste wird der Expertenrat je Antrag ausgelost. Wer darauf steht, legt seine
    Interessenbindungen und Honorare offen — die Satzung nennt beides ausdrücklich, und ohne
    diese Angabe wäre die Auslosung eine Auswahl unter Unbekannten.

    Der `schluessel` ist die pseudonyme Kennung, mit der die Ziehung rechnet. Er steht neben dem
    Namen und nicht an seiner Stelle: So bleibt eine Ziehung auch dann nachrechenbar, wenn
    jemand seine Einwilligung zur Namensnennung widerruft (§ 8 Abs 4) — Loswert und Platz
    bleiben stehen, der Name weicht dem Schlüssel.

    Gestrichen wird nicht gelöscht (Grundregel 7): Ein Eintrag, aus dem einmal gelost wurde,
    bleibt lesbar, sonst ließe sich die Ziehung nicht mehr nachvollziehen."""

    mitglied = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="fachlisteneintrag"
    )
    schluessel = models.CharField(
        max_length=16,
        unique=True,
        help_text="Pseudonyme Kennung für die Auslosung — stabil, auch nach einem Widerruf.",
    )
    fachgebiete = models.ManyToManyField(
        "verfahren.Kategorie",
        related_name="fachleute",
        help_text="Lebensbereiche, für die diese Person zur Verfügung steht (§ 6 Abs 7).",
    )
    interessenbindungen = models.TextField(
        max_length=4000,
        blank=True,
        help_text="Offenzulegen (§ 6 Abs 7). Leer heißt „keine“ — und wird auch so angezeigt.",
    )
    honorare = models.TextField(
        max_length=4000,
        blank=True,
        help_text="Entgeltliche Nebentätigkeiten und Zuwendungen — die Satzung nennt sie neben "
        "den Interessenbindungen ausdrücklich (§ 6 Abs 7).",
    )
    seit = models.DateField(default=timezone.localdate)
    gestrichen_am = models.DateField(null=True, blank=True)
    gestrichen_grund = models.CharField(max_length=200, blank=True)
    einwilligung_widerrufen_am = models.DateField(
        null=True,
        blank=True,
        help_text="§ 8 Abs 4: Die Einwilligung ist jederzeit widerrufbar; danach steht hier der "
        "Schlüssel statt des Namens. Der sachliche Inhalt bleibt erhalten.",
    )

    class Meta:
        ordering = ["schluessel"]
        verbose_name = "Fachlisten-Eintrag"
        verbose_name_plural = "Fachliste"

    def __str__(self) -> str:
        return f"{self.schluessel}: {self.anzeigename}"

    def save(self, *args, **kwargs):
        if not self.schluessel:
            import secrets

            self.schluessel = "F-" + secrets.token_hex(4).upper()
        return super().save(*args, **kwargs)

    @property
    def anzeigename(self) -> str:
        """Der Name — oder der Schlüssel, wenn die Einwilligung widerrufen wurde (§ 8 Abs 4)."""
        if self.einwilligung_widerrufen_am is not None:
            return self.schluessel
        return self.mitglied.anzeigename

    @property
    def gefuehrt(self) -> bool:
        return self.gestrichen_am is None

    def als_kandidat(self, ausschlussgrund: str = ""):
        """Der Eintrag, wie ihn die Ziehung sieht (`plattform_core.losziehung.Kandidat`)."""
        from plattform_core.losziehung import Kandidat

        return Kandidat(
            schluessel=self.schluessel,
            fachgebiete=frozenset(self.fachgebiete.values_list("slug", flat=True)),
            ausgeschlossen=bool(ausschlussgrund) or not self.gefuehrt,
            ausschlussgrund=ausschlussgrund or ("gestrichen" if not self.gefuehrt else ""),
        )


def unvereinbar(mitglied) -> str:
    """Warum jemand nicht in den Expertenrat gelost werden darf — oder leer.

    § 6 Abs 3 lit a schließt Mitglieder des Integritätsrats von anderen Räten aus; § 7 trennt
    Mandat und Beratung. Diese Prüfung gehört an den Lostopf und nicht an die Ansicht: Wer sie
    dort vergisst, hat sie nie."""
    if Rolle.hat(mitglied, Gremium.INTEGRITAETSRAT):
        return "Mitglied des Integritätsrats (§ 6 Abs 3 lit a)"
    from django.apps import apps

    if apps.is_installed("mandatare"):
        mandat = apps.get_model("mandatare", "Mandat")
        if mandat.objects.filter(mitglied=mitglied, beendet__isnull=True).exists():
            return "übt ein Mandat für die DDÖ aus (§ 6 Abs 3 lit a)"
    return ""


def lostopf_der_fachliste(fachgebiete=()) -> list:
    """Alle geführten Einträge als Kandidaten — mit den Unvereinbarkeiten schon gesetzt."""
    eintraege = Fachliste.objects.select_related("mitglied").prefetch_related("fachgebiete")
    return [e.als_kandidat(unvereinbar(e.mitglied)) for e in eintraege]


class Auslosung(models.Model):
    """Eine vollzogene Auslosung des Expertenrats (§ 6 Abs 7) — vollständig nachrechenbar.

    Gespeichert wird alles, was zum Nachrechnen nötig ist: der Anker, der Lostopf in der Form,
    in der er gelost wurde, die Ausgeschlossenen mit Grund und die gezogenen Plätze. Wer will,
    rechnet die Ziehung mit einem Prüfsummenwerkzeug nach — genau das meint § 2 Abs 6 mit
    „nachrechenbar"."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="auslosungen")
    runde = models.PositiveIntegerField(default=1)
    anker_lfd = models.BigIntegerField(help_text="Laufende Nummer des Audit-Eintrags, der den Zufall gab.")
    anker = models.CharField(max_length=64, help_text="Sein Hash — der Anker der Ziehung.")
    regel_fassung = models.PositiveIntegerField()
    groessen = models.JSONField()
    lostopf = models.JSONField()
    ausgeschlossen = models.JSONField(default=list)
    plaetze = models.JSONField(default=list)
    gezogen_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("antrag", "runde")]
        ordering = ["antrag", "runde"]
        verbose_name = "Auslosung"
        verbose_name_plural = "Auslosungen"

    def __str__(self) -> str:
        return f"Auslosung zu Antrag {self.antrag_id}, Runde {self.runde}"


def auslosen(antrag, runde: int = 1, jetzt=None):
    """Lost den Expertenrat für einen Antrag und legt die Rollen an (§ 6 Abs 7).

    Der Anker ist der Kopf der Audit-Kette in diesem Augenblick: Er steht jetzt fest und war
    vorher von niemandem auszurechnen. Größen und Regelfassung kommen aus der **eingefrorenen**
    Verfahrensordnung des Antrags, nicht aus dem laufenden Register (§ 5 Abs 5).

    Reicht der Lostopf nicht, geschieht nichts — und der Aufrufer erfährt es am Rückgabewert
    `None`. Eine halb besetzte Gruppe wäre schlimmer als keine: Sie sähe nach Beratung aus."""
    from plattform_core.losziehung import LosFehler, ziehen

    jetzt = jetzt or timezone.now()
    if Auslosung.objects.filter(antrag=antrag, runde=runde).exists():
        return None
    kopf = AuditEintrag.objects.order_by("-lfd").first()
    if kopf is None:
        return None
    ordnung = antrag.policy()
    groessen = [ordnung.expertenrat_gruppe1]
    # Frische Abfrage statt des Related-Zugriffs: `antrag.entwurf` legt beim Fehlschlag einen
    # negativen Eintrag im Objekt-Cache an — der Aufrufer bekäme danach auch dann „kein
    # Entwurf", wenn längst einer angelegt wurde. Genau daran ist ein Test gestolpert.
    entwurf = Entwurf.objects.filter(antrag=antrag).first()
    if entwurf is not None and entwurf.vollzugsbezug:
        groessen.append(ordnung.expertenrat_gruppe2)
    fachgebiete = list(antrag.kategorien.values_list("slug", flat=True))
    # Wer für diesen Antrag in einer früheren Runde schon gelost wurde, lost nicht noch einmal
    # mit: Sonst könnte ein Ausgetauschter in derselben Sache wieder auftauchen.
    frueher = set(
        Rolle.objects.filter(antrag=antrag).values_list("mitglied__fachlisteneintrag__schluessel", flat=True)
    )
    kandidaten = [
        k if k.schluessel not in frueher else type(k)(k.schluessel, k.fachgebiete, True, "in einer früheren Runde gelost")
        for k in lostopf_der_fachliste()
    ]
    try:
        ziehung = ziehen(kopf.hash, kandidaten, groessen, fachgebiete)
    except LosFehler as fehler:
        AuditEintrag.anhaengen(
            {"typ": "auslosung_nicht_moeglich", "antrag": antrag.pk, "runde": runde, "grund": str(fehler)}
        )
        return None

    auslosung = Auslosung.objects.create(
        antrag=antrag,
        runde=runde,
        anker_lfd=kopf.lfd,
        anker=kopf.hash,
        regel_fassung=ziehung.version,
        groessen=groessen,
        lostopf=list(ziehung.lostopf),
        ausgeschlossen=[list(a) for a in ziehung.ausgeschlossen],
        plaetze=[
            {"schluessel": p.schluessel, "gruppe": p.gruppe, "rang": p.rang, "loswert": p.loswert}
            for p in ziehung.plaetze
        ],
        gezogen_am=jetzt,
    )
    gremien = {1: Gremium.EXPERTENRAT_1, 2: Gremium.EXPERTENRAT_2}
    for platz in ziehung.plaetze:
        eintrag = Fachliste.objects.filter(schluessel=platz.schluessel).first()
        if eintrag is None:
            continue
        Rolle.objects.create(
            mitglied=eintrag.mitglied,
            gremium=gremien[platz.gruppe],
            endet_am=standard_ende(),
            bestaetigt=True,  # die Bestätigung liegt in der Bestellung auf die Fachliste
            antrag=antrag,
            auslosung=auslosung,
        )
    AuditEintrag.anhaengen(
        {
            "typ": "expertenrat_ausgelost",
            "antrag": antrag.pk,
            "runde": runde,
            "anker_lfd": kopf.lfd,
            "anker": kopf.hash,
            "regel_fassung": ziehung.version,
            "groessen": groessen,
            "plaetze": [[p.gruppe, p.schluessel] for p in ziehung.plaetze],
        }
    )
    return auslosung


#: § 6 Abs 10: „der Koordinationsrat legt der Mitgliederversammlung binnen 30 Tagen einen
#: Vorschlag ... vor." Satzungsfest — deshalb im Code und nicht im Register.
SATZUNG_UEBERLASTUNG_TAGE = 30


class Ueberlastungsmeldung(models.Model):
    """Eine Überlastungsmeldung nach § 6 Abs 10 — sofort öffentlich, mit laufender Frist.

    „Meldet eine berichtspflichtige Stelle begründet, dass die Gesamtheit der ihr zugewiesenen
    Aufgaben ihre Kapazität übersteigt, so ist die Meldung unverzüglich zu veröffentlichen; der
    Koordinationsrat legt der Mitgliederversammlung binnen 30 Tagen einen Vorschlag zur
    Reihung, Streckung oder Rückstellung der Umsetzung zur Beschlussfassung vor."

    Der Vorschlag ist ein Beschluss des Koordinationsrats (`Anlass.UEBERLASTUNG`); seine
    Wirkung bringt ihn als Sachantrag in die Mitgliederversammlung ein — die Plattform **ist**
    die Mitgliederversammlung (§ 5)."""

    stelle = models.CharField(max_length=120, help_text="Wer meldet — Organ, Gliederung oder Mandat, nie eine Person.")
    begruendung = models.TextField(max_length=4000)
    gemeldet_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    gemeldet_am = models.DateTimeField(default=timezone.now)
    vorschlag = models.TextField(max_length=4000, blank=True)
    beschluss = models.ForeignKey(
        "gremien.GremienBeschluss", null=True, blank=True, on_delete=models.SET_NULL, related_name="ueberlastungen"
    )
    antrag_an_mv = models.ForeignKey(
        Antrag, null=True, blank=True, on_delete=models.SET_NULL, related_name="+",
        help_text="Der Vorschlag als Antrag an die Mitgliederversammlung.",
    )
    erledigt_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-gemeldet_am"]
        verbose_name = "Überlastungsmeldung"
        verbose_name_plural = "Überlastungsmeldungen"

    def __str__(self) -> str:
        return f"Überlastungsmeldung {self.stelle} ({self.gemeldet_am:%d.%m.%Y})"

    @property
    def frist(self):
        return self.gemeldet_am + timedelta(days=SATZUNG_UEBERLASTUNG_TAGE)


class Interessenbindung(models.Model):
    """Die Offenlegung eines Rolleninhabers **zu diesem Antrag** (§ 6 Abs 7, FB-I2).

    Die Fachliste nennt Bindungen und Honorare allgemein; ob es zu DIESER Sache eine gibt,
    fragt die Plattform beim Abstimmen über die Einreichung — Pflichtfeld, „keine" ist eine
    Antwort. Sie steht öffentlich beim Vorschlag: Wer den Text geschrieben hat, sagt, was ihn
    mit dem Gegenstand verbindet."""

    antrag = models.ForeignKey(Antrag, on_delete=models.CASCADE, related_name="interessenbindungen")
    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    runde = models.PositiveIntegerField(default=1)
    text = models.CharField(max_length=1000)
    erklaert_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("antrag", "mitglied", "runde")]
        ordering = ["erklaert_am"]
        verbose_name = "Interessenbindung"
        verbose_name_plural = "Interessenbindungen"

    def __str__(self) -> str:
        return f"Interessenbindung von Mitglied {self.mitglied_id} zu Antrag {self.antrag_id}"


class WunschVermerk(models.Model):
    """Ein Wunsch der Unterstützer aus der Vorrunde, den die Gruppe 1 als berücksichtigt abhakt (FB-I2).

    Der Haken ist eine Auskunft, kein Urteil: Er sagt „wir haben das gelesen und in Fassung n
    aufgenommen" — ob das stimmt, prüfen die Unterstützer in der nächsten Runde selbst."""

    entwurf = models.ForeignKey(Entwurf, on_delete=models.CASCADE, related_name="wunschvermerke")
    kommentar = models.ForeignKey("verfahren.Kommentar", on_delete=models.CASCADE, related_name="+")
    fassung = models.PositiveIntegerField(help_text="In welcher Fassung der Wunsch berücksichtigt wurde.")
    durch = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    vermerkt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        unique_together = [("entwurf", "kommentar")]

    def __str__(self) -> str:
        return f"Wunsch {self.kommentar_id} berücksichtigt in Fassung {self.fassung}"


class HinweisQuelle(models.TextChoices):
    PARAMETERTEST = "parametertest", "Auswertung eines Parametertests"
    HERVORHEBUNG = "hervorhebung", "Kandidat für Hervorhebung"
    MUSTER = "muster", "Muster-Bericht"
    LAST = "last", "Lastwarnung"


class HinweisStatus(models.TextChoices):
    OFFEN = "offen", "offen"
    BESCHLUSS = "beschluss", "Beschluss angelegt"
    VERWORFEN = "verworfen", "verworfen"
    KENNTNIS = "kenntnis", "zur Kenntnis genommen"


class Hinweis(models.Model):
    """Ein Eintrag im Posteingang des Koordinationsrats (FB-I5).

    Die Zukunftswerkstatt schlägt vor — hier landet der Vorschlag, und hier entscheidet ein
    Mensch mit Grund, was daraus wird: Beschluss, Kenntnisnahme oder Verwerfen. Nichts
    geschieht ohne diesen Schritt (Grundregel 5). Gelöscht wird nichts; auch ein verworfener
    Hinweis bleibt mit seinem Grund stehen."""

    quelle = models.CharField(max_length=20, choices=HinweisQuelle.choices)
    titel = models.CharField(max_length=200)
    text = models.TextField(max_length=4000)
    parametertest = models.ForeignKey(
        ParameterTest, null=True, blank=True, on_delete=models.SET_NULL, related_name="hinweise"
    )
    antrag = models.ForeignKey(Antrag, null=True, blank=True, on_delete=models.SET_NULL, related_name="+")
    status = models.CharField(max_length=12, choices=HinweisStatus.choices, default=HinweisStatus.OFFEN)
    grund = models.CharField(max_length=500, blank=True)
    erledigt_von = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.PROTECT, related_name="+"
    )
    erledigt_am = models.DateTimeField(null=True, blank=True)
    angelegt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-angelegt_am"]
        verbose_name = "Hinweis"
        verbose_name_plural = "Posteingang"

    def __str__(self) -> str:
        return f"{self.get_quelle_display()}: {self.titel}"


# ── Wirkungen der neuen Anlässe ────────────────────────────────────────────────────────


def einreichung_wirkung(beschluss, jetzt=None) -> None:
    """Beschließt die Gruppe 1 die Einreichung, wird eingereicht (§ 5 Abs 12).

    Nur wenn das Fenster noch offen und der Antrag noch in der Beratung ist — sonst ist die
    Frist inzwischen ausgewertet, und ein nachträgliches Einreichen träfe ein Verfahren, das
    schon weiter ist."""
    entwurf = beschluss.entwurf
    if entwurf is None or beschluss.ergebnis != "dafuer":
        return
    if entwurf.status != EntwurfsStatus.IN_ARBEIT:
        _vermerken(beschluss, "Nicht eingereicht: Das Entwurfsfenster war nicht mehr in Arbeit.")
        return
    from plattform_core import Phase

    if entwurf.antrag.phase != Phase.BERATUNG.value:
        _vermerken(beschluss, "Nicht eingereicht: Der Antrag war nicht mehr in der Beratung.")
        return
    entwurf.einreichen(jetzt)
    _vermerken(beschluss, f"Eingereicht (Runde {entwurf.runde}).")


def austausch_wirkung(beschluss, jetzt=None) -> None:
    """Der Koordinationsrat entscheidet über den Austauschantrag der Gruppe 2 (§ 6 Abs 7).

    Stattgeben beendet die **für diesen Antrag** gelosten oder berufenen Rollen der Gruppe 1
    — nicht alle Rollen der Partei, das wäre seit der Auslosung ein Eingriff in fremde
    Verfahren — und lost eine neue Runde. Der Entwurf geht an die neue Gruppe."""
    pruefung = beschluss.pruefungen_austausch.first()
    if pruefung is None or pruefung.korat_entscheid:
        return
    entwurf = pruefung.entwurf
    entscheid = "stattgegeben" if beschluss.ergebnis == "dafuer" else "abgelehnt"
    pruefung.korat_entscheid = entscheid
    pruefung.korat_begruendung = f"Beschluss {beschluss.nummer}: {beschluss.beschreibung}"[:2000]
    pruefung.save(update_fields=["korat_entscheid", "korat_begruendung"])
    if entscheid == "stattgegeben":
        betroffen = list(Rolle.fuer_antrag(Gremium.EXPERTENRAT_1, entwurf.antrag))
        for rolle in betroffen:
            rolle.beendet_grund = f"Austausch durch den Koordinationsrat, Beschluss {beschluss.nummer} (§ 6 Abs 7)"
            rolle.save(update_fields=["beendet_grund"])
        letzte = Auslosung.objects.filter(antrag=entwurf.antrag).order_by("-runde").first()
        neue = auslosen(entwurf.antrag, runde=(letzte.runde + 1) if letzte else 2, jetzt=jetzt)
        entwurf.zurueck_an_gruppe_1(
            f"Austausch der Gruppe 1 durch den Koordinationsrat, Beschluss {beschluss.nummer} (§ 6 Abs 7).",
            jetzt,
            frist_erneuern=True,
        )
        _vermerken(
            beschluss,
            f"Stattgegeben — {len(betroffen)} Rollen der Gruppe 1 für diesen Antrag beendet; "
            + ("neu gelost." if neue else "keine neue Ziehung möglich (Lostopf reicht nicht)."),
        )
    else:
        _vermerken(beschluss, "Abgelehnt — der Vorschlag bleibt bei Gruppe 2 zur Prüfung.")
    AuditEintrag.anhaengen(
        {
            "typ": "austausch_entschieden",
            "antrag": entwurf.antrag_id,
            "entscheid": entscheid,
            "pruefung": pruefung.pk,
            "beschluss": beschluss.pk,
        }
    )


def hervorhebung_anregen_wirkung(beschluss, jetzt=None) -> None:
    """Der Koordinationsrat beantragt die Hervorhebung beim Integritätsrat (FB-D4).

    Zwei Räte, vier Augen: Die Zukunftswerkstatt meldet, der Koordinationsrat beantragt, der
    Integritätsrat beschließt (§ 5 Abs 10 lit b). Die Wirkung hier ist genau ein neuer
    Beschluss beim Integritätsrat — nie die Hervorhebung selbst."""
    if beschluss.ergebnis != "dafuer" or beschluss.antrag_id is None:
        return
    if GremienBeschluss.objects.filter(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.HERVORHEBUNG,
        antrag=beschluss.antrag,
        status=BeschlussStatus.OFFEN,
    ).exists():
        _vermerken(beschluss, "Beim Integritätsrat läuft bereits ein Beschluss zur Hervorhebung.")
        return
    neu = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.HERVORHEBUNG,
        gegenstand=f"Antrag hervorheben: {beschluss.antrag.titel}"[:200],
        beschreibung=f"Auf Antrag des Koordinationsrats, Beschluss {beschluss.nummer}:\n{beschluss.beschreibung}"[:4000],
        optionen=JA_NEIN,
        frist=beschluss_frist(),
        antrag=beschluss.antrag,
        angelegt_von=beschluss.angelegt_von,
        angelegt_am=jetzt or timezone.now(),
    )
    _vermerken(beschluss, f"Beim Integritätsrat als {neu.nummer} eingebracht.")
    AuditEintrag.anhaengen(
        {
            "typ": "gremienbeschluss_angelegt",
            "gremium": Gremium.INTEGRITAETSRAT.value,
            "anlass": Anlass.HERVORHEBUNG.value,
            "antrag": beschluss.antrag_id,
            "beschluss": neu.pk,
            "nummer": neu.nummer,
            "auf_antrag": beschluss.nummer,
        }
    )


def ueberlastung_wirkung(beschluss, jetzt=None) -> None:
    """Der Vorschlag des Koordinationsrats geht als Antrag an die Mitgliederversammlung (§ 6 Abs 10)."""
    meldung = beschluss.ueberlastungen.first()
    if meldung is None or meldung.erledigt_am or beschluss.ergebnis != "dafuer":
        return
    from verfahren.models import Verfahrensordnung, antrag_einbringen

    ordnung = Verfahrensordnung.objects.filter(aktiv=True).first()
    if ordnung is None:
        _vermerken(beschluss, "Nicht eingebracht: Es gilt keine Verfahrensordnung.")
        return
    antrag = antrag_einbringen(
        beschluss.angelegt_von,
        titel=f"Vorschlag des Koordinationsrats zur Überlastungsmeldung „{meldung.stelle}“"[:200],
        wortlaut=beschluss.beschreibung,
        begruendung=(
            f"Überlastungsmeldung vom {timezone.localtime(meldung.gemeldet_am):%d.%m.%Y} (§ 6 Abs 10): "
            f"{meldung.begruendung}\n\nBeschluss {beschluss.nummer} des Koordinationsrats."
        ),
        ordnung=ordnung,
    )
    meldung.vorschlag = beschluss.beschreibung
    meldung.antrag_an_mv = antrag
    meldung.erledigt_am = jetzt or timezone.now()
    meldung.save(update_fields=["vorschlag", "antrag_an_mv", "erledigt_am"])
    _vermerken(beschluss, f"Als Antrag {antrag.pk} in die Mitgliederversammlung eingebracht.")
    AuditEintrag.anhaengen(
        {"typ": "ueberlastung_vorschlag", "meldung": meldung.pk, "beschluss": beschluss.pk, "antrag": antrag.pk}
    )


def _kennzahlen_schnappschuss() -> dict:
    from parameter.kennzahlen import werte

    return werte()


def parametertest_wirkung(beschluss, jetzt=None) -> None:
    """Der Test beginnt — der Wert steht im Register, das Band sagt es (§ 6 Abs 11 lit c).

    Ein Parameter trägt nur einen Test zugleich: Zwei Werte auf einer Stellgröße wären keine
    Messung. Ist der Rat dagegen oder kommt kein Ergebnis zustande, bleibt der Test als
    „verworfen" stehen — man soll sehen, was nicht angeordnet wurde."""
    test = beschluss.parametertests.first()
    if test is None or test.status != TestStatus.GEPLANT:
        return
    jetzt = jetzt or timezone.now()
    if beschluss.ergebnis != "dafuer":
        test.status = TestStatus.VERWORFEN
        test.auswertung = f"Nicht angeordnet — Beschluss {beschluss.nummer} ohne Zustimmung."
        test.ausgewertet_am = jetzt
        test.save(update_fields=["status", "auswertung", "ausgewertet_am"])
        return
    parameter = test.parameter
    if parameter.status == Status.IM_TEST:
        test.status = TestStatus.VERWORFEN
        test.auswertung = "Nicht angeordnet — auf diesem Parameter läuft schon ein Test."
        test.ausgewertet_am = jetzt
        test.save(update_fields=["status", "auswertung", "ausgewertet_am"])
        _vermerken(beschluss, test.auswertung)
        return
    test.alter_wert = parameter.wert
    test.beginn = timezone.localdate(jetzt)
    test.werte_vorher = _kennzahlen_schnappschuss()
    test.status = TestStatus.LAEUFT
    test.save(update_fields=["alter_wert", "beginn", "werte_vorher", "status"])
    parameter.wert = test.testwert
    parameter.status = Status.IM_TEST
    parameter.test_bis = test.ende
    parameter.test_hypothese = test.hypothese[:300]
    parameter.geaendert_am = jetzt
    parameter.save(update_fields=["wert", "status", "test_bis", "test_hypothese", "geaendert_am"])
    Aenderung.objects.create(
        parameter=parameter,
        alter_wert=test.alter_wert,
        neuer_wert=test.testwert,
        grund=f"Test bis {test.ende:%d.%m.%Y} — {test.hypothese} (Beschluss {beschluss.nummer}, § 6 Abs 11 lit c)"[:1000],
        geaendert_am=jetzt,
        durch=f"Koordinationsrat, Beschluss {beschluss.nummer}",
    )
    AuditEintrag.anhaengen(
        {
            "typ": "parametertest_begonnen",
            "schluessel": parameter.schluessel,
            "alt": test.alter_wert,
            "neu": test.testwert,
            "bis": test.ende.isoformat(),
            "beschluss": beschluss.pk,
        }
    )
    _vermerken(beschluss, f"Test läuft bis {test.ende:%d.%m.%Y}; der Wert gilt für neu beginnende Verfahren.")


def parameter_einfuehrung_wirkung(beschluss, jetzt=None) -> None:
    """Die Einführung: der Testwert wird der geltende Wert — mit Begründung im Register."""
    test = beschluss.einfuehrungen.first()
    if test is None or test.status != TestStatus.AUSGEWERTET:
        return
    jetzt = jetzt or timezone.now()
    if beschluss.ergebnis != "dafuer":
        test.status = TestStatus.VERWORFEN
        test.auswertung = (test.auswertung + f"\n\nNicht eingeführt — Beschluss {beschluss.nummer} ohne Zustimmung.")[:4000]
        test.save(update_fields=["status", "auswertung"])
        return
    parameter = test.parameter
    alt = parameter.wert
    parameter.wert = test.testwert
    parameter.status = Status.GUELTIG
    parameter.test_bis = None
    parameter.test_hypothese = ""
    parameter.geaendert_am = jetzt
    parameter.save(update_fields=["wert", "status", "test_bis", "test_hypothese", "geaendert_am"])
    Aenderung.objects.create(
        parameter=parameter,
        alter_wert=alt,
        neuer_wert=test.testwert,
        grund=f"Einführung nach Test — {beschluss.beschreibung or test.hypothese} (Beschluss {beschluss.nummer}, § 6 Abs 11 lit c)"[:1000],
        geaendert_am=jetzt,
        durch=f"Koordinationsrat, Beschluss {beschluss.nummer}",
    )
    test.status = TestStatus.EINGEFUEHRT
    test.save(update_fields=["status"])
    AuditEintrag.anhaengen(
        {
            "typ": "parameter_eingefuehrt",
            "schluessel": parameter.schluessel,
            "alt": alt,
            "neu": test.testwert,
            "beschluss": beschluss.pk,
        }
    )
    _vermerken(beschluss, f"Eingeführt: {parameter.schluessel} = {test.testwert}.")


def parametertests_fortschreiben(jetzt=None) -> int:
    """Beendet abgelaufene Tests: Der Wert fällt zurück, die Auswertung landet im Posteingang.

    Lazy wie der Phasenautomat — wer den Bereich oder das Register öffnet, stößt es an. Der
    Rückfall ist der Rückweg, den die Satzung verlangt („jederzeit rückholbar"); ob der
    Testwert eingeführt wird, ist danach eine neue Frage an den Rat."""
    from plattform_core.parametertest import abgelaufen

    jetzt = jetzt or timezone.now()
    heute = timezone.localdate(jetzt)
    beendet = 0
    for test in ParameterTest.objects.filter(status=TestStatus.LAEUFT).select_related("parameter"):
        if not abgelaufen(test.ende, heute):
            continue
        parameter = test.parameter
        test.werte_nachher = _kennzahlen_schnappschuss()
        g = test.gegenueberstellung()
        if g.vollstaendig:
            anteil = f" ({g.anteil:+} %)" if g.anteil is not None else ""
            test.auswertung = (
                f"{test.messgroesse}: vorher {g.vorher}, während des Tests {g.nachher}, "
                f"Differenz {g.differenz}{anteil}. Hypothese: {test.hypothese}"
            )
        else:
            test.auswertung = f"{test.messgroesse}: kein vollständiger Vergleich möglich. Hypothese: {test.hypothese}"
        test.status = TestStatus.AUSGEWERTET
        test.ausgewertet_am = jetzt
        test.save(update_fields=["werte_nachher", "auswertung", "status", "ausgewertet_am"])
        if parameter.status == Status.IM_TEST and parameter.wert == test.testwert:
            parameter.wert = test.alter_wert
            parameter.status = Status.GUELTIG
            parameter.test_bis = None
            parameter.test_hypothese = ""
            parameter.geaendert_am = jetzt
            parameter.save(update_fields=["wert", "status", "test_bis", "test_hypothese", "geaendert_am"])
            Aenderung.objects.create(
                parameter=parameter,
                alter_wert=test.testwert,
                neuer_wert=test.alter_wert,
                grund=f"Testende {test.ende:%d.%m.%Y} — Rückweg: {test.rueckweg}"[:1000],
                geaendert_am=jetzt,
                durch="Testende (§ 6 Abs 11 lit c)",
            )
        Hinweis.objects.create(
            quelle=HinweisQuelle.PARAMETERTEST,
            titel=f"{parameter.schluessel}: Test {test.testwert} ausgewertet"[:200],
            text=test.auswertung,
            parametertest=test,
            angelegt_am=jetzt,
        )
        AuditEintrag.anhaengen(
            {"typ": "parametertest_ausgewertet", "schluessel": parameter.schluessel, "test": test.pk}
        )
        beendet += 1
    return beendet

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
    Anlass.AUSSETZUNG: lambda beschluss, jetzt: aussetzung_wirkung(beschluss, jetzt),
    Anlass.AUSSETZUNG_AUFHEBEN: lambda beschluss, jetzt: aussetzung_aufheben_wirkung(
        beschluss, jetzt
    ),
    Anlass.REGELPRUEFUNG: lambda beschluss, jetzt: regelpruefung_wirkung(beschluss, jetzt),
    Anlass.EINREICHUNG: lambda beschluss, jetzt: einreichung_wirkung(beschluss, jetzt),
    Anlass.AUSTAUSCH: lambda beschluss, jetzt: austausch_wirkung(beschluss, jetzt),
    Anlass.HERVORHEBUNG_ANREGEN: lambda beschluss, jetzt: hervorhebung_anregen_wirkung(beschluss, jetzt),
    Anlass.UEBERLASTUNG: lambda beschluss, jetzt: ueberlastung_wirkung(beschluss, jetzt),
    Anlass.PARAMETERTEST: lambda beschluss, jetzt: parametertest_wirkung(beschluss, jetzt),
    Anlass.PARAMETER_EINFUEHRUNG: lambda beschluss, jetzt: parameter_einfuehrung_wirkung(
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
