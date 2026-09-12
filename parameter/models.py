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

from django.conf import settings
from django.db import DatabaseError, models
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.translation import gettext_noop


class Gruppe(models.TextChoices):
    """Die Ordnung der Registerseite (FB-J2). Reihenfolge = Reihenfolge der Karten."""

    VERFAHREN = "verfahren", _("Verfahren")
    GREMIEN = "gremien", _("Gremien")
    WEICHERFILTER = "weicherfilter", _("WeicherFilter")
    FAECHER = "faecher", _("Fächer")
    KI = "ki", _("Zukunftswerkstatt")
    SCHUTZ = "schutz", _("Schutz")
    KACHELN = "kacheln", _("Kacheln")
    MANDATARE = "mandatare", _("Mandatare")


class Status(models.TextChoices):
    """Was mit einem Wert gerade geschieht (FB-J2, FB-J3).

    Ein Wert „im Test" wirkt sofort überall, wo die Stellgröße gelesen wird; Werte der
    Verfahrensordnung sind vom Test ausgenommen (D-J3g), laufende Verfahren bleiben so unberührt
    (§ 5 Abs 5). „Vorgeschlagen" heißt: Die Zukunftswerkstatt oder ein
    Mensch schlägt ihn vor, entschieden ist nichts."""

    GUELTIG = "gueltig", _("gültig")
    IM_TEST = "im_test", _("im Test")
    VORGESCHLAGEN = "vorgeschlagen", _("vorgeschlagen")


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
        help_text="Ein Wert „im Test“ gilt bei Werten der Verfahrensordnung nur für neu beginnende Verfahren (§ 5 Abs 5); alle anderen Stellgrößen wirken sofort.",
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


class TestStatus(models.TextChoices):
    """Wo ein Parametertest steht (FB-J3, § 6 Abs 11 lit c)."""

    GEPLANT = "geplant", "geplant — Beschluss steht aus"
    LAEUFT = "laeuft", "läuft"
    AUSGEWERTET = "ausgewertet", "ausgewertet"
    EINGEFUEHRT = "eingefuehrt", "eingeführt"
    VERWORFEN = "verworfen", "verworfen"


class ParameterTest(models.Model):
    """Ein befristeter, veröffentlichter, rückholbarer Test eines Registerwerts (§ 6 Abs 11 lit c).

    Die Satzung beschreibt den Weg genau: Der Koordinationsrat ordnet an, der Test läuft
    befristet, die Ergebnisse fließen in die Zukunftswerkstatt, und die **Einführung** braucht
    wieder seine Freigabe — mit Begründung im Register. Jeder dieser Schritte ist hier ein
    Feld, damit man später sieht, was wann geschah, und nicht nur, was am Ende galt.

    Der Test setzt den Wert im Register; das Register wirkt nur auf Verfahren, die neu
    beginnen (§ 5 Abs 5). Laufende Verfahren behalten ihre eingefrorene Ordnung — ein Test,
    der sie erreichte, wäre keiner, sondern ein Eingriff."""

    parameter = models.ForeignKey(Parameter, on_delete=models.CASCADE, related_name="tests")
    testwert = models.CharField(max_length=100)
    alter_wert = models.CharField(
        max_length=100, blank=True, help_text="Der Wert vor dem Test — der Rückweg führt hierher."
    )
    hypothese = models.CharField(max_length=300, help_text="Was der Test zeigen soll — steht öffentlich am Band.")
    messgroesse = models.CharField(
        max_length=80, help_text="Kennung aus /kennzahlen.json, an der der Erfolg gemessen wird."
    )
    beginn = models.DateField(null=True, blank=True)
    ende = models.DateField(help_text="Danach fällt der Wert von selbst zurück.")
    rueckweg = models.TextField(max_length=1000, help_text="Wie der alte Wert zurückkommt, wenn es schiefgeht.")
    status = models.CharField(max_length=16, choices=TestStatus.choices, default=TestStatus.GEPLANT)
    beschluss = models.ForeignKey(
        "gremien.GremienBeschluss", null=True, blank=True, on_delete=models.SET_NULL, related_name="parametertests"
    )
    einfuehrung_beschluss = models.ForeignKey(
        "gremien.GremienBeschluss", null=True, blank=True, on_delete=models.SET_NULL, related_name="einfuehrungen"
    )
    werte_vorher = models.JSONField(default=dict, blank=True, help_text="Kennzahlen-Schnappschuss zu Beginn.")
    werte_nachher = models.JSONField(default=dict, blank=True, help_text="Kennzahlen-Schnappschuss am Ende.")
    auswertung = models.TextField(max_length=4000, blank=True)
    ki_lauf = models.ForeignKey(
        "ki.KILauf", null=True, blank=True, on_delete=models.PROTECT, related_name="parametertests"
    )
    angeordnet_von = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    angelegt_am = models.DateTimeField(default=timezone.now)
    ausgewertet_am = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-angelegt_am"]
        verbose_name = "Parametertest"
        verbose_name_plural = "Parametertests"

    def __str__(self) -> str:
        return f"Test {self.parameter_id}: {self.testwert} bis {self.ende:%d.%m.%Y} ({self.get_status_display()})"

    def gegenueberstellung(self):
        """Die Messgröße vorher und nachher — Zahlen, kein Urteil (plattform_core.parametertest)."""
        from plattform_core.parametertest import gegenueberstellen

        return gegenueberstellen(self.werte_vorher or {}, self.werte_nachher or {}, self.messgroesse)


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
        "einheit": gettext_noop("Prozent"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Ab welcher Übereinstimmung die Plattform beim Einbringen auf einen bestehenden "
        "Antrag hinweist. Ein hoher Wert lässt fast alles durch, ein niedriger lenkt Menschen häufig zu "
        "fremden Anträgen — beides verschiebt, wo sich Unterstützung sammelt. Der Hinweis schlägt vor; "
        "einbringen kann man immer."),
        "quelle": "§ 5 Abs 10 lit d · Anweisung des Gründers: „zu prüfen ob ein anderer antrag mit "
        "ähnlichem inhalt bereits eingegangen ist“",
    },
    {
        "schluessel": "aehnlichkeit-treffer",
        "wert": "3",
        "einheit": gettext_noop("Anträge"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Wie viele ähnliche Anträge beim Einbringen höchstens gezeigt werden."),
        "quelle": "§ 5 Abs 10 lit d",
    },
    {
        "schluessel": "kategorien-je-antrag",
        "wert": "3",
        "einheit": gettext_noop("Lebensbereiche"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Wie vielen Lebensbereichen ein Antrag automatisch zugeordnet wird. Die "
        "Zuordnung entscheidet mit, in welchem Ast des Fächers er auftaucht und wen sein Abo erreicht."),
        "quelle": "§ 5 Abs 10 lit d",
    },
    {
        "schluessel": "kategorien-regel",
        "wert": "1",
        "einheit": gettext_noop("Regelfassung"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Fassung der Zuordnungsregel für Lebensbereiche (schlagworte-v1): Zuordnung "
        "über gepflegte Schlagwortlisten, keine KI. Offengelegt und nachrechenbar (§ 2 Abs 6)."),
        "quelle": "§ 2 Abs 6",
    },
    {
        "schluessel": "chat-zeichen-hoechstzahl",
        "wert": "4000",
        "einheit": gettext_noop("Zeichen"),
        "gruppe": "schutz",
        "beschreibung": gettext_noop("Wie lang ein Beitrag in der Beratung sein darf. Wer die Zahl senkt, zwingt zur "
        "Kürze; wer sie hebt, lässt Wände aus Text zu."),
        "quelle": "§ 5 Abs 3 lit c",
    },
    {
        "schluessel": "chat-bearbeitungsfenster-minuten",
        "wert": "5",
        "einheit": gettext_noop("Minuten"),
        "gruppe": "schutz",
        "beschreibung": gettext_noop("Wie lange ein eigener Beitrag noch geändert werden darf. Danach steht er — "
        "eine Abwägung zwischen dem Berichtigen von Tippfehlern und der Verlässlichkeit des Gesagten."),
        "quelle": "§ 5 Abs 3 lit e",
    },
    {
        "schluessel": "kritik-mindestzeichen",
        "wert": "80",
        "einheit": gettext_noop("Zeichen"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Wie lang eine Kritik am Vorschlag des Expertenrats mindestens sein muss, damit "
        "sie als Änderungswunsch zählt. Zu hoch schließt Knappe aus, zu niedrig überschwemmt den "
        "Expertenrat."),
        "quelle": "§ 5 Abs 12 · Anweisung des Gründers: „muss konkrete Kritik beinhalten“",
    },
    {
        "schluessel": "weicherfilter-regel",
        "wert": "2",
        "einheit": gettext_noop("Regelfassung"),
        "gruppe": "weicherfilter",
        "beschreibung": gettext_noop("Fassung der Reihungsregel des WeicherFilters (v2): neun Regler, Punkte aus "
        "Regler mal Merkmal, Favoriten-zuerst als sichtbarer Schalter. Voreinstellung neutral."),
        "quelle": "§ 2 Abs 6 · § 5 Abs 10 lit d",
    },
    {
        "schluessel": "weicherfilter-profile-hoechstzahl",
        "wert": "5",
        "einheit": gettext_noop("Profile"),
        "gruppe": "weicherfilter",
        "beschreibung": gettext_noop("Wie viele eigene Filterprofile ein Mitglied speichern kann."),
        "quelle": "§ 5 Abs 10 lit d",
    },
    {
        "schluessel": "faecher-regel",
        "wert": "2",
        "einheit": gettext_noop("Regelfassung"),
        "gruppe": "faecher",
        "beschreibung": gettext_noop("Fassung des Layout-Algorithmus für den Lebensbereiche-Fächer (v2): "
        "überlappungsfreie Anordnung über alle Anker, Auffächern ab Ebene 5."),
        "quelle": "§ 2 Abs 6",
    },
    {
        "schluessel": "faecher-kinder-hoechstzahl",
        "wert": "3",
        "einheit": gettext_noop("Äste"),
        "gruppe": "faecher",
        "beschreibung": gettext_noop("Wie viele Unteräste ein Ast im Fächer zeigt, bevor er aufgefächert werden muss."),
        "quelle": "§ 5 Abs 10 lit a",
    },
    {
        "schluessel": "kacheln-hervorgehoben",
        "wert": "3",
        "einheit": gettext_noop("Kacheln"),
        "gruppe": "kacheln",
        "beschreibung": gettext_noop("Wie viele hervorgehobene Abstimmungen im Feld „Wichtige Abstimmungen“ stehen. "
        "Wer hervorhebt, entscheidet der Integritätsrat — wie viele Platz haben, dieser Wert."),
        "quelle": "§ 5 Abs 6",
    },
    {
        "schluessel": "kacheln-abgeschlossen",
        "wert": "20",
        "einheit": gettext_noop("Einträge"),
        "gruppe": "kacheln",
        "beschreibung": gettext_noop("Wie viele abgeschlossene Verfahren im Feed erscheinen, bevor abgeschnitten wird."),
        "quelle": "§ 5 Abs 10 lit d",
    },
    {
        "schluessel": "uebersicht-abstimmungen",
        "wert": "20",
        "einheit": gettext_noop("Einträge"),
        "gruppe": "kacheln",
        "beschreibung": gettext_noop(
            "Wie viele entschiedene Abstimmungen die öffentliche Übersicht zeigt, bevor sie auf "
            "Umsetzungsregister und Parlament verweist. Laufende Abstimmungen erscheinen immer — nur mit "
            "Beteiligung, die Tendenz bleibt bis zum Fristende verdeckt."
        ),
        "quelle": "§ 5 Abs 10 lit d · § 5 Abs 3 lit e",
    },
    {
        "schluessel": "chat-faden-wurzeln",
        "wert": "50",
        "einheit": gettext_noop("Beiträge"),
        "gruppe": "kacheln",
        "beschreibung": gettext_noop(
            "Wie viele Wurzelbeiträge (mit ihren Antworten) der Chat eines Antrags auf einmal zeigt. "
            "Ältere Beiträge kommen auf Wunsch nach — gelöscht oder verborgen wird nichts; im "
            "Abstimmungs-Chat sind es die vordersten der offengelegten Reihung."
        ),
        "quelle": "§ 5 Abs 3 lit c",
    },
    {
        "schluessel": "gremien-beschluesse-seite",
        "wert": "50",
        "einheit": gettext_noop("Beschlüsse"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop(
            "Wie viele Beschlüsse die öffentliche Beschlussliste auf einmal zeigt. Jeder Beschluss "
            "bleibt unter seiner Nummer erreichbar."
        ),
        "quelle": "§ 6 Abs 9 (Anzeige)",
    },
    {
        "schluessel": "adresswechsel-wartefrist-stunden",
        "wert": "72",
        "einheit": gettext_noop("Stunden"),
        "gruppe": "schutz",
        "beschreibung": gettext_noop(
            "Wie lange eine verwaltungsseitige Änderung der Anmeldeadresse wartet, bevor sie wirksam "
            "wird. In dieser Zeit kann die bisherige Adresse widersprechen; zusätzlich braucht es einen "
            "zweiten Admin. Der Login läuft passwortlos über die Adresse — ohne Frist wäre eine Änderung "
            "eine Kontoübernahme."
        ),
        "quelle": "§ 4 Abs 2 · § 5 Abs 8 (Stimmgeheimnis)",
    },
    {
        "schluessel": "suche-treffer-hoechstzahl",
        "wert": "24",
        "einheit": gettext_noop("Treffer"),
        "gruppe": "faecher",
        "beschreibung": gettext_noop("Wie viele Treffer die Suche im Lebensbereiche-Fächer höchstens zeigt."),
        "quelle": "§ 5 Abs 10 lit a",
    },
    {
        "schluessel": "gespraeche-liste-hoechstzahl",
        "wert": "30",
        "einheit": gettext_noop("Gespräche"),
        "gruppe": "kacheln",
        "beschreibung": gettext_noop("Wie viele Gespräche das Panel „Meine Gespräche“ auf einmal zeigt. Der Zähler "
        "am Griff zählt unabhängig davon alle."),
        "quelle": "§ 5 Abs 3 lit c",
    },
    {
        "schluessel": "archiv-audit-anzeige",
        "wert": "60",
        "einheit": gettext_noop("Ereignisse"),
        "gruppe": "kacheln",
        "beschreibung": gettext_noop("Wie viele Audit-Ereignisse die Zeitleiste im Archiv zeigt. Der Export enthält "
        "immer alle — die Kürzung betrifft nur die Anzeige und wird dort benannt."),
        "quelle": "§ 5 Abs 3 lit e · § 5 Abs 8",
    },
    {
        "schluessel": "ki-antwort-hoechsttokens",
        "wert": "900",
        "einheit": gettext_noop("Tokens"),
        "gruppe": "ki",
        "beschreibung": gettext_noop("Wie lang die Antwort eines Modell-Laufs höchstens sein darf. Begrenzt Kosten "
        "und hält Einschätzungen knapp."),
        "quelle": "§ 6 Abs 11 lit b",
    },
    {
        "schluessel": "anstoss-mindestabstand-sekunden",
        "wert": "60",
        "einheit": gettext_noop("Sekunden"),
        "gruppe": "schutz",
        "beschreibung": gettext_noop("Wartezeit zwischen zwei Anstößen derselben Person — hält die Rückmeldung offen "
        "und den Kanal frei von Fluten."),
        "quelle": "§ 5 Abs 10 lit b",
    },
    {
        "schluessel": "anstoss-tagesgrenze",
        "wert": "20",
        "einheit": gettext_noop("Anstöße"),
        "gruppe": "schutz",
        "beschreibung": gettext_noop("Wie viele Anstöße eine Person am Tag senden kann."),
        "quelle": "§ 5 Abs 10 lit b",
    },
    {
        "schluessel": "verfahren-unterstuetzung-schwelle",
        "wert": "3",
        "einheit": gettext_noop("Unterstützungen"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Wie viele Unterstützungen ein Antrag braucht, um in die Beratung zu kommen. "
        "Gilt für neue Anträge; laufende behalten ihre eingefrorene Fassung."),
        "quelle": "§ 5 Abs 3 lit b",
    },
    {
        "schluessel": "verfahren-unterstuetzung-tage",
        "wert": "60",
        "einheit": gettext_noop("Tage"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Frist, in der ein Antrag die Unterstützungsschwelle erreichen muss. "
        "Danach verfällt er und kann nach der Sperrfrist neu eingebracht werden."),
        "quelle": "§ 5 Abs 3 lit b · Anweisung des Gründers: „Fristen für Unterstützungsanträge auf 2 Monate“",
    },
    {
        "schluessel": "expertenrat-erstvorschlag-tage",
        "wert": "21",
        "einheit": gettext_noop("Tage"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Zeit des Expertenrats für den ersten Vorschlag, gerechnet ab Beratungsbeginn. "
        "Zugleich die Mindestdauer der Beratung — kürzer darf sie nach der Satzung nicht sein."),
        "quelle": "§ 5 Abs 3 lit c · Anweisung des Gründers: „hat 3 Wochen zeit um einen ersten Vorschlag auszuarbeiten“",
    },
    {
        "schluessel": "verfahren-abstimmung-tage",
        "wert": "28",
        "einheit": gettext_noop("Tage"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Dauer der Endabstimmung. Die Satzung verlangt mindestens sieben Tage; "
        "vier Wochen geben auch jenen Zeit, die nicht täglich hereinschauen."),
        "quelle": "§ 5 Abs 3 lit d · Anweisung des Gründers: „hat die gesamte Bevölkerung dann 4 Wochen Zeit“",
    },
    {
        "schluessel": "verfahren-mindestbeteiligung-prozent",
        "wert": "5",
        "einheit": gettext_noop("Prozent"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Anteil der Stimmberechtigten, der sich beteiligen muss, damit ein Ergebnis "
        "zustande kommt. Die Satzung setzt fünf Prozent als Untergrenze — darunter geht es nicht."),
        "quelle": "§ 5 Abs 4",
    },
    {
        "schluessel": "verfahren-wiedereinbringung-monate",
        "wert": "6",
        "einheit": gettext_noop("Monate"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Sperrfrist, bevor ein abgelehnter oder verfallener Antrag im Wortlaut "
        "erneut eingebracht werden kann."),
        "quelle": "§ 5 Abs 3 lit b",
    },
    {
        "schluessel": "gremien-review-tage",
        "wert": "14",
        "einheit": gettext_noop("Tage"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Frist der Unterstützer in der Entwurfsschleife: Vorschlag annehmen oder mit "
        "konkretem Wunsch zurückgeben. Nach Ablauf wertet die Frist aus — Untätigkeit hemmt nie."),
        "quelle": "§ 5 Abs 12",
    },
    {
        "schluessel": "gremien-ueberarbeitung-tage",
        "wert": "14",
        "einheit": gettext_noop("Tage"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Überarbeitungsfrist des Expertenrats je Rückgabe-Runde. Verstreicht sie ohne "
        "neue Einreichung, geht die zuletzt vorgelegte Fassung zur Endabstimmung."),
        "quelle": "§ 5 Abs 12",
    },
    {
        "schluessel": "expertenrat-gruppe1-groesse",
        "wert": "3",
        "einheit": gettext_noop("Personen"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Größe der ersten Gruppe des Expertenrats, die je Antrag aus der "
        "Fachliste gelost wird. Die Satzung verlangt mindestens drei; nach oben ist der Wert "
        "offen — mehr Fachleute heißt mehr Blickwinkel und mehr Aufwand. Der Wert wird beim "
        "Einbringen an den Antrag geheftet und wirkt nie auf laufende Verfahren zurück."),
        "quelle": "§ 6 Abs 7 · § 6 Abs 8",
    },
    {
        "schluessel": "expertenrat-gruppe2-groesse",
        "wert": "3",
        "einheit": gettext_noop("Personen"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Größe der zweiten Gruppe, die Vorschläge mit Vollzugs- oder "
        "Beschaffungsbezug auf Interessenkonflikte und Korruptionsgefahr prüft. Sie wird aus "
        "dem Rest desselben Lostopfes gezogen und ist dadurch von der ersten getrennt."),
        "quelle": "§ 6 Abs 7 · § 6 Abs 8",
    },
    {
        "schluessel": "gremien-pruefung-tage",
        "wert": "7",
        "einheit": gettext_noop("Tage"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Frist der Gruppe 2 für ihre Prüfung eines Vorschlags mit Vollzugs- oder "
        "Beschaffungsbezug. Läuft sie ohne Ergebnis ab, geht der Vorschlag weiter an die "
        "Unterstützer — mit dem offengelegten Vermerk, dass Gruppe 2 ihn nicht validiert hat. "
        "Kurz genug, dass niemand blockieren kann; lang genug, um wirklich zu prüfen."),
        "quelle": "§ 6 Abs 7",
    },
    {
        "schluessel": "gremien-beschluss-tage",
        "wert": "7",
        "einheit": gettext_noop("Tage"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Regelfrist einer internen Abstimmung in einem Rat. Danach wird mit den "
        "vorliegenden Stimmen ausgewertet — beschlussfähig ab der Hälfte der aktiven Rollen, "
        "entschieden mit einfacher Mehrheit der abgegebenen Stimmen. Wirkt sofort auf neu angelegte Beschlüsse; kein Teil der Verfahrensordnung."),
        "quelle": "§ 6 Abs 2 lit e",
    },
    {
        "schluessel": "gremien-hoechstrunden",
        "wert": "3",
        "einheit": gettext_noop("Runden"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Höchstzahl der Runden der Entwurfsschleife; danach geht der Vorschlag in jedem "
        "Fall zur Endabstimmung."),
        "quelle": "§ 5 Abs 12 („Rundenzahl per Verfahrensordnung“)",
    },
    {
        "schluessel": "vorschlag-annahme-prozent",
        "wert": "50",
        "einheit": gettext_noop("Prozent"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Zustimmungsanteil, den der Beitrag „Passt alles“ im Abstimmungs-Chat "
        "überschreiten muss, damit der Vorschlag zur Endabstimmung geht — zusätzlich muss er an "
        "erster Stelle stehen."),
        "quelle": "§ 5 Abs 12 · Anweisung des Gründers: „mehr als 50%“",
    },
    {
        "schluessel": "vorschlag-chat-reihung",
        "wert": "1",
        "einheit": gettext_noop("Regelfassung"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Fassung der Reihungsregel des Abstimmungs-Chats (engagement-v1): "
        "Engagement = Zustimmungen + Ablehnungen absteigend, dann Zustimmungsanteil, dann Zeit. "
        "Offengelegt und nachrechenbar (§ 2 Abs 6)."),
        "quelle": "Anweisung des Gründers: „die kommentare mit dem meisten engagement erscheinen ganz oben“",
    },
    {
        "schluessel": "gremien-rollen-dauer-tage",
        "wert": "730",
        "einheit": gettext_noop("Tage"),
        "gruppe": "gremien",
        "beschreibung": gettext_noop("Regeldauer einer Gremien-Rolle (zwei Jahre): Bestellung auf öffentliche "
        "Ausschreibung, Bestätigung durch die Mitgliederversammlung, automatisches Erlöschen. Wirkt sofort auf neu berufene Rollen; kein Teil der Verfahrensordnung."),
        "quelle": "§ 6 Abs 8",
    },
    {
        "schluessel": "ki-monatstokens",
        "wert": "1000000",
        "einheit": gettext_noop("Tokens/Monat"),
        "gruppe": "ki",
        "beschreibung": gettext_noop("Hartes Monatsbudget des Modell-Steckplatzes. Ist es erschöpft, wird der "
        "Steckplatz stumm, bis der Monat wechselt — Kostendeckel der Zukunftswerkstatt."),
        "quelle": "Grundregel: Die KI schlägt vor, sie entscheidet nie",
    },
    {
        "schluessel": "mandatsfrage-abstimmung-tage",
        "wert": "7",
        "einheit": gettext_noop("Tage"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Dauer der Abstimmung über eine Mandatsfrage — die Ja-Nein-Frage, die ein "
        "Mandatar aus einem Instant-Report heraus ohne Unterstützungs- und Beratungsphase eröffnet. "
        "Nie unter sieben Tagen: Das ist das Satzungsminimum, kleinere Werte klemmt der Code darauf fest. "
        "Beim Eröffnen wird die Dauer in die Ordnung des Antrags eingefroren; laufende Mandatsfragen "
        "behalten ihre Dauer. Kein Ordnungsschlüssel der Verfahrensordnung, daher befristet testbar."),
        "quelle": "§ 7 Abs 9 · § 5 Abs 3 lit d",
    },
    {
        "schluessel": "mandatar-monatsbericht-frist-tage",
        "wert": "7",
        "einheit": gettext_noop("Tage"),
        "gruppe": "mandatare",
        "beschreibung": gettext_noop("Tag des Folgemonats, bis zu dem der Monatsbericht eines Mandatars als "
        "fristgerecht gilt. Die sieben Tage für Rechenschaft und Sammelbericht nach einem Sitzungstag "
        "stehen dagegen in der Satzung und sind hier nicht einstellbar. Wirkt sofort; kein Teil der "
        "Verfahrensordnung."),
        "quelle": "§ 7 Abs 3 lit b",
    },
    {
        "schluessel": "region-nebenwohnsitz-zaehlt",
        "wert": "0",
        "einheit": gettext_noop("0 oder 1"),
        "gruppe": "verfahren",
        "beschreibung": gettext_noop("Ob ein hinterlegter Nebenwohnsitz ein Mitglied zusätzlich der zweiten Region "
        "zuordnet — für die Anzeige regionaler Anträge und das Einbringen auf dieser Ebene. Am "
        "Stimmrecht ändert der Nebenwohnsitz nichts: Eine regionale Stimmberechtigung gibt es nicht "
        "(§ 5 Abs 6). Nur der Wert 1 schaltet ein; alles andere wirkt wie 0. Wirkt sofort."),
        "quelle": "§ 14 Abs 3 · § 5 Abs 6",
    },
]


def erstbestand_sicherstellen() -> int:
    """Fehlende Erstbestands-Einträge anlegen (bestehende Werte bleiben
    unangetastet — das Register gehört den Menschen, nicht dem Code). Die
    Schema-Kennung (FB-M5) wird nachgetragen, wenn sie fehlt — sie ist Bedeutung,
    kein Wert.

    Eine Abfrage für den ganzen Bestand, nicht eine je Eintrag: Die öffentliche
    Registerseite und /parameter.json rufen das bei jedem GET auf, und 36 einzelne
    `get_or_create` waren dort 36 SELECTs vor der ersten eigenen Zeile (Befund #78).
    Geschrieben wird nur, was fehlt oder abweicht."""
    from plattform_core.schema import schema_key

    vorhanden = Parameter.objects.in_bulk(
        [e["schluessel"] for e in ERSTBESTAND], field_name="schluessel"
    )
    neu = 0
    for eintrag in ERSTBESTAND:
        vorlage = {**eintrag, "schema_key": schema_key(eintrag["schluessel"])}
        parameter = vorhanden.get(eintrag["schluessel"])
        angelegt = parameter is None
        if angelegt:
            # get_or_create statt create: Zwei gleichzeitige erste Aufrufe dürfen sich nicht
            # gegenseitig mit einem Eindeutigkeitsfehler abbrechen.
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
