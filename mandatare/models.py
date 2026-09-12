"""Die Mandatar-Steuerung, Stufe M1 (§ 7 Abs 9 E-2.5, F-71).

Ein öffentlicher Bereich je Mandatsträger: Lichtbild, aktuelle Aufgaben und
laufende Entscheidungsprozesse samt Fristen — und die daraus entstehenden,
vom Mandatar betreuten Abstimmungen (verknüpfte Anträge, F-70). Die Pflicht,
diese Informationen einzustellen, kommt aus der Mandatsvereinbarung
(§ 7 Abs 3 lit b); die Plattform macht sie sichtbar. Seit 0.46 pflegt der
Mandatar den Bereich selbst: Die Rolle „Mandatar“ ist abgeleitet (offenes
Mandat, `Mitglied.ist_mandatar`), der Instant-Report ist die `Aufgabe` mit
Zeitpunkt und Sitzungstag, aus ihm entsteht die Mandatsfrage
(`verfahren.models.mandatsfrage_eroeffnen`), und nach jedem Sitzungstag sind
Sammelbericht (`Bericht`) und Rechenschaft (`Rechenschaft`) fällig — die
Fristen rechnet `plattform_core.rechenschaft`.

Das Lichtbild liegt bewusst in der Datenbank (kleines Binärfeld, streng
begrenzt): Der Plattenspeicher des Dienstes ist flüchtig, die Datenbank
wird gesichert — so überlebt das Foto jeden Neustart ohne Zusatzdienst."""

from __future__ import annotations

from datetime import date

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from plattform_core import Phase
from plattform_core.rechenschaft import (
    RECHENSCHAFT_TAGE,
    SAMMELBERICHT_TAGE,
    Lage,
    berichtsmonate,
    faellig_am,
    lage,
    monatsbericht_faellig_am,
)
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

    @classmethod
    def aktive_von(cls, mitglied):
        """Die offenen Mandate eines Mitglieds — dieselbe Bedingung wie die Unvereinbarkeits-
        prüfung der Gremien (`beendet` leer). Reihenfolge: Ebene, Gebiet, Antritt (Meta)."""
        if mitglied is None or not getattr(mitglied, "pk", None):
            return cls.objects.none()
        return cls.objects.filter(mitglied=mitglied, beendet__isnull=True)

    @property
    def initialen(self) -> str:
        teile = (self.mitglied.get_full_name() or self.mitglied.anzeigename).split()
        return "".join(t[0].upper() for t in teile[:2]) or "?"

    def sitzungstage(self):
        """Aufgaben, die einen Sitzungstag des Vertretungskörpers ankündigen (mit Frist)."""
        return self.aufgaben.filter(sitzungstag=True, frist__isnull=False)

    def offene_pflichten(self, heute: date | None = None) -> dict:
        """Was nach § 7 Abs 3 lit b und Abs 5 gerade fällig oder ausständig ist — Zahlen, kein Urteil.

        Rückgabe: `{"sammelberichte": [...], "rechenschaften": [...], "monatsberichte": [...]}`.
        Sammelberichte und Rechenschaften: je vergangener Sitzungstag ohne Eintrag ein Dict
        `{"aufgabe", "sitzungstag", "faellig", "lage"}`; Monatsberichte: je geschuldetem Monat ohne
        Bericht ein Dict `{"monat", "faellig", "lage"}`. Erledigtes erscheint nicht. `lage` ist
        `plattform_core.rechenschaft.Lage` (offen mit Resttagen oder ausständig seit n Tagen).

        Ohne `heute` gilt der Sitzungstag als vorbei, sobald sein Zeitpunkt erreicht ist; mit
        übergebenem `heute` (Tests, Stichtagsrechnung) zählt der Kalendertag."""
        jetzt = timezone.now() if heute is None else None
        if heute is None:
            heute = timezone.localdate(jetzt)
        from parameter.models import zahl

        karenz = zahl("mandatar-monatsbericht-frist-tage", 7)

        mit_bericht = set(
            self.berichte.filter(art=Berichtsart.SAMMELBERICHT, aufgabe__isnull=False).values_list(
                "aufgabe_id", flat=True
            )
        )
        mit_rechenschaft = set(
            self.rechenschaft.filter(aufgabe__isnull=False).values_list("aufgabe_id", flat=True)
        )
        sammelberichte, rechenschaften = [], []
        for aufgabe in self.sitzungstage().order_by("frist"):
            tag = timezone.localdate(aufgabe.frist)
            vorbei = aufgabe.frist <= jetzt if jetzt is not None else tag <= heute
            if not vorbei:
                continue
            if aufgabe.pk not in mit_bericht:
                faellig = faellig_am(tag, SAMMELBERICHT_TAGE)
                sammelberichte.append(
                    {"aufgabe": aufgabe, "sitzungstag": tag, "faellig": faellig, "lage": lage(faellig, None, heute)}
                )
            if aufgabe.pk not in mit_rechenschaft:
                faellig = faellig_am(tag, RECHENSCHAFT_TAGE)
                rechenschaften.append(
                    {"aufgabe": aufgabe, "sitzungstag": tag, "faellig": faellig, "lage": lage(faellig, None, heute)}
                )

        berichtete_monate = set(
            self.berichte.filter(art=Berichtsart.MONATSBERICHT, monat__isnull=False).values_list(
                "monat", flat=True
            )
        )
        monatsberichte = []
        for monat in berichtsmonate(self.angetreten, self.beendet, heute):
            if monat in berichtete_monate:
                continue
            faellig = monatsbericht_faellig_am(monat, karenz)
            monatsberichte.append({"monat": monat, "faellig": faellig, "lage": lage(faellig, None, heute)})
        return {
            "sammelberichte": sammelberichte,
            "rechenschaften": rechenschaften,
            "monatsberichte": monatsberichte,
        }


class Aufgabenstatus(models.TextChoices):
    OFFEN = "offen", _("offen")
    LAUFEND = "laufend", _("laufend")
    ERLEDIGT = "erledigt", _("erledigt")


class Aufgabe(models.Model):
    """Eine aktuelle Aufgabe bzw. ein laufender Entscheidungsprozess des
    Mandatars — mit Frist und, wo vorhanden, der daraus entstandenen,
    von ihm betreuten Abstimmung (§ 7 Abs 9)."""

    mandat = models.ForeignKey(Mandat, on_delete=models.CASCADE, related_name="aufgaben")
    titel = models.CharField(max_length=200)
    beschreibung = models.TextField(max_length=4000, blank=True)
    frist = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Zeitpunkt der Frist (Datum und Uhrzeit, Wiener Zeit). Ein reines Datum gilt bis 23:59.",
    )
    sitzungstag = models.BooleanField(
        default=False,
        help_text="Die Frist ist ein Sitzungstag des Vertretungskörpers — danach sind Sammelbericht "
        "(§ 7 Abs 3 lit b) und Rechenschaft (§ 7 Abs 5) fällig.",
    )
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
            and self.frist < timezone.now()
        )

    @property
    def sitzungstag_datum(self) -> date | None:
        """Der Wiener Kalendertag des Sitzungstags — Basis der Sieben-Tage-Fristen."""
        if not self.sitzungstag or self.frist is None:
            return None
        return timezone.localdate(self.frist)


class Beschluss(models.TextChoices):
    """Was die Plattform zu dem Gegenstand beschlossen hatte — abgeleitet aus dem Antrag."""

    ANGENOMMEN = "angenommen", _("angenommen")
    ABGELEHNT = "abgelehnt", _("abgelehnt")
    KEINER = "keiner", _("kein Beschluss der Plattform")


class Stimmverhalten(models.TextChoices):
    DAFUER = "dafuer", _("dafür")
    DAGEGEN = "dagegen", _("dagegen")
    ENTHALTEN = "enthalten", _("enthalten")
    NICHT_TEILGENOMMEN = "nicht_teilgenommen", _("nicht teilgenommen")


class Rechenschaft(models.Model):
    """Das Rechenschaftsregister (§ 7 Abs 5): Wie der Vertretungskörper entschied, wie der
    Mandatar stimmte und warum — neben dem Beschluss der Plattform, falls es einen gab.

    Erwartet wird ein Eintrag je angekündigtem Sitzungstag binnen sieben Tagen
    (`plattform_core.rechenschaft.RECHENSCHAFT_TAGE`). Fehlt er, zeigt die Plattform den
    Ausstand — ohne Sanktion (§ 7 Abs 2 und 4). Eine Abweichung vom Plattformbeschluss wird
    nebeneinandergestellt, nicht bewertet. Einträge werden nicht gelöscht."""

    mandat = models.ForeignKey(Mandat, on_delete=models.CASCADE, related_name="rechenschaft")
    aufgabe = models.ForeignKey(
        Aufgabe,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rechenschaft",
        help_text="Der angekündigte Sitzungstag, zu dem dieser Eintrag gehört.",
    )
    antrag = models.ForeignKey(
        Antrag,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rechenschaft",
        help_text="Der Beschluss der Plattform zu diesem Gegenstand, falls es einen gab.",
    )
    gegenstand = models.CharField(max_length=200, help_text="Worüber der Vertretungskörper abstimmte.")
    sitzung_am = models.DateField()
    beschluss_plattform = models.CharField(
        max_length=16,
        choices=Beschluss.choices,
        default=Beschluss.KEINER,
        help_text="Bei gesetztem Antrag aus dessen Phase abgeleitet und beim Speichern gesetzt.",
    )
    stimme = models.CharField(max_length=20, choices=Stimmverhalten.choices)
    begruendung = models.TextField(max_length=4000)
    eingetragen_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-sitzung_am", "-eingetragen_am"]
        verbose_name = "Rechenschaft"
        verbose_name_plural = "Rechenschaftsregister"

    def __str__(self) -> str:
        return f"{self.gegenstand} ({self.sitzung_am:%d.%m.%Y}, {self.get_stimme_display()})"

    def save(self, *args, **kwargs):
        if self.antrag_id is not None:
            self.beschluss_plattform = self.beschluss_aus_antrag(self.antrag)
        super().save(*args, **kwargs)

    @staticmethod
    def beschluss_aus_antrag(antrag) -> str:
        """angenommen / abgelehnt / keiner — nur ein beendetes Verfahren ist ein Beschluss."""
        if antrag is None:
            return Beschluss.KEINER
        if antrag.phase == Phase.ANGENOMMEN.value:
            return Beschluss.ANGENOMMEN
        if antrag.phase == Phase.ABGELEHNT.value:
            return Beschluss.ABGELEHNT
        return Beschluss.KEINER

    @property
    def weicht_ab(self) -> bool:
        """Stimme des Mandatars und Beschluss der Plattform gehen auseinander — sichtbar, nicht bewertet."""
        return (
            self.beschluss_plattform == Beschluss.ANGENOMMEN and self.stimme != Stimmverhalten.DAFUER
        ) or (self.beschluss_plattform == Beschluss.ABGELEHNT and self.stimme != Stimmverhalten.DAGEGEN)

    @property
    def frist(self) -> date:
        """Bis wann der Eintrag nach § 7 Abs 5 zu erwarten war."""
        return faellig_am(self.sitzung_am, RECHENSCHAFT_TAGE)

    def lage(self, heute: date | None = None) -> Lage:
        heute = heute or timezone.localdate()
        return lage(self.frist, timezone.localdate(self.eingetragen_am), heute)


class Berichtsart(models.TextChoices):
    MONATSBERICHT = "monatsbericht", _("Monatsbericht")
    SAMMELBERICHT = "sammelbericht", _("Sammelbericht")


class Bericht(models.Model):
    """Berichte nach § 7 Abs 3 lit b: der Monatsbericht für jeden vollen Kalendermonat des
    Mandats und der Sammelbericht binnen sieben Tagen nach jedem Sitzungstag.

    Kein Löschen, kein Bearbeiten — wer nachträgt, schreibt einen neuen Bericht mit Vermerk."""

    mandat = models.ForeignKey(Mandat, on_delete=models.CASCADE, related_name="berichte")
    art = models.CharField(max_length=16, choices=Berichtsart.choices)
    monat = models.DateField(
        null=True,
        blank=True,
        help_text="Erster Tag des berichteten Monats — beim Monatsbericht Pflicht.",
    )
    aufgabe = models.ForeignKey(
        Aufgabe,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="berichte",
        help_text="Der Sitzungstag, den ein Sammelbericht abschließt — beim Sammelbericht Pflicht.",
    )
    text = models.TextField(max_length=8000)
    eingereicht_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-eingereicht_am"]
        verbose_name = "Bericht"
        verbose_name_plural = "Berichte"
        constraints = [
            models.UniqueConstraint(
                fields=["mandat", "art", "monat"],
                condition=models.Q(monat__isnull=False),
                name="bericht_monat_einmalig",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.get_art_display()} {self.monat or self.aufgabe_id or ''}".strip()

    @property
    def faellig_am(self) -> date | None:
        """Der letzte Tag der Frist dieses Berichts — oder None, wenn kein Bezug gesetzt ist."""
        if self.art == Berichtsart.MONATSBERICHT and self.monat is not None:
            from parameter.models import zahl

            return monatsbericht_faellig_am(self.monat, zahl("mandatar-monatsbericht-frist-tage", 7))
        if self.art == Berichtsart.SAMMELBERICHT and self.aufgabe is not None and self.aufgabe.frist:
            return faellig_am(timezone.localdate(self.aufgabe.frist), SAMMELBERICHT_TAGE)
        return None

    def lage(self, heute: date | None = None) -> Lage | None:
        faellig = self.faellig_am
        if faellig is None:
            return None
        return lage(faellig, timezone.localdate(self.eingereicht_am), heute or timezone.localdate())
