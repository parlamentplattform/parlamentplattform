"""Der Wort-Diff (FB-G6): Was am Vorschlag neu ist, muss sichtbar werden."""

from __future__ import annotations

from plattform_core import wortdiff


def zusammensetzen(teile, arten) -> str:
    return "".join(text for art, text in teile if art in arten)


def test_gleicher_text_hat_keine_aenderung():
    teile = wortdiff.vergleichen("Ein Satz bleibt.", "Ein Satz bleibt.")
    assert [art for art, _ in teile] == ["gleich"]
    assert wortdiff.zusammenfassung(teile) == {"ein": 0, "aus": 0, "unveraendert": True}


def test_ein_geaendertes_wort_bleibt_ein_geaendertes_wort():
    """Zeilenweise wäre der ganze Satz ausgetauscht — wortweise sind es zwei Wörter."""
    teile = wortdiff.vergleichen(
        "Die Sitzungen der Gemeinde werden aufgezeichnet.",
        "Die Sitzungen der Gemeinde werden veröffentlicht.",
    )
    assert wortdiff.zusammenfassung(teile) == {"ein": 1, "aus": 1, "unveraendert": False}
    assert "aufgezeichnet" in zusammensetzen(teile, {"aus"})
    assert "veröffentlicht" in zusammensetzen(teile, {"ein"})


def test_alter_und_neuer_text_lassen_sich_wieder_herstellen():
    alt, neu = "Alpha beta gamma delta.", "Alpha gamma delta epsilon."
    teile = wortdiff.vergleichen(alt, neu)
    assert zusammensetzen(teile, {"gleich", "aus"}).strip() == alt.strip()
    assert zusammensetzen(teile, {"gleich", "ein"}).strip() == neu.strip()


def test_ergaenzung_am_ende_zaehlt_nur_als_einfuegung():
    teile = wortdiff.vergleichen("Ein Satz.", "Ein Satz. Und noch einer.")
    assert wortdiff.zusammenfassung(teile)["aus"] == 0
    assert wortdiff.zusammenfassung(teile)["ein"] == 3


def test_leerer_ausgangstext_ist_reine_einfuegung():
    teile = wortdiff.vergleichen("", "Ganz neu.")
    assert [art for art, _ in teile] == ["ein"]
    assert wortdiff.vergleichen("", "") == []


def test_benachbarte_abschnitte_werden_zusammengefasst():
    teile = wortdiff.vergleichen("a b c d", "x y c d")
    assert [art for art, _ in teile] == ["aus", "ein", "gleich"], "kein Flickenteppich je Wort"


def test_absaetze_zaehlen_die_bezugsstellen():
    text = "Erster Absatz.\n\n  \n\nZweiter Absatz.\n\nDritter."
    assert wortdiff.absaetze(text) == ["Erster Absatz.", "Zweiter Absatz.", "Dritter."]
    assert wortdiff.absaetze("") == []
