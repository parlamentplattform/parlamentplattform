"""Spätere lokale Erfassung ist weder Vollständigkeit noch juristische Verifikation."""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

import pytest

from plattform_core.quellenfortschritt import Quelle, vergleichen

JETZT = datetime(2026, 11, 3, 3, tzinfo=UTC)
AUFNAHME = JETZT - timedelta(days=1)
ALT = Quelle("NOR00000001", 1, date(2026, 1, 1), "a" * 64, AUFNAHME - timedelta(days=1))


def befund(neu, alt=ALT):
    return vergleichen([alt], [neu] if neu else [], aufnahme=AUFNAHME, jetzt=JETZT)[0]


def test_unveraenderter_stand_und_fehlender_vergleich_werden_unterschieden():
    assert befund(ALT).vergleichbar and not befund(ALT).metadaten_spaeter
    assert not befund(None).vergleichbar and not befund(None).dokument_spaeter
    assert vergleichen([], [], aufnahme=AUFNAHME, jetzt=JETZT) == ()


def test_spaeterer_stichtag_oder_geaenderte_metadaten_nur_nach_der_aufnahme():
    spaet = AUFNAHME + timedelta(hours=1)
    assert befund(replace(ALT, norm_id=2, stand=date(2026, 1, 2), importiert=spaet)).metadaten_spaeter
    assert befund(replace(ALT, norm_id=2, metadaten_hash="b" * 64, importiert=spaet)).metadaten_spaeter
    assert not befund(replace(ALT, norm_id=2, importiert=spaet)).metadaten_spaeter
    assert not befund(replace(ALT, norm_id=2, stand=date(2026, 1, 2))).metadaten_spaeter
    assert not befund(replace(ALT, metadaten_hash="b" * 64, importiert=AUFNAHME)).metadaten_spaeter


def test_juengerer_import_eines_aelteren_historischen_stichtags_ist_keine_neuere_quelle():
    b = befund(replace(ALT, stand=date(2025, 12, 31), importiert=AUFNAHME + timedelta(hours=1)))
    assert not b.vergleichbar and not b.metadaten_spaeter and not b.dokument_spaeter


def test_neuer_text_geaenderter_text_und_geaenderter_parser_sind_nachlesbar():
    text = replace(ALT, text_id=7, text_hash="b" * 64, text_parser=1,
                   text_erfasst=AUFNAHME + timedelta(hours=1))
    assert befund(text).dokument_spaeter and befund(text).spaeterer_text == 7
    damals = replace(text, text_erfasst=AUFNAHME - timedelta(hours=1))
    assert not befund(replace(text, text_id=8), damals).dokument_spaeter
    assert befund(replace(text, text_id=8, text_hash="c" * 64), damals).dokument_spaeter
    assert befund(replace(text, text_id=8, text_parser=2), damals).dokument_spaeter


def test_fremde_quelle_ist_keine_aenderung_und_reihung_ist_nach_kennung():
    andere = replace(ALT, kennung="NOR00000002", norm_id=2)
    befunde = vergleichen([andere, ALT], [ALT], aufnahme=AUFNAHME, jetzt=JETZT)
    assert [b.kennung for b in befunde] == [ALT.kennung, andere.kennung]
    assert befunde[0].vergleichbar and not befunde[1].vergleichbar


@pytest.mark.parametrize("feld,wert", [
    ("kennung", "X"), ("norm_id", True), ("stand", JETZT), ("metadaten_hash", "z" * 64),
    ("importiert", JETZT.replace(tzinfo=None)), ("text_id", 1), ("text_hash", "a" * 64),
])
def test_unvollstaendige_oder_ungueltige_quelle_wird_abgewiesen(feld, wert):
    with pytest.raises(ValueError):
        replace(ALT, **{feld: wert})


@pytest.mark.parametrize("ausgang,ende", [(JETZT, AUFNAHME), (AUFNAHME.replace(tzinfo=None), JETZT)])
def test_unplausible_vergleichszeit_wird_abgewiesen(ausgang, ende):
    with pytest.raises(ValueError):
        vergleichen([ALT], [ALT], aufnahme=ausgang, jetzt=ende)


def test_doppelte_kennungen_und_zukuenftige_erfassungen_sind_keine_gute_nachricht():
    with pytest.raises(ValueError):
        vergleichen([ALT, ALT], [], aufnahme=AUFNAHME, jetzt=JETZT)
    with pytest.raises(ValueError):
        vergleichen([ALT], [ALT, ALT], aufnahme=AUFNAHME, jetzt=JETZT)
    with pytest.raises(ValueError):
        befund(replace(ALT, importiert=JETZT + timedelta(seconds=1)))
