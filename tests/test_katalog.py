"""Der Übersetzungskatalog gegen den Code — in beide Richtungen (Gesamtprüfung 0.45, Cluster D).

Anlass: 21 Texte der Beschluss- und Aussetzungs-Views (0.43/0.44), der Auslosungshinweis, das
aria-label des Fristrings und zwölf Beschriftungen des Markdown-Exports waren mit `_()` oder
`{% translate %}` markiert und hatten trotzdem keinen Katalogeintrag — auf Englisch blieben sie
deutsch, und kein Test merkte es (Befunde #60, #61, #88). Dazu vierzehn von Hand mit rohen
Zeilenumbrüchen geschriebene Einträge, die `tools/po_pruefen.py` stumm verstümmelte (#58, #59),
und rund sechzig Einträge, die kein Code mehr nennt (#92).

Ohne `gettext` auf dem Arbeitsplatz gibt es kein `makemessages`; diese Datei ersetzt den
Abgleich, den es leisten würde: Vorlagen per Regex (mit Djangos `%`-Maskierung und
`{{ var }}` → `%(var)s`), Python per `ast`, dazu `_("…")` in Filterargumenten und Tag-Parametern.
"""

from __future__ import annotations

import ast
import pathlib
import re
import sys

import pytest

WURZEL = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WURZEL / "tools"))

from po_pruefen import PO, KatalogFehler, lesen  # noqa: E402

KONTEXT_TRENNER = "\x04"
PLURAL_TRENNER = "\x00"  # so bildet die .mo den Schlüssel eines Pluralpaars
GETTEXT_NAMEN = {
    "_", "gettext", "gettext_lazy", "gettext_noop", "ngettext", "ngettext_lazy",
    "pgettext", "pgettext_lazy", "npgettext", "npgettext_lazy",
}
AUSGESCHLOSSENE_TEILE = {".venv", "venv", "node_modules", "__pycache__", "docs", "_to_delete"}

#: Katalogeinträge ohne Fundstelle im Code, die trotzdem bleiben — mit Grund.
BEWUSST_OHNE_FUNDSTELLE = {
    # Die Sprachnamen des Umschalters stehen in ihrer eigenen Sprache und werden nie übersetzt;
    # der Eintrag hält sie im Katalog sichtbar, damit sie beim nächsten makemessages nicht fehlen.
    "DE · Deutsch",
    "EN · English",
}

#: Texte im Code ohne Katalogeintrag, die bewusst unübersetzt bleiben — mit Grund.
BEWUSST_OHNE_EINTRAG: set[str] = set()


def _dateien(muster: str) -> list[pathlib.Path]:
    return sorted(
        d for d in WURZEL.rglob(muster) if not (set(d.parts) & AUSGESCHLOSSENE_TEILE)
    )


def _literal(roh: str) -> str:
    """Ein Vorlagen-Stringliteral: umschließende Anführungszeichen weg, Maskierung auflösen."""
    roh = roh.strip()
    if len(roh) >= 2 and roh[0] == roh[-1] and roh[0] in "\"'":
        innen = roh[1:-1]
        return innen.replace("\\" + roh[0], roh[0])
    return roh


def _trim(text: str) -> str:
    """Djangos `trimmed`: Zeilenumbrüche samt Randleerraum werden ein Leerzeichen."""
    return re.sub(r"\s*\n\s*", " ", text.strip())


def _blocktext(rumpf: str) -> str:
    """Djangos Schlüsselbildung für den Rumpf eines blocktranslate:
    `%` → `%%`, `{{ var }}` → `%(var)s` (django/templatetags/i18n.py)."""
    teile = []
    for stueck in re.split(r"(\{\{\s*[\w.]+\s*\}\})", rumpf):
        m = re.fullmatch(r"\{\{\s*([\w.]+)\s*\}\}", stueck)
        if m:
            teile.append(f"%({m.group(1)})s")
        else:
            teile.append(stueck.replace("%", "%%"))
    return "".join(teile)


TRANSLATE = re.compile(
    r"\{%\s*trans(?:late)?\s+(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')((?:(?!%\}).)*)%\}", re.S
)
BLOCK = re.compile(
    r"\{%\s*blocktrans(?:late)?\b((?:(?!%\}).)*)%\}(.*?)\{%\s*endblocktrans(?:late)?\s*%\}", re.S
)
INLINE_GETTEXT = re.compile(r"\b_\(\s*(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')\s*\)")
KONTEXT = re.compile(r"\bcontext\s+(\"(?:[^\"\\]|\\.)*\"|'(?:[^'\\]|\\.)*')")


def texte_der_vorlage(quelle: str) -> set[str]:
    """Alle Katalogschlüssel, die eine Vorlage bei der Auslieferung nachschlägt."""
    schluessel: set[str] = set()
    for m in TRANSLATE.finditer(quelle):
        text, rest = _literal(m.group(1)), m.group(2)
        k = KONTEXT.search(rest)
        schluessel.add(f"{_literal(k.group(1))}{KONTEXT_TRENNER}{text}" if k else text)
    for m in BLOCK.finditer(quelle):
        kopf, rumpf = m.group(1), m.group(2)
        trimmed = re.search(r"\btrimmed\b", kopf) is not None
        k = KONTEXT.search(kopf)
        praefix = f"{_literal(k.group(1))}{KONTEXT_TRENNER}" if k else ""
        singular, _, plural = rumpf.partition("{% plural %}")
        if "{% plural %}" in rumpf:
            # ngettext sucht den Schlüssel „singular\x00plural“ — zwei getrennte msgid-Einträge
            # fände es nicht; deshalb wird hier das Paar verlangt (msgid + msgid_plural).
            paar = [_blocktext(_trim(t) if trimmed else t) for t in (singular, plural)]
            schluessel.add(praefix + PLURAL_TRENNER.join(paar))
        else:
            schluessel.add(praefix + _blocktext(_trim(singular) if trimmed else singular))
    for m in INLINE_GETTEXT.finditer(quelle):
        schluessel.add(_literal(m.group(1)))
    return schluessel


#: Module, deren `_` eine No-op-Markierung ist (plattform_core bleibt Django-frei): Die Texte
#: sind für den Katalog vorgemerkt, ihre Übersetzung ist Datenpflege und darf nachkommen —
#: die Vorlagen übersetzen sie per `{% translate variable %}`, sobald ein Eintrag da ist (#90).
NOOP_MODULE = {"plattform_core/rollen.py", "plattform_core/regelwerk.py"}


def texte_der_python_datei(quelle: str, alles_vorgemerkt: bool = False) -> dict[str, bool]:
    """Konstanten, die durch eine gettext-Funktion laufen — per ast, nicht per Regex.

    Schlüssel → vorgemerkt? `gettext_noop` (und `_` in NOOP_MODULE) markiert nur: Der Text soll
    im Katalog stehen, wird aber erst an anderer Stelle übersetzt — er ist kein Fehlbestand."""
    schluessel: dict[str, bool] = {}
    try:
        baum = ast.parse(quelle)
    except SyntaxError:
        return schluessel
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.Call):
            continue
        funk = knoten.func
        name = funk.id if isinstance(funk, ast.Name) else funk.attr if isinstance(funk, ast.Attribute) else ""
        if name not in GETTEXT_NAMEN:
            continue
        args = [a.value for a in knoten.args if isinstance(a, ast.Constant) and isinstance(a.value, str)]
        if not args:
            continue
        vorgemerkt = alles_vorgemerkt or name == "gettext_noop"
        if name.startswith("pgettext") and len(args) >= 2:
            k = f"{args[0]}{KONTEXT_TRENNER}{args[1]}"
        elif name.startswith("npgettext") and len(args) >= 3:
            k = f"{args[0]}{KONTEXT_TRENNER}{args[1]}{PLURAL_TRENNER}{args[2]}"
        elif name.startswith("ngettext") and len(args) >= 2:
            k = PLURAL_TRENNER.join(args[:2])
        else:
            k = args[0]
        schluessel[k] = schluessel.get(k, True) and vorgemerkt
    return schluessel


def texte_im_code() -> dict[str, list[str]]:
    """Schlüssel → Fundstellen, über alle Vorlagen und Python-Dateien der Anwendung.
    Nur vorgemerkte Fundstellen tragen das Präfix „vorgemerkt:“."""
    fundstellen: dict[str, list[str]] = {}
    for d in _dateien("*.html") + _dateien("*.txt"):
        if "templates" not in d.parts:
            continue
        for s in texte_der_vorlage(d.read_text(encoding="utf-8")):
            fundstellen.setdefault(s, []).append(str(d.relative_to(WURZEL)))
    for d in _dateien("*.py"):
        if d.name.startswith("test_") or "tests" in d.parts or "tools" in d.parts:
            continue
        rel = d.relative_to(WURZEL).as_posix()
        for s, vorgemerkt in texte_der_python_datei(d.read_text(encoding="utf-8"), rel in NOOP_MODULE).items():
            fundstellen.setdefault(s, []).append(("vorgemerkt:" if vorgemerkt else "") + rel)
    return fundstellen


def nur_vorgemerkt(orte: list[str]) -> bool:
    return all(o.startswith("vorgemerkt:") for o in orte)


def katalog() -> dict[str, str]:
    """Schlüssel → Übersetzung, in der Form, in der die .mo sie führt (Plural: „eins\x00viele“)."""
    try:
        eintraege = lesen()
    except KatalogFehler as kaputt:
        pytest.fail("django.po ist syntaktisch ungültig:\n  " + "\n  ".join(kaputt.fehler))
    return {e.mo_schluessel(): e.mo_wert() for e in eintraege if e.msgid}


# ── Das Werkzeug selbst (#59) ─────────────────────────────────────────────────────────────


def test_po_pruefen_weist_rohe_zeilenumbrueche_zurueck(tmp_path):
    """Ein von Hand geschriebener Absatz mit echtem Zeilenumbruch ist keine .po-Syntax.
    Vorher las das Werkzeug daraus einen um ein Zeichen gekürzten Schlüssel und verwarf den
    Rest stumm — die .mo trug dann einen Schlüssel, den keine Vorlage je nachschlägt."""
    kaputt = tmp_path / "kaputt.po"
    kaputt.write_text(
        'msgid ""\nmsgstr ""\n\nmsgid "Erste Zeile\nzweite Zeile."\nmsgstr "First line\nsecond line."\n',
        encoding="utf-8",
    )
    with pytest.raises(KatalogFehler) as info:
        lesen(kaputt)
    meldung = "\n".join(info.value.fehler)
    assert "Zeile 4" in meldung and "Zeile 5" in meldung  # msgid-Zeile und ihre Fortsetzung
    assert "Zeile 6" in meldung  # die msgstr-Zeile ebenso


def test_po_pruefen_liest_gueltige_mehrzeiler(tmp_path):
    """Die beiden gültigen Schreibweisen ergeben denselben Schlüssel mit `\\n` darin."""
    gut = tmp_path / "gut.po"
    gut.write_text(
        'msgid ""\nmsgstr ""\n\n'
        'msgid ""\n"Erste Zeile\\n"\n"zweite Zeile."\nmsgstr ""\n"First line\\n"\n"second line."\n\n'
        'msgid "Eins\\nzwei"\nmsgstr "One\\ntwo"\n',
        encoding="utf-8",
    )
    eintraege = {e.msgid: e.msgstr for e in lesen(gut) if e.msgid}
    assert eintraege == {"Erste Zeile\nzweite Zeile.": "First line\nsecond line.", "Eins\nzwei": "One\ntwo"}


def test_der_katalog_selbst_ist_gueltig():
    """Der eingecheckte Katalog muss durch die strenge Lesung kommen (Befund #58: 14 Blöcke)."""
    assert PO.exists()
    katalog()


# ── Code ↔ Katalog (#60, #61, #88, #62, #63) ──────────────────────────────────────────────


def test_jeder_markierte_text_hat_einen_katalogeintrag():
    """Was mit `_()` oder `{% translate %}` markiert ist, verspricht eine Übersetzung.

    Fehlt der Eintrag, bleibt der Text auf Englisch deutsch — mitten zwischen englischen Zeilen.
    Der Test ersetzt `makemessages`, das auf diesem Arbeitsplatz nicht läuft."""
    vorhanden = katalog()
    fehlend = sorted(
        (s, orte) for s, orte in texte_im_code().items()
        if s not in vorhanden and s not in BEWUSST_OHNE_EINTRAG and not nur_vorgemerkt(orte)
    )
    assert not fehlend, "Markiert, aber ohne Katalogeintrag:\n  " + "\n  ".join(
        f"{s!r}  ← {', '.join(sorted(set(orte)))}" for s, orte in fehlend
    )


def test_vorgemerkte_datentexte_sind_markiert():
    """Befund #90: Rollenmatrix, Regelverzeichnis und Erstbestand sind deutsche Datentabellen;
    ihre Texte müssen markiert sein (No-op-`_` bzw. gettext_noop), damit sie in den Katalog
    finden können — und die Vorlagen übersetzen sie per `{% translate variable %}`."""
    im_code = texte_im_code()
    vorgemerkt = {s for s, orte in im_code.items() if any(o.startswith("vorgemerkt:") for o in orte)}
    assert "Expertenrat — Gruppe 1 (Entwurf)" in vorgemerkt  # rollen.py
    assert "Rollenmatrix „Wer darf was“" in vorgemerkt  # regelwerk.py
    assert "Regelfassung" in vorgemerkt  # ERSTBESTAND (Einheit)
    for vorlage, variablen in {
        "verfahren/templates/verfahren/rollen.html": ("rolle.name", "f.titel", "rolle.wie_hinein", "f.stand.name_de"),
        "parameter/templates/parameter/regeln.html": ("r.titel", "r.grund", "wirkung.name_de"),
        "parameter/templates/parameter/liste.html": ("p.beschreibung", "p.einheit"),
    }.items():
        quelle = (WURZEL / vorlage).read_text(encoding="utf-8")
        for v in variablen:
            assert f"{{% translate {v} %}}" in quelle, f"{vorlage}: {v} wird nicht übersetzt"


def test_kein_katalogeintrag_ohne_fundstelle():
    """Umgekehrt: Ein Eintrag, den kein Code mehr nennt, ist tot — er täuscht Vollständigkeit vor
    und bindet Pflege an Texte, die niemand liest (Befund #92). Ein Eintrag, dessen Schlüssel
    vom Code abweicht (ein Leerzeichen, ein `%` statt `%%`), fällt hier auf, weil er dann in
    beiden Listen steht: als fehlend oben und als fundstellenlos hier."""
    im_code = texte_im_code()
    tot = sorted(
        s for s in katalog() if s not in im_code and s not in BEWUSST_OHNE_FUNDSTELLE
    )
    assert not tot, "Katalogeinträge ohne Fundstelle im Code:\n  " + "\n  ".join(repr(s) for s in tot)
