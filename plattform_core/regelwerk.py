"""Das Verzeichnis der automatisierten Regeln (§ 2 Abs 6).

Die Satzung verlangt einen Satz, der es in sich hat: *„Jede automatisierte Sortierung oder
Auswahl erfolgt nach offengelegten, versionierten und nachrechenbaren Regeln. Modelle,
Regelwerke und Änderungen daran sind mit Datum und Begründung öffentlich zu dokumentieren; der
Integritätsrat prüft sie mindestens jährlich."*

Vier Forderungen also: offengelegt, versioniert, nachrechenbar, mit Datum und Begründung. Diese
Datei erfüllt die letzte — sie ist das Verzeichnis, auf das sich die jährliche Prüfung stützt.

**Von Hand gepflegt, nicht erzeugt.** Ein Programm kann aufzählen, welche Module es gibt; eine
*Begründung* kann es nicht schreiben. Genau die verlangt die Satzung aber — „warum gibt es diese
Fassung" ist eine Aussage über Menschen und ihre Absichten. Deshalb steht hier eine Liste, die
jemand geschrieben hat, und ein Test (`parameter/test_regelwerk.py`), der anschlägt, sobald ein
Modul in `plattform_core` weder im Verzeichnis noch in der begründeten Ausnahmeliste steht.

Die **Wirkung** trennt, was ein Leser wissen muss: Eine Regel, die *entscheidet*, bindet ihn;
eine, die *reiht*, bestimmt, was er zuerst sieht; eine, die *darstellt*, tut ihm nichts. Alle
drei stehen hier — aber niemand soll sie verwechseln müssen.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass

#: Fassung dieses Verzeichnisses. Sie steigt, wenn eine Regel hinzukommt, verschwindet oder
#: ihre Wirkung ändert — nicht, wenn eine der verzeichneten Regeln ihre eigene Fassung erhöht.
VERSION = 1

SATZUNG = "§ 2 Abs 6"


class Wirkung(enum.StrEnum):
    """Was eine Regel mit einem Menschen macht — die einzige Einteilung, die er braucht."""

    ENTSCHEIDET = "entscheidet"
    REIHT = "reiht"
    ORDNET_ZU = "ordnet zu"
    RECHNET = "rechnet"
    STELLT_DAR = "stellt dar"

    @property
    def erklaerung(self) -> str:
        return {
            "entscheidet": "Das Ergebnis bindet — es bestimmt, was im Verfahren geschieht.",
            "reiht": "Bestimmt die Reihenfolge, in der etwas erscheint.",
            "ordnet zu": "Teilt ein oder erkennt Ähnlichkeit — schlägt vor, entscheidet nicht.",
            "rechnet": "Rechnet, ohne zu entscheiden.",
            "stellt dar": "Bereitet auf, ohne auszuwählen.",
        }[self.value]

    @property
    def muss_versioniert_sein(self) -> bool:
        """§ 2 Abs 6 verlangt Versionierung für Sortierung und Auswahl — nicht für Anzeige."""
        return self in (Wirkung.ENTSCHEIDET, Wirkung.REIHT, Wirkung.ORDNET_ZU)


@dataclass(frozen=True)
class Regel:
    """Eine automatisierte Regel der Plattform, wie § 2 Abs 6 sie dokumentiert sehen will."""

    modul: str
    titel: str
    zweck: str
    wirkung: Wirkung
    satzung: str
    #: Fassung der Regel (`VERSION` im Modul). None, wo das Modul keine führt.
    fassung: int | None
    #: Seit wann die geltende Fassung gilt — ISO-Datum. Leer, wo es sich nicht belegen ließ;
    #: eine erfundene Zahl wäre schlimmer als die Lücke, denn genau dieses Datum verlangt § 2 Abs 6.
    seit: str
    #: Warum es diese Fassung gibt — ein Satz, den ein Mitglied ohne Programmierkenntnisse liest.
    grund: str
    #: Wie ein Mensch das Ergebnis selbst nachrechnen kann.
    nachrechenbar: str = ""
    #: Stellgröße im Parameterregister, die diese Fassung spiegelt.
    registerschluessel: str = ""
    #: Was gegenüber § 2 Abs 6 fehlt — offen benannt statt verschwiegen.
    luecke: str = ""

    @property
    def vollstaendig(self) -> bool:
        """Erfüllt diese Zeile, was § 2 Abs 6 verlangt?"""
        versioniert = self.fassung is not None or not self.wirkung.muss_versioniert_sein
        return bool(self.seit) and bool(self.grund) and versioniert and not self.luecke


#: Module in `plattform_core`, die keine Regel im Sinne des § 2 Abs 6 sind — mit dem Grund.
#: Der Test hält diese Liste gegen den Ordner: Ein neues Modul muss hier oder im Verzeichnis
#: stehen, sonst schlägt er an. Stillschweigen ist die eine Möglichkeit, die es nicht gibt.
KEINE_REGEL: dict[str, str] = {
    "__init__.py": "Nur die Versionsnummer der Software und die Phasen-Aufzählung.",
    "regelwerk.py": "Dieses Verzeichnis selbst.",
}


def verzeichnis() -> tuple[Regel, ...]:
    """Alle verzeichneten Regeln, geordnet nach Wirkung — Bindendes zuerst."""
    reihenfolge = list(Wirkung)
    return tuple(sorted(REGELN, key=lambda r: (reihenfolge.index(r.wirkung), r.titel)))


def nach_wirkung() -> list[tuple[Wirkung, tuple[Regel, ...]]]:
    """Die Regeln in Gruppen — für eine Seite, die zuerst zeigt, was bindet."""
    gruppen = []
    for wirkung in Wirkung:
        treffer = tuple(r for r in verzeichnis() if r.wirkung is wirkung)
        if treffer:
            gruppen.append((wirkung, treffer))
    return gruppen


def zaehlung() -> dict[str, int]:
    regeln = verzeichnis()
    return {
        "regeln": len(regeln),
        "vollstaendig": sum(1 for r in regeln if r.vollstaendig),
        "mit_luecke": sum(1 for r in regeln if r.luecke),
        "ohne_datum": sum(1 for r in regeln if not r.seit),
        "bindend": sum(1 for r in regeln if r.wirkung is Wirkung.ENTSCHEIDET),
    }


def als_dict() -> list[dict]:
    """Das Verzeichnis in Datenform — für die eingefrorene Momentaufnahme einer Prüfung.

    Der Vermerk „geprüft am …" wäre ohne die Liste, auf die er sich bezieht, wertlos: Regeln
    ändern sich, und ein Jahr später wüsste niemand mehr, was geprüft worden ist."""
    return [
        {
            "modul": r.modul,
            "titel": r.titel,
            "wirkung": r.wirkung.value,
            "satzung": r.satzung,
            "fassung": r.fassung,
            "seit": r.seit,
            "grund": r.grund,
            "registerschluessel": r.registerschluessel,
            "luecke": r.luecke,
        }
        for r in verzeichnis()
    ]


#: Das Verzeichnis. Jede Zeile ist von Hand geschrieben — Datum und Begründung verlangt die
#: Satzung, und beides kann kein Programm erfinden.
REGELN: tuple[Regel, ...] = (
    Regel(
        modul="tally.py",
        titel="Auszählung von Sachfragen",
        zweck=(
            "Zählt die Ja-, Nein- und Enthaltungsstimmen einer Sachabstimmung und stellt fest, ob der "
            "Antrag angenommen ist: Zuerst muss die Mindestbeteiligung erreicht sein, dann "
            "entscheidet die Mehrheit. Gerechnet wird ausschließlich mit ganzen Zahlen, damit kein "
            "Rundungsfehler über einen Beschluss entscheiden kann."
        ),
        wirkung=Wirkung.ENTSCHEIDET,
        satzung="§ 5 Abs 4 (mit § 3 Abs 1 lit b — eine Stimme je Mensch)",
        fassung=1,
        seit="2026-08-19",
        grund=(
            "Sie steht seit dem Fundament der Plattform so da: Das Ergebnis einer Abstimmung soll "
            "jede Person mit Papier und Bleistift nachrechnen können, und die Reihenfolge, in der die "
            "Stimmen eingehen, darf am Ergebnis nichts ändern."
        ),
        nachrechenbar=(
            "Nach Abstimmungsende gibt es zu jedem Antrag einen JSON-Export der Stimmliste. Von Hand: "
            "Ja + Nein + Enthaltung durch die Zahl der Stimmberechtigten teilen — das muss mindestens "
            "die Mindestbeteiligung ergeben; dann genügt Ja > Nein (bei der Basis „abgegeben': Ja > "
            "die Hälfte aller abgegebenen Stimmen). Wer rechnen lassen will: `python3 "
            "verify/nachrechnen.py export.json`, ein zweites, unabhängiges Programm aus reiner "
            "Standardbibliothek. Die Mindestbeteiligung stammt aus der am Antrag eingefrorenen "
            "Verfahrensordnung, nicht aus dem laufenden Parameterregister."
        ),
    ),
    Regel(
        modul="tally.py",
        titel="Auszählung der Zustimmungswahl bei Kandidaturen",
        zweck=(
            "Zählt eine Mandats-Kandidatur aus: Jedes Mitglied kann mehreren Bewerbungen zustimmen; "
            "die Bewerbung mit den meisten Zustimmungen gewinnt, und die Reihenfolge der "
            "Zustimmungszahlen ergibt die Reihung des Wahlvorschlags. Bei Stimmengleichheit steht die "
            "früher eingereichte Bewerbung vorn."
        ),
        wirkung=Wirkung.ENTSCHEIDET,
        satzung="§ 7 Abs 1 (Satzungsentwurf 2.5), mit § 5 Abs 4 für die Mindestbeteiligung",
        fassung=1,
        seit="2026-09-01",
        grund=(
            "Seit dem 1. September 2026 wählt das Parlament auch Personen: Mandats-Kandidaturen "
            "laufen als Anträge, an denen man sich beteiligt, statt als getrennte Wahl. Dafür "
            "brauchte es eine Auszählung, die Zustimmungen zählt statt Ja und Nein — und eine offene "
            "Regel für den Gleichstand, damit nicht der Zufall über die Listenreihung entscheidet."
        ),
        nachrechenbar=(
            "Der JSON-Export des Antrags enthält alle Bewerbungen und alle Zustimmungen. Von Hand: "
            "die Zustimmungen je Bewerbung zählen, absteigend ordnen, bei gleicher Zahl die früher "
            "eingereichte Bewerbung zuerst. Die Beteiligung ist die Zahl der Menschen, die mindestens "
            "einer Bewerbung zugestimmt haben; sie muss die Mindestbeteiligung der eingefrorenen "
            "Verfahrensordnung erreichen, sonst gilt niemand als gewählt."
        ),
    ),
    Regel(
        modul="eligibility.py",
        titel="Stimmberechtigung und Anwartschaft",
        zweck=(
            "Entscheidet, ob ein Mitglied bei einer bestimmten Abstimmung mitstimmen darf. Maßstab "
            "ist die ununterbrochene Mitgliedschaft am Tag des Abstimmungsbeginns: drei Monate bei "
            "Sachfragen, zwölf Monate bei Personenwahlen, Mandatsnominierungen, Satzungsänderungen "
            "und der Auflösung. Für die erste Organbestellung und die erste Verfahrensordnung "
            "entfällt die Anwartschaft."
        ),
        wirkung=Wirkung.ENTSCHEIDET,
        satzung="§ 4 Abs 4 (Übergangsregel: § 4 Abs 4 lit d)",
        fassung=1,
        seit="2026-08-19",
        grund=(
            "Sie steht seit dem Fundament so da. Die Monatsrechnung ist im Modul ausgeschrieben statt "
            "aus einer fremden Programmbibliothek geholt, damit die Frist eines Menschen nie davon "
            "abhängt, welche Bibliothek gerade installiert ist."
        ),
        nachrechenbar=(
            "Beitrittsdatum nehmen, drei beziehungsweise zwölf Kalendermonate dazuzählen und mit dem "
            "Tag des Abstimmungsbeginns vergleichen. Fällt der Zieltag auf einen Tag, den der "
            "Zielmonat nicht hat, gilt der letzte Tag dieses Monats — Beitritt am 30. November, "
            "Sachfrage, Erfüllungstag 28. (im Schaltjahr 29.) Februar."
        ),
    ),
    Regel(
        modul="phases.py",
        titel="Phasenautomat des Antragsverfahrens",
        zweck=(
            "Bestimmt, wann ein Antrag von einer Phase in die nächste wechselt: Unterstützung, "
            "Beratung, Abstimmung, dann angenommen oder abgelehnt — und Verfall, wenn die "
            "Unterstützungsschwelle in der Frist nicht erreicht wird. Ein Übergang geschieht "
            "ausschließlich durch Zeitablauf oder eine erreichte Schwelle, nie weil jemand ihn "
            "auslöst; die einzige Ausnahme ist die förmliche Zurückweisung durch den Integritätsrat, "
            "die außerhalb dieses Automaten steht."
        ),
        wirkung=Wirkung.ENTSCHEIDET,
        satzung="§ 5 Abs 3 (Ausnahme der Zurückweisung: § 5 Abs 2)",
        fassung=1,
        seit="2026-08-19",
        grund=(
            "Sie steht seit dem Fundament so da. Der Automat liest nie die Uhr des Servers, sondern "
            "bekommt den Zeitpunkt übergeben, und ein Übergang gilt zum Fristzeitpunkt — nicht zu dem "
            "Moment, in dem ein Hintergrundprogramm zufällig lief. Ein verspäteter Server verschiebt "
            "dadurch keine Frist eines Menschen, und jeder frühere Zustand lässt sich exakt "
            "wiederherstellen."
        ),
        nachrechenbar=(
            "Phasenbeginn plus die Frist aus der am Antrag eingefrorenen Verfahrensordnung ergibt das "
            "Fristende; in der Unterstützungsphase kommt der Vergleich der Unterstützungszahl mit der "
            "Schwelle dazu. Beide Zahlen stehen auf der Antragsseite, die geltenden Fristen im "
            "Eintrag „Eingefrorene Verfahrensordnung'."
        ),
    ),
    Regel(
        modul="policy.py",
        titel="Eingefrorene Verfahrensordnung",
        zweck=(
            "Trägt die Verfahrensregeln eines Antrags: Unterstützungsschwelle, Fristen, "
            "Mindestbeteiligung und Mehrheitsbasis. Beim Einbringen wird die dann geltende Fassung "
            "als unveränderliche Kopie an den Antrag geheftet, damit eine spätere Änderung ein "
            "laufendes Verfahren nicht mehr erreicht. Jede Fassung, die die satzungsfesten "
            "Untergrenzen unterschreitet — Beratung mindestens 21 Tage, Abstimmung mindestens 7 Tage, "
            "Beteiligung mindestens 5 Prozent —, wird zurückgewiesen."
        ),
        wirkung=Wirkung.ENTSCHEIDET,
        satzung="§ 5 Abs 5 (Einfrieren), mit § 5 Abs 3 lit b bis d, § 5 Abs 4 und § 5 Abs 7",
        fassung=1,
        seit="2026-09-05",
        grund=(
            "Seit dem 5. September 2026 lassen sich Fristen und Schwellen im Parameterregister "
            "pflegen und daraus eine neue Fassung der Verfahrensordnung erzeugen. Erzeugen und In- "
            "Kraft-Setzen sind bewusst zwei Schritte, weil das eine eine Rechnung und das andere eine "
            "Entscheidung ist; und die Untergrenzen der Satzung bleiben im Programmtext statt im "
            "Register, damit die Verwaltung sie über eine Stellgröße nicht aushebeln kann."
        ),
        nachrechenbar=(
            "Jeder Antrag führt seine eingefrorene Kopie im Export mit — dort steht Zahl für Zahl, "
            "wonach er entschieden wurde. In der Verwaltung stellt ein Abgleich das Register und die "
            "geltende Ordnung Feld für Feld nebeneinander; fehlt im Register ein Wert, verweigert die "
            "Erzeugung die Arbeit, statt ihn stillschweigend zu ergänzen."
        ),
        registerschluessel="verfahren-unterstuetzung-schwelle · verfahren-unterstuetzung-tage · expertenrat-erstvorschlag-tage · verfahren-abstimmung-tage · verfahren-mindestbeteiligung-prozent · verfahren-wiedereinbringung-monate",
    ),
    Regel(
        modul="gremienbeschluss.py",
        titel="Auszählung interner Beschlüsse der Räte",
        zweck=(
            "Zählt die internen Abstimmungen der Räte aus. Anwesend ist, wer abgestimmt hat; "
            "beschlussfähig ist ein Rat ab der aufgerundeten Hälfte seiner besetzten Rollen, "
            "entschieden wird mit einfacher Mehrheit der abgegebenen Stimmen. Ein Gleichstand ist "
            "kein Beschluss, und ein Gremium ohne besetzte Rollen beschließt nichts."
        ),
        wirkung=Wirkung.ENTSCHEIDET,
        satzung=(
            "§ 6 Abs 2 lit e (über Verweise auch für Integritätsrat und Gliederungen), mit § 6 Abs 9"
        ),
        fassung=1,
        seit="2026-09-05",
        grund=(
            "Die Satzung sagt „bei Anwesenheit der Hälfte seiner Mitglieder'; für ein Gremium, das "
            "sich nicht in einem Raum trifft, musste jemand entscheiden, was Anwesenheit heißt. Bis "
            "dahin entschied bei der Prüfung durch die zweite Gruppe des Expertenrats, wer zuerst auf "
            "einen Knopf drückte — eine einzelne Person, sofort und ohne Frist. Gedacht war diese "
            "Gruppe als Redundanz und Korruptionsprüfung; eine Redundanz aus einer Person ist keine."
        ),
        nachrechenbar=(
            "Jeder Beschluss steht öffentlich unter einer zitierfähigen Nummer (etwa „IR-2026-04') "
            "mit jeder einzelnen Stimme und jeder Begründung, ohne Anmeldung einsehbar. Nachzurechnen "
            "ist: die Zahl der abgegebenen Stimmen gegen die aufgerundete Hälfte der zum Zeitpunkt "
            "der Auszählung aktiven Rollen — bei fünf Rollen sind das drei —, dann die höchste "
            "Stimmenzahl unter den Optionen; steht sie zweimal, gibt es kein Ergebnis."
        ),
        registerschluessel="gremien-beschluss-tage · gremien-pruefung-tage (Fristen der Beschlüsse; die Auszählung selbst liest kein Register)",
    ),
    Regel(
        modul="hashchain.py",
        titel="Audit-Kette des Protokolls",
        zweck=(
            "Versiegelt das Protokoll: Jeder Eintrag im Audit-Log trägt eine Prüfsumme über seinen "
            "eigenen Inhalt und die Prüfsumme des Vorgängers. Wer nachträglich einen alten Eintrag "
            "ändert, verändert damit zwangsläufig alle folgenden Prüfsummen — die Änderung fällt auf. "
            "Über Menschen entscheidet dieses Modul nichts; es rechnet und meldet, wo eine Kette "
            "nicht mehr stimmt."
        ),
        wirkung=Wirkung.RECHNET,
        satzung="§ 5 Abs 8 (mit § 3 Abs 1 lit c)",
        fassung=None,
        seit="2026-08-19",
        grund=(
            "Sie steht seit dem Fundament so da und ist absichtlich in rund sechzig Zeilen erklärbar: "
            "„Jeder Eintrag versiegelt alle vorherigen' — statt eines Aufwands, den am Ende niemand "
            "nachprüfen würde (ADR-005)."
        ),
        nachrechenbar=(
            "Die Prüfsumme ist SHA-256 über die Prüfsumme des Vorgängers und den Ereignisinhalt in "
            "kanonischer Form: sortierte Schlüssel, keine Leerzeichen, UTF-8. Die erste Kette beginnt "
            "bei vierundsechzig Nullen. Die Prüffunktion nennt nicht nur, dass etwas nicht stimmt, "
            "sondern den ersten Eintrag, dessen Prüfsumme nicht zu seinem Inhalt passt."
        ),
    ),
    Regel(
        modul="weicherfilter.py",
        titel="WeicherFilter: die selbst eingestellte Reihung",
        zweck=(
            "Reiht die Einträge im Bereich für Anträge und Gesetzesvorschläge nach neun Reglern, die "
            "das Mitglied selbst stellt: Punkte = Summe aus Reglerstellung mal Merkmal, jedes Merkmal "
            "zwischen 0 und 1. Ist kein Regler gesetzt, bleibt die neutrale Grundordnung nach Phase "
            "und Frist erhalten; bei Punktgleichheit ebenso."
        ),
        wirkung=Wirkung.REIHT,
        satzung="§ 2 Abs 6 letzter Satz · § 5 Abs 10 lit d",
        fassung=2,
        seit="2026-09-02",
        grund=(
            "Aus dem einen richtungslosen Regler „gestimmt“ wurden zwei — wofür und wogegen ich "
            "gestimmt habe —, „Nur noch kurz online“ misst seither die tatsächliche Phasendauer statt "
            "pauschal sechzig Tage, und jeder Antrag zeigt seinen Punktewert samt Aufschlüsselung. "
            "Weil jeden Regler das Mitglied für die eigene Ansicht selbst stellt und die Reihung ohne "
            "gesetzten Regler streng neutral bleibt, ist sie nach § 2 Abs 6 letzter Satz ausdrücklich "
            "keine Sortierung durch die Partei — offengelegt, versioniert und nachrechenbar ist sie "
            "trotzdem."
        ),
        nachrechenbar=(
            "Jeder Antrag im Feed nennt seine Punkte und die Aufschlüsselung nach den gesetzten "
            "Reglern. Wer die neun Werte mit den Merkmalen multipliziert und addiert, erhält dieselbe "
            "Zahl; unter /parameter/#weicherfilter steht die Regel Regler für Regler."
        ),
        registerschluessel="weicherfilter-regel",
    ),
    Regel(
        modul="vorschlagschat.py",
        titel="Abstimmungs-Chat: Reihung nach Engagement und Auswertung",
        zweck=(
            "Reiht die Beiträge zum Vorschlag des Expertenrats nach Beteiligung — Zustimmungen plus "
            "Ablehnungen, die Richtung zählt nicht — und wertet nach Fristablauf aus: Der "
            "Systembeitrag „Passt alles“ muss an erster Stelle stehen und mehr als die Hälfte "
            "Zustimmung tragen, sonst geht der Vorschlag mit der Kritik zurück an den Expertenrat. "
            "Bleibt jede Reaktion aus, gilt er als angenommen — Stille hemmt das Verfahren nie."
        ),
        wirkung=Wirkung.ENTSCHEIDET,
        satzung="§ 5 Abs 13 · § 5 Abs 12 · § 2 Abs 6",
        fassung=1,
        seit="2026-09-04",
        grund=(
            "Erste Fassung: Bis dahin klickten die Unterstützer ein Formular „annehmen / mit Wunsch "
            "zurückgeben“ an. Seither wird diese Entscheidung offen als Gespräch geführt, und eine "
            "Kritik zählt nur als Änderungswunsch, wenn sie sich auf einen benannten Absatz des "
            "Vorschlags bezieht."
        ),
        nachrechenbar=(
            "Jeder Beitrag zeigt seine Zustimmungen und Ablehnungen. Beteiligung = beide Zahlen "
            "addiert; bei Gleichstand entscheidet der höhere Zustimmungsanteil, dann der ältere "
            "Beitrag. Die Auswertung gibt Zahlen, Anteil und Schwelle mit aus, nicht nur ihr Ergebnis "
            "— sie steht so im Archiv."
        ),
        registerschluessel="vorschlag-chat-reihung",
    ),
    Regel(
        modul="faecher.py",
        titel="Favoriten-Fächer: Anordnung der Lebensbereiche",
        zweck=(
            "Berechnet, welche Knoten des Lebensbereiche-Baums im Favoriten-Feld erscheinen und wo "
            "sie stehen: fünf Ebenen um den angeklickten Anker, jede Ebene vollständig bis zwölf "
            "Knoten, darüber nur noch der entfaltete Ast mit höchstens drei Kindern und „+n“. Die "
            "Reihenfolge kommt aus dem Kategorienbaum selbst, nicht aus einer Bewertung von Anträgen "
            "oder Menschen."
        ),
        wirkung=Wirkung.REIHT,
        satzung="§ 5 Abs 10 lit a · § 2 Abs 6",
        fassung=2,
        seit="2026-09-02",
        grund=(
            "Beschriftungen überlappten und waren hart abgeschnitten („Bildungssy“, „Infrastruktu“). "
            "Die zweite Fassung zeigt immer fünf Ebenen, teilt jeder Pille eine Höchstbreite zu und "
            "kürzt Namen nie unter sechs Zeichen; der volle Name bleibt als Titel lesbar."
        ),
        nachrechenbar=(
            "Die Regel ist reine Geometrie und hängt an keiner Datenbank: Jede Ebene verteilt ihre "
            "Knoten gleichmäßig über 92 Prozent der Feldbreite, jede Pille erhält die Breite b = "
            "r·Spanne/(n−1+r). Die Rechenprobe über alle 312 Knoten und alle Äste zeigt, dass sich "
            "keine zwei sichtbaren Pillen überlappen."
        ),
        registerschluessel="faecher-regel",
    ),
    Regel(
        modul="similarity.py",
        titel="Ähnlichkeitshinweis beim Einbringen",
        zweck=(
            "Vergleicht einen neuen Antrag mit den offenen Anträgen und zeigt bis zu drei ähnliche "
            "samt ihrer Beteiligung an, damit sichtbar wird, wo sich Unterstützung bereits sammelt. "
            "Gerechnet wird ohne Modell: Beide Texte werden in Dreizeichenfolgen zerlegt, der Wert "
            "ist die Zahl der gemeinsamen geteilt durch die Zahl aller vorkommenden Folgen; ab 18 "
            "Prozent erscheint der Hinweis. Er schlägt vor und blockiert nie — „Trotzdem einbringen“ "
            "bleibt immer gleichwertig möglich."
        ),
        wirkung=Wirkung.ORDNET_ZU,
        satzung="§ 5 Abs 10 lit d · § 2 Abs 6",
        fassung=1,
        seit="2026-08-19",
        grund=(
            "Erste und bis heute einzige Fassung: Der Hinweis kam mit dem Einbringen im Browser, weil "
            "jede Eingabe zuerst zu einer Übersicht bereits gestellter ähnlicher Anträge führen soll. "
            "Bewusst rein lexikalisch gerechnet, damit jedes Mitglied den angezeigten Wert selbst "
            "überprüfen kann."
        ),
        nachrechenbar=(
            "Text kleinschreiben, Satzzeichen entfernen, in Dreizeichenfolgen zerlegen — der "
            "angezeigte Wert ist die Größe der Schnittmenge geteilt durch die Größe der "
            "Vereinigungsmenge. Mit Papier und Bleistift nachvollziehbar: kein Modell, kein Zufall, "
            "kein fremder Dienst."
        ),
        registerschluessel="aehnlichkeit-schwelle-prozent",
    ),
    Regel(
        modul="klassifikation.py",
        titel="Zuordnung der Anträge zu Lebensbereichen",
        zweck=(
            "Ordnet jeden neuen Antrag selbst in den Baum der Lebensbereiche ein, damit niemand "
            "Kategorien ankreuzen muss. Jeder Knoten bringt eine gepflegte Schlagwortliste mit; ein "
            "Schlagwort trifft, wenn ein Wort des Antragstexts damit beginnt. Punktestand je Knoten "
            "ist die Zahl der getroffenen Schlagworte, die tiefste passende Ebene gewinnt. Die "
            "Zuordnung ist ein Vorschlag ohne Sperrwirkung und durch Menschen korrigierbar."
        ),
        wirkung=Wirkung.ORDNET_ZU,
        satzung="§ 5 Abs 10 lit d · § 2 Abs 6",
        fassung=1,
        seit="2026-08-19",
        grund=(
            "Erste Fassung: Mit dem Kategorienbaum fiel die Entscheidung, die Einordnung nicht dem "
            "Einbringenden aufzubürden und sie trotzdem ohne künstliche Intelligenz zu treffen — über "
            "gepflegte Schlagwortlisten, die jeder nachlesen kann."
        ),
        nachrechenbar=(
            "Die Schlagwortlisten stehen offen in der Datei policies/kategorien-v2.yaml. Wer zählt, "
            "wie viele davon im eigenen Antragstext vorkommen, erhält denselben Punktestand; jede "
            "Zuordnung steht zusätzlich mit dem Vermerk „schlagworte-v1“ im Prüfprotokoll."
        ),
        registerschluessel="kategorien-regel",
    ),
    Regel(
        modul="rollen.py",
        titel="Rollenmatrix „Wer darf was“",
        zweck=(
            "Führt für jede der vierzehn Rollen der Partei auf, was die Satzung ihr aufträgt und was "
            "die Software heute davon kann — Fähigkeit für Fähigkeit mit ● verfügbar, ◐ teilweise "
            "oder ○ geplant, bei Geplantem mit dem Bauschritt. Die Matrix wählt nichts aus, reiht "
            "nichts und öffnet keine Zugänge; sie ist eine Auskunft über den Bauzustand."
        ),
        wirkung=Wirkung.STELLT_DAR,
        satzung="§ 6 · § 3 Abs 1 lit c",
        fassung=1,
        seit="2026-09-05",
        grund=(
            "Erste Fassung: Bis dahin ließ sich nirgends nachlesen, welche Rechte die Satzung einer "
            "Rolle gibt und welche davon schon gebaut sind. Seither steht das öffentlich unter "
            "/rollen/ — mit dem Stand von 164 Fähigkeiten, davon 66 verfügbar, 33 teilweise und 65 "
            "geplant."
        ),
        nachrechenbar=(
            "Die Zahlen unter der Übersicht sind die ausgezählten Zeilen der Tabelle darüber; wer "
            "nachzählt, kommt auf dieselbe Summe. Zwölf Tests halten die Matrix gegen die Rollen, die "
            "es im Code wirklich gibt: kein ○ ohne Bauschritt, kein ◐ ohne Angabe, was fehlt."
        ),
    ),
    Regel(
        modul="schema.py",
        titel="Sprachneutrales Parameter-Schema",
        zweck=(
            "Übersetzt die deutschen Stellgrößen dieser Instanz in englische, überall gleich "
            "bedeutende Kennungen und baut daraus die offen abrufbaren Dateien /parameter.json und "
            "/kennzahlen.json. Umgekehrt prüft es den Export einer Partnerinstanz gegen dasselbe "
            "Schema und beanstandet jedes personenbezogene Feld."
        ),
        wirkung=Wirkung.STELLT_DAR,
        satzung="§ 12 Abs 5; § 2 Abs 6",
        fassung=None,
        seit="2026-09-05",
        grund=(
            "Fünfundzwanzig weitere Stellgrößen bekamen eine englische Kennung, damit Partnerparteien "
            "im Ausland ihre eigenen Werte mit unseren vergleichen können, ohne Deutsch zu lesen."
        ),
        nachrechenbar=(
            "Die Kennungen stehen offen in /parameter.json und /kennzahlen.json, dort jeweils neben "
            "dem deutschen Schlüssel. (docs/SCHEMA.md steht noch auf Fassung 1.0 und führt erst zwölf "
            "der Kennungen — die Datei ist die kürzere Quelle, die Schnittstelle die vollständige.)"
        ),
    ),
    Regel(
        modul="wortdiff.py",
        titel="Wortweiser Vergleich zweier Fassungen",
        zweck=(
            "Vergleicht den ursprünglichen Antrag mit dem Vorschlag des Expertenrats und markiert "
            "Wort für Wort, was hinzugekommen und was weggefallen ist. Wer über den Vorschlag "
            "abstimmt, sieht damit, was daran geändert wurde."
        ),
        wirkung=Wirkung.STELLT_DAR,
        satzung="§ 5 Abs 12 und Abs 13; § 2 Abs 6",
        fassung=1,
        seit="2026-09-04",
        grund=(
            "Der Vergleich arbeitet auf Wörtern statt auf Zeilen, damit ein umformulierter Satz die "
            "drei geänderten Wörter zeigt und nicht den ganzen Absatz als ausgetauscht — sonst wäre "
            "nicht erkennbar, wie viel wirklich anders ist."
        ),
        nachrechenbar=(
            "Antrag und Vorschlag bleiben beide dauerhaft öffentlich einsehbar; wer die zwei Texte "
            "selbst nebeneinanderlegt, muss auf dieselben geänderten Wörter kommen. Das Modul färbt "
            "nur, es wählt nichts aus."
        ),
    ),
    Regel(
        modul="diagramme.py",
        titel="Servergerenderte SVG-Diagramme",
        zweck=(
            "Zeichnet die Bilder der öffentlichen Übersichtsseite — Verlaufslinie, Säulen je Zeitraum "
            "und den 100-Prozent-Balken einer Abstimmung — direkt auf dem Server, ohne JavaScript und "
            "ohne fremde Diagramm-Bibliothek. Es rechnet nur die Achsenwerte und die Länge der Balken "
            "aus den bereits veröffentlichten Zahlen."
        ),
        wirkung=Wirkung.STELLT_DAR,
        satzung="§ 5 Abs 3 lit e · § 2 Abs 6",
        fassung=None,
        seit="2026-08-26",
        grund=(
            "Seit es die dunkle Ansicht gibt, bringt jedes Diagramm seinen eigenen hellen Grund mit: "
            "Die auf Farbfehlsichtigkeit geprüfte Farbwahl gilt nur auf hellem Papier, und ein Bild, "
            "das man nicht lesen kann, ist keine Auskunft."
        ),
        nachrechenbar=(
            "Jede Zahl im Bild steht auf derselben Seite auch als Text (ADR-008), und die Tooltips "
            "nennen den Wert beim Überfahren. Farbe trägt nie allein die Information; wer die Zahlen "
            "addiert, kommt auf dieselben Anteile."
        ),
    ),
    Regel(
        modul="beitraege.py",
        titel="Beitragsabgleich: Zahlung zu Mitglied",
        zweck=(
            "Sucht in den Gutschriften des Vereinskontos die persönliche Beitragsreferenz (Form "
            "DDOE-0042-A1B2C3) und ordnet den Eingang dem Mitglied zu, dem diese Referenz gehört. "
            "Eingänge ohne bekannte Referenz fallen still heraus; vom Absender bleibt nur ein "
            "Ja/Nein, ob sein Name zum Mitglied passt — IBAN und Klarname verlassen den Abgleich nie."
        ),
        wirkung=Wirkung.ORDNET_ZU,
        satzung="§ 4 Abs 3; § 2 Abs 6; § 8",
        fassung=1,
        seit="2026-08-31",
        grund=(
            "Damit ein Mitglied nach seiner Überweisung nicht darauf warten muss, dass jemand den "
            "Eingang von Hand nachträgt: Der Beitrag wird selbst erkannt, eine Beitragspause endet, "
            "und die Mitwirkung ist wieder frei."
        ),
        nachrechenbar=(
            "Die eigene Referenz steht auf der Beitragsseite /beitrag/, dort auch die private Liste "
            "der eigenen Eingänge mit Betrag und Buchungstag — zum Vergleich mit dem eigenen "
            "Kontoauszug. Gesucht wird nach einem offenen Muster: die Buchstaben DDOE, eine "
            "vierstellige Nummer, sechs Zeichen aus A–F und Ziffern; Trennstriche und Kleinschreibung "
            "sind dabei gleichgültig."
        ),
    ),
    Regel(
        modul="bankauszug.py",
        titel="Kontoauszug-Leser (camt.053 und CSV)",
        zweck=(
            "Liest eine aus dem Online-Banking heruntergeladene Umsatzdatei — camt.053-XML oder CSV — "
            "und übergibt die Gutschriften in derselben schlanken Form an den Beitragsabgleich wie "
            "ein Bankdienst. Ausgaben des Vereinskontos werden übergangen, die Datei selbst nie "
            "gespeichert."
        ),
        wirkung=Wirkung.RECHNET,
        satzung="§ 4 Abs 3; § 2 Abs 6",
        fassung=None,
        seit="2026-08-31",
        grund=(
            "Weil kein Kontoinformationsdienst verfügbar war, sollte der Beitragsabgleich trotzdem "
            "sofort funktionieren: Wer die Umsatzliste aus dem Online-Banking hochlädt, bekommt "
            "dieselbe Zuordnung, dieselbe Freischaltung und dieselben Prüfhinweise wie über die "
            "Bankschnittstelle."
        ),
        nachrechenbar=(
            "Dieselbe Datei zweimal eingelesen ergibt dieselben Umsätze. Wo die Bank keine Referenz "
            "liefert, bildet sich die Kennung als 'csv-' gefolgt von den ersten 32 Zeichen der "
            "SHA-256-Prüfsumme über Buchungstag, Betrag und Verwendungszweck, verbunden mit je einem "
            "senkrechten Strich — mit jedem Prüfsummenwerkzeug nachrechenbar."
        ),
    ),
    Regel(
        modul="kurztext.py",
        titel="Leser der Partner-Kurzfassungen",
        zweck=(
            "Liest die fremdsprachigen Kurzfassungen der Einladung an Partnerparteien aus dem "
            "Repository und zerlegt sie in Überschrift, Absätze und den kursiven Schlusssatz. Das "
            "Arbeitsmaterial hinter dem waagrechten Strich — Glossar und offene Punkte für "
            "Muttersprachler — bleibt draußen."
        ),
        wirkung=Wirkung.STELLT_DAR,
        satzung="§ 12 Abs 1 · § 12 Abs 2",
        fassung=1,
        seit="2026-09-04",
        grund=(
            "Damit die Einladung in Französisch, Spanisch, Italienisch und Japanisch als eigene Seite "
            "erscheinen kann, ohne dass die internen Notizen aus derselben Datei versehentlich mit "
            "auf die Seite geraten."
        ),
        nachrechenbar=(
            "Die Quelldateien liegen offen unter docs/partner/kurz/; wer Seite und Datei "
            "nebeneinanderlegt, sieht denselben Text. Was der Leser nicht kennt — etwa Tabellen oder "
            "Listen —, erscheint unverändert als Absatz: Es verschwindet nichts unbemerkt."
        ),
    ),
)
