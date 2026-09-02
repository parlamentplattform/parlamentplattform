"""Der WeicherFilter-Kern (P5, FB-B1/B2): offene, nachrechenbare Reihung — Regel v2."""

from plattform_core.weicherfilter import (
    ALTE_NAMEN,
    HOECHSTWERT,
    REGLER,
    VERSION,
    ist_neutral,
    regler_bereinigen,
    reihen,
)


def test_bereinigen_begrenzt_und_verwirft_unbekanntes():
    roh = {"chronologisch": "250", "ablaufend": -5, "fremd": 99, "ja": "abc"}
    sauber = regler_bereinigen(roh)
    assert sauber["chronologisch"] == HOECHSTWERT
    assert sauber["ablaufend"] == 0 and sauber["ja"] == 0
    assert "fremd" not in sauber
    assert set(sauber) == set(REGLER)
    assert regler_bereinigen(None) == dict.fromkeys(REGLER, 0)


def test_alter_regler_gestimmt_lebt_in_beiden_richtungen_weiter():
    """Regel v1 kannte „gestimmt“ richtungslos; v2 trennt wofür und wogegen (D-B2)."""
    assert ALTE_NAMEN == {"gestimmt": ("ja", "nein")}
    sauber = regler_bereinigen({"gestimmt": 40})
    assert sauber["ja"] == 40 and sauber["nein"] == 40
    sauber = regler_bereinigen({"gestimmt": 40, "nein": 10})  # ein neuer Wert hat Vorrang
    assert sauber["ja"] == 40 and sauber["nein"] == 10


def test_neutral_heisst_alle_regler_null():
    assert ist_neutral({}) and ist_neutral(None)
    assert not ist_neutral({"abstimmungen": 1})
    assert not ist_neutral({"gestimmt": 5})


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


def test_wofuer_und_wogegen_sind_getrennte_regler():
    eintraege = [
        {"id": "gegen", "merkmale": {"nein": 1.0}},
        {"id": "dafuer", "merkmale": {"ja": 1.0}},
    ]
    assert [e["id"] for e in reihen(eintraege, {"ja": 100})] == ["dafuer", "gegen"]
    assert [e["id"] for e in reihen(eintraege, {"nein": 100})] == ["gegen", "dafuer"]


def test_favoriten_zuerst_ist_eine_offene_partition():
    eintraege = [
        {"id": 1, "merkmale": {"abstimmungen": 1.0}, "favorit": False},
        {"id": 2, "merkmale": {}, "favorit": True},
        {"id": 3, "merkmale": {"abstimmungen": 1.0}, "favorit": True},
    ]
    # Ohne Schalter zählt nur die Rechnung (stabil bei Gleichstand).
    assert [e["id"] for e in reihen(eintraege, {"abstimmungen": 50})] == [1, 3, 2]
    # Mit Schalter: Favoriten vor allen anderen, innerhalb nach Punkten, dann Grundordnung.
    lage = reihen(eintraege, {"abstimmungen": 50}, favoriten_zuerst=True)
    assert [e["id"] for e in lage] == [3, 2, 1]
    assert [e["favorit"] for e in lage] == [True, True, False]
    # Neutral + Schalter: Favoriten zuerst, sonst unverändert.
    assert [e["id"] for e in reihen(eintraege, {}, favoriten_zuerst=True)] == [2, 3, 1]


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
    assert VERSION == 2 and len(REGLER) == 9
    assert REGLER == (
        "ja", "nein", "unterstuetzt", "entdeckungen", "unterstuetzungsphase",
        "abstimmungen", "chronologisch", "ablaufend", "schwelle",
    )
