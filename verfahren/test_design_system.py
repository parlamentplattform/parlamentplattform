"""Statische Prüfungen des Design-Systems (Design-Spezifikation App-Look, FB-P2/P3/P4).

Diese Tests lesen Templates und Dateien, ohne die Datenbank zu brauchen. Sie sichern
die Regeln, die sich nicht aus einer einzelnen Seite ablesen lassen: Tokens statt
harter Farben, Dark Mode ohne Lücken, Sans-Typografie, keine Inline-Handler.
"""

import re
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
BASE = WURZEL / "verfahren" / "templates" / "verfahren" / "base.html"

# Tokens laut Design-Spezifikation 2.1–2.4 (Pflicht auf :root)
SPEC_TOKENS = [
    "--bg", "--surface", "--surface-2", "--ink", "--muted", "--line", "--deep", "--gold", "--gold-soft",
    "--gold-deep", "--night-1", "--night-2", "--night-3", "--ok", "--ok-bg", "--warn", "--warn-bg",
    "--info", "--info-bg", "--pillar-1", "--pillar-2", "--pillar-3", "--pillar-4", "--shadow",
    "--shadow-lift", "--overlay", "--scrim", "--sans", "--serif", "--bar", "--d-fast", "--d-base",
    "--d-slide", "--d-grow", "--e-out", "--e-in", "--e-spring",
]
# Tokens, die im Dunkelblock einen eigenen Wert bekommen (Spec 2.1, Spalte „Dunkel“)
DUNKEL_TOKENS = [
    "--bg", "--surface", "--surface-2", "--ink", "--muted", "--line", "--deep", "--gold-deep", "--ok",
    "--ok-bg", "--warn", "--warn-bg", "--info", "--info-bg", "--pillar-1", "--shadow", "--shadow-lift",
    "--overlay", "--scrim",
]
HEX = re.compile(r"#[0-9a-fA-F]{3,8}\b")


def _style() -> str:
    text = BASE.read_text(encoding="utf-8")
    return text.split("<style>", 1)[1].split("</style>", 1)[0]


def _bloecke(css: str) -> tuple[str, str, str, str]:
    """Liefert (hell, dunkel-system, dunkel-manuell, rest) aus dem Stilblock."""
    hell = re.search(r":root\{(.*?)\n\}", css, re.S)
    system = re.search(r':root:not\(\[data-theme="light"\]\)\{(.*?)\n\}\}', css, re.S)
    manuell = re.search(r':root\[data-theme="dark"\]\{(.*?)\n\}', css, re.S)
    assert hell and system and manuell, "Token-Blöcke (hell, dunkel-system, dunkel-manuell) fehlen"
    rest = css
    for m in (hell, system, manuell):
        rest = rest.replace(m.group(0), "")
    return hell.group(1), system.group(1), manuell.group(1), rest


def _templates() -> list[Path]:
    return [p for p in WURZEL.glob("*/templates/**/*.html")]


def test_tokens_vollstaendig_und_dunkel_dreifach():
    hell, system, manuell, _ = _bloecke(_style())
    fehlend = [t for t in SPEC_TOKENS if f"{t}:" not in hell]
    assert not fehlend, f"Tokens fehlen auf :root: {fehlend}"
    for name, block in (("system", system), ("manuell", manuell)):
        fehlend = [t for t in DUNKEL_TOKENS if f"{t}:" not in block]
        assert not fehlend, f"Dunkelblock {name} ohne {fehlend}"
    # Beide Dunkelblöcke sind wortgleich — sonst driften Systemthema und Schalter auseinander.
    assert system.strip() == manuell.strip()
    # Gold und Nacht bleiben in beiden Themen gleich (Spec 2.1).
    for t in ("--gold:", "--gold-soft:", "--night-1:", "--night-2:", "--night-3:"):
        assert t not in system


def test_kein_hex_ausserhalb_der_token_bloecke():
    _, _, _, rest = _bloecke(_style())
    treffer = HEX.findall(rest)
    assert not treffer, f"Harte Farben außerhalb der Tokens in base.html: {treffer}"


def test_alte_tokennamen_sind_aliase():
    hell, _, _, _ = _bloecke(_style())
    for alt in ("--paper", "--karton", "--matt", "--linkfarbe", "--goldsoft", "--goldtief", "--nacht1",
                "--schatten", "--ok-grund", "--info-grund", "--warn-grund"):
        m = re.search(rf"{re.escape(alt)}:([^;]+);", hell)
        assert m and m.group(1).startswith("var(--"), f"{alt} muss ein Alias auf ein Spec-Token sein"


def test_keine_harten_farben_in_inline_styles_der_templates():
    """Inline-Styles außerhalb von SVG-Grafiken dürfen kein Hex tragen (Spec 1.5)."""
    treffer = []
    for pfad in _templates():
        text = pfad.read_text(encoding="utf-8")
        text = re.sub(r"<svg.*?</svg>", "", text, flags=re.S)
        for m in re.finditer(r'style="([^"]*)"', text):
            if HEX.search(m.group(1)):
                treffer.append(f"{pfad.relative_to(WURZEL)}: {m.group(1)}")
    assert not treffer, "\n".join(treffer)


def test_vollzug_badges_ueber_token_klassen():
    from verfahren.templatetags.phasen import KLASSEN, vollzug_klasse

    assert set(KLASSEN) == {"umgesetzt", "in_umsetzung", "blockiert", "zurueckgestellt", "offen"}
    assert vollzug_klasse("umgesetzt") == "badge-ok"
    assert vollzug_klasse("unbekannt") == "badge-still"
    css = _style()
    for klasse in set(KLASSEN.values()):
        assert f".{klasse}{{" in css


def test_sans_ueberall_serif_nur_wortmarke_und_buehne():
    """D-P2: Sans für alles Bedienbare; Serif nur in der Wortmarke und im Bühnen-H1 der Erklärseiten."""
    css = _style()
    _, _, _, rest = _bloecke(css)
    assert re.search(r"body\{[^}]*font-family:var\(--sans\)", rest)
    assert not re.search(r"h1,h2,h3\{[^}]*--serif", rest)
    serif_regeln = [
        regel.split("{")[0].strip()
        for regel in rest.split("}")
        if "var(--serif)" in regel
    ]
    erlaubt = {"header .marke", ".marke", ".fuss-grid .marke2", ".held h1"}
    assert set(serif_regeln) <= erlaubt, f"Serif außerhalb von Wortmarke und Bühne: {serif_regeln}"
    assert "system-ui" not in rest and "Georgia" not in rest
    for pfad in _templates():
        if pfad.name == "base.html":
            continue
        text = pfad.read_text(encoding="utf-8")
        assert "var(--serif)" not in text and "Georgia" not in text, f"Serif in {pfad.name}"
