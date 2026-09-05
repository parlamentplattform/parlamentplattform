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
from django.utils.translation import gettext_lazy as _


class Gruppe(models.TextChoices):
    """Die Ordnung der Registerseite (FB-J2). Reihenfolge = Reihenfolge der Karten."""

    VERFAHREN = "verfahren", _("Verfahren")
    GREMIEN = "gremien", _("Gremien")
    WEICHERFILTER = "weicherfilter", _("WeicherFilter")
    FAECHER = "faecher", _("Fächer")
    KI = "ki", _("Zukunftswerkstatt")
    SCHUTZ = "schutz", _("Schutz")
    KACHELN = "kacheln", _("Kacheln")


class Status(models.TextChoices):
    """Was mit einem Wert gerade geschieht (FB-J2, FB-J3).

    Ein Wert „im Test" wirkt nur auf Verfahren, die neu beginnen — laufende behalten ihre
    eingefrorene Fassung (§ 5 Abs 5). „Vorgeschlagen" heißt: Die Zukunftswerkstatt oder ein
    Mensch schlägt ihn vor, entschieden ist nichts."""

    GUELTIG = "gueltig", "gültig"
    IM_TEST = "im_test", "im Test"
    VORGESCHLAGEN = "vorgeschlagen", "vorgeschlagen"


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
    gruppe = models.CharField(
        max_length=20, choices=Gruppe.choices, default=Gruppe.VERFAHREN,
        help_text="Ordnet den Eintrag auf der Registerseite ein (FB-J2).",
    )
    status = models.CharField(
        max_length=16, choices=Status.choices, default=Status.GUELTIG,
        help_text="Ein Wert „im Test“ gilt nur für neu beginnende Verfahren (§ 5 Abs 5).",
    )
    test_bis = models.DateField(
        null=True, blank=True, help_text="Ende eines laufenden Tests — danach fällt der Wert zurück."
    )
    test_hypothese = models.CharField(
        max_length=300, blank=True, help_text="Was der Test zeigen soll — steht öffentlich am Band."
    )
    geaendert_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["gruppe", "schluessel"]
        verbose_name = "Parameter"
        verbose_name_plural = "Parameterregister"

    def __str__(self) -> str:
        return f"{self.schluessel} = {self.wert}{(' ' + self.einheit) if self.einheit else ''}"


class Aenderung(models.Model):
    """Eine Wertänderung im Register (FB-J2) — append-only, öffentlich nachlesbar.

    Die Historie stand bisher nur im Audit-Log. Dort ist sie fälschungssicher, aber niemand
    findet sie: Wer wissen will, warum eine Frist heute 21 Tage beträgt, soll das am Parameter
    selbst sehen. Gelöscht wird hier nichts (Grundregel 7)."""

    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE, related_name="historie")
    alter_wert = models.CharField(max_length=100)
    neuer_wert = models.CharField(max_length=100)
    grund = models.TextField(max_length=1000)
    geaendert_am = models.DateTimeField(default=timezone.now)
    durch = models.CharField(
        max_length=80, blank=True,
        help_text="Wer die Änderung veranlasst hat — Rolle oder Organ, nie eine Person.",
    )

    class Meta:
        ordering = ["-geaendert_am"]
        verbose_name = "Änderung"
        verbose_name_plural = "Änderungen"

    def __str__(self) -> str:
        return f"{self.parameter_id}: {self.alter_wert} → {self.neuer_wert}"


def zahl(schluessel: str, standard: int) -> int:
    """Registerwert als ganze Zahl — mit ehrlichem Rückfall auf den
    eingebauten Zielwert (Eintrag fehlt, Wert unlesbar, DB nicht bereit)."""
    try:
        eintrag = Parameter.objects.filter(schluessel=schluessel).only("wert").first()
        return int(eintrag.wert) if eintrag else standard
    except (DatabaseError, ValueError, TypeError):
        return standard


#: Kürzel interner Dokumente — sie gehören nicht in die öffentliche Quellenangabe.
INTERNE_KENNUNGEN = ("F-6", "F-4", "F-2", "FB-", "A0-", "ADR-", "· L7", "Ring 0")

ERSTBESTAND = [
    {
        "schluessel": "aehnlichkeit-schwelle-prozent",
        "wert": "18",
        "einheit": "Prozent",
        "gruppe": "verfahren",
        "beschreibung": "Ab welcher Übereinstimmung die Plattform beim Einbringen auf einen bestehenden "
        "Antrag hinweist. Ein hoher Wert lässt fast alles durch, ein niedriger lenkt Menschen häufig zu "
        "fremden Anträgen — beides verschiebt, wo sich Unterstützung sammelt. Der Hinweis schlägt vor; "
        "einbringen kann man immer.",
        "quelle": "§ 5 Abs 10 lit d · Anweisung des Gründers: „zu prüfen ob ein anderer antrag mit "
        "ähnlichem inhalt bereits eingegangen ist“",
    },
    {
        "schluessel": "aehnlichkeit-treffer",
        "wert": "3",
        "einheit": "Anträge",
        "gruppe": "verfahren",
        "beschreibung": "Wie viele ähnliche Anträge beim Einbringen höchstens gezeigt werden.",
        "quelle": "§ 5 Abs 10 lit d",
    },
    {
        "schluessel": "kategorien-je-antrag",
        "wert": "3",
        "einheit": "Lebensbereiche",
        "gruppe": "verfahren",
        "beschreibung": "Wie vielen Lebensbereichen ein Antrag automatisch zugeordnet wird. Die "
        "Zuordnung entscheidet mit, in welchem Ast des Fächers er auftaucht und wen sein Abo erreicht.",
        "quelle": "§ 5 Abs 10 lit d",
    },
    {
        "schluessel": "kategorien-regel",
        "wert": "1",
        "einheit": "Regelfassung",
        "gruppe": "verfahren",
        "beschreibung": "Fassung der Zuordnungsregel für Lebensbereiche (schlagworte-v1): Zuordnung "
        "über gepflegte Schlagwortlisten, keine KI. Offengelegt und nachrechenbar (§ 2 Abs 6).",
        "quelle": "§ 2 Abs 6",
    },
    {
        "schluessel": "chat-zeichen-hoechstzahl",
        "wert": "4000",
        "einheit": "Zeichen",
        "gruppe": "schutz",
        "beschreibung": "Wie lang ein Beitrag in der Beratung sein darf. Wer die Zahl senkt, zwingt zur "
        "Kürze; wer sie hebt, lässt Wände aus Text zu.",
        "quelle": "§ 5 Abs 3 lit c",
    },
    {
        "schluessel": "chat-bearbeitungsfenster-minuten",
        "wert": "5",
        "einheit": "Minuten",
        "gruppe": "schutz",
        "beschreibung": "Wie lange ein eigener Beitrag noch geändert werden darf. Danach steht er — "
        "eine Abwägung zwischen dem Berichtigen von Tippfehlern und der Verlässlichkeit des Gesagten.",
        "quelle": "§ 5 Abs 3 lit e",
    },
    {
        "schluessel": "kritik-mindestzeichen",
        "wert": "80",
        "einheit": "Zeichen",
        "gruppe": "gremien",
        "beschreibung": "Wie lang eine Kritik am Vorschlag des Expertenrats mindestens sein muss, damit "
        "sie als Änderungswunsch zählt. Zu hoch schließt Knappe aus, zu niedrig überschwemmt den "
        "Expertenrat.",
        "quelle": "§ 5 Abs 12 · Anweisung des Gründers: „muss konkrete Kritik beinhalten“",
    },
    {
        "schluessel": "weicherfilter-regel",
        "wert": "2",
        "einheit": "Regelfassung",
        "gruppe": "weicherfilter",
        "beschreibung": "Fassung der Reihungsregel des WeicherFilters (v2): neun Regler, Punkte aus "
        "Regler mal Merkmal, Favoriten-zuerst als sichtbarer Schalter. Voreinstellung neutral.",
        "quelle": "§ 2 Abs 6 · § 5 Abs 10 lit d",
    },
    {
        "schluessel": "weicherfilter-profile-hoechstzahl",
        "wert": "5",
        "einheit": "Profile",
        "gruppe": "weicherfilter",
        "beschreibung": "Wie viele eigene Filterprofile ein Mitglied speichern kann.",
        "quelle": "§ 5 Abs 10 lit d",
    },
    {
        "schluessel": "faecher-regel",
        "wert": "2",
        "einheit": "Regelfassung",
        "gruppe": "faecher",
        "beschreibung": "Fassung des Layout-Algorithmus für den Lebensbereiche-Fächer (v2): "
        "überlappungsfreie Anordnung über alle Anker, Auffächern ab Ebene 5.",
        "quelle": "§ 2 Abs 6",
    },
    {
        "schluessel": "faecher-kinder-hoechstzahl",
        "wert": "3",
        "einheit": "Äste",
        "gruppe": "faecher",
        "beschreibung": "Wie viele Unteräste ein Ast im Fächer zeigt, bevor er aufgefächert werden muss.",
        "quelle": "§ 5 Abs 10 lit a",
    },
    {
        "schluessel": "kacheln-hervorgehoben",
        "wert": "3",
        "einheit": "Kacheln",
        "gruppe": "kacheln",
        "beschreibung": "Wie viele hervorgehobene Abstimmungen im Feld „Wichtige Abstimmungen“ stehen. "
        "Wer hervorhebt, entscheidet der Integritätsrat — wie viele Platz haben, dieser Wert.",
        "quelle": "§ 5 Abs 6",
    },
    {
        "schluessel": "kacheln-abgeschlossen",
        "wert": "20",
        "einheit": "Einträge",
        "gruppe": "kacheln",
        "beschreibung": "Wie viele abgeschlossene Verfahren im Feed erscheinen, bevor abgeschnitten wird.",
        "quelle": "§ 5 Abs 10 lit d",
    },
    {
        "schluessel": "suche-treffer-hoechstzahl",
        "wert": "24",
        "einheit": "Treffer",
        "gruppe": "faecher",
        "beschreibung": "Wie viele Treffer die Suche im Lebensbereiche-Fächer höchstens zeigt.",
        "quelle": "§ 5 Abs 10 lit a",
    },
    {
        "schluessel": "gespraeche-liste-hoechstzahl",
        "wert": "30",
        "einheit": "Gespräche",
        "gruppe": "kacheln",
        "beschreibung": "Wie viele Gespräche das Panel „Meine Gespräche“ auf einmal zeigt. Der Zähler "
        "am Griff zählt unabhängig davon alle.",
        "quelle": "§ 5 Abs 3 lit c",
    },
    {
        "schluessel": "archiv-audit-anzeige",
        "wert": "60",
        "einheit": "Ereignisse",
        "gruppe": "kacheln",
        "beschreibung": "Wie viele Audit-Ereignisse die Zeitleiste im Archiv zeigt. Der Export enthält "
        "immer alle — die Kürzung betrifft nur die Anzeige und wird dort benannt.",
        "quelle": "§ 5 Abs 3 lit e · § 5 Abs 8",
    },
    {
        "schluessel": "ki-antwort-hoechsttokens",
        "wert": "900",
        "einheit": "Tokens",
        "gruppe": "ki",
        "beschreibung": "Wie lang die Antwort eines Modell-Laufs höchstens sein darf. Begrenzt Kosten "
        "und hält Einschätzungen knapp.",
        "quelle": "§ 6 Abs 11 lit b",
    },
    {
        "schluessel": "anstoss-mindestabstand-sekunden",
        "wert": "60",
        "einheit": "Sekunden",
        "gruppe": "schutz",
        "beschreibung": "Wartezeit zwischen zwei Anstößen derselben Person — hält die Rückmeldung offen "
        "und den Kanal frei von Fluten.",
        "quelle": "§ 5 Abs 10 lit b",
    },
    {
        "schluessel": "anstoss-tagesgrenze",
        "wert": "20",
        "einheit": "Anstöße",
        "gruppe": "schutz",
        "beschreibung": "Wie viele Anstöße eine Person am Tag senden kann.",
        "quelle": "§ 5 Abs 10 lit b",
    },
    {
        "schluessel": "verfahren-unterstuetzung-schwelle",
        "wert": "3",
        "einheit": "Unterstützungen",
        "gruppe": "verfahren",
        "beschreibung": "Wie viele Unterstützungen ein Antrag braucht, um in die Beratung zu kommen. "
        "Gilt für neue Anträge; laufende behalten ihre eingefrorene Fassung.",
        "quelle": "§ 5 Abs 3 lit b",
    },
    {
        "schluessel": "verfahren-unterstuetzung-tage",
        "wert": "60",
        "einheit": "Tage",
        "gruppe": "verfahren",
        "beschreibung": "Frist, in der ein Antrag die Unterstützungsschwelle erreichen muss. "
        "Danach verfällt er und kann nach der Sperrfrist neu eingebracht werden.",
        "quelle": "§ 5 Abs 3 lit b · Anweisung des Gründers: „Fristen für Unterstützungsanträge auf 2 Monate“",
    },
    {
        "schluessel": "expertenrat-erstvorschlag-tage",
        "wert": "21",
        "einheit": "Tage",
        "gruppe": "gremien",
        "beschreibung": "Zeit des Expertenrats für den ersten Vorschlag, gerechnet ab Beratungsbeginn. "
        "Zugleich die Mindestdauer der Beratung — kürzer darf sie nach der Satzung nicht sein.",
        "quelle": "§ 5 Abs 3 lit c · Anweisung des Gründers: „hat 3 Wochen zeit um einen ersten Vorschlag auszuarbeiten“",
    },
    {
        "schluessel": "verfahren-abstimmung-tage",
        "wert": "28",
        "einheit": "Tage",
        "gruppe": "verfahren",
        "beschreibung": "Dauer der Endabstimmung. Die Satzung verlangt mindestens sieben Tage; "
        "vier Wochen geben auch jenen Zeit, die nicht täglich hereinschauen.",
        "quelle": "§ 5 Abs 3 lit d · Anweisung des Gründers: „hat die gesamte Bevölkerung dann 4 Wochen Zeit“",
    },
    {
        "schluessel": "verfahren-mindestbeteiligung-prozent",
        "wert": "5",
        "einheit": "Prozent",
        "gruppe": "verfahren",
        "beschreibung": "Anteil der Stimmberechtigten, der sich beteiligen muss, damit ein Ergebnis "
        "zustande kommt. Die Satzung setzt fünf Prozent als Untergrenze — darunter geht es nicht.",
        "quelle": "§ 5 Abs 4",
    },
    {
        "schluessel": "verfahren-wiedereinbringung-monate",
        "wert": "6",
        "einheit": "Monate",
        "gruppe": "verfahren",
        "beschreibung": "Sperrfrist, bevor ein abgelehnter oder verfallener Antrag im Wortlaut "
        "erneut eingebracht werden kann.",
        "quelle": "§ 5 Abs 3 lit b",
    },
    {
        "schluessel": "gremien-review-tage",
        "wert": "14",
        "einheit": "Tage",
        "gruppe": "gremien",
        "beschreibung": "Frist der Unterstützer in der Entwurfsschleife: Vorschlag annehmen oder mit "
        "konkretem Wunsch zurückgeben. Nach Ablauf wertet die Frist aus — Untätigkeit hemmt nie.",
        "quelle": "§ 5 Abs 12",
    },
    {
        "schluessel": "gremien-ueberarbeitung-tage",
        "wert": "14",
        "einheit": "Tage",
        "gruppe": "gremien",
        "beschreibung": "Überarbeitungsfrist des Expertenrats je Rückgabe-Runde. Verstreicht sie ohne "
        "neue Einreichung, geht die zuletzt vorgelegte Fassung zur Endabstimmung.",
        "quelle": "§ 5 Abs 12",
    },
    {
        "schluessel": "gremien-pruefung-tage",
        "wert": "7",
        "einheit": "Tage",
        "gruppe": "gremien",
        "beschreibung": "Frist der Gruppe 2 für ihre Prüfung eines Vorschlags mit Vollzugs- oder "
        "Beschaffungsbezug. Läuft sie ohne Ergebnis ab, geht der Vorschlag weiter an die "
        "Unterstützer — mit dem offengelegten Vermerk, dass Gruppe 2 ihn nicht validiert hat. "
        "Kurz genug, dass niemand blockieren kann; lang genug, um wirklich zu prüfen.",
        "quelle": "§ 6 Abs 7",
    },
    {
        "schluessel": "gremien-beschluss-tage",
        "wert": "7",
        "einheit": "Tage",
        "gruppe": "gremien",
        "beschreibung": "Regelfrist einer internen Abstimmung in einem Rat. Danach wird mit den "
        "vorliegenden Stimmen ausgewertet — beschlussfähig ab der Hälfte der aktiven Rollen, "
        "entschieden mit einfacher Mehrheit der abgegebenen Stimmen.",
        "quelle": "§ 6 Abs 2 lit e",
    },
    {
        "schluessel": "gremien-hoechstrunden",
        "wert": "3",
        "einheit": "Runden",
        "gruppe": "gremien",
        "beschreibung": "Höchstzahl der Runden der Entwurfsschleife; danach geht der Vorschlag in jedem "
        "Fall zur Endabstimmung.",
        "quelle": "§ 5 Abs 12 („Rundenzahl per Verfahrensordnung“)",
    },
    {
        "schluessel": "vorschlag-annahme-prozent",
        "wert": "50",
        "einheit": "Prozent",
        "gruppe": "gremien",
        "beschreibung": "Zustimmungsanteil, den der Beitrag „Passt alles“ im Abstimmungs-Chat "
        "überschreiten muss, damit der Vorschlag zur Endabstimmung geht — zusätzlich muss er an "
        "erster Stelle stehen.",
        "quelle": "§ 5 Abs 12 · Anweisung des Gründers: „mehr als 50%“",
    },
    {
        "schluessel": "vorschlag-chat-reihung",
        "wert": "1",
        "einheit": "Regelfassung",
        "gruppe": "gremien",
        "beschreibung": "Fassung der Reihungsregel des Abstimmungs-Chats (engagement-v1): "
        "Engagement = Zustimmungen + Ablehnungen absteigend, dann Zustimmungsanteil, dann Zeit. "
        "Offengelegt und nachrechenbar (§ 2 Abs 6).",
        "quelle": "Anweisung des Gründers: „die kommentare mit dem meisten engagement erscheinen ganz oben“",
    },
    {
        "schluessel": "gremien-rollen-dauer-tage",
        "wert": "730",
        "einheit": "Tage",
        "gruppe": "gremien",
        "beschreibung": "Regeldauer einer Gremien-Rolle (zwei Jahre): Bestellung auf öffentliche "
        "Ausschreibung, Bestätigung durch die Mitgliederversammlung, automatisches Erlöschen.",
        "quelle": "§ 6 Abs 8",
    },
    {
        "schluessel": "ki-monatstokens",
        "wert": "1000000",
        "einheit": "Tokens/Monat",
        "gruppe": "ki",
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
        # Schema-Kennung, Gruppe und Quelle sind **Beschreibung**, nicht Wert: Sie folgen dem
        # Erstbestand, damit eine Umbenennung im Schema oder eine neue Ordnung der Registerseite
        # nicht an bestehenden Einträgen vorbeigeht. Der Wert selbst bleibt unangetastet — er
        # gehört den Menschen, nicht dem Code.
        if not angelegt and parameter.schema_key != vorlage["schema_key"] and vorlage["schema_key"]:
            parameter.schema_key = vorlage["schema_key"]
            felder.append("schema_key")
        if not angelegt and vorlage.get("gruppe") and parameter.gruppe != vorlage["gruppe"]:
            parameter.gruppe = vorlage["gruppe"]
            felder.append("gruppe")
        # Interne Kennungen aus der Quelle nehmen (Entscheidung 4.9.2026): Sie verweisen auf
        # Dokumente, die Besuchern nichts sagen — teils auf nicht öffentliche. Der Wert bleibt
        # unangetastet, die Quelle ist Beschreibung.
        if not angelegt and any(k in (parameter.quelle or "") for k in INTERNE_KENNUNGEN):
            parameter.quelle = vorlage["quelle"]
            felder.append("quelle")
        if felder:
            parameter.save(update_fields=felder)
    return neu
