"""Mitglieder: eigenes User-Modell von Tag 1 (in Django später unumkehrbar schwer).

Authentifizierung wandert in Woche 2 zu Keycloak (Passkey, TOTP, später
ID Austria); dieses Modell bleibt dann die fachliche Mitgliederverwaltung,
Keycloak macht nur den Login.
"""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models

from plattform_core import Gegenstand, stimmberechtigt


class Bundesland(models.TextChoices):
    BURGENLAND = "burgenland", "Burgenland"
    KAERNTEN = "kaernten", "Kärnten"
    NIEDEROESTERREICH = "niederoesterreich", "Niederösterreich"
    OBEROESTERREICH = "oberoesterreich", "Oberösterreich"
    SALZBURG = "salzburg", "Salzburg"
    STEIERMARK = "steiermark", "Steiermark"
    TIROL = "tirol", "Tirol"
    VORARLBERG = "vorarlberg", "Vorarlberg"
    WIEN = "wien", "Wien"


class Identitaetsstufe(models.TextChoices):
    UNGEPRUEFT = "ungeprueft", "ungeprüft"
    GEPRUEFT = "geprueft", "geprüft (Einladungscode nach Identitätsfeststellung)"
    PRAESENZ = "praesenz", "Präsenz-Identitätsfeststellung (§ 13 Abs 2)"
    EID = "eid", "elektronischer Identitätsnachweis (§ 2 Abs 4)"


class Mitgliedsstatus(models.TextChoices):
    """Stand der Mitgliedschaft (F-51). „pausiert“ lässt Lesen und Anmelden zu,
    Mitwirkungsrechte (einbringen, unterstützen, beraten, abstimmen) ruhen,
    bis der Mitgliedsbeitrag wieder eingegangen ist (§ 4 Abs 3).
    „ausgeschlossen“ setzt zusätzlich das Konto inaktiv (§ 4 Abs 6)."""

    AKTIV = "aktiv", "aktiv"
    PAUSIERT = "pausiert", "pausiert (Beitrag ausständig)"
    AUSGESCHLOSSEN = "ausgeschlossen", "ausgeschlossen"


class Mitglied(AbstractUser):
    """Ein Mensch, ein Konto (§ 4 Abs 4 lit e)."""

    beitritt = models.DateField(
        null=True,
        blank=True,
        help_text="Beginn der aktuellen, ununterbrochenen Mitgliedschaft — Basis der Anwartschaft (§ 4 Abs 4).",
    )
    identitaetsstufe = models.CharField(
        max_length=20, choices=Identitaetsstufe.choices, default=Identitaetsstufe.UNGEPRUEFT
    )
    pseudonym_oeffentlich = models.CharField(
        max_length=50,
        blank=True,
        help_text="Beständiges öffentliches Pseudonym für Anträge (§ 5 Abs 3 lit a). Leer = Klarname.",
    )
    gemeinde = models.CharField(
        max_length=120,
        blank=True,
        help_text="Wohnsitz-Gemeinde — Grundlage der territorialen Zuordnung (§ 14 Abs 3).",
    )
    bundesland = models.CharField(
        max_length=20,
        choices=Bundesland.choices,
        blank=True,
        help_text="Wohnsitz-Bundesland — regionale Anträge sind nur in der eigenen Region möglich (F-43).",
    )
    wohnsitz = models.ForeignKey(
        "Gemeinde",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mitglieder",
        help_text="Eindeutiger Verweis ins amtliche Gemeindeverzeichnis — Quelle für gemeinde und bundesland.",
    )
    status = models.CharField(
        max_length=16,
        choices=Mitgliedsstatus.choices,
        default=Mitgliedsstatus.AKTIV,
        help_text="Stand der Mitgliedschaft (F-51) — jede Änderung läuft über die Verwaltung und wird auditiert.",
    )
    status_grund = models.TextField(
        blank=True,
        help_text="Begründung des aktuellen Status (z. B. Beschlussreferenz bei Ausschluss, § 4 Abs 6).",
    )
    beitrag_zuletzt_am = models.DateField(
        null=True,
        blank=True,
        help_text="Letzter vermerkter Beitragseingang (§ 4 Abs 3) — bis zum Kontoauszug-Import händisch gepflegt.",
    )
    ist_admin = models.BooleanField(
        default=False,
        help_text="Zugang zur Mitgliederverwaltung (F-51). Ernennen und Entziehen können nur Admins; "
        "jeder Wechsel wird auditiert.",
    )

    class Meta:
        verbose_name = "Mitglied"
        verbose_name_plural = "Mitglieder"

    def ist_stimmberechtigt(self, gegenstand: Gegenstand | str, stichtag, uebergang: bool = False) -> bool:
        if self.beitritt is None:
            return False
        if self.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
            return False
        if self.status != Mitgliedsstatus.AKTIV:
            return False  # pausiert oder ausgeschlossen: Mitwirkungsrechte ruhen (F-51)
        return stimmberechtigt(self.beitritt, gegenstand, stichtag, uebergang=uebergang)

    @property
    def anzeigename(self) -> str:
        return self.pseudonym_oeffentlich or self.get_full_name() or self.username

    @property
    def ist_fixer_admin(self) -> bool:
        """Der satzungsgebende Erstzugang (DDOE_FIX_ADMIN): immer Admin, kann weder
        pausiert noch ausgeschlossen werden, und niemand kann ihm die Rechte entziehen —
        damit die Verwaltung nie herrenlos wird."""
        return (self.email or "").lower() == getattr(settings, "DDOE_FIX_ADMIN", "").lower()

    @property
    def hat_adminrechte(self) -> bool:
        return self.is_active and (self.ist_admin or self.ist_fixer_admin)

    @property
    def darf_mitwirken(self) -> bool:
        """Einbringen, unterstützen, beraten — nur mit aktivem Status (F-51)."""
        return self.is_active and self.status == Mitgliedsstatus.AKTIV


def stimmberechtigte_zaehlen(gegenstand, stichtag, uebergang: bool = False) -> int:
    """Zahl der am Stichtag stimmberechtigten Mitglieder (§ 4 Abs 4 lit a).
    Wird bei Abstimmungsbeginn festgestellt, am Antrag gespeichert und
    veröffentlicht — danach nie mehr verändert."""
    anzahl = 0
    for m in (
        Mitglied.objects.filter(is_active=True, status=Mitgliedsstatus.AKTIV)
        .exclude(beitritt=None)
        .exclude(identitaetsstufe=Identitaetsstufe.UNGEPRUEFT)
    ):
        if m.ist_stimmberechtigt(gegenstand, stichtag, uebergang=uebergang):
            anzahl += 1
    return anzahl


class Gemeinde(models.Model):
    """Amtliches Gemeindeverzeichnis (Statistik Austria, Gebietsstand 2026).

    Grundlage der territorialen Zuordnung (§ 14, F-43): Die Wohnsitz-Gemeinde
    wird bei der Registrierung gegen diese Liste geprüft — keine Freitexte,
    keine Tippfehler, eindeutige Zuordnung zu Bezirk und Bundesland. Mit der
    ID Austria kommt die Zuordnung später amtlich; bis dahin gilt diese Liste.
    Aktualisierung per `manage.py gemeinden_laden` aus daten/gemeinden.csv."""

    kennziffer = models.CharField(max_length=5, unique=True)
    name = models.CharField(max_length=120, db_index=True)
    bezirk = models.CharField(max_length=120)
    bundesland = models.CharField(max_length=20, choices=Bundesland.choices)

    class Meta:
        ordering = ["name"]
        verbose_name = "Gemeinde"
        verbose_name_plural = "Gemeinden"

    def __str__(self) -> str:
        return f"{self.name} ({self.bezirk})"

    @property
    def anzeige(self) -> str:
        return f"{self.name} ({self.bezirk})"

    @staticmethod
    def name_normalisieren(text: str) -> str:
        """Tolerantes Matching: Groß/klein egal, „Sankt“ = „St.“."""
        t = " ".join(text.strip().casefold().split())
        return t.replace("sankt ", "st. ").replace("st ", "st. ")

    @classmethod
    def finden(cls, eingabe: str) -> tuple[Gemeinde | None, list[Gemeinde]]:
        """Findet die Gemeinde zur Eingabe (Name oder „Name (Bezirk)“).

        Rückgabe (treffer, kandidaten): genau einer -> (gemeinde, []);
        mehrdeutig -> (None, [kandidaten]); unbekannt -> (None, [])."""
        norm = cls.name_normalisieren(eingabe)
        alle = list(cls.objects.all())
        # 1) exakte Anzeige „Name (Bezirk)“
        volltreffer = [g for g in alle if cls.name_normalisieren(g.anzeige) == norm]
        if len(volltreffer) == 1:
            return volltreffer[0], []
        # 2) exakter Gemeindename
        treffer = [g for g in alle if cls.name_normalisieren(g.name) == norm]
        if len(treffer) == 1:
            return treffer[0], []
        return None, treffer
