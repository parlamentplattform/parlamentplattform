"""Das Lauf-Archiv, das Budget und die Warteschlange des Modell-Steckplatzes (F-60, Ring 0b).

Jeder KI-Aufruf hinterlässt einen Lauf — auch der gescheiterte: Zweck,
Eingabe, Antwort, Modell, Tokenverbrauch, Dauer, Auftragsversion. Das Archiv ist die
Rechenschaft des Steckplatzes; seine Kennzahlen stehen öffentlich auf der
Zukunftswerkstatt-Seite. Die Monatsgrenze stoppt neue Aufrufe ab dem archivierten
Tokenverbrauch (Register „ki-monatstokens“, F-68). Ein bereits begonnener Aufruf
kann Resttokens überschreiten; daraus folgt keine garantierte Geldobergrenze.

Seit 0.50 gibt es daneben `KIAuftrag`: die Warteschlange (FB-H1/FB-H6). Was nicht in der
Anfrage selbst gerechnet werden muss — betroffene Gesetze beim Einbringen, nachgezogene
Textvektoren —, wird eingereiht und vom Hintergrundlauf „zukunftswerkstatt“ mit Tageskontingent
(„ki-tageslaeufe“) abgearbeitet (`ki/warteschlange.py`). Das Ergebnis bleibt im Lauf; der
Auftrag verweist nur darauf."""

from __future__ import annotations

import copy
import time
import uuid

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ki.anbieter import AnbieterFehler, Einbettung, SteckplatzStumm, anbieter_waehlen
from ki.betriebszugang import SteckplatzWartet, einzeln

MONATSTOKENS_STANDARD = 1_000_000  # Zielwert, offener Parameter (→ F-68)


class SteckplatzZugang(models.Model):
    """Betriebliche Zugangssperre, weder Budgetwert noch Archiv-/Verfahrensstand."""

    name = models.CharField(max_length=24, primary_key=True)
    belegt = models.BooleanField(default=False)

    class Meta:
        verbose_name = _("Betrieblicher KI-Zugang")
        verbose_name_plural = _("Betriebliche KI-Zugänge")

    def __str__(self):
        return self.name


def _textstand_schuetzen(instanz, felder, update_fields):
    if instanz.pk is None or update_fields is not None and not any(
        f in felder or f + "_id" in felder for f in update_fields
    ):
        return
    vorher = type(instanz).objects.filter(pk=instanz.pk).values(*felder).first()
    if vorher is None and instanz._state.adding:
        return
    if vorher is None or any(vorher[f] != getattr(instanz, f) for f in felder):
        raise ValidationError(_("Der gespeicherte Textkontext bleibt unverändert."))


class LaufQuerySet(models.QuerySet):
    geschuetzte_eingaben = frozenset({"kontext", "eingabe"})

    def update(self, **kwargs):
        if self.geschuetzte_eingaben & kwargs.keys():
            raise ValidationError(_("Der gespeicherte Textkontext bleibt unverändert."))
        return super().update(**kwargs)

    def bulk_update(self, objs, fields, batch_size=None):
        # Vor Djangos innerem atomic(savepoint=False) ablehnen, damit kein
        # abgefangener Schreibschutzfehler die umgebende Verfahrenstransaktion vergiftet.
        if self.geschuetzte_eingaben & set(fields):
            raise ValidationError(_("Der gespeicherte Textkontext bleibt unverändert."))
        return super().bulk_update(objs, fields, batch_size=batch_size)

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False,
                    update_fields=None, unique_fields=None):
        if update_conflicts and self.geschuetzte_eingaben & set(update_fields or []):
            raise ValidationError(_("Der gespeicherte Textkontext bleibt unverändert."))
        return super().bulk_create(
            objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts, update_conflicts=update_conflicts,
            update_fields=update_fields, unique_fields=unique_fields,
        )

    def delete(self):
        raise ValidationError(_("Aufträge und Läufe der Zukunftswerkstatt bleiben erhalten."))


class ArchivQuerySet(LaufQuerySet):
    """Ein fertiger Lauf hat keine betrieblich veränderlichen Felder."""

    def update(self, **kwargs):
        raise ValidationError(_("Ein archivierter KI-Lauf bleibt unverändert."))

    def bulk_update(self, objs, fields, batch_size=None):
        raise ValidationError(_("Ein archivierter KI-Lauf bleibt unverändert."))

    def bulk_create(self, objs, batch_size=None, ignore_conflicts=False, update_conflicts=False,
                    update_fields=None, unique_fields=None):
        if update_conflicts:
            raise ValidationError(_("Ein archivierter KI-Lauf bleibt unverändert."))
        return super().bulk_create(objs, batch_size=batch_size, ignore_conflicts=ignore_conflicts,
                                   update_fields=update_fields, unique_fields=unique_fields)


class AuftragQuerySet(LaufQuerySet):
    geschuetzte_eingaben = LaufQuerySet.geschuetzte_eingaben | frozenset({
        "antrag", "antrag_id", "zweck", "quellenart", "fassung_nummer", "vorschlagsfassung", "vorschlagsfassung_id",
        "quellenkontext",
        "angefordert_von", "angefordert_von_id", "erstellt_am",
        "beanstandung", "beanstandung_id", "ursprung", "ursprung_id", "korrekturkontext",
    })


class Zweck(models.TextChoices):
    EINSCHAETZUNG = "einschaetzung", _("Einschätzung für die Gremien-Werkstatt")
    PARAMETERVORSCHLAG = "parametervorschlag", _("Vorschlag der Zukunftswerkstatt zu einem Parametertest")
    AEHNLICHKEIT = "aehnlichkeit", _("Textvektoren für den Bedeutungsvergleich beim Einbringen")
    RECHTSBEZUG = "rechtsbezug", _("Betroffene Gesetze — Vorschlag der Zukunftswerkstatt")
    KORREKTUR = "korrektur", _("Nachrechnung eines beanstandeten öffentlichen Rechtsbezugs")


class KILauf(models.Model):
    """Append-only: Läufe werden nie geändert oder gelöscht."""

    zweck = models.CharField(max_length=20, choices=Zweck.choices)
    antrag = models.ForeignKey(
        "verfahren.Antrag", null=True, blank=True, on_delete=models.SET_NULL, related_name="ki_laeufe"
    )
    angefordert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    eingabe = models.TextField()
    antwort = models.TextField(blank=True)
    anbieter = models.CharField(max_length=30)
    modell = models.CharField(max_length=60)
    #: Fassung des Auftragstexts (`ki/auftraege/<zweck>-v<n>.md`), leer bei Läufen ohne Datei (FB-H1).
    auftrag_version = models.CharField(max_length=40, blank=True, default="")
    #: Tatsächlich verwendeter Textstand; leer bei früheren Läufen ohne Kontextnachweis.
    kontext = models.JSONField(default=dict, blank=True)
    tokens_ein = models.PositiveIntegerField(default=0)
    tokens_aus = models.PositiveIntegerField(default=0)
    dauer_ms = models.PositiveIntegerField(default=0)
    erfolgreich = models.BooleanField(default=True)
    fehler = models.CharField(max_length=300, blank=True)
    erstellt_am = models.DateTimeField(default=timezone.now)
    objects = ArchivQuerySet.as_manager()

    class Meta:
        ordering = ["-erstellt_am"]
        verbose_name = "KI-Lauf"
        verbose_name_plural = "KI-Läufe"

    def __str__(self) -> str:
        return f"KI-Lauf {self.get_zweck_display()} ({self.modell}, {self.erstellt_am:%d.%m.%Y})"

    def save(self, *args, **kwargs):
        if not self._state.adding or self.pk is not None and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(_("Ein archivierter KI-Lauf bleibt unverändert."))
        kwargs["force_insert"] = True  # auch bei gleichzeitig neu vergebener expliziter PK niemals UPDATE
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Aufträge und Läufe der Zukunftswerkstatt bleiben erhalten."))

    @classmethod
    def monatsverbrauch(cls, jetzt=None) -> int:
        """Tokens des laufenden Kalendermonats nach Wiener Kalender — `jetzt` darf UTC sein."""
        heute = timezone.localdate(jetzt or timezone.now())
        summe = cls.objects.filter(
            erstellt_am__year=heute.year, erstellt_am__month=heute.month
        ).aggregate(ein=Sum("tokens_ein"), aus=Sum("tokens_aus"))
        return (summe["ein"] or 0) + (summe["aus"] or 0)

    @classmethod
    def monatsbudget(cls) -> int:
        """Seit F-68 führt das Parameterregister (ki-monatstokens); die
        Umgebungsvariable bleibt der Rückfall vor dem Erstbestand."""
        from parameter.models import zahl

        return zahl(
            "ki-monatstokens", getattr(settings, "DDOE_KI_MONATSTOKENS", MONATSTOKENS_STANDARD)
        )


class Auftragsstatus(models.TextChoices):
    GEPLANT = "geplant", _("in der Warteschlange")
    LAEUFT = "laeuft", _("läuft")
    ERLEDIGT = "erledigt", _("erledigt")
    GESCHEITERT = "gescheitert", _("gescheitert")


class KIAuftrag(models.Model):
    """Ein Auftrag in der Warteschlange der Zukunftswerkstatt (FB-H1, FB-H6).

    Je Antrag, Zweck und Fassung genau einer; Korrekturen je Beanstandung einer (idempotent). Der Auftrag trägt nur
    den Zustand — reserviert wird atomar per UPDATE wie beim Postauftrag, damit zwei Worker nie
    denselben Auftrag zugleich rechnen; scheitert ein Lauf, rückt der nächste Versuch nach hinten
    (2, 4, 8 … Minuten), nach `HOECHSTVERSUCHE` gilt der Auftrag als gescheitert. Das Ergebnis
    steht im verknüpften Lauf (Archiv, Grundregel 5); der Auftrag wird nie gelöscht."""

    zweck = models.CharField(max_length=20, choices=Zweck.choices)
    antrag = models.ForeignKey("verfahren.Antrag", on_delete=models.PROTECT, related_name="ki_auftraege")
    fassung_nummer = models.PositiveIntegerField(default=1)
    quellenart = models.CharField(max_length=10, default="antrag", choices=[
        ("antrag", _("Antrag")), ("vorschlag", _("Vorschlag des Expertenrats")),
    ])
    vorschlagsfassung = models.ForeignKey(
        "gremien.EntwurfsFassung", null=True, blank=True, on_delete=models.PROTECT, related_name="ki_auftraege",
    )
    kontext = models.JSONField(default=dict, blank=True)
    quellenkontext = models.JSONField(_("Amtlicher Quellenkontext"), default=dict, blank=True)
    beanstandung = models.OneToOneField(
        "verfahren.Beanstandung", null=True, blank=True, on_delete=models.PROTECT, related_name="korrekturauftrag",
    )
    ursprung = models.ForeignKey(
        KILauf, null=True, blank=True, on_delete=models.PROTECT, related_name="korrekturauftraege",
    )
    korrekturkontext = models.JSONField(default=dict, blank=True)
    angefordert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    status = models.CharField(max_length=12, choices=Auftragsstatus.choices, default=Auftragsstatus.GEPLANT)
    lauf = models.ForeignKey(KILauf, null=True, blank=True, on_delete=models.SET_NULL, related_name="auftraege")
    erstellt_am = models.DateTimeField(default=timezone.now)
    erledigt_am = models.DateTimeField(null=True, blank=True)
    versuche = models.PositiveIntegerField(default=0)
    zuletzt_versucht_am = models.DateTimeField(null=True, blank=True)
    naechster_versuch = models.DateTimeField(null=True, blank=True)
    gesperrt_bis = models.DateTimeField(null=True, blank=True)
    sperrcode = models.CharField(max_length=32, default="", blank=True)
    fehler = models.CharField(max_length=300, default="", blank=True)
    objects = AuftragQuerySet.as_manager()

    class Meta:
        ordering = ["pk"]
        verbose_name = "KI-Auftrag"
        verbose_name_plural = "KI-Aufträge"
        constraints = [
            models.UniqueConstraint(
                fields=["zweck", "antrag", "quellenart", "fassung_nummer"], name="kiauftrag_einmal_je_quelle",
                condition=models.Q(beanstandung__isnull=True),
            ),
            models.CheckConstraint(
                condition=(models.Q(zweck="korrektur", beanstandung__isnull=False, ursprung__isnull=False)
                           | (~models.Q(zweck="korrektur") & models.Q(beanstandung__isnull=True, ursprung__isnull=True, korrekturkontext={}))),
                name="kiauftrag_korrekturbezug",
            ),
            models.CheckConstraint(
                condition=(models.Q(quellenart="antrag", vorschlagsfassung__isnull=True)
                           | models.Q(quellenart="vorschlag", vorschlagsfassung__isnull=False)),
                name="kiauftrag_quellenreferenz",
            ),
        ]

    def __str__(self) -> str:
        return f"KI-Auftrag {self.get_zweck_display()} zu Antrag {self.antrag_id} ({self.status})"

    def save(self, *args, **kwargs):
        if self._state.adding and self.pk is not None and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(_("Der gespeicherte Textkontext bleibt unverändert."))
        _textstand_schuetzen(
            self, ("kontext", "quellenkontext", "zweck", "antrag_id", "quellenart", "fassung_nummer", "vorschlagsfassung_id",
                   "beanstandung_id", "ursprung_id", "korrekturkontext",
                   "angefordert_von_id", "erstellt_am"),
            kwargs.get("update_fields"),
        )
        if self._state.adding:
            kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Aufträge und Läufe der Zukunftswerkstatt bleiben erhalten."))


class VergleichQuerySet(LaufQuerySet):
    geschuetzte_eingaben = frozenset({
        "kennung", "kontext", "eingabe", "eingabe_sha256", "angefordert_von", "angefordert_von_id", "erstellt_am",
    })


class Vergleichsanfrage(models.Model):
    """Private ausdrückliche Anforderung vor dem Einbringen, kein öffentlicher Antrag.

    Eine Kennung darf höchstens einmal gestartet werden. Ein abgebrochener Prozess
    gibt sie nicht zeitgesteuert für einen womöglich noch laufenden Anbieter frei.
    Ein neuer Versuch benötigt später eine neue ausdrückliche Anforderung.
    """

    kennung = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    angefordert_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    kontext = models.JSONField()
    eingabe = models.TextField()
    eingabe_sha256 = models.CharField(max_length=64)
    erstellt_am = models.DateTimeField(default=timezone.now)
    begonnen_am = models.DateTimeField(null=True, blank=True)
    beendet_am = models.DateTimeField(null=True, blank=True)
    lauf = models.OneToOneField(KILauf, null=True, blank=True, on_delete=models.PROTECT, related_name="vergleichsanfrage")
    # Rein betriebliche Zustände, keine inhaltliche Bewertung eines Modells.
    status = models.CharField(max_length=16, default="bereit", choices=[
        ("bereit", _("angefordert")), ("laeuft", _("läuft")),
        ("fertig", _("beantwortet")), ("ohne_ergebnis", _("ohne Modellvergleich")),
    ])
    meldung = models.CharField(max_length=32, blank=True)
    objects = VergleichQuerySet.as_manager()

    class Meta:
        ordering = ["erstellt_am", "kennung"]

    def __str__(self):
        return str(self.kennung)

    def save(self, *args, **kwargs):
        if self._state.adding and self.pk is not None and type(self).objects.filter(pk=self.pk).exists():
            raise ValidationError(_("Der gespeicherte Textkontext bleibt unverändert."))
        _textstand_schuetzen(self, ("kennung", "kontext", "eingabe", "eingabe_sha256", "angefordert_von_id", "erstellt_am"),
                            kwargs.get("update_fields"))
        if self._state.adding:
            kwargs["force_insert"] = True
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValidationError(_("Aufträge und Läufe der Zukunftswerkstatt bleiben erhalten."))


def steckplatz_stand() -> dict:
    """Der öffentliche Stand: angeschlossen?, Verbrauch, Budget, Läufe, Warteschlange."""
    from ki.warteschlange import warteschlange_stand

    anbieter = anbieter_waehlen()
    return {
        "angeschlossen": anbieter is not None,
        "anbieter": getattr(anbieter, "name", ""),
        "modell": getattr(anbieter, "modell", ""),
        "einbettungsmodell": getattr(anbieter, "einbettungsmodell", ""),
        "laeufe": KILauf.objects.count(),
        "monatsverbrauch": KILauf.monatsverbrauch(),
        "monatsbudget": KILauf.monatsbudget(),
        "warteschlange": warteschlange_stand(),
    }


def _anbieter_bereit():
    """Der gemeinsame Vorlauf jedes Aufrufs: Anbieter da, Budget nicht erschöpft — sonst SteckplatzStumm."""
    anbieter = anbieter_waehlen()
    if anbieter is None:
        raise SteckplatzWartet(
            "Kein KI-Anbieter angeschlossen — der Steckplatz ist leer (Schlüssel fehlt)."
        )
    if KILauf.monatsverbrauch() >= KILauf.monatsbudget():
        raise SteckplatzWartet(
            "Das Monats-Tokenbudget des Steckplatzes ist erschöpft — er bleibt stumm, bis der Monat wechselt."
        )
    return anbieter


@einzeln
def lauf_ausfuehren(
    zweck: str, auftrag: str, eingabe: str, mitglied, antrag=None, auftrag_version: str = "", *, kontext=None,
) -> KILauf:
    """Der eine Weg durch den Steckplatz: Budget prüfen, fragen, archivieren.

    Wirft SteckplatzStumm mit ehrlichem Grund, wenn kein Anbieter angeschlossen
    ist, das Monatsbudget erschöpft ist oder der Anbieter nicht antwortet —
    ein gescheiterter Anbieter-Aufruf steht trotzdem im Archiv."""
    kontext = copy.deepcopy(kontext or {})
    anbieter = _anbieter_bereit()
    beginn = time.monotonic()
    try:
        antwort = anbieter.frage(auftrag, eingabe)
    except AnbieterFehler as fehler:
        KILauf.objects.create(
            zweck=zweck,
            antrag=antrag,
            angefordert_von=mitglied,
            eingabe=eingabe,
            anbieter=anbieter.name,
            modell=getattr(anbieter, "modell", ""),
            auftrag_version=auftrag_version,
            kontext=kontext,
            dauer_ms=int((time.monotonic() - beginn) * 1000),
            erfolgreich=False,
            fehler=str(fehler)[:300],
        )
        raise SteckplatzStumm(f"Der Anbieter hat nicht geantwortet ({fehler}).") from fehler
    return KILauf.objects.create(
        zweck=zweck,
        antrag=antrag,
        angefordert_von=mitglied,
        eingabe=eingabe,
        antwort=antwort.text,
        anbieter=anbieter.name,
        modell=antwort.modell,
        auftrag_version=auftrag_version,
        kontext=kontext,
        tokens_ein=antwort.tokens_ein,
        tokens_aus=antwort.tokens_aus,
        dauer_ms=int((time.monotonic() - beginn) * 1000),
    )


@einzeln
def einbettung_ausfuehren(
    texte: list[str], mitglied, antrag=None, zeitgrenze: float | None = None, *, kontext=None,
) -> tuple[KILauf, Einbettung]:
    """Textvektoren über den Steckplatz — derselbe Weg wie `lauf_ausfuehren`: Budget prüfen, einbetten,
    archivieren (Zweck „aehnlichkeit“). Das Archiv hält die Texte und die Zahl der Vektoren fest,
    nicht die Vektoren selbst — die gehören zu ihrem Antrag (`verfahren.AntragsEinbettung`).
    `zeitgrenze` gibt der Anbieter-Verbindung eine eigene, kürzere Frist (Aufruf in einer Anfrage);
    ohne sie gilt die des Steckplatzes.
    Wirft SteckplatzStumm, wenn der Steckplatz leer, das Budget erschöpft oder der Anbieter stumm ist."""
    kontext = copy.deepcopy(kontext or {})
    anbieter = _anbieter_bereit()
    eingabe = "\n\n---\n\n".join(texte)
    beginn = time.monotonic()
    try:
        einbettung = anbieter.einbetten(texte, zeitgrenze=zeitgrenze)
    except AnbieterFehler as fehler:
        KILauf.objects.create(
            zweck=Zweck.AEHNLICHKEIT,
            kontext=kontext,
            antrag=antrag,
            angefordert_von=mitglied,
            eingabe=eingabe,
            anbieter=anbieter.name,
            modell=getattr(anbieter, "einbettungsmodell", ""),
            dauer_ms=int((time.monotonic() - beginn) * 1000),
            erfolgreich=False,
            fehler=str(fehler)[:300],
        )
        raise SteckplatzStumm(f"Der Anbieter hat nicht geantwortet ({fehler}).") from fehler
    dimension = len(einbettung.vektoren[0]) if einbettung.vektoren else 0
    lauf = KILauf.objects.create(
        zweck=Zweck.AEHNLICHKEIT,
        kontext=kontext,
        antrag=antrag,
        angefordert_von=mitglied,
        eingabe=eingabe,
        antwort=f"{len(einbettung.vektoren)} Vektoren à {dimension} Dimensionen",
        anbieter=anbieter.name,
        modell=einbettung.modell,
        tokens_ein=einbettung.tokens,
        dauer_ms=int((time.monotonic() - beginn) * 1000),
    )
    return lauf, einbettung
