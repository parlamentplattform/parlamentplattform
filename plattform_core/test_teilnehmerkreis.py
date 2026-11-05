"""Gebietsschlüssel und Hauptwohnsitzregel ohne aktuelle Profil- oder Stimmrechte."""

from dataclasses import replace

import pytest

from plattform_core.teilnehmerkreis import (
    Gebiet,
    GebietsFehler,
    Gemeindestand,
    gebiet_fuer,
    hauptwohnsitz_gehoert_dazu,
)

POLSENZ = Gemeindestand("40510", "St. Marienkirchen an der Polsenz", "Eferding", "oberoesterreich")
HAUSRUCK = Gemeindestand("41227", "St. Marienkirchen am Hausruck", "Ried", "oberoesterreich")
SCHAERDING = Gemeindestand("41419", "St. Marienkirchen bei Schärding", "Schärding", "oberoesterreich")
EFERDING = Gemeindestand("40503", "Eferding", "Eferding", "oberoesterreich")
WIEN = Gemeindestand("90001", "Wien", "Wien", "wien")
STAMM = (POLSENZ, HAUSRUCK, SCHAERDING, EFERDING, WIEN)


@pytest.mark.parametrize("haupt", [POLSENZ, HAUSRUCK, SCHAERDING])
def test_gleichnamige_gemeinden_vergeben_keine_fremden_rechte(haupt):
    gebiet = gebiet_fuer("gemeinde", haupt, STAMM)
    assert gebiet.kennung == f"gemeinde:{haupt.kennziffer}"
    for g in STAMM:
        assert hauptwohnsitz_gehoert_dazu(gebiet, "oesterreich", g.kennziffer) is (g == haupt)


def test_bezirk_umfasst_seine_gemeinden_und_nicht_das_ganze_land():
    gebiet = gebiet_fuer("bezirk", POLSENZ, STAMM)
    assert gebiet.gemeinden == ("40503", "40510")
    assert gebiet.name == "Eferding"
    assert gebiet == gebiet_fuer("bezirk", EFERDING, reversed(STAMM))
    assert not hauptwohnsitz_gehoert_dazu(gebiet, "oesterreich", HAUSRUCK.kennziffer)


def test_gleicher_bezirksname_in_anderem_land_wird_nicht_zusammengelegt():
    fremd = Gemeindestand("10101", "Andere Gemeinde", "Eferding", "burgenland")
    assert fremd.kennziffer not in gebiet_fuer("bezirk", POLSENZ, (*STAMM, fremd)).gemeinden


def test_land_umfasst_nur_die_festgehaltenen_gemeinden_des_landes():
    gebiet = gebiet_fuer("land", POLSENZ, STAMM)
    assert gebiet.gemeinden == ("40503", "40510", "41227", "41419")
    assert gebiet.land == "oberoesterreich"
    assert not hauptwohnsitz_gehoert_dazu(gebiet, "oesterreich", WIEN.kennziffer)


@pytest.mark.parametrize("art", ["", "ausland", "ohne_festen_wohnsitz", "nebenwohnsitz"])
def test_region_braucht_tatsaechlichen_hauptwohnsitz_auch_bei_alter_fk(art):
    gebiet = gebiet_fuer("gemeinde", POLSENZ, STAMM)
    assert not hauptwohnsitz_gehoert_dazu(gebiet, art, POLSENZ.kennziffer)


@pytest.mark.parametrize("art", ["", "ausland", "ohne_festen_wohnsitz", "oesterreich"])
def test_bund_braucht_keine_territoriale_zuordnung(art):
    gebiet = gebiet_fuer("bund", None, ())
    assert hauptwohnsitz_gehoert_dazu(gebiet, art, None)
    assert gebiet.kennung == "bund"


@pytest.mark.parametrize("ebene", ["land", "bezirk", "gemeinde"])
def test_fehlende_hauptgemeinde_ist_keine_region(ebene):
    with pytest.raises(GebietsFehler, match="Hauptwohnsitz"):
        gebiet_fuer(ebene, None, STAMM)


def test_wien_gemeinde_und_land_sind_keine_erfundene_bezirksvertretung():
    assert gebiet_fuer("gemeinde", WIEN, STAMM).gemeinden == ("90001",)
    assert gebiet_fuer("land", WIEN, STAMM).gemeinden == ("90001",)
    with pytest.raises(GebietsFehler, match="Wiener Gemeindebezirke"):
        gebiet_fuer("bezirk", WIEN, STAMM)


def test_gebietsausdehnung_aendert_kennung_alter_stand_bleibt_erhalten():
    alt = gebiet_fuer("bezirk", POLSENZ, STAMM)
    neu = gebiet_fuer("bezirk", POLSENZ, (*STAMM, Gemeindestand("40511", "Neu", "Eferding", "oberoesterreich")))
    assert neu.kennung != alt.kennung
    assert alt.gemeinden == ("40503", "40510")
    assert Gebiet.aus_dict(alt.als_dict()) == alt


@pytest.mark.parametrize("daten", [
    None, {}, {"fassung": 1},
    {**gebiet_fuer("gemeinde", POLSENZ, STAMM).als_dict(), "fassung": True},
    {**gebiet_fuer("gemeinde", POLSENZ, STAMM).als_dict(), "fassung": 2},
    {**gebiet_fuer("gemeinde", POLSENZ, STAMM).als_dict(), "gemeinden": [40510]},
    {**gebiet_fuer("gemeinde", POLSENZ, STAMM).als_dict(), "kennung": "gemeinde:41227"},
    {**gebiet_fuer("gemeinde", POLSENZ, STAMM).als_dict(), "mehr": 1},
    {**gebiet_fuer("gemeinde", POLSENZ, STAMM).als_dict(), "ebene": []},
])
def test_unbekannter_oder_verfaelschter_stand_wird_nicht_zu_parteiweiten_rechten(daten):
    with pytest.raises(GebietsFehler):
        Gebiet.aus_dict(daten)


@pytest.mark.parametrize("kennziffer", ["4051", "405100", "４０５１０", 40510, None])
def test_nur_echte_fuenfstellige_ascii_kennziffer(kennziffer):
    with pytest.raises(GebietsFehler):
        replace(POLSENZ, kennziffer=kennziffer)


def test_doppelte_oder_fremde_gemeindestammzuordnung_scheitert():
    with pytest.raises(GebietsFehler, match="nicht eindeutig"):
        gebiet_fuer("gemeinde", POLSENZ, (*STAMM, POLSENZ))
    with pytest.raises(GebietsFehler, match="nicht zu diesem"):
        gebiet_fuer("gemeinde", replace(POLSENZ, name="Falscher Ort"), STAMM)
