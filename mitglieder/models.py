"""Mitglieder: eigenes User-Modell von Tag 1 (in Django später unumkehrbar schwer).

Authentifizierung wandert in Woche 2 zu Keycloak (Passkey, TOTP, später
ID Austria); dieses Modell bleibt dann die fachliche Mitgliederverwaltung,
Keycloak macht nur den Login.
"""

from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models

from plattform_core import Gegenstand, stimmberechtigt


class Identitaetsstufe(models.TextChoices):
    UNGEPRUEFT = "ungeprueft", "ungeprüft"
    GEPRUEFT = "geprueft", "geprüft (Einladungscode nach Identitätsfeststellung)"
    PRAESENZ = "praesenz", "Präsenz-Identitätsfeststellung (§ 13 Abs 2)"
    EID = "eid", "elektronischer Identitätsnachweis (§ 2 Abs 4)"


class Mitglied(AbstractUser):
    """Ein Mensch, ein Konto (§ 4 Abs 4 lit e)."""

    beitritt = models.DateField(
        null=True, blank=True,
        help_text="Beginn der aktuellen, ununterbrochenen Mitgliedschaft — Basis der Anwartschaft (§ 4 Abs 4).",
    )
    identitaetsstufe = models.CharField(
        max_length=20, choices=Identitaetsstufe.choices, default=Identitaetsstufe.UNGEPRUEFT
    )
    pseudonym_oeffentlich = models.CharField(
        max_length=50, blank=True,
        help_text="Beständiges öffentliches Pseudonym für Anträge (§ 5 Abs 3 lit a). Leer = Klarname.",
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
