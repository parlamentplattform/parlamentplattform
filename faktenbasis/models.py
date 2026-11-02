"""Amtliche Metadaten als unveränderliche Schnappschüsse, getrennt von KI-Vorschlägen."""

from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _


class SchnappschussQuerySet(models.QuerySet):
    def update(self, **kwargs):
        raise ValidationError(_("Ein Fakten-Schnappschuss wird nicht überschrieben."))

    def delete(self):
        raise ValidationError(_("Ein Fakten-Schnappschuss bleibt erhalten."))


class Schnappschuss(models.Model):
    objects = SchnappschussQuerySet.as_manager()

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValidationError(_("Ein Fakten-Schnappschuss wird nicht überschrieben."))
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Ein Fakten-Schnappschuss bleibt erhalten."))


class RisImport(Schnappschuss):
    gesetzesnummer = models.CharField(max_length=8)
    stand = models.DateField()
    begonnen_am = models.DateTimeField(default=timezone.now)
    beendet_am = models.DateTimeField(default=timezone.now)
    erfolgreich = models.BooleanField()
    treffer = models.PositiveIntegerField(default=0)
    gelesen = models.PositiveSmallIntegerField(default=0)
    neu = models.PositiveSmallIntegerField(default=0)
    api_url = models.TextField(blank=True)
    antwort_hash = models.CharField(max_length=64, blank=True)
    antwort = models.JSONField(default=dict)
    fehlercode = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["-beendet_am", "-pk"]
        verbose_name = _("RIS-Import")
        verbose_name_plural = _("RIS-Importe")

    def __str__(self):
        return f"RIS-Import {self.pk}: {self.gesetzesnummer} ({self.stand})"


class Norm(Schnappschuss):
    ris_id = models.CharField(max_length=11, db_index=True)
    gesetzesnummer = models.CharField(max_length=8, db_index=True)
    kurztitel = models.TextField()
    titel = models.TextField(blank=True)
    typ = models.CharField(max_length=100, blank=True)
    abschnitt = models.CharField(max_length=100, blank=True)
    stand = models.DateField()
    quelle = models.TextField()
    rohdaten = models.JSONField()
    inhalt_hash = models.CharField(max_length=64)
    importlauf = models.ForeignKey(RisImport, on_delete=models.PROTECT, related_name="normen")

    class Meta:
        ordering = ["-stand", "ris_id", "-pk"]
        verbose_name = _("Norm-Schnappschuss")
        verbose_name_plural = _("Norm-Schnappschüsse")
        constraints = [
            models.UniqueConstraint(fields=["ris_id", "stand", "inhalt_hash"], name="norm_inhalt_je_stand"),
        ]

    def __str__(self):
        return f"{self.ris_id}: {self.kurztitel} ({self.stand})"
