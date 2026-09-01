"""Der Anstoß (F-69): das begleitende Feedback-Widget auf jeder Seite.

Mitglieder — und Gäste — können der Plattform jederzeit Anstöße geben:
Wünsche, Störendes, Fehlendes. Jede Nachricht wird in der eigenen Datenbank
der Plattform gespeichert (kein Drittserver, keine zusätzlichen Zugänge,
volle DSGVO-Hoheit) und in der Verwaltung gesichtet, ausgewertet und
exportiert. So wird die stetige Verbesserung schon in der Alpha-Phase
Teil des Projekts."""

from django.conf import settings
from django.db import models


class AnstossStatus(models.TextChoices):
    NEU = "neu", "neu"
    GESICHTET = "gesichtet", "gesichtet"
    ERLEDIGT = "erledigt", "erledigt"


class Anstoss(models.Model):
    text = models.TextField(max_length=4000)
    seite = models.CharField(
        max_length=300, blank=True, help_text="Pfad der Seite, von der aus der Anstoß gesendet wurde."
    )
    nutzer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="anstoesse",
        help_text="Nur gesetzt, wenn angemeldet gesendet — sonst anonym.",
    )
    erstellt = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=12, choices=AnstossStatus.choices, default=AnstossStatus.NEU)
    vermerk = models.CharField(max_length=300, blank=True, help_text="Interner Bearbeitungsvermerk.")

    class Meta:
        ordering = ["-erstellt"]
        verbose_name = "Anstoß"
        verbose_name_plural = "Anstöße"

    def __str__(self) -> str:  # pragma: no cover
        return f"Anstoß #{self.pk} ({self.get_status_display()})"
