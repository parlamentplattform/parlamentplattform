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
        help_text="Letzter Beitragseingang (§ 4 Abs 3) — verbucht der Bankabgleich (F-59) oder die Verwaltung.",
    )
    ist_admin = models.BooleanField(
        default=False,
        help_text="Zugang zur Mitgliederverwaltung (F-51). Ernennen und Entziehen können nur Admins; "
        "jeder Wechsel wird auditiert.",
    )
    favoriten_zuerst = models.BooleanField(
        default=True,
        help_text="WeicherFilter in der Voreinstellung: ★ Favoriten zuerst (FB-B1). Gilt, solange kein Profil aktiv ist.",
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

    @property
    def hat_gremienrolle(self) -> bool:
        """Aktive Rolle in einem Gremium (F-66)? Lazy importiert — die
        Gremien-Werkstatt hängt von den Mitgliedern ab, nicht umgekehrt."""
        from gremien.models import Gremium, Rolle

        return Rolle.hat(self, *Gremium.values)


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


class Bankkopplung(models.Model):
    """Die PSD2-Kopplung des Vereinskontos an einen Kontoinformationsdienst (F-59).

    Es gibt genau ein Vereinskonto; alte Kopplungen bleiben deaktiviert stehen
    (Nachvollziehbarkeit). Die Zustimmung erteilt ausschließlich die Konto-
    inhaberin bzw. der Kontoinhaber im eigenen Online-Banking — die Plattform
    kennt keine Bankzugangsdaten, nur die Kennungen des Dienstes.
    """

    requisition_id = models.CharField(max_length=64)
    account_id = models.CharField(max_length=64, blank=True)
    institution_id = models.CharField(max_length=64)
    gekoppelt_am = models.DateTimeField(auto_now_add=True)
    consent_bis = models.DateField(
        null=True, blank=True, help_text="Ende der Bank-Zustimmung — danach in der Verwaltung neu koppeln."
    )
    zuletzt_abgerufen = models.DateTimeField(null=True, blank=True)
    abruf_tag = models.DateField(null=True, blank=True)
    abrufe_heute = models.PositiveSmallIntegerField(default=0)
    aktiv = models.BooleanField(default=True)

    ABRUFE_PRO_TAG = 4  # PSD2-Kontingent für unbegleitete Abrufe

    class Meta:
        ordering = ["-gekoppelt_am"]
        verbose_name = "Bankkopplung"
        verbose_name_plural = "Bankkopplungen"

    def __str__(self) -> str:
        return f"{self.institution_id} ({'aktiv' if self.aktiv else 'inaktiv'})"

    @classmethod
    def aktuelle(cls):
        return cls.objects.filter(aktiv=True, account_id__gt="").first()

    def abruf_erlaubt(self) -> bool:
        from django.utils import timezone

        heute = timezone.localdate()
        return self.abruf_tag != heute or self.abrufe_heute < self.ABRUFE_PRO_TAG

    def abruf_vermerken(self) -> None:
        from django.utils import timezone

        heute = timezone.localdate()
        if self.abruf_tag != heute:
            self.abruf_tag, self.abrufe_heute = heute, 0
        self.abrufe_heute += 1
        self.zuletzt_abgerufen = timezone.now()
        self.save(update_fields=["abruf_tag", "abrufe_heute", "zuletzt_abgerufen"])


class Beitragseingang(models.Model):
    """Ein verbuchter Beitragseingang (F-59, § 4 Abs 3) — bewusst schmal:
    kein Absendername, keine IBAN. `namens_hinweis` hält nur fest, DASS der
    Absendername erkennbar vom Mitgliedsnamen abwich (für die Verwaltung)."""

    mitglied = models.ForeignKey(Mitglied, on_delete=models.PROTECT, related_name="beitraege")
    betrag = models.DecimalField(max_digits=9, decimal_places=2)
    gebucht_am = models.DateField()
    umsatz_id = models.CharField(max_length=140, unique=True)
    namens_hinweis = models.BooleanField(default=False)
    erfasst_am = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-gebucht_am", "-pk"]
        verbose_name = "Beitragseingang"
        verbose_name_plural = "Beitragseingänge"

    def __str__(self) -> str:
        return f"Eingang {self.gebucht_am} → Mitglied {self.mitglied_id}"


def beitrag_verbuchen(mitglied: Mitglied, eingang, namens_ok: bool) -> bool:
    """Verbucht einen zugeordneten Eingang: Beitragsdatum, Freischaltung, Audit, Mail.

    Idempotent über die Umsatz-ID (jeder Bankumsatz zählt genau einmal).
    Freischaltung wie auf der Willkommensseite versprochen: Der erste Eingang
    hebt „ungeprüft“ auf „geprüft“; ein pausiertes Konto wird wieder aktiv
    (§ 4 Abs 3). Jede Verbuchung landet im öffentlichen Audit-Log (F-22) —
    ohne Betrag: Die Höhe ist Selbsteinschätzung und bleibt privat.
    """
    from django.db import transaction

    from verfahren.models import AuditEintrag

    with transaction.atomic():
        _eintrag, neu = Beitragseingang.objects.get_or_create(
            umsatz_id=eingang.umsatz_id,
            defaults={
                "mitglied": mitglied,
                "betrag": eingang.betrag,
                "gebucht_am": eingang.gebucht_am,
                "namens_hinweis": not namens_ok,
            },
        )
        if not neu:
            return False
        felder = ["beitrag_zuletzt_am"]
        if mitglied.beitrag_zuletzt_am is None or eingang.gebucht_am > mitglied.beitrag_zuletzt_am:
            mitglied.beitrag_zuletzt_am = eingang.gebucht_am
        if mitglied.status == Mitgliedsstatus.PAUSIERT:
            mitglied.status = Mitgliedsstatus.AKTIV
            mitglied.status_grund = "Beitragseingang automatisch abgeglichen (F-59)."
            felder += ["status", "status_grund"]
        if mitglied.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
            mitglied.identitaetsstufe = Identitaetsstufe.GEPRUEFT
            felder += ["identitaetsstufe"]
        mitglied.save(update_fields=felder)
        AuditEintrag.anhaengen(
            {"typ": "beitrag", "aktion": "eingang_verbucht", "mitglied": mitglied.pk}
        )

    from django.conf import settings
    from django.core.mail import send_mail

    try:  # Bestätigung ist Höflichkeit, keine Bedingung — Verbuchung steht bereits.
        send_mail(
            "Ihr Mitgliedsbeitrag ist eingegangen",
            "Danke! Ihr Beitrag wurde Ihrem Konto zugeordnet — Ihre Mitwirkungsrechte "
            "sind damit aktiv. Den Stand sehen Sie jederzeit unter "
            "https://parlament.ddoe.at/beitrag/\n\nDirekte Demokratie Österreich",
            settings.DEFAULT_FROM_EMAIL,
            [mitglied.email],
        )
    except OSError:
        pass
    return True
