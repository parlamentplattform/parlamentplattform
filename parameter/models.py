"""Das Parameterregister (F-68, Ring 0b): die offenen Stellschrauben des
Systems — öffentlich, mit Herkunft, jede Änderung dokumentiert.

Grundsatz der Zukunftswerkstatt: An diesen Parametern lernt die Demokratie
(Fristen, Runden, Budgets). Sie stehen nicht verstreut im Code, sondern in
einem Register mit Beschreibung und Quelle; der Code liest von hier und
fällt auf seine eingebauten Zielwerte zurück, wenn ein Eintrag fehlt.
Ändern kann vorerst die Verwaltung — nur mit Grund, und jeder Schritt landet
im öffentlichen Audit-Log. Später beschließt die Mitgliederversammlung über
die versionierte Verfahrensordnung (F-65: Änderungen als dokumentierte
Experimente)."""

from __future__ import annotations

from django.db import DatabaseError, models
from django.utils import timezone


class Parameter(models.Model):
    schluessel = models.SlugField(max_length=60, unique=True, allow_unicode=False)
    schema_key = models.CharField(
        max_length=80,
        blank=True,
        default="",
        help_text="Sprachneutrale Kennung im gemeinsamen Schema (docs/SCHEMA.md), z. B. „draft_loop.review_days“; leer = nur lokal.",
    )
    wert = models.CharField(max_length=100)
    einheit = models.CharField(max_length=30, blank=True)
    beschreibung = models.TextField(max_length=1000)
    quelle = models.CharField(max_length=200, help_text="Satzungs-/Konzeptstelle, z. B. „§ 5 Abs 12“.")
    geaendert_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["schluessel"]
        verbose_name = "Parameter"
        verbose_name_plural = "Parameterregister"

    def __str__(self) -> str:
        return f"{self.schluessel} = {self.wert}{(' ' + self.einheit) if self.einheit else ''}"


def zahl(schluessel: str, standard: int) -> int:
    """Registerwert als ganze Zahl — mit ehrlichem Rückfall auf den
    eingebauten Zielwert (Eintrag fehlt, Wert unlesbar, DB nicht bereit)."""
    try:
        eintrag = Parameter.objects.filter(schluessel=schluessel).only("wert").first()
        return int(eintrag.wert) if eintrag else standard
    except (DatabaseError, ValueError, TypeError):
        return standard


#: Kürzel interner Dokumente — sie gehören nicht in die öffentliche Quellenangabe.
INTERNE_KENNUNGEN = ("F-6", "F-4", "F-2", "FB-", "A0-", "· L7", "Ring 0")

ERSTBESTAND = [
    {
        "schluessel": "gremien-review-tage",
        "wert": "14",
        "einheit": "Tage",
        "beschreibung": "Frist der Unterstützer in der Entwurfsschleife: Vorschlag annehmen oder mit "
        "konkretem Wunsch zurückgeben. Nach Ablauf wertet die Frist aus — Untätigkeit hemmt nie.",
        "quelle": "§ 5 Abs 12",
    },
    {
        "schluessel": "gremien-ueberarbeitung-tage",
        "wert": "14",
        "einheit": "Tage",
        "beschreibung": "Überarbeitungsfrist des Expertenrats je Rückgabe-Runde. Verstreicht sie ohne "
        "neue Einreichung, geht die zuletzt vorgelegte Fassung zur Endabstimmung.",
        "quelle": "§ 5 Abs 12",
    },
    {
        "schluessel": "gremien-hoechstrunden",
        "wert": "3",
        "einheit": "Runden",
        "beschreibung": "Höchstzahl der Runden der Entwurfsschleife; danach geht der Vorschlag in jedem "
        "Fall zur Endabstimmung.",
        "quelle": "§ 5 Abs 12 („Rundenzahl per Verfahrensordnung“)",
    },
    {
        "schluessel": "vorschlag-annahme-prozent",
        "wert": "50",
        "einheit": "Prozent",
        "beschreibung": "Zustimmungsanteil, den der Beitrag „Passt alles“ im Abstimmungs-Chat "
        "überschreiten muss, damit der Vorschlag zur Endabstimmung geht — zusätzlich muss er an "
        "erster Stelle stehen.",
        "quelle": "§ 5 Abs 12 · Anweisung des Gründers: „mehr als 50%“",
    },
    {
        "schluessel": "vorschlag-chat-reihung",
        "wert": "1",
        "einheit": "Regelfassung",
        "beschreibung": "Fassung der Reihungsregel des Abstimmungs-Chats (engagement-v1): "
        "Engagement = Zustimmungen + Ablehnungen absteigend, dann Zustimmungsanteil, dann Zeit. "
        "Offengelegt und nachrechenbar (§ 2 Abs 6).",
        "quelle": "Anweisung des Gründers: „die kommentare mit dem meisten engagement erscheinen ganz oben“",
    },
    {
        "schluessel": "gremien-rollen-dauer-tage",
        "wert": "730",
        "einheit": "Tage",
        "beschreibung": "Regeldauer einer Gremien-Rolle (zwei Jahre): Bestellung auf öffentliche "
        "Ausschreibung, Bestätigung durch die Mitgliederversammlung, automatisches Erlöschen.",
        "quelle": "§ 6 Abs 8",
    },
    {
        "schluessel": "ki-monatstokens",
        "wert": "1000000",
        "einheit": "Tokens/Monat",
        "beschreibung": "Hartes Monatsbudget des Modell-Steckplatzes. Ist es erschöpft, wird der "
        "Steckplatz stumm, bis der Monat wechselt — Kostendeckel der Zukunftswerkstatt.",
        "quelle": "Grundregel: Die KI schlägt vor, sie entscheidet nie",
    },
]


def erstbestand_sicherstellen() -> int:
    """Fehlende Erstbestands-Einträge anlegen (bestehende Werte bleiben
    unangetastet — das Register gehört den Menschen, nicht dem Code). Die
    Schema-Kennung (FB-M5) wird nachgetragen, wenn sie fehlt — sie ist Bedeutung,
    kein Wert."""
    from plattform_core.schema import schema_key

    neu = 0
    for eintrag in ERSTBESTAND:
        vorlage = {**eintrag, "schema_key": schema_key(eintrag["schluessel"])}
        parameter, angelegt = Parameter.objects.get_or_create(
            schluessel=eintrag["schluessel"], defaults=vorlage
        )
        neu += int(angelegt)
        felder = []
        if not angelegt and not parameter.schema_key and vorlage["schema_key"]:
            parameter.schema_key = vorlage["schema_key"]
            felder.append("schema_key")
        # Interne Kennungen aus der Quelle nehmen (Entscheidung 4.9.2026): Sie verweisen auf
        # Dokumente, die Besuchern nichts sagen — teils auf nicht öffentliche. Der Wert bleibt
        # unangetastet, die Quelle ist Beschreibung.
        if not angelegt and any(k in (parameter.quelle or "") for k in INTERNE_KENNUNGEN):
            parameter.quelle = vorlage["quelle"]
            felder.append("quelle")
        if felder:
            parameter.save(update_fields=felder)
    return neu
