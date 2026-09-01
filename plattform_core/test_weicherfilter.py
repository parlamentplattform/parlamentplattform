"""Der WeicherFilter-Kern (P5): offene, nachrechenbare Reihung."""

from plattform_core.weicherfilter import (
    HOECHSTWERT,
    REGLER,
    VERSION,
    ist_neutral,
    regler_bereinigen,
    reihen,
)


def test_bereinigen_begrenzt_und_verwirft_unbekanntes():
    roh = {"chronologisch": "250", "ablaufend": -5, "fremd": 99, "gestimmt": "abc"}
    sauber = regler_bereinigen(roh)
    assert sauber["chronologisch"] == HOECHSTWERT
    assert sauber["ablaufend"] == 0 and sauber["gestimmt"] == 0
    assert "fremd" not in sauber
    assert set(sauber) == set(REGLER)
    assert regler_bereinigen(None) == dict.fromkeys(REGLER, 0)


def test_neutral_heisst_alle_regler_null():
    assert ist_neutral({}) and ist_neutral(None)
    assert not ist_neutral({"abstimmungen": 1})


def test_reihung_folgt_den_reglern_und_bleibt_bei_gleichstand_stabil():
    eintraege = [
        {"id": 1, "merkmale": {"abstimmungen": 1.0}},
        {"id": 2, "merkmale": {"abstimmungen": 1.0}},
        {"id": 3, "merkmale": {"chronologisch": 1.0}},
    ]
    # Neutral: Reihenfolge unverändert, null Punkte.
    neutral = reihen(eintraege, {})
    assert [e["id"] for e in neutral] == [1, 2, 3]
    assert all(e["punkte"] == 0 for e in neutral)

    # Chronologie-Regler hebt Eintrag 3; 1 und 2 bleiben in Grundordnung (stabil).
    lage = reihen(eintraege, {"chronologisch": 50})
    assert [e["id"] for e in lage] == [3, 1, 2]
    assert lage[0]["punkte"] == 50.0

    # Zwei Regler: Punkte addieren sich, die Aufschlüsselung liegt offen.
    lage = reihen(eintraege, {"chronologisch": 50, "abstimmungen": 80})
    assert [e["id"] for e in lage] == [1, 2, 3]
    assert lage[0]["punkte"] == 80.0 and lage[0]["anteile"] == {"abstimmungen": 80.0}
    assert lage[2]["anteile"] == {"chronologisch": 50.0}


def test_merkmale_werden_auf_null_bis_eins_begrenzt():
    eintraege = [
        {"id": 1, "merkmale": {"schwelle": 7.0}},  # fehlerhafte Eingabe > 1
        {"id": 2, "merkmale": {"schwelle": -3.0}},
        {"id": 3, "merkmale": {}},
    ]
    lage = reihen(eintraege, {"schwelle": 100})
    assert lage[0]["id"] == 1 and lage[0]["punkte"] == 100.0
    assert lage[1]["punkte"] == 0.0 and lage[2]["punkte"] == 0.0


def test_version_ist_teil_der_offenen_regel():
    assert VERSION == 1 and len(REGLER) == 8
