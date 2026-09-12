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
    GEPRUEFT = "geprueft", "geprüft (Beitragseingang verbucht)"
    PRAESENZ = "praesenz", "Präsenz-Identitätsfeststellung (§ 13 Abs 2)"
    EID = "eid", "elektronischer Identitätsnachweis (§ 2 Abs 4)"


class Mitgliedsstatus(models.TextChoices):
    """Stand der Mitgliedschaft (F-51). „pausiert“ lässt Lesen und Anmelden zu,
    Mitwirkungsrechte (einbringen, unterstützen, beraten, abstimmen) ruhen,
    bis der Mitgliedsbeitrag wieder eingegangen ist (§ 4 Abs 3).
    „ausgeschlossen“ setzt zusätzlich das Konto inaktiv (§ 4 Abs 6).
    „ausgetreten“ ist der selbst erklärte Austritt (§ 4 Abs 5): Konto inaktiv, Stammdaten
    geleert, Beiträge zu Verfahren bleiben stehen — nichts wird gelöscht, was ein Verfahren
    betrifft."""

    AKTIV = "aktiv", "aktiv"
    PAUSIERT = "pausiert", "pausiert (Beitrag ausständig)"
    AUSGESCHLOSSEN = "ausgeschlossen", "ausgeschlossen"
    AUSGETRETEN = "ausgetreten", "ausgetreten"


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
    geprueft_seit = models.DateField(
        null=True,
        blank=True,
        help_text="Tag, seit dem das Konto nicht mehr „ungeprüft“ ist — Stichtagsprüfung der "
        "Stimmberechtigung (§ 4 Abs 4 lit a): Zähler und Nenner folgen demselben Tag.",
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
        help_text="Wohnsitz-Bundesland — regionale Anträge sind nur in der eigenen Region möglich.",
    )
    wohnsitz = models.ForeignKey(
        "Gemeinde",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mitglieder",
        help_text="Eindeutiger Verweis ins amtliche Gemeindeverzeichnis — Quelle für gemeinde und bundesland.",
    )
    nebenwohnsitz = models.ForeignKey(
        "Gemeinde",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="nebenwohnsitz_mitglieder",
        help_text="Zweiter Wohnsitz im amtlichen Gemeindeverzeichnis — ordnet nur zusätzlich einer Region zu, "
        "sobald die Stellgröße region-nebenwohnsitz-zaehlt auf 1 steht; am Stimmrecht ändert er nichts (§ 5 Abs 6).",
    )
    status = models.CharField(
        max_length=16,
        choices=Mitgliedsstatus.choices,
        default=Mitgliedsstatus.AKTIV,
        help_text="Stand der Mitgliedschaft — jede Änderung läuft über die Verwaltung und wird auditiert.",
    )
    status_grund = models.TextField(
        blank=True,
        help_text="Begründung des aktuellen Status (z. B. Beschlussreferenz bei Ausschluss, § 4 Abs 6).",
    )
    status_seit = models.DateField(
        null=True,
        blank=True,
        help_text="Tag, seit dem der aktuelle Status gilt (leer = seit jeher) — Stichtagsprüfung "
        "der Stimmberechtigung (§ 4 Abs 4 lit a).",
    )
    beitrag_zuletzt_am = models.DateField(
        null=True,
        blank=True,
        help_text="Letzter Beitragseingang (§ 4 Abs 3) — verbucht der Bankabgleich oder die Verwaltung.",
    )
    ist_admin = models.BooleanField(
        default=False,
        help_text="Zugang zur Mitgliederverwaltung. Ernennen und Entziehen können nur Admins; "
        "jeder Wechsel wird auditiert.",
    )
    favoriten_zuerst = models.BooleanField(
        default=True,
        help_text="WeicherFilter in der Voreinstellung: ★ Favoriten zuerst. Gilt, solange kein Profil aktiv ist.",
    )

    class Meta:
        verbose_name = "Mitglied"
        verbose_name_plural = "Mitglieder"

    def ist_stimmberechtigt(self, gegenstand: Gegenstand | str, stichtag, uebergang: bool = False) -> bool:
        """Stimmberechtigt AM STICHTAG (§ 4 Abs 4 lit a) — nicht zum Aufrufzeitpunkt.

        Beitritt, Freischaltung (`geprueft_seit`) und Status (`status_seit`) werden alle
        gegen denselben Tag geprüft. Nur so steht ein Mitglied genau dann im Zähler,
        wenn es auch im Nenner (`stimmberechtigte_zaehlen`) gezählt wurde; wer erst nach
        Abstimmungsbeginn freigeschaltet oder wieder aktiv wird, stimmt bei dieser
        Abstimmung nicht mit."""
        if self.beitritt is None:
            return False
        if self.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
            return False
        # Altbestand ohne Datum: die Datenmigration trägt den Beitritt nach; hier als Rückfall.
        geprueft_seit = self.geprueft_seit or self.beitritt
        if geprueft_seit > stichtag:
            return False  # am Stichtag noch ungeprüft — stand nicht im Nenner
        if self.status != Mitgliedsstatus.AKTIV:
            return False  # pausiert oder ausgeschlossen: Mitwirkungsrechte ruhen (F-51)
        if self.status_seit is not None and self.status_seit > stichtag:
            return False  # am Stichtag noch pausiert oder ausgeschlossen
        return stimmberechtigt(self.beitritt, gegenstand, stichtag, uebergang=uebergang)

    def identitaetsstufe_setzen(self, stufe: str) -> list[str]:
        """Setzt die Stufe und führt `geprueft_seit` nach (§ 4 Abs 4 lit a).
        Gibt die geänderten Feldnamen zurück; speichert nicht."""
        felder: list[str] = []
        if stufe == self.identitaetsstufe:
            return felder
        self.identitaetsstufe = stufe
        felder.append("identitaetsstufe")
        if stufe == Identitaetsstufe.UNGEPRUEFT:
            self.geprueft_seit = None
            felder.append("geprueft_seit")
        elif self.geprueft_seit is None:
            from django.utils import timezone

            self.geprueft_seit = timezone.localdate()
            felder.append("geprueft_seit")
        return felder

    def status_setzen(self, status: str, grund: str = "") -> list[str]:
        """Setzt den Status samt Begründung und `status_seit`; speichert nicht."""
        from django.utils import timezone

        felder: list[str] = []
        if status != self.status:
            self.status = status
            self.status_seit = timezone.localdate()
            felder += ["status", "status_seit"]
        if grund != self.status_grund:
            self.status_grund = grund
            felder.append("status_grund")
        return felder

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
    def adresswechsel_offen(self) -> bool:
        """Läuft gerade eine verwaltungsseitige Änderung der Anmeldeadresse (F-51)?
        Solange ja, gehört das Konto möglicherweise nicht mehr dem Menschen, der
        abgestimmt hat — Stimmabgabe und Registereinsicht sollen in dieser Zeit ruhen."""
        return Adresswechsel.objects.filter(mitglied=self, status=Adresswechsel.Status.OFFEN).exists()

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

    @property
    def aktive_mandate(self):
        """Die offenen Mandate (§ 7) — Queryset, geordnet nach Ebene, Gebiet, Antritt.
        Lazy: `mandatare` hängt von den Mitgliedern ab, nicht umgekehrt."""
        from mandatare.models import Mandat

        return Mandat.aktive_von(self)

    @property
    def ist_mandatar(self) -> bool:
        """Die Rolle „Mandatar“ ist abgeleitet, kein Datensatz: Sie entsteht mit dem Mandat
        und endet, sobald `Mandat.beendet` gesetzt ist. Kein Gremium, keine Rollen-Zeile."""
        return self.is_authenticated and self.aktive_mandate.exists()


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


class Adresswechsel(models.Model):
    """Verwaltungsseitige Änderung der Anmeldeadresse — nie sofort wirksam (F-51).

    Der Login ist passwortlos und läuft über die E-Mail-Adresse. Wer sie an einem
    fremden Konto ändern kann, übernimmt das Konto — und sieht unter „Meine Stimme
    prüfen“ das Pseudonym, das in der veröffentlichten Stimmliste neben dem Stimm-
    wert steht (§ 5 Abs 3: das Stimmgeheimnis ist das zentrale Versprechen). Darum
    drei Hürden, die ein einzelner Admin nicht überspringen kann:

    1. Nachricht mit Einspruchslink an die BISHERIGE Adresse (nur ihr Inhaber kann
       widersprechen — die neue Adresse kontrolliert womöglich der Angreifer);
    2. Wartefrist (Register „adresswechsel-wartefrist-stunden“, Zielwert 72 h);
    3. Bestätigung durch einen ZWEITEN Admin (Vier-Augen).

    Bis dahin bleibt die alte Adresse Anmeldeadresse; Anmeldelinks gehen nie an
    die neue. Das öffentliche Audit-Log führt jeden Schritt als eigene Aktion —
    ohne Adresswerte. Der satzungsgebende Erstzugang (DDOE_FIX_ADMIN) ist von
    diesem Weg ganz ausgenommen, und seine Adresse bekommt kein anderes Konto.
    """

    class Status(models.TextChoices):
        OFFEN = "offen", "offen"
        WIRKSAM = "wirksam", "wirksam"
        WIDERRUFEN = "widerrufen", "widerrufen"

    WARTEFRIST_STUNDEN = 72  # Zielwert; gelesen wird das Register

    mitglied = models.ForeignKey(Mitglied, on_delete=models.CASCADE, related_name="adresswechsel")
    neue_email = models.EmailField()
    beantragt_von = models.ForeignKey(
        Mitglied, null=True, on_delete=models.SET_NULL, related_name="beantragte_adresswechsel"
    )
    beantragt_am = models.DateTimeField(auto_now_add=True)
    frist_bis = models.DateTimeField()
    bestaetigt_von = models.ForeignKey(
        Mitglied, null=True, blank=True, on_delete=models.SET_NULL, related_name="bestaetigte_adresswechsel"
    )
    bestaetigt_am = models.DateTimeField(null=True, blank=True)
    einspruch_hash = models.CharField(max_length=64, unique=True)
    status = models.CharField(max_length=12, choices=Status.choices, default=Status.OFFEN)
    erledigt_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-beantragt_am"]
        verbose_name = "Adresswechsel"
        verbose_name_plural = "Adresswechsel"

    def __str__(self) -> str:
        return f"Adresswechsel für Mitglied {self.mitglied_id} ({self.status})"

    @staticmethod
    def wartefrist_stunden() -> int:
        from parameter.models import zahl

        return zahl("adresswechsel-wartefrist-stunden", Adresswechsel.WARTEFRIST_STUNDEN)

    @classmethod
    def offener(cls, mitglied) -> Adresswechsel | None:
        return cls.objects.filter(mitglied=mitglied, status=cls.Status.OFFEN).first()

    @classmethod
    def beantragen(cls, mitglied, neue_email: str, durch) -> tuple[Adresswechsel, str]:
        """Legt den Antrag an; gibt (wechsel, einspruch_klartext) zurück. Der Klartext
        existiert nur in der Nachricht an die bisherige Adresse."""
        from datetime import timedelta

        from django.utils import timezone

        from mitglieder.auth_flows import _neues_token

        klar, gehasht = _neues_token()
        wechsel = cls.objects.create(
            mitglied=mitglied,
            neue_email=neue_email.lower(),
            beantragt_von=durch,
            frist_bis=timezone.now() + timedelta(hours=cls.wartefrist_stunden()),
            einspruch_hash=gehasht,
        )
        return wechsel, klar

    @classmethod
    def per_einspruch(cls, klartext: str) -> Adresswechsel | None:
        import hashlib

        gehasht = hashlib.sha256(klartext.encode()).hexdigest()
        return cls.objects.select_related("mitglied").filter(einspruch_hash=gehasht).first()

    @property
    def frist_abgelaufen(self) -> bool:
        from django.utils import timezone

        return timezone.now() >= self.frist_bis

    @property
    def ist_faellig(self) -> bool:
        return self.status == self.Status.OFFEN and self.bestaetigt_von_id is not None and self.frist_abgelaufen

    def _protokollieren(self, aktion: str, **extra) -> None:
        from verfahren.models import AuditEintrag

        AuditEintrag.anhaengen(
            {"typ": "verwaltung", "aktion": aktion, "mitglied": self.mitglied_id, **extra}
        )  # bewusst ohne Adressen: Das Audit-Log ist öffentlich (F-22)

    def bestaetigen(self, durch) -> bool:
        """Vier-Augen: nur ein ANDERER Admin als der Antragsteller."""
        from django.utils import timezone

        if self.status != self.Status.OFFEN or durch.pk == self.beantragt_von_id or self.bestaetigt_von_id:
            return False
        self.bestaetigt_von, self.bestaetigt_am = durch, timezone.now()
        self.save(update_fields=["bestaetigt_von", "bestaetigt_am"])
        self._protokollieren("email_geaendert_bestaetigt", durch=durch.pk)
        return True

    def widerrufen(self, anlass: str, durch=None) -> bool:
        """Einspruch des Mitglieds („einspruch“) oder Abbruch durch einen Admin („abbruch“)."""
        from django.utils import timezone

        if self.status != self.Status.OFFEN:
            return False
        self.status, self.erledigt_am = self.Status.WIDERRUFEN, timezone.now()
        self.save(update_fields=["status", "erledigt_am"])
        extra = {"anlass": anlass}
        if durch is not None:
            extra["durch"] = durch.pk
        self._protokollieren("email_geaendert_widerrufen", **extra)
        return True

    def wirksam_machen(self) -> bool:
        """Macht die neue Adresse zur Anmeldeadresse — nur wenn Frist um, zweiter Admin
        bestätigt hat und weder der fixe Admin betroffen ist noch seine Adresse vergeben wird."""
        from django.utils import timezone

        if not self.ist_faellig:
            return False
        m = self.mitglied
        fix = getattr(settings, "DDOE_FIX_ADMIN", "").lower()
        vergeben = Mitglied.objects.filter(email__iexact=self.neue_email).exclude(pk=m.pk).exists()
        if m.ist_fixer_admin or self.neue_email == fix or vergeben:
            self.widerrufen("nicht_zulaessig")
            return False
        felder = ["email"]
        if m.username == m.email:
            m.username = self.neue_email  # Registrierte führen die Adresse als Anmeldenamen
            felder.append("username")
        m.email = self.neue_email
        m.save(update_fields=felder)
        self.status, self.erledigt_am = self.Status.WIRKSAM, timezone.now()
        self.save(update_fields=["status", "erledigt_am"])
        self._protokollieren("email_geaendert_wirksam")
        return True

    @classmethod
    def faellige_anwenden(cls) -> int:
        """Lazy wie die Phasenautomatik: Wer eine Verwaltungsseite öffnet oder einen
        Anmeldelink anfordert, stößt fällige Wechsel an. Gibt die Zahl der wirksam gemachten zurück."""
        from django.utils import timezone

        anzahl = 0
        for w in cls.objects.filter(
            status=cls.Status.OFFEN, bestaetigt_von__isnull=False, frist_bis__lte=timezone.now()
        ).select_related("mitglied"):
            if w.wirksam_machen():
                anzahl += 1
        return anzahl


class Drosselzaehler(models.Model):
    """Versuche je Verbindung, Zweck und Stunde (F-49, Befunde #19/#66).

    In der Datenbank statt im prozesslokalen Cache: Zwei gunicorn-Worker führen sonst
    zwei Eimer, und ein Neustart setzt den Stand auf null. Keine Verfahrensdaten —
    Zeilen älter als zwei Stunden räumt `drossel_zuviel` im Vorbeigehen ab. Die
    Kennung ist die Verbindungsadresse; gespeichert wird sie nur für diese Stunde."""

    zweck = models.CharField(max_length=30)
    kennung = models.CharField(max_length=64)
    stunde = models.IntegerField(help_text="Unix-Zeit geteilt durch 3600.")
    anzahl = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name = "Drosselzähler"
        verbose_name_plural = "Drosselzähler"
        constraints = [
            models.UniqueConstraint(fields=["zweck", "kennung", "stunde"], name="drossel_je_zweck_kennung_stunde")
        ]

    def __str__(self) -> str:
        return f"{self.zweck}: {self.anzahl} in Stunde {self.stunde}"


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
            felder += mitglied.status_setzen(
                Mitgliedsstatus.AKTIV, "Beitragseingang automatisch abgeglichen (F-59)."
            )
        if mitglied.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
            # Freischaltung zählt ab HEUTE, nicht ab Buchungstag: Der Nenner einer laufenden
            # Abstimmung wurde ohne dieses Mitglied festgestellt (§ 4 Abs 4 lit a).
            felder += mitglied.identitaetsstufe_setzen(Identitaetsstufe.GEPRUEFT)
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
