"""Was das Parameterregister niemals dürfen darf (FB-J4, Grundregel 4).

A0-03: „all diese regelungen kann der koordinationsrat nutzen um leichte weichenstellungen
vorzunehmen **ohne dabei Stimmdifferenzierung zuzulassen**." Satzung § 6 Abs 11 lit c letzter
Satz. Der Schutz dagegen kann nicht in einer Prüfung beim Speichern liegen — er liegt darin,
dass es **keinen solchen Parameter gibt** und die Auszählung keinen lesen könnte.
"""

from __future__ import annotations

import pathlib
import re

from parameter.models import ERSTBESTAND
from plattform_core import tally

WURZEL = pathlib.Path(__file__).resolve().parent.parent

#: Wortstämme, die auf eine Gewichtung von Stimmen hindeuten.
VERDACHT = ("gewicht", "faktor", "multiplikator", "weight", "bonus", "malus", "punkte_je_stimme")


def test_kein_parameter_gewichtet_eine_stimme():
    """Kein Eintrag im Register darf auch nur nach Stimmgewichtung klingen."""
    fehler = []
    for eintrag in ERSTBESTAND:
        text = f"{eintrag['schluessel']} {eintrag.get('beschreibung', '')}".lower()
        for wort in VERDACHT:
            if wort in eintrag["schluessel"].lower():
                fehler.append(f"{eintrag['schluessel']}: Schlüssel enthält „{wort}“")
            elif wort in text and "stimm" in text:
                fehler.append(f"{eintrag['schluessel']}: Beschreibung verbindet „{wort}“ mit Stimmen")
    assert not fehler, "Grundregel 4 — keine Stimmgewichtung:\n  " + "\n  ".join(fehler)


def test_die_auszaehlung_liest_kein_register():
    """Die Auszählung darf keinen Parameter lesen — sonst könnte ein Wert das Ergebnis biegen.

    Sie bekommt ihre Schwellen aus der **eingefrorenen** Verfahrensordnung des Antrags
    (§ 5 Abs 5), nicht aus dem laufenden Register."""
    quelle = (WURZEL / "plattform_core/tally.py").read_text(encoding="utf-8")
    assert "parameter" not in quelle.lower(), "die Auszählung greift auf das Register zu"
    assert "import" not in quelle or "django" not in quelle.lower(), "der Kern bleibt frei von Django"


def test_jede_stimme_zaehlt_eins():
    """Die Rechnung selbst: drei Ja sind drei, nicht 3,5 — gleich, von wem sie kommen."""
    from plattform_core.policy import Policy

    ordnung = Policy(
        id="probe", version=1, unterstuetzung_schwelle=1, unterstuetzung_frist_tage=60,
        beratung_tage=21, abstimmung_tage=28, mindestbeteiligung=0.05,
    )
    stimmen = [("p1", "ja"), ("p2", "ja"), ("p3", "ja"), ("p4", "nein"), ("p5", "enthaltung")]
    ergebnis = tally.auszaehlen(stimmen, stimmberechtigte=20, policy=ordnung)
    assert (ergebnis.ja, ergebnis.nein, ergebnis.enthaltung) == (3, 1, 1)
    assert all(isinstance(w, int) for w in (ergebnis.ja, ergebnis.nein, ergebnis.enthaltung))
    # Dieselben fünf Stimmen in anderer Reihenfolge ergeben dasselbe — niemand zählt doppelt
    andere = tally.auszaehlen(list(reversed(stimmen)), stimmberechtigte=20, policy=ordnung)
    assert (andere.ja, andere.nein, andere.enthaltung) == (3, 1, 1)


#: Wo Stimmen gezählt und Ergebnisse festgestellt werden. Nur hier wäre eine Gewichtung
#: überhaupt wirksam — im WeicherFilter meint „Gewicht" die Stellung eines Reglers, der
#: ausschließlich die eigene Ansicht sortiert und keine einzige Stimme berührt.
STIMMENDE_MODULE = ("tally.py", "eligibility.py")


def _nur_code(quelle: str) -> str:
    """Der ausführbare Teil einer Datei — ohne Docstrings und Kommentare.

    Beides erklärt, was der Code tut, und darf dabei Wörter verwenden, die im Code selbst
    ein Alarmzeichen wären („Kreuzmultiplikation", „gestimmt"). Geprüft wird, was läuft."""
    import ast

    baum = ast.parse(quelle)
    for knoten in ast.walk(baum):
        if isinstance(knoten, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if (
                knoten.body
                and isinstance(knoten.body[0], ast.Expr)
                and isinstance(knoten.body[0].value, ast.Constant)
                and isinstance(knoten.body[0].value.value, str)
            ):
                knoten.body.pop(0)  # der Docstring
    return ast.unparse(baum)


def test_kein_code_multipliziert_eine_stimme():
    """In den Modulen, die Stimmen zählen, wird keine Stimme mit irgendetwas multipliziert."""
    verdaechtig = []
    for name in STIMMENDE_MODULE:
        quelle = _nur_code((WURZEL / "plattform_core" / name).read_text(encoding="utf-8"))
        for nr, zeile in enumerate(quelle.splitlines(), 1):
            if re.search(r"(stimm|ja|nein|enthaltung)\w*\s*\*[^*]|gewicht|faktor|multiplik", zeile, re.I):
                verdaechtig.append(f"{name} (entkleidet):{nr}: {zeile.strip()[:80]}")
    assert not verdaechtig, "Verdacht auf Stimmgewichtung:\n  " + "\n  ".join(verdaechtig)


def test_der_weicherfilter_wirkt_nur_auf_die_eigene_ansicht():
    """Zur Abgrenzung: Der WeicherFilter gewichtet — aber Anzeigeplätze, nicht Stimmen.

    Er darf das (§ 5 Abs 10 lit d: die Reihung gehört dem Mitglied), solange er nachweislich
    nichts an der Auszählung ändert. Dieser Test hält die Grenze fest, damit niemand später
    das eine für das andere hält. Geprüft wird der ausführbare Code — in den Erklärungen darf
    „gestimmt" vorkommen, denn zwei der neun Regler heißen genau so."""
    code = _nur_code((WURZEL / "plattform_core/weicherfilter.py").read_text(encoding="utf-8")).lower()
    for verboten in ("auszaehl", "tally", "stimmberechtigt", "mehrheit"):
        assert verboten not in code, f"der WeicherFilter fasst {verboten} an"
