"""Das Lauf-Archiv und das Budget des Modell-Steckplatzes (F-60, Ring 0b).

Jeder KI-Aufruf hinterlässt einen Lauf — auch der gescheiterte: Zweck,
Eingabe, Antwort, Modell, Tokenverbrauch, Dauer. Das Archiv ist die
Rechenschaft des Steckplatzes; seine Kennzahlen stehen öffentlich auf der
Zukunftswerkstatt-Seite. Ein Monats-Tokenbudget deckelt die Kosten hart:
Ist es erschöpft, wird der Steckplatz stumm, bis der Monat wechselt
(Zielwert — wandert mit F-68 ins Parameterregister)."""

from __future__ import annotations

import time

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.utils import timezone

from ki.anbieter import AnbieterFehler, SteckplatzStumm, anbieter_waehlen

MONATSTOKENS_STANDARD = 1_000_000  # Zielwert, offener Parameter (→ F-68)


class Zweck(models.TextChoices):
    EINSCHAETZUNG = "einschaetzung", "Einschätzung für die Gremien-Werkstatt"


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
        jetzt = jetzt or timezone.now()
        summe = cls.objects.filter(
            erstellt_am__year=jetzt.year, erstellt_am__month=jetzt.month
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


def steckplatz_stand() -> dict:
    """Der öffentliche Stand: angeschlossen?, Verbrauch, Budget, Läufe."""
    anbieter = anbieter_waehlen()
    return {
        "angeschlossen": anbieter is not None,
        "anbieter": getattr(anbieter, "name", ""),
        "modell": getattr(anbieter, "modell", ""),
        "laeufe": KILauf.objects.count(),
        "monatsverbrauch": KILauf.monatsverbrauch(),
        "monatsbudget": KILauf.monatsbudget(),
    }


def lauf_ausfuehren(zweck: str, auftrag: str, eingabe: str, mitglied, antrag=None) -> KILauf:
    """Der eine Weg durch den Steckplatz: Budget prüfen, fragen, archivieren.

    Wirft SteckplatzStumm mit ehrlichem Grund, wenn kein Anbieter angeschlossen
    ist, das Monatsbudget erschöpft ist oder der Anbieter nicht antwortet —
    ein gescheiterter Anbieter-Aufruf steht trotzdem im Archiv."""
    anbieter = anbieter_waehlen()
    if anbieter is None:
        raise SteckplatzStumm(
            "Kein KI-Anbieter angeschlossen — der Steckplatz ist leer (Schlüssel fehlt)."
        )
    if KILauf.monatsverbrauch() >= KILauf.monatsbudget():
        raise SteckplatzStumm(
            "Das Monats-Tokenbudget des Steckplatzes ist erschöpft — er bleibt stumm, bis der Monat wechselt."
        )
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
        tokens_ein=antwort.tokens_ein,
        tokens_aus=antwort.tokens_aus,
        dauer_ms=int((time.monotonic() - beginn) * 1000),
    )
