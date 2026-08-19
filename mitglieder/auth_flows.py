"""Registrierung und passwortloser Login (F-37, F-02).

Grundsätze:
- Double-Opt-in: Ein Konto wird erst nutzbar, wenn die E-Mail-Adresse über
  einen zeitlich begrenzten, einmaligen Link bestätigt wurde.
- Passwortlos: Der Login verschickt einen Magic-Link. Kein Passwort heißt
  kein Passwort-Leak — und der spätere Umstieg auf ID Austria (F-39) ersetzt
  nur den Linkversand durch den Broker, nicht die Architektur.
- Tokens werden nur als SHA-256-Hash gespeichert; das Klartext-Token existiert
  ausschließlich in der versendeten E-Mail.
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone

BESTAETIGUNG_GUELTIG = timedelta(hours=48)
LOGIN_GUELTIG = timedelta(minutes=30)


def _neues_token() -> tuple[str, str]:
    klar = secrets.token_urlsafe(32)
    return klar, hashlib.sha256(klar.encode()).hexdigest()


class EinmalToken(models.Model):
    """Ein Einmal-Token für E-Mail-Bestätigung oder Login."""

    class Zweck(models.TextChoices):
        BESTAETIGUNG = "bestaetigung", "E-Mail-Bestätigung"
        LOGIN = "login", "Login"

    mitglied = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="tokens")
    zweck = models.CharField(max_length=16, choices=Zweck.choices)
    token_hash = models.CharField(max_length=64, unique=True)
    erstellt_am = models.DateTimeField(default=timezone.now)
    gueltig_bis = models.DateTimeField()
    verbraucht_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Einmal-Token"
        verbose_name_plural = "Einmal-Tokens"

    def __str__(self) -> str:
        return f"{self.zweck} für Mitglied {self.mitglied_id}"

    @classmethod
    def ausstellen(cls, mitglied, zweck: str) -> str:
        """Erzeugt ein Token, speichert nur den Hash, gibt den Klartext zurück."""
        klar, gehasht = _neues_token()
        dauer = BESTAETIGUNG_GUELTIG if zweck == cls.Zweck.BESTAETIGUNG else LOGIN_GUELTIG
        cls.objects.create(
            mitglied=mitglied,
            zweck=zweck,
            token_hash=gehasht,
            gueltig_bis=timezone.now() + dauer,
        )
        return klar

    @classmethod
    def einloesen(cls, klartext: str, zweck: str):
        """Gibt das Mitglied zurück, wenn das Token gültig ist, und entwertet es.
        Sonst None. Konstantzeitvergleich ist hier unnötig (Hash-Lookup)."""
        gehasht = hashlib.sha256(klartext.encode()).hexdigest()
        try:
            t = cls.objects.select_related("mitglied").get(token_hash=gehasht, zweck=zweck)
        except cls.DoesNotExist:
            return None
        if t.verbraucht_am is not None or timezone.now() > t.gueltig_bis:
            return None
        t.verbraucht_am = timezone.now()
        t.save(update_fields=["verbraucht_am"])
        return t.mitglied


def beitragsreferenz(mitglied) -> str:
    """Persönlicher Verwendungszweck für die Beitragsüberweisung (F-38) —
    ableitbar, aber nicht erratbar (kein reines Inkrement)."""
    stamm = hashlib.sha256(f"ddoe-beitrag-{mitglied.pk}-{mitglied.username}".encode()).hexdigest()[:6].upper()
    return f"DDOE-{mitglied.pk:04d}-{stamm}"
