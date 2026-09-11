"""Parametertests (FB-J3): die Rechnung ist reine Rechnung — und hat keine Meinung."""

from datetime import date

from hypothesis import given
from hypothesis import strategies as st

from plattform_core.parametertest import (
    VERSION,
    abgelaufen,
    flach,
    gegenueberstellen,
    laeuft,
    messgroessen,
)

KENNZAHLEN = {
    "members.active": 120,
    "motions.total": 14,
    "motions.by_phase": {"unterstuetzung": 5, "beratung": 3, "abstimmung": 2},
    "votes.turnout_mean": 0.41,
    "system": "ddoe-at",
    "angeschlossen": True,
    "leer": None,
}


def test_es_gibt_eine_fassung():
    assert VERSION == 1


def test_flach_macht_pfade_und_laesst_nur_zahlen_uebrig():
    f = flach(KENNZAHLEN)
    assert f["motions.by_phase.beratung"] == 3
    assert f["votes.turnout_mean"] == 0.41
    assert "system" not in f and "leer" not in f
    assert "angeschlossen" not in f, "ein Wahrheitswert ist keine Messgröße"


def test_messgroessen_sind_alphabetisch_und_vollstaendig():
    assert messgroessen(KENNZAHLEN) == sorted(flach(KENNZAHLEN))
    assert "motions.by_phase.abstimmung" in messgroessen(KENNZAHLEN)


def test_gegenueberstellung_rechnet_differenz_und_anteil():
    g = gegenueberstellen({"votes": {"turnout_mean": 0.4}}, {"votes": {"turnout_mean": 0.45}}, "votes.turnout_mean")
    assert g.vollstaendig
    assert g.differenz == 0.05
    assert g.anteil == 12.5


def test_ganze_zahlen_bleiben_ganz():
    g = gegenueberstellen({"motions": {"total": 10}}, {"motions": {"total": 13}}, "motions.total")
    assert g.differenz == 3 and isinstance(g.differenz, int)
    assert g.anteil == 30.0


def test_aus_null_wird_kein_anteil():
    """Wer vorher nichts hatte, hat keinen Prozentsatz — sonst stünde da „unendlich"."""
    g = gegenueberstellen({"a": 0}, {"a": 5}, "a")
    assert g.differenz == 5 and g.anteil is None


def test_fehlende_messgroesse_bleibt_unvollstaendig():
    g = gegenueberstellen({"a": 1}, {}, "a")
    assert not g.vollstaendig and g.differenz is None and g.anteil is None
    g = gegenueberstellen({}, {}, "nie.gemessen")
    assert g.vorher is None and g.nachher is None


def test_laeuft_vom_beginn_bis_einschliesslich_ende():
    beginn, ende = date(2026, 10, 1), date(2026, 10, 31)
    assert not laeuft(beginn, ende, date(2026, 9, 30))
    assert laeuft(beginn, ende, date(2026, 10, 1))
    assert laeuft(beginn, ende, date(2026, 10, 31))
    assert not laeuft(beginn, ende, date(2026, 11, 1))
    assert not laeuft(None, ende, date(2026, 10, 15)), "ohne Beginn läuft nichts"


def test_abgelaufen_ist_der_tag_danach():
    ende = date(2026, 10, 31)
    assert not abgelaufen(ende, ende)
    assert abgelaufen(ende, date(2026, 11, 1))


@given(
    st.dictionaries(
        st.text(min_size=1, max_size=8, alphabet="abcdefgh"),
        st.one_of(
            st.integers(-1000, 1000),
            st.floats(-1000, 1000, allow_nan=False),
            st.text(max_size=4),
            st.booleans(),
            st.none(),
            st.dictionaries(st.text(min_size=1, max_size=4, alphabet="xyz"), st.integers(-9, 9), max_size=3),
        ),
        max_size=6,
    )
)
def test_flach_verliert_keine_zahl_und_erfindet_keine(werte):
    """Jede Zahl im Baum steht genau einmal in der flachen Liste — und nichts anderes."""
    f = flach(werte)
    erwartet = 0
    for wert in werte.values():
        if isinstance(wert, dict):
            erwartet += sum(1 for v in wert.values() if isinstance(v, (int, float)) and not isinstance(v, bool))
        elif isinstance(wert, (int, float)) and not isinstance(wert, bool):
            erwartet += 1
    assert len(f) == erwartet
    assert all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in f.values())


@given(st.floats(-1e6, 1e6, allow_nan=False), st.floats(-1e6, 1e6, allow_nan=False))
def test_die_differenz_ist_nachher_minus_vorher(vorher, nachher):
    g = gegenueberstellen({"k": vorher}, {"k": nachher}, "k")
    assert g.differenz is not None
    assert abs(g.differenz - (nachher - vorher)) < 1e-3
