"""Besuchszählung für die öffentliche Übersichtsseite (F-50/F-52).

Datensparsam by design: Es werden ausschließlich Tages-Summen gespeichert —
keine IP-Adressen, keine Cookies, keine Profile. Für die Zahl „Besucherinnen
und Besucher je Tag" wird aus IP + Browserkennung + Tagesdatum + SECRET_KEY
eine kurze Einwegkennung gebildet und nur diese gespeichert; sie ist nicht
zur Adresse zurückrechenbar und ab Mitternacht wertlos (der Tag wandert aus
der Formel). Dieselbe Idee nutzen datenschutzfreundliche Zähler wie Plausible.
"""

from __future__ import annotations

import hashlib

from django.conf import settings
from django.db import models
from django.db.models import F
from django.utils import timezone


class TagesZahl(models.Model):
    """Seitenaufrufe je Tag (gesamte Plattform)."""

    datum = models.DateField(unique=True)
    aufrufe = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["datum"]
        verbose_name = "Tageszahl"
        verbose_name_plural = "Tageszahlen"

    def __str__(self) -> str:
        return f"{self.datum}: {self.aufrufe} Aufrufe"


class TagesBesucher(models.Model):
    """Eine anonyme Tageskennung je Besucherin bzw. Besucher (F-52)."""

    datum = models.DateField(db_index=True)
    kennung = models.CharField(max_length=16)

    class Meta:
        unique_together = [("datum", "kennung")]
        verbose_name = "Tagesbesucher-Kennung"
        verbose_name_plural = "Tagesbesucher-Kennungen"

    def __str__(self) -> str:
        return f"Besucher-Kennung am {self.datum}"


class AntragAufruf(models.Model):
    """Aufrufe je Antrag und Tag — Grundlage für „meistgelesene Anträge" (F-50)."""

    antrag = models.ForeignKey("verfahren.Antrag", on_delete=models.CASCADE, related_name="aufrufe")
    datum = models.DateField()
    aufrufe = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("antrag", "datum")]
        verbose_name = "Antragsaufruf"
        verbose_name_plural = "Antragsaufrufe"

    def __str__(self) -> str:
        return f"Antrag {self.antrag_id} am {self.datum}: {self.aufrufe}"


def tageskennung(ip: str, browser: str, datum) -> str:
    """Anonyme Einwegkennung: nicht zurückrechenbar, nur am selben Tag stabil."""
    roh = f"{settings.SECRET_KEY}:{datum.isoformat()}:{ip}:{browser}"
    return hashlib.sha256(roh.encode()).hexdigest()[:16]


def aufruf_zaehlen(ip: str, browser: str, antrag_id: int | None = None) -> None:
    """Zählt einen Seitenaufruf (und optional den Antrag). Nur Summen, nie Personen."""
    heute = timezone.localdate()
    TagesZahl.objects.get_or_create(datum=heute)  # legt die Zeile bei 0 an …
    TagesZahl.objects.filter(datum=heute).update(aufrufe=F("aufrufe") + 1)  # … und zählt atomar hoch
    TagesBesucher.objects.get_or_create(datum=heute, kennung=tageskennung(ip, browser, heute))
    if antrag_id is not None:
        AntragAufruf.objects.get_or_create(antrag_id=antrag_id, datum=heute)
        AntragAufruf.objects.filter(antrag_id=antrag_id, datum=heute).update(aufrufe=F("aufrufe") + 1)
