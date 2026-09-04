"""Der Leser der Partner-Kurzfassungen (FB-M9)."""

from __future__ import annotations

from plattform_core import kurztext

BEISPIEL = """# Pour les partis et les initiatives du monde entier

La DDÖ est un parti autrichien sans programme politique. Nous construisons
le logiciel qui permet à la société de décider.

La plateforme est en phase alpha.

*La version complète de la page partenaires est en anglais.*

---

## Glossar dieser Sprachfassung

Satzungs-Baukasten → « kit de statuts »

## Was eine Muttersprachlerin noch ansehen sollte

- « kit de statuts » ist eine Prägung.
"""


def test_liest_ueberschrift_absaetze_und_schluss():
    d = kurztext.lesen(BEISPIEL)
    assert d["ueberschrift"] == "Pour les partis et les initiatives du monde entier"
    assert len(d["absaetze"]) == 2
    assert d["schluss"] == "La version complète de la page partenaires est en anglais."
    assert kurztext.ist_vollstaendig(d)


def test_arbeitsmaterial_hinter_dem_strich_bleibt_draussen():
    """Glossar und offene Punkte sind für uns, nicht für die Leserin."""
    d = kurztext.lesen(BEISPIEL)
    alles = " ".join([d["ueberschrift"], *d["absaetze"], d["schluss"]])
    for verboten in ("Glossar", "Muttersprachlerin", "Prägung", "Satzungs-Baukasten"):
        assert verboten not in alles, verboten


def test_zeilenumbrueche_im_absatz_werden_zu_leerzeichen():
    """Die Quelldateien brechen Zeilen zum Lesen um — das ist kein Absatzwechsel."""
    d = kurztext.lesen(BEISPIEL)
    assert "Nous construisons le logiciel" in d["absaetze"][0]
    assert "\n" not in d["absaetze"][0]


def test_fehlende_teile_zerstoeren_nichts():
    leer = kurztext.lesen("")
    assert leer == {"ueberschrift": "", "absaetze": [], "schluss": ""}
    assert not kurztext.ist_vollstaendig(leer)

    ohne_schluss = kurztext.lesen("# Titel\n\nEin Absatz.")
    assert ohne_schluss["schluss"] == ""
    assert kurztext.ist_vollstaendig(ohne_schluss)

    nur_text = kurztext.lesen("Ein Absatz ohne Überschrift.")
    assert not kurztext.ist_vollstaendig(nur_text), "ohne Überschrift keine Seite"


def test_fetter_text_gilt_nicht_als_schlusssatz():
    """`**…**` ist Hervorhebung im Absatz, `*…*` der leise Schlusssatz."""
    d = kurztext.lesen("# Titel\n\n**Wichtig.**\n\n*Schluss.*")
    assert d["absaetze"] == ["**Wichtig.**"]
    assert d["schluss"] == "Schluss."


def test_alle_ausgelieferten_fassungen_sind_lesbar():
    """Was im Repo liegt, muss sich anzeigen lassen — sonst fällt es erst live auf."""
    import pathlib

    ordner = pathlib.Path(__file__).resolve().parent.parent / "docs/partner/kurz"
    dateien = sorted(ordner.glob("*.md"))
    assert len(dateien) >= 5, "de, fr, es, it, ja"
    for d in dateien:
        gelesen = kurztext.lesen(d.read_text(encoding="utf-8"))
        assert kurztext.ist_vollstaendig(gelesen), d.name
        assert len(gelesen["absaetze"]) >= 4, f"{d.name}: {len(gelesen['absaetze'])} Absätze"
        if d.name != "de.md":
            assert gelesen["schluss"], f"{d.name}: der Verweis auf die englische Vollfassung fehlt"
