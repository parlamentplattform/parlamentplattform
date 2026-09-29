"""Das Lauf-Archiv, das Budget und die Warteschlange des Modell-Steckplatzes (F-60, Ring 0b).

Jeder KI-Aufruf hinterlässt einen Lauf — auch der gescheiterte: Zweck,
Eingabe, Antwort, Modell, Tokenverbrauch, Dauer, Auftragsversion. Das Archiv ist die
Rechenschaft des Steckplatzes; seine Kennzahlen stehen öffentlich auf der
Zukunftswerkstatt-Seite. Ein Monats-Tokenbudget deckelt die Kosten hart:
Ist es erschöpft, wird der Steckplatz stumm, bis der Monat wechselt
(Register „ki-monatstokens“, F-68).

Seit 0.50 gibt es daneben `KIAuftrag`: die Warteschlange (FB-H1/FB-H6). Was nicht in der
Anfrage selbst gerechnet werden muss — betroffene Gesetze beim Einbringen, nachgezogene
Textvektoren —, wird eingereiht und vom Hintergrundlauf „zukunftswerkstatt“ mit Tageskontingent
(„ki-tageslaeufe“) abgearbeitet (`ki/warteschlange.py`). Das Ergebnis bleibt im Lauf; der
Auftrag verweist nur darauf."""

from __future__ import annotations

import time

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from ki.anbieter import AnbieterFehler, Einbettung, SteckplatzStumm, anbieter_waehlen

MONATSTOKENS_STANDARD = 1_000_000  # Zielwert, offener Parameter (→ F-68)


class Zweck(models.TextChoices):
    EINSCHAETZUNG = "einschaetzung", _("Einschätzung für die Gremien-Werkstatt")
    PARAMETERVORSCHLAG = "parametervorschlag", _("Vorschlag der Zukunftswerkstatt zu einem Parametertest")
    AEHNLICHKEIT = "aehnlichkeit", _("Textvektoren für den Bedeutungsvergleich beim Einbringen")
    RECHTSBEZUG = "rechtsbezug", _("Betroffene Gesetze — Vorschlag der Zukunftswerkstatt")


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
    tokens_ein = models.PositiveIntegerField(default=0)
    tokens_aus = models.PositiveIntegerField(default=0)
    dauer_ms = models.PositiveIntegerField(default=0)
    erfolgreich = models.BooleanField(default=True)
    fehler = models.CharField(max_length=300, blank=True)
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-erstellt_am"]
        verbose_name = "KI-Lauf"
        verbose_name_plural = "KI-Läufe"

    def __str__(self) -> str:
        return f"KI-Lauf {self.get_zweck_display()} ({self.modell}, {self.erstellt_am:%d.%m.%Y})"

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

    Je Antrag, Zweck und Fassung genau einer (Einreihen ist idempotent). Der Auftrag trägt nur
    den Zustand — reserviert wird atomar per UPDATE wie beim Postauftrag, damit zwei Worker nie
    denselben Auftrag zugleich rechnen; scheitert ein Lauf, rückt der nächste Versuch nach hinten
    (2, 4, 8 … Minuten), nach `HOECHSTVERSUCHE` gilt der Auftrag als gescheitert. Das Ergebnis
    steht im verknüpften Lauf (Archiv, Grundregel 5); der Auftrag wird nie gelöscht."""

    zweck = models.CharField(max_length=20, choices=Zweck.choices)
    antrag = models.ForeignKey("verfahren.Antrag", on_delete=models.PROTECT, related_name="ki_auftraege")
    fassung_nummer = models.PositiveIntegerField(default=1)
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

    class Meta:
        ordering = ["pk"]
        verbose_name = "KI-Auftrag"
        verbose_name_plural = "KI-Aufträge"
        constraints = [
            models.UniqueConstraint(fields=["zweck", "antrag", "fassung_nummer"], name="kiauftrag_einmal_je_fassung")
        ]

    def __str__(self) -> str:
        return f"KI-Auftrag {self.get_zweck_display()} zu Antrag {self.antrag_id} ({self.status})"


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
        raise SteckplatzStumm(
            "Kein KI-Anbieter angeschlossen — der Steckplatz ist leer (Schlüssel fehlt)."
        )
    if KILauf.monatsverbrauch() >= KILauf.monatsbudget():
        raise SteckplatzStumm(
            "Das Monats-Tokenbudget des Steckplatzes ist erschöpft — er bleibt stumm, bis der Monat wechselt."
        )
    return anbieter


def lauf_ausfuehren(
    zweck: str, auftrag: str, eingabe: str, mitglied, antrag=None, auftrag_version: str = ""
) -> KILauf:
    """Der eine Weg durch den Steckplatz: Budget prüfen, fragen, archivieren.

    Wirft SteckplatzStumm mit ehrlichem Grund, wenn kein Anbieter angeschlossen
    ist, das Monatsbudget erschöpft ist oder der Anbieter nicht antwortet —
    ein gescheiterter Anbieter-Aufruf steht trotzdem im Archiv."""
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
        tokens_ein=antwort.tokens_ein,
        tokens_aus=antwort.tokens_aus,
        dauer_ms=int((time.monotonic() - beginn) * 1000),
    )


def einbettung_ausfuehren(
    texte: list[str], mitglied, antrag=None, zeitgrenze: float | None = None
) -> tuple[KILauf, Einbettung]:
    """Textvektoren über den Steckplatz — derselbe Weg wie `lauf_ausfuehren`: Budget prüfen, einbetten,
    archivieren (Zweck „aehnlichkeit“). Das Archiv hält die Texte und die Zahl der Vektoren fest,
    nicht die Vektoren selbst — die gehören zu ihrem Antrag (`verfahren.AntragsEinbettung`).
    `zeitgrenze` gibt der Anbieter-Verbindung eine eigene, kürzere Frist (Aufruf in einer Anfrage);
    ohne sie gilt die des Steckplatzes.
    Wirft SteckplatzStumm, wenn der Steckplatz leer, das Budget erschöpft oder der Anbieter stumm ist."""
    anbieter = _anbieter_bereit()
    eingabe = "\n\n---\n\n".join(texte)
    beginn = time.monotonic()
    try:
        einbettung = anbieter.einbetten(texte, zeitgrenze=zeitgrenze)
    except AnbieterFehler as fehler:
        KILauf.objects.create(
            zweck=Zweck.AEHNLICHKEIT,
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
