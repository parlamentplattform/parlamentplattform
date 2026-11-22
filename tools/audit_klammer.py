"""Stellt für jeden Aufruf von `AuditEintrag.anhaengen` außerhalb der Tests fest, ob er mit der
schreibenden Handlung in einer Transaktion steht (GP-129; CLAUDE.md § 4: jede schreibende
Verwaltungs- oder Gremienhandlung schreibt ihren Audit-Eintrag in derselben Transaktion).

    python tools/audit_klammer.py          # alle Aufrufstellen mit Einstufung
    python tools/audit_klammer.py --offen  # nur die ungeklärten (Ausgang 1, wenn es welche gibt)

Einstufung je Aufrufstelle (Datei und umschließende Funktion):

- ``atomic``: lexikalisch gefasst, also innerhalb von ``with transaction.atomic()`` oder in einer
  Funktion mit ``@transaction.atomic`` (auch einer äußeren Funktion derselben Datei).
- ``aufrufer``: die umschließende Funktion wird außerhalb der Tests nur aus gefassten Stellen
  aufgerufen (Aufrufgraph bis zum Fixpunkt; Rekursion und Funktionen ohne Aufrufer zählen nicht
  als gefasst). Ein Methodenaufruf ``x.m()`` wird der Klasse zugeordnet, deren Name dem
  Empfänger entspricht (``entwurf.m()`` → ``Entwurf.m``), ``self.m()`` der eigenen Klasse;
  sonst zählt er für jede Methode dieses Namens. Aufrufe aus einer Verteilertabelle
  (``VERMITTLER``) zählen als Aufrufe der Funktion, die die Tabelle liest.
- ``begruendet``: nicht gefasst, aber in ``BEGRUENDET`` mit einem Satz begründet, warum keine
  gemeinsame Transaktion nötig ist (etwa: der Audit-Eintrag ist die einzige Schreibhandlung).
- ``gemeldet``: nicht gefasst und als zu fassen erkannt; die Fassung liegt bei der zuständigen
  App (``ZU_FASSEN``). Wer die Stelle fasst, streicht sie dort.
- ``offen``: nichts davon. Der Wächter ``parameter/test_audit_klammer.py`` lässt keine offene
  Stelle zu.

Die Prüfung ist rein lexikalisch (``ast``) und führt nichts aus. Schlüssel der Listen ist
``"pfad/datei.py:Klasse.funktion"``, damit verschobene Zeilen nichts ändern.
"""

from __future__ import annotations

import ast
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
AUSGENOMMEN = {"venv", ".venv", "node_modules", "migrations", "e2e", "output", "docs", ".git"}

# Dateien, deren Aufrufe im Aufrufgraphen nicht zählen: Sie laufen nie im Betrieb.
NUR_DEMO = {"verfahren/management/commands/demo_seed.py"}

# Verteilertabellen auf Modulebene: Aufrufe in ihren Lambdas gelten als Aufrufe der Funktion,
# die die Tabelle liest ("datei:Tabellenname" -> Funktionsname).
VERMITTLER: dict[str, str] = {
    "gremien/models.py:WIRKUNGEN": "wirkung_anwenden",
}

# Nicht gefasste Stellen, die keine gemeinsame Transaktion brauchen — je ein Satz, warum.
BEGRUENDET: dict[str, str] = {
    "anstoss/views.py:_ausfuhr_vermerken": (
        "Die Ausfuhr der Anstöße liest nur; der Eintrag ist ihre einzige Schreibhandlung und steht "
        "vor der Antwort, sodass ohne Eintrag keine Datei hinausgeht."
    ),
    "faktenbasis/ris_historie.py:abrufen": (
        "Die beiden ungefassten Einträge sind die einzige Schreibhandlung ihres Zweigs (leere "
        "Trefferseite, gescheiterter Abruf); der Fehlereintrag muss gerade die Rücknahme der "
        "Archivierung überdauern, das Archivieren selbst steht mit seinem Eintrag in einer Transaktion."
    ),
    "faktenbasis/verwaltung.py:_audit": (
        "Zusatzvermerk, wer einen Abruf ausgelöst hat: Der Importlauf speichert sich mit eigenem "
        "Audit-Eintrag in eigener Transaktion, und ein Netzabruf soll keine Datenbanktransaktion offen halten."
    ),
    "mitglieder/post.py:_senden": (
        "Hält einen schon erfolgten E-Mail-Versand fest, der sich nicht zurückrollen lässt; außer "
        "dem Audit-Eintrag schreibt die Funktion nichts."
    ),
    "verfahren/management/commands/demo_seed.py:hervorhebungen_ohne_beschluss_zuruecknehmen": (
        "Läuft nur beim Anlegen der Demodaten (DDOE_DEMO=1), nie im Betrieb; die Demodaten werden "
        "bei einem Fehler ohnehin neu angelegt."
    ),
}

# Nicht gefasste Stellen, die gefasst werden sollen: Schlüssel -> zuständiges Paket und wo die
# Klammer hingehört. Wer eine Stelle fasst, streicht ihre Zeile. Seit der Schlusspflege 0.115.0
# (GP-129) leer: Die 31 Stellen aus Stand 0.114.0 sind gefasst.
ZU_FASSEN: dict[str, str] = {}


@dataclass(frozen=True)
class Stelle:
    datei: str
    funktion: str
    zeile: int
    einstufung: str

    @property
    def schluessel(self) -> str:
        return f"{self.datei}:{self.funktion}"


def _ist_atomic(knoten: ast.AST) -> bool:
    """`transaction.atomic` oder `atomic`, jeweils auch als Aufruf (`atomic()`, `atomic(using=…)`)."""
    if isinstance(knoten, ast.Call):
        knoten = knoten.func
    if isinstance(knoten, ast.Attribute):
        return knoten.attr == "atomic"
    if isinstance(knoten, ast.Name):
        return knoten.id == "atomic"
    return False


def _ist_anhaengen(knoten: ast.Call) -> bool:
    return (
        isinstance(knoten.func, ast.Attribute)
        and knoten.func.attr == "anhaengen"
        and isinstance(knoten.func.value, ast.Name)
        and knoten.func.value.id == "AuditEintrag"
    )


@dataclass
class _Aufruf:
    """Ein Aufruf im Graphen: wer ruft (Definitionsschlüssel), ob lexikalisch gefasst, und wie
    der Aufgerufene heißt (Name, Empfänger, ob über `self` in welcher Klasse)."""

    aufrufer: str
    gefasst: bool
    name: str
    empfaenger: str | None
    klasse_self: str | None


@dataclass
class _Rohstelle:
    datei: str
    funktion: str  # qualifizierter Pfad ("Klasse.methode.innere") oder "<modul>"
    definition: str  # Knoten im Aufrufgraphen ("Klasse.methode" oder "funktion")
    zeile: int
    gefasst: bool


@dataclass
class _Bestand:
    stellen: list[_Rohstelle] = field(default_factory=list)
    aufrufe: list[_Aufruf] = field(default_factory=list)
    methoden: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    funktionen: set[str] = field(default_factory=set)


class _Sucher(ast.NodeVisitor):
    def __init__(self, datei: str, bestand: _Bestand) -> None:
        self.datei = datei
        self.bestand = bestand
        self.pfad: list[str] = []
        self.klassen: list[str] = []
        self.definitionen: list[str] = []
        self.gefasst = 0

    def _definition(self) -> str:
        return self.definitionen[-1] if self.definitionen else "<modul>"

    def _funktion(self, knoten: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        for dekorator in knoten.decorator_list:
            self.visit(dekorator)
        dekoriert = any(_ist_atomic(d) for d in knoten.decorator_list)
        in_klasse = bool(self.klassen) and self.pfad and self.pfad[-1] == self.klassen[-1]
        if in_klasse:
            schluessel = f"{self.klassen[-1]}.{knoten.name}"
            self.bestand.methoden[knoten.name].add(self.klassen[-1])
        else:
            schluessel = knoten.name
            self.bestand.funktionen.add(knoten.name)
        self.pfad.append(knoten.name)
        self.definitionen.append(schluessel)
        self.gefasst += dekoriert
        for anweisung in knoten.body:
            self.visit(anweisung)
        self.gefasst -= dekoriert
        self.definitionen.pop()
        self.pfad.pop()

    visit_FunctionDef = _funktion
    visit_AsyncFunctionDef = _funktion

    def visit_ClassDef(self, knoten: ast.ClassDef) -> None:
        self.pfad.append(knoten.name)
        self.klassen.append(knoten.name)
        self.generic_visit(knoten)
        self.klassen.pop()
        self.pfad.pop()

    def visit_Assign(self, knoten: ast.Assign) -> None:
        vermittler = None
        if not self.definitionen:
            for ziel in knoten.targets:
                if isinstance(ziel, ast.Name):
                    vermittler = VERMITTLER.get(f"{self.datei}:{ziel.id}") or vermittler
        if vermittler:
            self.definitionen.append(vermittler)
            self.generic_visit(knoten)
            self.definitionen.pop()
        else:
            self.generic_visit(knoten)

    def visit_With(self, knoten: ast.With) -> None:
        gefasst = any(_ist_atomic(eintrag.context_expr) for eintrag in knoten.items)
        for eintrag in knoten.items:
            self.visit(eintrag)
        self.gefasst += gefasst
        for anweisung in knoten.body:
            self.visit(anweisung)
        self.gefasst -= gefasst

    def visit_Call(self, knoten: ast.Call) -> None:
        if _ist_anhaengen(knoten):
            self.bestand.stellen.append(
                _Rohstelle(
                    self.datei,
                    ".".join(self.pfad) or "<modul>",
                    self._definition(),
                    knoten.lineno,
                    bool(self.gefasst),
                )
            )
        elif self.datei not in NUR_DEMO:
            funk = knoten.func
            if isinstance(funk, ast.Name):
                self.bestand.aufrufe.append(_Aufruf(self._definition(), bool(self.gefasst), funk.id, None, None))
            elif isinstance(funk, ast.Attribute):
                wert = funk.value
                empfaenger = wert.id if isinstance(wert, ast.Name) else wert.attr if isinstance(wert, ast.Attribute) else None
                klasse_self = self.klassen[-1] if empfaenger == "self" and self.klassen else None
                self.bestand.aufrufe.append(
                    _Aufruf(self._definition(), bool(self.gefasst), funk.attr, empfaenger, klasse_self)
                )
        self.generic_visit(knoten)


def _ziele(aufruf: _Aufruf, bestand: _Bestand) -> list[str]:
    """Die Definitionen, die dieser Aufruf treffen kann."""
    klassen = bestand.methoden.get(aufruf.name, set())
    if aufruf.empfaenger is None:
        return [aufruf.name] if aufruf.name in bestand.funktionen else []
    if aufruf.klasse_self and aufruf.klasse_self in klassen:
        return [f"{aufruf.klasse_self}.{aufruf.name}"]
    passend = [k for k in klassen if k.lower() == (aufruf.empfaenger or "").lower()]
    if passend:
        return [f"{k}.{aufruf.name}" for k in passend]
    ziele = [f"{k}.{aufruf.name}" for k in sorted(klassen)]
    if aufruf.name in bestand.funktionen:
        ziele.append(aufruf.name)  # modul.funktion(...)
    return ziele


def _gefasste_definitionen(bestand: _Bestand) -> set[str]:
    """Kleinster Fixpunkt: Eine Definition ist gefasst, wenn sie aufgerufen wird und jeder
    Aufruf, der sie treffen kann, lexikalisch gefasst ist oder aus einer gefassten Definition kommt."""
    eingehend: dict[str, list[tuple[str, bool]]] = defaultdict(list)
    for aufruf in bestand.aufrufe:
        for ziel in _ziele(aufruf, bestand):
            eingehend[ziel].append((aufruf.aufrufer, aufruf.gefasst))
    gefasst: set[str] = set()
    while True:
        neu = {
            ziel
            for ziel, liste in eingehend.items()
            if liste and all(lex or aufrufer in gefasst for aufrufer, lex in liste)
        }
        if neu == gefasst:
            return gefasst
        gefasst = neu


def _ist_testdatei(pfad: Path) -> bool:
    return pfad.name.startswith("test") or pfad.name == "conftest.py" or "tests" in pfad.parts


def bestand_lesen(wurzel: Path = WURZEL) -> _Bestand:
    bestand = _Bestand()
    for pfad in sorted(wurzel.rglob("*.py")):
        relativ = pfad.relative_to(wurzel)
        if AUSGENOMMEN & set(relativ.parts) or _ist_testdatei(relativ):
            continue
        baum = ast.parse(pfad.read_text(encoding="utf-8"), filename=str(pfad))
        _Sucher(relativ.as_posix(), bestand).visit(baum)
    return bestand


def stellen(wurzel: Path = WURZEL) -> list[Stelle]:
    """Alle Aufrufstellen außerhalb der Tests mit Einstufung, sortiert nach Datei und Zeile."""
    bestand = bestand_lesen(wurzel)
    gefasst = _gefasste_definitionen(bestand)
    ergebnis: list[Stelle] = []
    for r in bestand.stellen:
        schluessel = f"{r.datei}:{r.funktion}"
        if r.gefasst:
            einstufung = "atomic"
        elif r.definition in gefasst:
            einstufung = "aufrufer"
        elif schluessel in BEGRUENDET:
            einstufung = "begruendet"
        elif schluessel in ZU_FASSEN:
            einstufung = "gemeldet"
        else:
            einstufung = "offen"
        ergebnis.append(Stelle(r.datei, r.funktion, r.zeile, einstufung))
    return ergebnis


def veraltete_eintraege(gefunden: list[Stelle]) -> list[str]:
    """Einträge in BEGRUENDET oder ZU_FASSEN ohne passende ungefasste Stelle (zum Aufräumen)."""
    noch_da = {s.schluessel for s in gefunden if s.einstufung in ("begruendet", "gemeldet")}
    return sorted((set(BEGRUENDET) | set(ZU_FASSEN)) - noch_da)


def main(argv: list[str]) -> int:
    gefunden = stellen()
    nur_offen = "--offen" in argv
    for stelle in gefunden:
        if nur_offen and stelle.einstufung != "offen":
            continue
        zusatz = f"  [{ZU_FASSEN[stelle.schluessel]}]" if stelle.einstufung == "gemeldet" else ""
        print(f"{stelle.einstufung:10} {stelle.datei}:{stelle.zeile}  {stelle.funktion}{zusatz}")
    zaehlung: dict[str, int] = defaultdict(int)
    for stelle in gefunden:
        zaehlung[stelle.einstufung] += 1
    print(" · ".join(f"{name}: {zahl}" for name, zahl in sorted(zaehlung.items())))
    for schluessel in veraltete_eintraege(gefunden):
        print(f"veraltet   {schluessel}")
    return 1 if zaehlung.get("offen") else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
