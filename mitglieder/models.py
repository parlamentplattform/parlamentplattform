"""Mitglieder: eigenes User-Modell von Tag 1 (in Django später unumkehrbar schwer).

Authentifizierung wandert in Woche 2 zu Keycloak (Passkey, TOTP, später
ID Austria); dieses Modell bleibt dann die fachliche Mitgliederverwaltung,
Keycloak macht nur den Login.
"""

from __future__ import annotations

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

    class Meta:
        verbose_name = "Mitglied"
        verbose_name_plural = "Mitglieder"

    def ist_stimmberechtigt(self, gegenstand: Gegenstand | str, stichtag, uebergang: bool = False) -> bool:
        if self.beitritt is None:
            return False
        if self.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
            return False
        return stimmberechtigt(self.beitritt, gegenstand, stichtag, uebergang=uebergang)

    @property
    def anzeigename(self) -> str:
        return self.pseudonym_oeffentlich or self.get_full_name() or self.username


def stimmberechtigte_zaehlen(gegenstand, stichtag, uebergang: bool = False) -> int:
    """Zahl der am Stichtag stimmberechtigten Mitglieder (§ 4 Abs 4 lit a).
    Wird bei Abstimmungsbeginn festgestellt, am Antrag gespeichert und
    veröffentlicht — danach nie mehr verändert."""
    anzahl = 0
    for m in (
        Mitglied.objects.filter(is_active=True)
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
