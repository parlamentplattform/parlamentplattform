"""Wer darf was: die Rollen der Partei und ihre Fähigkeiten auf der Plattform (FB-K6).

Diese Datei ist ein öffentlicher Soll/Ist-Abgleich in Datenform. Für jede Rolle steht hier, was
die Satzung ihr aufträgt und was die Software heute davon kann — Fähigkeit für Fähigkeit, mit
einem von drei Zeichen:

    ● verfügbar   — die Funktion existiert und ist erreichbar
    ◐ teilweise   — sie existiert, aber nicht so, wie die Satzung sie vorsieht
    ○ geplant     — sie existiert nicht; dann steht der Bauschritt dabei

Dass auch die ungebauten Zeilen erscheinen, ist der Kern der Sache. Eine Übersicht, die nur
Fertiges zeigt, verschweigt die halbe Satzung; eine, die Geplantes als vorhanden ausgibt, wäre
eine Werbefläche. Das Statuszeichen macht aus dem Mangel eine Auskunft.

Die Matrix steht hier und nicht als Text in einer Vorlage, weil sie sonst nach dem ersten neuen
Gremium falsch wäre, ohne dass es jemand merkt. Ein Test in `verfahren/test_rollen.py` hält sie
gegen die Rollen, die es im Code wirklich gibt.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field


def _(text: str) -> str:
    """No-op-Markierung für den Übersetzungskatalog (Befund #90).

    plattform_core bleibt Django-frei, also gibt es hier kein gettext. Die Markierung macht
    die Texte für makemessages, po_pruefen und tests/test_katalog.py sichtbar; übersetzt wird
    erst in der Vorlage — `{% translate rolle.name %}` schlägt den deutschen Text im Katalog
    nach und fällt auf ihn zurück, solange keine Übersetzung eingetragen ist."""
    return text


#: Fassung dieser Matrix. Sie steigt, wenn Rollen oder Fähigkeiten hinzukommen oder ihren
#: Status ändern — die Seite nennt sie, damit ein Ausdruck von heute morgen zuzuordnen ist.
VERSION = 2


class Stand(enum.StrEnum):
    """Wie weit die Plattform eine Fähigkeit trägt."""

    VERFUEGBAR = "verfuegbar"
    TEILWEISE = "teilweise"
    GEPLANT = "geplant"

    @property
    def zeichen(self) -> str:
        return {"verfuegbar": "●", "teilweise": "◐", "geplant": "○"}[self.value]

    @property
    def name_de(self) -> str:
        return {"verfuegbar": _("verfügbar"), "teilweise": _("teilweise"), "geplant": _("geplant")}[
            self.value
        ]


@dataclass(frozen=True)
class Faehigkeit:
    """Eine Tätigkeit, die eine Rolle auf der Plattform ausüben kann — oder können soll."""

    titel: str
    stand: Stand
    satzung: str = ""
    #: Django-URL-Name, wenn die Fähigkeit eine eigene, aufrufbare Seite hat.
    urlname: str = ""
    #: Wo die Fähigkeit sonst sitzt — für alles, was an einem einzelnen Antrag, Entwurf oder
    #: Beschluss hängt und deshalb keine allgemeine Adresse haben kann („auf jeder Antragsseite“).
    ort: str = ""
    #: Bei `TEILWEISE`: was gegenüber der Satzung fehlt. Bei `GEPLANT` leer.
    einschraenkung: str = ""
    #: Bei `GEPLANT`: der Bauschritt, mit dem sie kommt ("S10").
    bauschritt: str = ""

    def __post_init__(self) -> None:
        if self.stand is Stand.GEPLANT and self.urlname:
            raise ValueError(f"„{self.titel}“ ist geplant und hätte trotzdem eine Adresse.")
        if self.stand is Stand.VERFUEGBAR and self.einschraenkung:
            raise ValueError(f"„{self.titel}“ ist verfügbar und trägt trotzdem eine Einschränkung.")


@dataclass(frozen=True)
class Rolle:
    """Eine Rolle der Partei — aus der Satzung, nicht aus der Software gedacht."""

    schluessel: str
    name: str
    satzung: str
    #: Ein Satz, was die Rolle in der Partei ist. Aus der Satzung, nicht ausgedacht.
    was_sie_ist: str
    #: Wie man in die Rolle kommt — und, wo es abweicht, wie es heute zugeht.
    wie_hinein: str
    faehigkeiten: tuple[Faehigkeit, ...] = ()
    #: Gibt es diese Rolle heute überhaupt im Code? Steuert kein Verhalten, nur die Anzeige.
    im_code: bool = True
    #: Auf der Willkommensseite erscheinen nur die Rollen, die fast jeden betreffen.
    auf_der_startseite: bool = False
    hinweis: str = ""

    @property
    def gebaut(self) -> int:
        return sum(1 for f in self.faehigkeiten if f.stand is Stand.VERFUEGBAR)

    @property
    def offen(self) -> int:
        return sum(1 for f in self.faehigkeiten if f.stand is Stand.GEPLANT)


@dataclass(frozen=True)
class Gruppe:
    """Die Ordnung der Seite: Zugang · Räte der Satzung · Ämter und Außenbeziehungen."""

    schluessel: str
    name: str
    erklaerung: str
    rollen: tuple[Rolle, ...] = field(default_factory=tuple)



# ── Gast und Mitglied ─────────────────────────────────────────────────────
GAST = Rolle(
    schluessel="gast",
    name=_("Gast"),
    satzung="§ 3 Abs 1 lit c, § 5 Abs 8",
    was_sie_ist=_("Keine Rolle der Satzung, sondern deren Folge: Die Verfahren der ParlamentPlattform sind öffentlich, protokolliert und nachprüfbar; Ergebnisse werden vollständig veröffentlicht (§ 3 Abs 1 lit c)."),
    wie_hinein=_("Die Seite aufrufen. Kein Konto, keine Anmeldung, keine Cookies außer Session und CSRF."),
    auf_der_startseite=True,
    faehigkeiten=(
        Faehigkeit(
            titel=_("Das Parlament ansehen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:parlament",
        ),
        Faehigkeit(
            titel=_("Einen Antrag im Wortlaut lesen — mit den eingefrorenen Regeln, der Beratung und dem Ergebnis"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("Die Fächer der Lebensbereiche durchsuchen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:parlament",
        ),
        Faehigkeit(
            titel=_("Das Archiv eines Antrags herunterladen (JSON, Markdown)"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("Ein Abstimmungsergebnis nachrechnen — Stimmen-Export nach Ende der Abstimmung"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("Das Umsetzungsregister ansehen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:umsetzung",
        ),
        Faehigkeit(
            titel=_("Die Mandatare mit Aufgaben und Fristen ansehen"),
            stand=Stand.VERFUEGBAR,
            urlname="mandatare:liste",
        ),
        Faehigkeit(
            titel=_("Das Parameterregister und die geltende Verfahrensordnung lesen"),
            stand=Stand.VERFUEGBAR,
            urlname="parameter:liste",
        ),
        Faehigkeit(
            titel=_("Die Beschlüsse der Räte lesen, jeden unter seiner Nummer"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:beschluesse",
        ),
        Faehigkeit(
            titel=_("Die Besetzung aller Gremien einsehen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:uebersicht",
        ),
        Faehigkeit(
            titel=_("Parameter und Kennzahlen maschinenlesbar beziehen"),
            stand=Stand.VERFUEGBAR,
            urlname="parameter:export",
        ),
        Faehigkeit(
            titel=_("Die Zukunftswerkstatt und die Rechenschaft des Modell-Steckplatzes lesen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:zukunftswerkstatt",
        ),
        Faehigkeit(
            titel=_("Die Partner-Seiten lesen und das Übertragungspaket laden"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:partner",
        ),
        Faehigkeit(
            titel=_("Die Zahlen der Plattform einsehen"),
            stand=Stand.VERFUEGBAR,
            urlname="uebersicht:index",
        ),
        Faehigkeit(
            titel=_("Einen Anstoß zur Plattform senden"),
            stand=Stand.VERFUEGBAR,
            urlname="anstoss:senden",
        ),
        Faehigkeit(
            titel=_("Mitglied werden"),
            stand=Stand.VERFUEGBAR,
            urlname="mitglieder:registrieren",
        ),
        Faehigkeit(
            titel=_("Als Partnerpartei über die Plattform Kontakt aufnehmen"),
            stand=Stand.TEILWEISE,
            urlname="verfahren:partner",
            einschraenkung=_("Nur ein mailto-Link, kein Formular und kein Partner-Konto; beides kommt mit S14b."),
        ),
        Faehigkeit(
            titel=_("Diese Übersicht lesen: was jede Rolle darf und was davon schon gebaut ist"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:rollen",
        ),
        Faehigkeit(
            titel=_("Die Willkommensseite lesen — wie das Verfahren vom Antrag zum Beschluss läuft"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:index",
        ),
        Faehigkeit(
            titel=_("Alle automatisierten Regeln nachlesen — mit Fassung, Datum und Begründung"),
            stand=Stand.VERFUEGBAR,
            urlname="parameter:regeln",
        ),
        Faehigkeit(
            titel=_("Die öffentliche Fachliste einsehen — Lostopf des Expertenrats"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:fachliste",
        ),
    ),
)

MITGLIED = Rolle(
    schluessel="mitglied",
    name=_("Mitglied (bestätigt, aktiv)"),
    satzung="§ 4 Abs 2 bis 4, § 5",
    was_sie_ist=_("Mitglieder haben das Recht auf Einbringung, Unterstützung und Erörterung von Anträgen, auf Einsicht in alle zu veröffentlichenden Unterlagen und — nach Anwartschaft — auf Stimm- und Wahlrecht (§ 4 Abs 2)."),
    wie_hinein=_("Laut Satzung: Anmeldung, Identitätsnachweis nach § 2 Abs 4, Bekenntnis zu § 3, Aufnahme durch den Koordinationsrat binnen vier Wochen. Heute: Registrierung, E-Mail-Bestätigung, und der verbuchte Mitgliedsbeitrag schaltet die Mitwirkung frei."),
    auf_der_startseite=True,
    faehigkeiten=(
        Faehigkeit(
            titel=_("Einen Antrag einbringen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:einbringen",
        ),
        Faehigkeit(
            titel=_("Einen Antrag unterstützen und die Unterstützung zurückziehen"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("In der Beratung mitreden"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("Auf Beiträge reagieren — im Abstimmungs-Chat als Unterstützer über den Vorschlag entscheiden"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("Über einen Antrag abstimmen"),
            stand=Stand.TEILWEISE,
            ort=_("auf jeder Antragsseite"),
            einschraenkung=_("Die Anwartschaft von drei Monaten (§ 4 Abs 4 lit b) wird nicht geprüft: Die Übergangsregel steht standardmäßig auf 1 und gilt für jede Abstimmung, während § 4 Abs 4 lit d sie nur für die erste Bestellung der Organe und die erste Verfahrensordnung vorsieht."),
        ),
        Faehigkeit(
            titel=_("Die eigene Stimme im Stimmregister prüfen (Pseudonym und Prüfcode)"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("Ein Thema als Favorit merken"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:parlament",
        ),
        Faehigkeit(
            titel=_("Einen Lebensbereich abonnieren"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:parlament",
        ),
        Faehigkeit(
            titel=_("Die eigene Reihung mit dem WeicherFilter einstellen, speichern und benennen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:parlament",
        ),
        Faehigkeit(
            titel=_("Die eigenen Gespräche verfolgen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:gespraeche",
        ),
        Faehigkeit(
            titel=_("Eine Einschätzung der Zukunftswerkstatt beanstanden"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("Einen Beitrag melden"),
            stand=Stand.TEILWEISE,
            ort=_("auf jeder Antragsseite"),
            einschraenkung=(
                _("Gemeldet werden kann, abgeholfen wird nicht: Die Meldung wird gespeichert, aber von keiner Ansicht gelesen — es gibt keinen Weg, sie zu bearbeiten.")
            ),
        ),
        Faehigkeit(
            titel=_("Für ein Mandat kandidieren und Bewerbungen zustimmen"),
            stand=Stand.TEILWEISE,
            ort=_("auf jeder Antragsseite"),
            einschraenkung=_("Dieselbe Übergangsregel: Die Zwölf-Monats-Anwartschaft für Personenwahlen (§ 4 Abs 4 lit b) wird derzeit nicht geprüft."),
        ),
        Faehigkeit(
            titel=_("Den eigenen Beitragsstand sehen und den Beitrag zahlen"),
            stand=Stand.VERFUEGBAR,
            urlname="mitglieder:beitrag",
        ),
        Faehigkeit(
            titel=_("Unter einem beständigen Pseudonym auftreten"),
            stand=Stand.TEILWEISE,
            ort=_("auf jeder Antragsseite"),
            einschraenkung=_("Ohne gesetztes Pseudonym zeigt die Antragsseite den Klarnamen — die Satzung verlangt dafür ausdrückliche Einwilligung. Das Pseudonym setzt heute nur die Verwaltung, nicht das Mitglied."),
        ),
        Faehigkeit(
            titel=_("Das eigene Profil verwalten — Wohnsitz, Benachrichtigungen, Datenexport, Löschung"),
            stand=Stand.GEPLANT,
            bauschritt=_("S10"),
        ),
        Faehigkeit(
            titel=_("Mandatsträger bewerten und ein Abberufungsverfahren einleiten"),
            stand=Stand.GEPLANT,
            bauschritt=_("offen — Teil C weist dafür keinen Bauschritt aus"),
        ),
        Faehigkeit(
            titel=_("Schriftlich oder in Präsenz abstimmen"),
            stand=Stand.GEPLANT,
            bauschritt=_("offen — Teil C weist dafür keinen Bauschritt aus"),
        ),
        Faehigkeit(
            titel=_("Die Bestellung der Räte bestätigen und ihre Mitglieder abberufen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S9"),
        ),
    ),
)

MITGLIED_RUHT = Rolle(
    schluessel="mitglied_ruht",
    name=_("Mitglied in Aufnahme oder pausiert"),
    satzung="§ 4 Abs 1, § 4 Abs 3, § 4 Abs 4 lit b",
    was_sie_ist=_("Über die Aufnahme entscheidet der Koordinationsrat binnen vier Wochen; Antrags-, Unterstützungs-, Rede- und Einsichtsrechte bestehen ab dem Tag der Aufnahme uneingeschränkt (§ 4 Abs 1, Abs 4 lit b)."),
    wie_hinein=_("Nach Registrierung und E-Mail-Bestätigung, bis der Mitgliedsbeitrag verbucht ist — oder wenn die Verwaltung ein Konto mit begründetem, auditiertem Beschluss pausiert."),
    hinweis=(
        _("Ein dritter Zustand: Wer ausgeschlossen ist (§ 4 Abs 5), ist nicht pausiert, sondern "
        "nicht mehr Mitglied — das ist keine Rolle, sondern ihr Ende. Das Konto bleibt stumm, "
        "die Beiträge zu laufenden Verfahren bleiben stehen — gelöscht wird nichts, was ein "
        "Verfahren betrifft.")
    ),
    auf_der_startseite=True,
    faehigkeiten=(
        Faehigkeit(
            titel=_("Alles lesen wie ohne Konto — Parlament, Anträge, Beschlüsse, Register"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:parlament",
        ),
        Faehigkeit(
            titel=_("Sich anmelden und angemeldet bleiben"),
            stand=Stand.VERFUEGBAR,
            urlname="mitglieder:login",
        ),
        Faehigkeit(
            titel=_("Den eigenen Beitragsstand sehen und den Beitrag zahlen"),
            stand=Stand.VERFUEGBAR,
            urlname="mitglieder:beitrag",
        ),
        Faehigkeit(
            titel=_("Erfahren, warum die Mitwirkung ruht und was sie wiederherstellt"),
            stand=Stand.VERFUEGBAR,
            ort=_("beim Versuch, einen Antrag einzubringen oder abzustimmen"),
        ),
        Faehigkeit(
            titel=_("Favoriten setzen und Lebensbereiche abonnieren"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:parlament",
        ),
        Faehigkeit(
            titel=_("Eine Einschätzung beanstanden und Beiträge melden"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("Antrag einbringen, unterstützen, mitreden, abstimmen"),
            stand=Stand.TEILWEISE,
            einschraenkung=_("Gesperrt, solange die Identitätsstufe ungeprüft oder der Status nicht aktiv ist. Die Satzung 2.5 kennt kein Ruhen dieser Rechte: § 4 Abs 4 lit b gewährt sie ab dem Tag der Aufnahme uneingeschränkt, § 4 Abs 3 schließt jede Wirkung des Beitrags auf Rechte aus."),
        ),
        Faehigkeit(
            titel=_("Aufgenommen werden — Entscheidung des Koordinationsrats binnen vier Wochen"),
            stand=Stand.GEPLANT,
            bauschritt=_("offen"),
        ),
        Faehigkeit(
            titel=_("Die Identität nachweisen — elektronisch (ID Austria) oder an einer Präsenzstelle"),
            stand=Stand.GEPLANT,
            bauschritt=_("offen — Teil C weist dafür keinen Bauschritt aus"),
        ),
        Faehigkeit(
            titel=_("Eine Ablehnung der Aufnahme beim Parteischiedsgericht bekämpfen"),
            stand=Stand.GEPLANT,
            bauschritt=_("offen — Teil C weist dafür keinen Bauschritt aus"),
        ),
    ),
)

# ── Expertenrat Gruppe 1 und Gruppe 2 ─────────────────────────────────────
EXPERTENRAT1 = Rolle(
    schluessel="expertenrat1",
    name=_("Expertenrat — Gruppe 1 (Entwurf)"),
    satzung="§ 6 Abs 7",
    was_sie_ist=_("Fachleute, die zur Beratung eines einzelnen Antrags herangezogen werden und in der ersten Gruppe den Vorschlag erarbeiten; der Expertenrat berät, er entscheidet nicht."),
    wie_hinein=(
        _("Zweistufig (Entscheidung des Gründers vom 5.9.2026): Auf die öffentlich geführte Fachliste "
        "beruft der Koordinationsrat nach öffentlicher Ausschreibung für zwei Jahre, bestätigt durch die "
        "Mitgliederversammlung (§ 6 Abs 8); für den einzelnen Antrag werden die Fachleute daraus nach "
        "einem offengelegten Zufallsverfahren gezogen (§ 6 Abs 7). Heute: Die Fachliste führt die "
        "Verwaltung, ausgelost wird je Antrag zu Beginn der Beratung — Anker ist der Kopf der "
        "Audit-Kette, jede Ziehung ist nachrechenbar. Die Berufung durch den Koordinationsrat und "
        "die Bestätigung durch die Mitgliederversammlung fehlen noch.")
    ),
    faehigkeiten=(
        Faehigkeit(
            titel=_("Anträge in der Beratung im eigenen Arbeitsbereich sehen"),
            stand=Stand.VERFUEGBAR,
            ort=_("im Entwurfsfenster eines Antrags"),
        ),
        Faehigkeit(
            titel=_("Entwurfsfenster zu einem Antrag öffnen — der Antragswortlaut wird Fassung 1"),
            stand=Stand.VERFUEGBAR,
            ort=_("im Entwurfsfenster eines Antrags"),
        ),
        Faehigkeit(
            titel=_("Fassungen anhängen; jede frueher geschriebene bleibt stehen"),
            stand=Stand.VERFUEGBAR,
            ort=_("im Entwurfsfenster eines Antrags"),
        ),
        Faehigkeit(
            titel=_("Wünsche der Unterstützer aus der Vorrunde lesen"),
            stand=Stand.VERFUEGBAR,
            ort=_("im Entwurfsfenster eines Antrags"),
        ),
        Faehigkeit(
            titel=_("Frist für den Erstvorschlag im Fenster sehen"),
            stand=Stand.VERFUEGBAR,
            ort=_("im Entwurfsfenster eines Antrags"),
        ),
        Faehigkeit(
            titel=_("Intern beraten — Beiträge werden festgehalten"),
            stand=Stand.TEILWEISE,
            ort=_("im Entwurfsfenster eines Antrags"),
            einschraenkung=_("Die Beiträge stehen nur im Arbeitsbereich der Gruppe; § 6 Abs 9 verlangt veröffentlichte Sitzungsprotokolle."),
        ),
        Faehigkeit(
            titel=_("KI-Einschätzung zum eigenen Entwurf anfordern"),
            stand=Stand.TEILWEISE,
            ort=_("im Entwurfsfenster eines Antrags"),
            einschraenkung=_("Der Modell-Steckplatz antwortet nur, wenn ein Anbieter angeschlossen und das Monats-Tokenbudget nicht erschoepft ist; sonst bleibt er stumm."),
        ),
        Faehigkeit(
            titel=_("Vollzugs- oder Beschaffungsbezug setzen — dann wird Gruppe 2 aus der Fachliste nachgelost und prüft vorab (§ 6 Abs 7)"),
            stand=Stand.VERFUEGBAR,
            ort=_("im Entwurfsfenster eines Antrags"),
        ),
        Faehigkeit(
            titel=_("Über die Einreichung intern abstimmen"),
            stand=Stand.TEILWEISE,
            ort=_("im Entwurfsfenster eines Antrags"),
            einschraenkung=_("Eigene Abstimmung ausserhalb der öffentlichen Beschlussliste: ohne Beschlussnummer, ohne Begruendung, ohne Frist; nur im Arbeitsbereich sichtbar (§ 6 Abs 9)."),
        ),
        Faehigkeit(
            titel=_("Vorschlag einreichen — an Gruppe 2 oder an die Unterstützer"),
            stand=Stand.VERFUEGBAR,
            ort=_("im Entwurfsfenster eines Antrags"),
        ),
        Faehigkeit(
            titel=_("Zurückgegebenen Vorschlag in einer neuen Runde überarbeiten"),
            stand=Stand.VERFUEGBAR,
            ort=_("im Entwurfsfenster eines Antrags"),
        ),
        Faehigkeit(
            titel=_("Der eingereichte Vorschlag steht mit Wortlaut und Wort-Diff öffentlich am Antrag"),
            stand=Stand.TEILWEISE,
            ort=_("im Entwurfsfenster eines Antrags"),
            einschraenkung=(
                _("Nur, solange der Vorschlag den Unterstützern vorliegt. Während der Prüfung durch Gruppe 2 ist er öffentlich nicht zu sehen.")
            ),
        ),
        Faehigkeit(
            titel=_("Die eigene Berufung steht mit Namen und Enddatum öffentlich"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:uebersicht",
        ),
        Faehigkeit(
            titel=_("Interessenbindungen und Honorare zum Antrag offenlegen"),
            stand=Stand.VERFUEGBAR,
            ort=_("im Entwurfsfenster, bei der Stimme über die Einreichung"),
        ),
        Faehigkeit(
            titel=_("Fassungen im Arbeitsplatz vergleichen (Diff) und Absätze kommentieren"),
            stand=Stand.GEPLANT,
            bauschritt=_("S9"),
        ),
        Faehigkeit(
            titel=_("Sich untereinander über andere Fragen abstimmen (Beschluss anlegen)"),
            stand=Stand.GEPLANT,
            bauschritt=_("S9"),
        ),
        Faehigkeit(
            titel=_("Für einen einzelnen Antrag aus der Fachliste ausgelost werden"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:fachliste",
        ),
        Faehigkeit(
            titel=_("Die Einschätzung der Zukunftswerkstatt als Arbeitsunterlage im Fenster nutzen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S11"),
        ),
    ),
)

EXPERTENRAT2 = Rolle(
    schluessel="expertenrat2",
    name=_("Expertenrat — Gruppe 2 (Prüfung)"),
    satzung="§ 6 Abs 7",
    was_sie_ist=_("Die zweite, unabhängig von der ersten besetzte Gruppe des Expertenrats; sie prüft deren Vorschlag auf Interessenkonflikte und Korruptionsgefahr."),
    wie_hinein=(
        _("Wie Gruppe 1 — mit dem Unterschied, dass beide Gruppen unabhängig voneinander besetzt sein "
        "müssen (§ 6 Abs 7): Wer den Vorschlag erarbeitet hat, prüft ihn nicht. Heute wird Gruppe 2 "
        "aus derselben Fachliste mitgelost, wenn der Vollzugsbezug zur Zeit einer Ziehung schon gesetzt "
        "ist — aus dem Rest des Lostopfs, sodass niemand in beiden Gruppen sitzt; sonst trägt die "
        "Verwaltung die Rolle ein. Die Fachliste selbst führt die Verwaltung.")
    ),
    faehigkeiten=(
        Faehigkeit(
            titel=_("Zur Prüfung vorgelegte Vorschläge mit Wortlaut sehen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:pruefung",
        ),
        Faehigkeit(
            titel=_("Über die Prüfung als Gremium abstimmen — mit Frist und Quorum"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:pruefung",
        ),
        Faehigkeit(
            titel=_("Vorschlag validieren"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:pruefung",
        ),
        Faehigkeit(
            titel=_("Vorschlag mit veröffentlichter Begruendung zurückgeben"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:pruefung",
        ),
        Faehigkeit(
            titel=_("Jede Stimme steht mit Namen und Begruendung öffentlich"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:beschluesse",
        ),
        Faehigkeit(
            titel=_("Prüfpunkte abhaken — sie wandern in die veröffentlichte Begründung"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:pruefung",
        ),
        Faehigkeit(
            titel=_("Beim Koordinationsrat den Austausch von Mitgliedern der Gruppe 1 beantragen"),
            stand=Stand.TEILWEISE,
            urlname="gremien:pruefung",
            einschraenkung=_("Der Antrag benennt keine einzelnen Personen; gibt der Koordinationsrat durch Beschluss statt, enden die für diesen Antrag gelosten Rollen der Gruppe 1, und es wird neu gelost."),
        ),
        Faehigkeit(
            titel=_("Die interne Beratung der Gruppe 1 einsehen"),
            stand=Stand.GEPLANT,
            bauschritt=_("offen"),
        ),
        Faehigkeit(
            titel=_("Interessenbindungen und Honorare der eigenen Mitglieder offenlegen"),
            stand=Stand.TEILWEISE,
            urlname="gremien:fachliste",
            einschraenkung=(
                _("Auf der Fachliste stehen sie allgemein; zum einzelnen Antrag legt Gruppe 1 sie bei der Einreichung offen — Gruppe 2 selbst wird beim Prüfen nicht danach gefragt.")
            ),
        ),
        Faehigkeit(
            titel=_("Sich untereinander über andere Fragen abstimmen (Beschluss anlegen)"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:pruefung",
        ),
        Faehigkeit(
            titel=_("Vergabe-Schwellenwerte und mögliche Bieter als Arbeitsunterlage nutzen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S12"),
        ),
    ),
)

# ── Koordinationsrat und Integritaetsrat ──────────────────────────────────
KOORDINATIONSRAT = Rolle(
    schluessel="koordinationsrat",
    name=_("Koordinationsrat"),
    satzung="§ 6 Abs 2",
    was_sie_ist=_("Er besteht aus fünf bis neun Mitgliedern und führt die laufenden Geschäfte, vertritt die Partei nach § 1 Abs 4, vollzieht die Beschlüsse der Mitgliederversammlung und ist ihr rechenschaftspflichtig."),
    wie_hinein=(
        _("Wahl durch die Mitgliederversammlung auf vier Jahre; in jedem Jahr ohne reguläre Wahl eine "
        "Bestätigungsabstimmung über den Rat als Ganzes; Abberufung einzelner Mitglieder auf Antrag von "
        "fünf Prozent der stimmberechtigten Mitglieder (§ 6 Abs 2 lit a bis c). Heute trägt die "
        "Verwaltung die Rolle ein, und die Bestätigung ist ein Häkchen statt einer Abstimmung.")
    ),
    faehigkeiten=(
        Faehigkeit(
            titel=_("Den Arbeitsbereich des Koordinationsrats öffnen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:koordination",
        ),
        Faehigkeit(
            titel=_("Über den Austauschantrag der Gruppe 2 durch Beschluss entscheiden"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:koordination",
        ),
        Faehigkeit(
            titel=_("In einem internen Beschluss des Rates abstimmen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:koordination",
        ),
        Faehigkeit(
            titel=_("Einen internen Beschluss anlegen und nach der Entscheidung den Umsetzungsvermerk schreiben"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:koordination",
        ),
        Faehigkeit(
            titel=_("Beschlüsse mit Nummer, Stimmen und Begründungen öffentlich nachweisen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:beschluesse",
        ),
        Faehigkeit(
            titel=_("Die Besetzung aller Räte einsehen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:uebersicht",
        ),
        Faehigkeit(
            titel=_("Mitglieder der Räte auf öffentliche Ausschreibung bestellen und abberufen"),
            stand=Stand.GEPLANT,
            bauschritt=_("offen"),
        ),
        Faehigkeit(
            titel=_("Das Parameterregister mit Wert, Begründung und Änderungsgeschichte einsehen"),
            stand=Stand.VERFUEGBAR,
            urlname="parameter:liste",
        ),
        Faehigkeit(
            titel=_("Befristete Tests neuer Registerwerte durch Beschluss anordnen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:koordination",
        ),
        Faehigkeit(
            titel=_("Die Einführung eines getesteten Registerwertes durch Beschluss freigeben"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:koordination",
        ),
        Faehigkeit(
            titel=_("Den Posteingang der Zukunftswerkstatt sichten"),
            stand=Stand.TEILWEISE,
            urlname="gremien:koordination",
            einschraenkung=_("Der Posteingang steht; heute speist ihn nur die Auswertung von Parametertests. Kandidaten für Hervorhebung und Muster-Berichte kommen erst mit der Zukunftswerkstatt."),
        ),
        Faehigkeit(
            titel=_("Überlastungsmeldungen veröffentlichen und binnen 30 Tagen einen Vorschlag an die Mitgliederversammlung vorlegen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:koordination",
        ),
        Faehigkeit(
            titel=_("Das öffentliche Umsetzungsregister einsehen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:umsetzung",
        ),
        Faehigkeit(
            titel=_("Die Hervorhebung eines Antrags beim Integritätsrat durch Beschluss beantragen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:koordination",
        ),
        Faehigkeit(
            titel=_("Parameter-Schema und Kennzahlen mit Partnersystemen austauschen"),
            stand=Stand.TEILWEISE,
            urlname="parameter:export",
            einschraenkung=_("Die Ausgabe steht offen für jeden — sprachneutrales Schema 1.0, aggregiert, ohne Personenbezug. Das Einlesen fremder Register, die Gegenüberstellung und ein Partner-Bereich im Koordinationsrat fehlen."),
        ),
        Faehigkeit(
            titel=_("Aufsicht über Faktenbasis, Parameterregister und Berichte der Zukunftswerkstatt"),
            stand=Stand.TEILWEISE,
            urlname="verfahren:zukunftswerkstatt",
            einschraenkung=_("Öffentlich einsehbar sind der Stand des Modell-Steckplatzes, das Budget und die letzten Läufe; eine Faktenbasis und die Berichte fehlen."),
        ),
    ),
)

INTEGRITAETSRAT = Rolle(
    schluessel="integritaetsrat",
    name=_("Integritätsrat"),
    satzung="§ 6 Abs 3",
    was_sie_ist=_("Das Aufsichtsorgan der Partei; er überwacht die Einhaltung der Satzung und der Verfahrensordnung, die Integrität von ParlamentPlattform und Zukunftswerkstatt und die Anwendung des § 5 Abs 6."),
    wie_hinein=(
        _("Wahl durch die Mitgliederversammlung auf vier Jahre, drei bis sieben Mitglieder. Sie dürfen "
        "keinem anderen Rat angehören, kein Mandat für die DDÖ ausüben und in keinem Dienst- oder "
        "Auftragsverhältnis zur Partei stehen (§ 6 Abs 3 lit a). Heute trägt die Verwaltung die Rolle "
        "ein; die Unvereinbarkeiten prüft niemand automatisch.")
    ),
    faehigkeiten=(
        Faehigkeit(
            titel=_("Einen eigenen Arbeitsbereich öffnen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:integritaet",
        ),
        Faehigkeit(
            titel=_("Eine Abstimmung durch veröffentlichten, begründeten Beschluss hervorheben"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:integritaet",
        ),
        Faehigkeit(
            titel=_("Einen Antrag durch begründeten Beschluss formal zurückweisen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:integritaet",
        ),
        Faehigkeit(
            titel=_("Den Vollzug eines Beschlusses oder eine laufende Abstimmung aussetzen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:integritaet",
        ),
        Faehigkeit(
            titel=_("Die Betroffenheit im Einzelfall feststellen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S9 — die Regeln selbst brauchen zuvor einen Beschluss der Mitgliederversammlung"),
        ),
        Faehigkeit(
            titel=_("In einem internen Beschluss des Rates abstimmen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:integritaet",
        ),
        Faehigkeit(
            titel=_("Beschlüsse aller Räte mit Stimmen und Begründungen einsehen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:beschluesse",
        ),
        Faehigkeit(
            titel=_("Ein Verfahren nachrechnen: Zeitleiste, Audit-Spur und Export je Antrag"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf jeder Antragsseite"),
        ),
        Faehigkeit(
            titel=_("Die offengelegten, versionierten Regelwerke prüfen"),
            stand=Stand.VERFUEGBAR,
            urlname="parameter:regeln",
        ),
        Faehigkeit(
            titel=_("Die eigene Besetzung öffentlich ausweisen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:uebersicht",
        ),
        Faehigkeit(
            titel=_("Mindestens jährlich öffentlich berichten"),
            stand=Stand.GEPLANT,
            bauschritt=_("S9"),
        ),
        Faehigkeit(
            titel=_("Ein unabhängiges externes Sicherheitsaudit veranlassen und veröffentlichen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S9"),
        ),
    ),
)

# ── Verwaltung und die drei noch nicht gebauten Raete ─────────────────────
VERWALTUNG = Rolle(
    schluessel="verwaltung",
    name=_("Verwaltung (Admin)"),
    satzung="§ 6 Abs 2 (laufende Geschäfte)",
    was_sie_ist=_("Kein Organ der Satzung, sondern der technische Notbehelf: Ein Konto mit Adminrechten führt die Geschäfte, bis die Räte nach § 6 Abs 4 bis 6 besetzt sind."),
    wie_hinein=_("Adminrechte vergibt und entzieht ein anderes Admin-Konto; der satzungsgebende Erstzugang (DDOE_FIX_ADMIN) ist immer Admin und kann weder pausiert noch entmachtet werden. Eine Wahl oder Bestellung gibt es nicht."),
    faehigkeiten=(
        Faehigkeit(
            titel=_("Mitglieder suchen und Stammdaten berichtigen"),
            stand=Stand.TEILWEISE,
            urlname="mitglieder:verwaltung",
            einschraenkung=(
                _("Dasselbe Formular setzt auch das öffentliche Pseudonym. Das Mitglied selbst kann es nicht ändern, obwohl es sein Name in jeder Debatte ist.")
            ),
        ),
        Faehigkeit(
            titel=_("Identitätsstufe setzen und damit die Mitwirkung freischalten"),
            stand=Stand.TEILWEISE,
            urlname="mitglieder:verwaltung",
            einschraenkung=_("Über die Aufnahme entscheidet nach § 4 Abs 1 der Koordinationsrat. Heute setzt die Verwaltung die Stufe im Stammdatenformular — ohne Beschluss, ohne Frist, ohne begründbare Ablehnung."),
        ),
        Faehigkeit(
            titel=_("Mitgliedschaft pausieren oder ausschließen"),
            stand=Stand.TEILWEISE,
            urlname="mitglieder:verwaltung",
            einschraenkung=_("Ein Ausschluss ist nach § 4 Abs 5 nur durch Entscheidung des Parteischiedsgerichts zulässig; der Knopf vollzieht den Beschluss, er ersetzt ihn nicht. Geprüft wird das nicht — verlangt wird nur eine Begründung, die im Audit-Log erscheint."),
        ),
        Faehigkeit(
            titel=_("Adminrechte vergeben und entziehen"),
            stand=Stand.VERFUEGBAR,
            urlname="mitglieder:verwaltung",
        ),
        Faehigkeit(
            titel=_("Beitragseingänge verbuchen, erinnern, Kontoauszug abgleichen"),
            stand=Stand.VERFUEGBAR,
            urlname="mitglieder:verwaltung_beitraege",
        ),
        Faehigkeit(
            titel=_("Rollen in die vier bestehenden Räte berufen, bestätigen und beenden"),
            stand=Stand.TEILWEISE,
            urlname="gremien:rollen",
            einschraenkung=_("§ 6 Abs 8 trennt Bestellung (Koordinationsrat) und Bestätigung (Mitgliederversammlung); heute liegt beides in einer Hand, die Bestätigung ist ein Haken im Formular. Besetzbar sind nur Expertenrat 1 und 2, Koordinationsrat und Integritätsrat."),
        ),
        Faehigkeit(
            titel=_("Werte im Parameterregister ändern"),
            stand=Stand.TEILWEISE,
            urlname="parameter:verwaltung",
            einschraenkung=_("Die Einführung eines Wertes bedarf nach § 6 Abs 11 lit c der Freigabe des Koordinationsrats, befristete Tests ordnet er an. Beides gibt es nicht; die Verwaltung ändert mit Pflicht-Grund, der im Register und im Audit-Log steht."),
        ),
        Faehigkeit(
            titel=_("Eine Fassung der Verfahrensordnung erzeugen und in Kraft setzen"),
            stand=Stand.TEILWEISE,
            urlname="parameter:verwaltung",
            einschraenkung=_("Über die Verfahrensordnung beschließt nach § 5 Abs 7 die Mitgliederversammlung. Solange die Plattform diese Abstimmung nicht führen kann, handelt die Verwaltung stellvertretend — in zwei Schritten und mit Pflicht-Grund im öffentlichen Audit-Log."),
        ),
        Faehigkeit(
            titel=_("Den Umsetzungsstand angenommener Anträge fortschreiben"),
            stand=Stand.TEILWEISE,
            einschraenkung=_("Das Umsetzungsregister führt nach § 6 Abs 10 der Integrations- und Berichtswesenrat. Bis es ihn gibt, schreiben Admins fort; jeder Eintrag ist öffentlich, dauerhaft und auditiert."),
        ),
        Faehigkeit(
            titel=_("Mandate anlegen, Aufgaben und Fotos pflegen"),
            stand=Stand.TEILWEISE,
            urlname="mandatare:verwaltung",
            einschraenkung=_("Nach § 7 Abs 3 lit b stellt der Mandatar die Informationen selbst ein. Heute pflegt die Verwaltung sie an seiner Stelle; der eigene Bereich des Mandatars kommt mit S10."),
        ),
        Faehigkeit(
            titel=_("Rückmeldungen aus dem Anstoß-Widget sichten, einordnen und ausführen"),
            stand=Stand.TEILWEISE,
            urlname="anstoss:verwaltung",
            einschraenkung=_("Stand setzen und Ausfuhr als CSV oder JSON gehen. Ein Feld für den Vermerk und eine Rückfrage per E-Mail fehlen in der Ansicht; wiederkehrende Probleme weiterzuleiten ist nach § 6 Abs 6 Sache des Supportrats."),
        ),
        Faehigkeit(
            titel=_("In die Arbeitsbereiche der Räte sehen"),
            stand=Stand.TEILWEISE,
            urlname="gremien:expertenrat",
            einschraenkung=_("Admins dürfen zuschauen, aber nicht mitstimmen — das prüfen die Handlungen selbst. Das uneingeschränkte Einsichtsrecht gibt § 6 Abs 3 lit c dem Integritätsrat, nicht der Verwaltung."),
        ),
        Faehigkeit(
            titel=_("Das Monatsbudget des Modell-Steckplatzes begrenzen"),
            stand=Stand.TEILWEISE,
            urlname="parameter:verwaltung",
            einschraenkung=_("Das Budget steht als Wert ki-monatstokens im Register. Welcher Anbieter und welches Modell angeschlossen sind, entscheidet allein die Server-Einstellung — dafür gibt es keine Ansicht und keinen Beschluss."),
        ),
    ),
)

ENTWICKLUNGSRAT = Rolle(
    schluessel="entwicklungsrat",
    name=_("Technischer Entwicklungsrat"),
    satzung="§ 6 Abs 4",
    was_sie_ist=_("Er verantwortet Erstellung, Betrieb und Optimierung von ParlamentPlattform und Zukunftswerkstatt, beauftragt und überwacht externe Dienstleister und berichtet regelmäßig."),
    wie_hinein=_("Bestellung durch den Koordinationsrat auf öffentliche Ausschreibung hin für zwei Jahre, bestätigt durch die Mitgliederversammlung (§ 6 Abs 8). Heute trägt die Verwaltung die Rolle ein."),
    im_code=True,
    faehigkeiten=(
        Faehigkeit(
            titel=_("Den Arbeitsbereich des Rates öffnen: Regelverzeichnis, Register, Zukunftswerkstatt"),
            stand=Stand.VERFUEGBAR,
            ort=_("unter „Mein Gremium“"),
        ),
        Faehigkeit(
            titel=_("Betrieb und Weiterentwicklung von Plattform und Zukunftswerkstatt verantworten"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Die Leitgestalt des Hauptzugangs weiterentwickeln"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen; die vier Felder stehen, geändert werden sie im Quelltext"),
        ),
        Faehigkeit(
            titel=_("Externe Dienstleister beauftragen und überwachen"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Regelmäßig berichten und Sitzungsprotokolle veröffentlichen"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Ergebnisse der Zukunftswerkstatt als gekennzeichnete Modellrechnung einspeisen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S11"),
        ),
        Faehigkeit(
            titel=_("Im Rat abstimmen und Beschlüsse veröffentlichen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:beschluesse",
        ),
    ),
)

BERICHTSWESENRAT = Rolle(
    schluessel="berichtswesenrat",
    name=_("Integrations- und Berichtswesenrat"),
    satzung="§ 6 Abs 5",
    was_sie_ist=_("Er führt die jährliche Evaluierung des Gesamtsystems durch und legt der Mitgliederversammlung einen öffentlichen Bericht samt Verbesserungsvorschlägen vor."),
    wie_hinein=_("Bestellung durch den Koordinationsrat auf öffentliche Ausschreibung hin für zwei Jahre, bestätigt durch die Mitgliederversammlung (§ 6 Abs 8). Heute trägt die Verwaltung die Rolle ein."),
    im_code=True,
    faehigkeiten=(
        Faehigkeit(
            titel=_("Den Arbeitsbereich des Rates öffnen: Umsetzungsregister und Überlastungsmeldungen"),
            stand=Stand.VERFUEGBAR,
            ort=_("unter „Mein Gremium“"),
        ),
        Faehigkeit(
            titel=_("Die jährliche Evaluierung des Gesamtsystems durchführen"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Beteiligung, Repräsentativität und Antragsdurchlauf messen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S13; erste aggregierte Zahlen stehen schon unter /kennzahlen.json"),
        ),
        Faehigkeit(
            titel=_("Die Wirkung der Regeln nach § 5 Abs 6 messen"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen; diese Regeln sind selbst ungebaut und brauchen einen Satzungsbeschluss"),
        ),
        Faehigkeit(
            titel=_("Den öffentlichen Bericht mit Verbesserungsvorschlägen vorlegen"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Das öffentliche Umsetzungsregister führen"),
            stand=Stand.TEILWEISE,
            urlname="verfahren:umsetzung",
            einschraenkung=_("Das Register steht; fortgeschrieben wird es heute von der Verwaltung, nicht vom Rat."),
        ),
        Faehigkeit(
            titel=_("Überlastungsmeldungen veröffentlichen (§ 6 Abs 10)"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:umsetzung",
        ),
        Faehigkeit(
            titel=_("Im Rat abstimmen und Beschlüsse veröffentlichen"),
            stand=Stand.VERFUEGBAR,
            urlname="gremien:beschluesse",
        ),
    ),
)

SUPPORTRAT = Rolle(
    schluessel="supportrat",
    name=_("Supportrat"),
    satzung="§ 6 Abs 6",
    was_sie_ist=_("Er baut Unterstützungsstrukturen auf Bundes-, Landes-, Bezirks- und Gemeindeebene auf, erstellt Schulungsunterlagen und leitet wiederkehrende Probleme als Verbesserungsvorschläge weiter."),
    wie_hinein=_("Bestellung durch den Koordinationsrat auf öffentliche Ausschreibung hin für zwei Jahre, bestätigt durch die Mitgliederversammlung (§ 6 Abs 8). Heute gar nicht: Die Plattform kennt den Rat nicht."),
    im_code=False,
    faehigkeiten=(
        Faehigkeit(
            titel=_("Unterstützungsstrukturen auf Bundes-, Landes-, Bezirks- und Gemeindeebene aufbauen"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Über Chat, E-Mail, Telefon und Präsenzstellen erreichbar sein"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Rückmeldungen der Mitglieder beantworten"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen; die Anstöße liegen heute in der Verwaltung, eine Antwort ist nicht vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Schulungsunterlagen erstellen und bereitstellen"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen; es gibt nur die dreiteilige Einführung nach der Bestätigung"),
        ),
        Faehigkeit(
            titel=_("Wiederkehrende Probleme als Verbesserungsvorschläge weiterleiten"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Identität bei einer Präsenzstelle feststellen"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen; die Stufe Präsenz setzt heute die Verwaltung von Hand"),
        ),
        Faehigkeit(
            titel=_("Im Rat abstimmen und Beschlüsse veröffentlichen"),
            stand=Stand.GEPLANT,
            bauschritt=_("kein Bauschritt vorgesehen"),
        ),
    ),
)

# ── Mandatar, Partnerpartei, Parteischiedsgericht ─────────────────────────
MANDATAR = Rolle(
    schluessel="mandatar",
    name=_("Mandatar"),
    satzung="§ 7, besonders Abs 9",
    was_sie_ist=_("Mandatsträger der DDÖ auf Bundes-, Landes-, Bezirks- oder Gemeindeebene. Die Plattform führt für jeden einen öffentlichen Bereich mit Aufgaben und Fristen; die Ergebnisse der von ihm betreuten Abstimmungen sind Beschlusslage und Richtschnur seines Handelns (§ 7 Abs 9)."),
    wie_hinein=(
        _("Über einen Kandidatur-Antrag auf der Plattform (§ 7 Abs 1): Jedes wählbare Mitglied "
        "stellt ihn selbst oder beteiligt sich an einem bestehenden — ein zweiter Antrag für "
        "dasselbe Mandat wird nicht eröffnet. Die Bewerbung mit der meisten Zustimmung gewinnt. "
        "Vor der Aufnahme in einen Wahlvorschlag steht eine schriftliche Mandatsvereinbarung "
        "(§ 7 Abs 3). Das errungene Mandat trägt heute noch die Verwaltung ein.")
    ),
    im_code=False,
    auf_der_startseite=True,
    faehigkeiten=(
        Faehigkeit(
            titel=_("Kandidatur für ein Mandat einbringen oder sich an einer bestehenden beteiligen"),
            stand=Stand.TEILWEISE,
            urlname="verfahren:einbringen",
            einschraenkung=(
                _("Einbringen geht; sich an einer bestehenden Kandidatur zu beteiligen, heißt heute, ihr zuzustimmen — eine eigene Bewerbung im fremden Antrag gibt es so nicht.")
            ),
        ),
        Faehigkeit(
            titel=_("Öffentlicher Bereich mit Lichtbild, Aufgaben und Fristen"),
            stand=Stand.VERFUEGBAR,
            urlname="mandatare:liste",
        ),
        Faehigkeit(
            titel=_("Betreute Abstimmung an einer Aufgabe zeigen"),
            stand=Stand.TEILWEISE,
            einschraenkung=_("Die Verknüpfung Aufgabe → Antrag besteht und wird öffentlich angezeigt; setzen kann sie nur die Verwaltung. Der Mandatar erzeugt selbst keine Abstimmung."),
        ),
        Faehigkeit(
            titel=_("Eigene Aufgaben, Fristen und das Lichtbild einstellen"),
            stand=Stand.TEILWEISE,
            einschraenkung=_("Eintragen kann nur die Verwaltung (/verwaltung/mandatare/). Der Mandatar hat keinen eigenen Zugang; /mandatare/mein/ kommt mit S10."),
        ),
        Faehigkeit(
            titel=_("Vollzugsbericht zu einem angenommenen Antrag abgeben"),
            stand=Stand.TEILWEISE,
            einschraenkung=_("Den Umsetzungsstand schreibt heute nur die Verwaltung fort, obwohl die Satzung Mandatsträger selbst zum Vollzugsbericht verpflichtet."),
        ),
        Faehigkeit(
            titel=_("Die Rolle „Mandatar“ auf der Plattform"),
            stand=Stand.GEPLANT,
            bauschritt=_("S10"),
        ),
        Faehigkeit(
            titel=_("Instant-Report zu einer Aufgabe samt Frist veröffentlichen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S10"),
        ),
        Faehigkeit(
            titel=_("Aus einem Report eine betreute Abstimmung erzeugen (Mandatsfrage)"),
            stand=Stand.GEPLANT,
            bauschritt=_("S10"),
        ),
        Faehigkeit(
            titel=_("Rechenschaftsregister: Beschluss, Stimmverhalten und Begründung binnen sieben Tagen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S10"),
        ),
        Faehigkeit(
            titel=_("Monatsbericht und Sammelbericht nach jedem Sitzungstag"),
            stand=Stand.GEPLANT,
            bauschritt=_("S10"),
        ),
    ),
)

PARTNER = Rolle(
    schluessel="partner",
    name=_("Partnerpartei (internationale Zusammenarbeit)"),
    satzung="§ 12, besonders Abs 5",
    was_sie_ist=_("Politische Organisationen und Parteien im In- und Ausland mit vergleichbaren Zielen der direkten Demokratie, mit denen die DDÖ Wissen, Software und bewährte Verfahren austauscht."),
    wie_hinein=_("Heute formlos: Partner-Seite lesen, Übertragungspaket laden, Kontakt per E-Mail an plattform@ddoe.at. Das bestätigte Partner-Konto und die Rolle mit eigenem Bereich kommen mit S14b."),
    im_code=False,
    faehigkeiten=(
        Faehigkeit(
            titel=_("Partner-Seite mit Vision, Modell, Schnittstellen und Einstieg lesen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:partner",
        ),
        Faehigkeit(
            titel=_("Kurzfassung in der eigenen Sprache lesen (FR, ES, IT, JA neben DE und EN)"),
            stand=Stand.VERFUEGBAR,
            ort=_("auf den Partner-Seiten"),
        ),
        Faehigkeit(
            titel=_("Übertragungspaket herunterladen: Satzungs-Baukasten, Einrichtung, Instanz-Vorlagen, Schema"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:partner_paket",
        ),
        Faehigkeit(
            titel=_("Parameter im gemeinsamen, sprachneutralen Schema abrufen"),
            stand=Stand.VERFUEGBAR,
            urlname="parameter:export",
        ),
        Faehigkeit(
            titel=_("Kennzahlen im gemeinsamen Schema abrufen"),
            stand=Stand.VERFUEGBAR,
            urlname="parameter:kennzahlen",
        ),
        Faehigkeit(
            titel=_("Umsetzungsstand maschinenlesbar abrufen"),
            stand=Stand.VERFUEGBAR,
            urlname="verfahren:umsetzung_json",
        ),
        Faehigkeit(
            titel=_("Kontakt aufnehmen"),
            stand=Stand.TEILWEISE,
            urlname="verfahren:partner",
            einschraenkung=_("Nur als E-Mail-Link an plattform@ddoe.at; das Kontaktformular kommt mit dem Partner-Konto (S14b)."),
        ),
        Faehigkeit(
            titel=_("Partner-Konto anlegen und von der Partei bestätigen lassen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S14b"),
        ),
        Faehigkeit(
            titel=_("Rolle „Partner“ und eigener Bereich für Partnerorganisationen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S14b"),
        ),
        Faehigkeit(
            titel=_("Parameter der eigenen Instanz einspielen und gegenüberstellen"),
            stand=Stand.GEPLANT,
            bauschritt=_("S14b"),
        ),
        Faehigkeit(
            titel=_("Dokumentierte Austauschformate der Koordinationsräte (Austausch-Protokolle)"),
            stand=Stand.GEPLANT,
            bauschritt=_("S14b"),
        ),
    ),
)

SCHIEDSGERICHT = Rolle(
    schluessel="schiedsgericht",
    name=_("Parteischiedsgericht"),
    satzung="§ 11, § 6 Abs 1 lit h",
    was_sie_ist=_("Innerparteiliche Schlichtungseinrichtung aus fünf unabhängigen Personen, die in allen Streitigkeiten aus dem Parteiverhältnis entscheidet und allein die Nichtigkeit satzungswidriger Beschlüsse feststellt."),
    wie_hinein=_("Von Fall zu Fall, nicht auf Dauer: Bei zwei Streitparteien macht jede zwei Mitglieder namhaft, diese wählen die vorsitzende Person; sonst entscheidet das Los aus einer öffentlich geführten Liste (§ 11 Abs 2). Mitglieder dürfen keinem anderen Organ angehören und kein Mandat der DDÖ ausüben (§ 11 Abs 3). Diese Liste führt die Plattform heute nicht."),
    im_code=False,
    faehigkeiten=(
        Faehigkeit(
            titel=_("Öffentlich geführte Liste, aus der die Mitglieder ausgelost werden"),
            stand=Stand.GEPLANT,
            bauschritt=_("nicht in Teil C (S1–S14) vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Anrufung durch ein Mitglied: Zurückweisung eines Antrags, Ablehnung der Aufnahme, Ausschluss"),
            stand=Stand.GEPLANT,
            bauschritt=_("nicht in Teil C (S1–S14) vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Nichtigkeit eines Beschlusses feststellen und die Feststellung veröffentlichen"),
            stand=Stand.GEPLANT,
            bauschritt=_("nicht in Teil C (S1–S14) vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Eine Aussetzung des Integritätsrats binnen sieben Tagen bestätigen"),
            stand=Stand.GEPLANT,
            bauschritt=_("nicht in Teil C (S1–S14) vorgesehen"),
        ),
        Faehigkeit(
            titel=_("Entscheidung mit Begründung binnen sechs Monaten veröffentlichen"),
            stand=Stand.GEPLANT,
            bauschritt=_("nicht in Teil C (S1–S14) vorgesehen"),
        ),
    ),
)


GRUPPEN: tuple[Gruppe, ...] = (
    Gruppe(
        schluessel="zugang",
        name=_("Zugang zur Plattform"),
        erklaerung=(
            _("Die Mitgliederversammlung ist diese Plattform (§ 5 Abs 1). Wer hier steht, ist kein "
            "Amtsträger — sondern jemand, der liest oder mitwirkt.")
        ),
        rollen=(GAST, MITGLIED, MITGLIED_RUHT),
    ),
    Gruppe(
        schluessel="raete",
        name=_("Die Räte der Satzung"),
        erklaerung=(
            _("Sieben Räte nach § 6. Sechs gibt es im Code, einer noch nicht — er steht trotzdem "
            "hier, weil sein Auftrag in der Satzung steht und die Lücke sichtbar bleiben soll.")
        ),
        rollen=(
            EXPERTENRAT1,
            EXPERTENRAT2,
            KOORDINATIONSRAT,
            INTEGRITAETSRAT,
            ENTWICKLUNGSRAT,
            BERICHTSWESENRAT,
            SUPPORTRAT,
        ),
    ),
    Gruppe(
        schluessel="aussen",
        name=_("Ämter, Schiedsstelle und Außenbeziehungen"),
        erklaerung=(
            _("Wer die Beschlüsse nach außen trägt, wer im Streitfall entscheidet, wer von anderen "
            "Parteien aus mit uns arbeitet — und die Verwaltung, die einspringt, solange die "
            "zuständigen Räte nicht besetzt sind.")
        ),
        rollen=(MANDATAR, SCHIEDSGERICHT, PARTNER, VERWALTUNG),
    ),
)

def alle_rollen(gruppen: tuple[Gruppe, ...]) -> tuple[Rolle, ...]:
    return tuple(rolle for gruppe in gruppen for rolle in gruppe.rollen)


def rolle(gruppen: tuple[Gruppe, ...], schluessel: str) -> Rolle | None:
    return next((r for r in alle_rollen(gruppen) if r.schluessel == schluessel), None)


def zaehlung(gruppen: tuple[Gruppe, ...]) -> dict[str, int]:
    """Wie viele Fähigkeiten in welchem Stand — der Soll/Ist-Abgleich in einer Zeile."""
    stände = {stand.value: 0 for stand in Stand}
    for r in alle_rollen(gruppen):
        for f in r.faehigkeiten:
            stände[f.stand.value] += 1
    stände["rollen"] = len(alle_rollen(gruppen))
    return stände
