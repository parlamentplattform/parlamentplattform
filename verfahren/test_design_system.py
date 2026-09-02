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
    erlaubt = {".leiste .marke", ".panel-kopf .marke", ".fuss-grid .marke2", ".held h1"}
    assert set(serif_regeln) <= erlaubt, f"Serif außerhalb von Wortmarke und Bühne: {serif_regeln}"
    assert "system-ui" not in rest and "Georgia" not in rest
    for pfad in _templates():
        if pfad.name == "base.html":
            continue
        text = pfad.read_text(encoding="utf-8")
        assert "var(--serif)" not in text and "Georgia" not in text, f"Serif in {pfad.name}"


def test_ein_reduced_motion_block_und_bewegung_ueber_tokens():
    """Spec 2.4: alle Dauern über --d-*, genau ein prefers-reduced-motion-Block, keine Keyframe-Leichen."""
    css = _style()
    assert css.count("prefers-reduced-motion") == 1
    block = css.split("@media (prefers-reduced-motion:reduce)", 1)[1]
    for pflicht in ("animation-duration:1ms!important", "transition-duration:1ms!important",
                    "scroll-behavior:auto!important", "::view-transition-group(*)"):
        assert pflicht in block
    literale = re.findall(r"(?<![\w-])\.\d+s\b", css)
    assert not literale, f"Literale Dauern statt Tokens: {literale}"
    assert "cubic-bezier(" not in _bloecke(css)[3], "Easings nur als --e-* Tokens"
    for leiche in ("blase-auf", ".mini-kachel", ".brotkrume", ".feld::after"):
        assert leiche not in css
    for einmal in (":focus-visible{", ".btn:hover{", ".chip:hover{"):
        assert css.count(einmal) == 1, f"{einmal} mehrfach definiert"


def test_keine_inline_handler_und_inline_skripte():
    """FB-P4, Spec 5: keine on…=-Attribute, kein hx-on, kein <script> ohne src — CSP-fähig."""
    treffer = []
    for pfad in _templates():
        text = pfad.read_text(encoding="utf-8")
        for m in re.finditer(r"\s(on[a-z]+)=|(hx-on[:\w-]*)=|(<script)(?![^>]*\ssrc=)", text):
            treffer.append(f"{pfad.relative_to(WURZEL)}: {m.group(0).strip()}")
    assert not treffer, "\n".join(treffer)


def test_skripte_in_der_richtigen_reihenfolge():
    kopf = BASE.read_text(encoding="utf-8").split("</head>", 1)[0]
    assert kopf.index("verfahren/js/thema.js") < kopf.index("<style>"), "thema.js vor dem Stil (kein Aufblitzen)"
    assert kopf.index("verfahren/js/app.js") < kopf.index("verfahren/js/alpine.min.js"), "Komponenten vor Alpine"
    assert "defer" not in kopf.split("thema.js", 1)[0].rsplit("<script", 1)[1]


def test_uebersetzungen_vollstaendig_und_kompiliert():
    """Definition of Done 3: keine leeren oder unsicheren Einträge, App-Rahmen auf Englisch."""
    import sys

    sys.path.insert(0, str(WURZEL / "tools"))
    from po_pruefen import lesen

    eintraege = [e for e in lesen() if e.msgid]
    leer = [e.schluessel for e in eintraege if not e.uebersetzt]
    assert not leer, f"Ohne Übersetzung: {leer}"
    assert not [e.schluessel for e in eintraege if e.fuzzy], "Unsichere (fuzzy) Einträge im Katalog"

    from django.utils import translation

    with translation.override("en"):
        from django.utils.translation import gettext

        for deutsch, englisch in [
            ("Verwaltung", "Administration"),
            ("Erscheinungsbild", "Appearance"),
            ("Hell", "Light"),
            ("Dunkel", "Dark"),
            ("Bereiche", "Sections"),
            ("Mehr", "More"),
            ("Menü schließen", "Close menu"),
            ("Anmelden zum Abstimmen", "Sign in to vote"),
            ("Favoriten", "Favourites"),
            ("Antrag einbringen", "Submit a motion"),
        ]:
            assert gettext(deutsch) == englisch, f"{deutsch!r} ist nicht kompiliert übersetzt"


def test_versionen_stimmen_ueberein():
    """Definition of Done 4: CHANGELOG, pyproject und plattform_core nennen dieselbe Version."""
    from plattform_core import __version__

    changelog = re.search(r"^## \[(\d+\.\d+\.\d+)\]", (WURZEL / "CHANGELOG.md").read_text(encoding="utf-8"), re.M)
    pyproject = re.search(r'^version = "(\d+\.\d+\.\d+)"', (WURZEL / "pyproject.toml").read_text(encoding="utf-8"), re.M)
    assert changelog and pyproject
    assert changelog.group(1) == pyproject.group(1) == __version__


def test_skelett_partial():
    from django.template.loader import render_to_string

    zeilen = render_to_string("verfahren/_skelett.html", {"art": "zeilen", "n": 5})
    assert zeilen.count('class="skelett b70"') == 5 and 'aria-hidden="true"' in zeilen
    kacheln = render_to_string("verfahren/_skelett.html", {"art": "kacheln", "n": 4})
    assert kacheln.count("kachel-form") == 4
    assert "punkte" not in zeilen  # test_weicherfilter_ansicht verbietet das Wort im Filter-Feld
