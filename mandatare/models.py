"""Die Mandatar-Steuerung, Stufe M1 (§ 7 Abs 9 E-2.5, F-71).

Ein öffentlicher Bereich je Mandatsträger: Lichtbild, aktuelle Aufgaben und
laufende Entscheidungsprozesse samt Fristen — und die daraus entstehenden,
vom Mandatar betreuten Abstimmungen (verknüpfte Anträge, F-70). Die Pflicht,
diese Informationen einzustellen, kommt aus der Mandatsvereinbarung
(§ 7 Abs 3 lit b); die Plattform macht sie sichtbar. Gepflegt wird der
Bereich vorerst von der Verwaltung — die eigene Mandatar-Rolle mit
Instant-Reports folgt als Stufe M2 auf dem Rollen-Fundament aus Ring 0a.

Das Lichtbild liegt bewusst in der Datenbank (kleines Binärfeld, streng
begrenzt): Der Plattenspeicher des Dienstes ist flüchtig, die Datenbank
wird gesichert — so überlebt das Foto jeden Neustart ohne Zusatzdienst."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone

from verfahren.models import Antrag, Ebene

FOTO_HOECHSTGROESSE = 800_000  # Bytes — genug für ein Porträt, zu wenig für Missbrauch

_MAGISCHE_ANFAENGE = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]


def foto_typ_erkennen(daten: bytes) -> str | None:
    """Erlaubte Bildformate an den magischen Bytes erkennen (kein Pillow nötig).
    JPEG, PNG — und WebP (RIFF….WEBP). Alles andere wird abgelehnt."""
    for anfang, typ in _MAGISCHE_ANFAENGE:
        if daten.startswith(anfang):
            return typ
    if daten[:4] == b"RIFF" and daten[8:12] == b"WEBP":
        return "image/webp"
    return None


class Mandat(models.Model):
    """Ein öffentliches Mandat eines DDÖ-Mitglieds — Nationalrat, Land, Bezirk
    oder Gemeinde. Beendete Mandate bleiben dokumentiert (Rechenschaft)."""

    mitglied = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mandate"
    )
    bezeichnung = models.CharField(
        max_length=120, help_text='Z. B. „Gemeinderat“, „Abgeordnete zum Nationalrat“.'
    )
    ebene = models.CharField(max_length=12, choices=Ebene.choices, default=Ebene.GEMEINDE)
    gebiet = models.CharField(max_length=120, blank=True)
    angetreten = models.DateField(default=timezone.localdate)
    beendet = models.DateField(null=True, blank=True)
    kandidatur = models.ForeignKey(
        Antrag,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mandate",
        help_text="Der Kandidatur-Antrag, aus dem dieses Mandat hervorging.",
    )
    vorstellung = models.TextField(max_length=2000, blank=True)
    foto = models.BinaryField(null=True, blank=True, editable=False)
    foto_typ = models.CharField(max_length=30, blank=True)

    class Meta:
        ordering = ["ebene", "gebiet", "angetreten"]
        verbose_name = "Mandat"
        verbose_name_plural = "Mandate"

    def __str__(self) -> str:
        return f"{self.bezeichnung} ({self.gebiet or self.get_ebene_display()})"

    @property
    def aktiv(self) -> bool:
        return self.beendet is None

    @property
    def initialen(self) -> str:
        teile = (self.mitglied.get_full_name() or self.mitglied.anzeigename).split()
        return "".join(t[0].upper() for t in teile[:2]) or "?"


class Aufgabenstatus(models.TextChoices):
    OFFEN = "offen", "offen"
    LAUFEND = "laufend", "laufend"
    ERLEDIGT = "erledigt", "erledigt"


class Aufgabe(models.Model):
    """Eine aktuelle Aufgabe bzw. ein laufender Entscheidungsprozess des
    Mandatars — mit Frist und, wo vorhanden, der daraus entstandenen,
    von ihm betreuten Abstimmung (§ 7 Abs 9)."""

    mandat = models.ForeignKey(Mandat, on_delete=models.CASCADE, related_name="aufgaben")
    titel = models.CharField(max_length=200)
    beschreibung = models.TextField(max_length=4000, blank=True)
    frist = models.DateField(null=True, blank=True)
    status = models.CharField(
        max_length=12, choices=Aufgabenstatus.choices, default=Aufgabenstatus.OFFEN
    )
    antrag = models.ForeignKey(
        Antrag,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mandats_aufgaben",
        help_text="Die aus der Aufgabe entstandene, vom Mandatar betreute Abstimmung.",
    )
    erstellt_am = models.DateTimeField(default=timezone.now)
    aktualisiert_am = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-aktualisiert_am"]
        verbose_name = "Mandats-Aufgabe"
        verbose_name_plural = "Mandats-Aufgaben"

    def __str__(self) -> str:
        return f"{self.titel} [{self.get_status_display()}]"

    @property
    def ueberfaellig(self) -> bool:
        return (
            self.status != Aufgabenstatus.ERLEDIGT
            and self.frist is not None
            and self.frist < timezone.localdate()
        )
