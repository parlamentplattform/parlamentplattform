"""Historischen Quellenvertrag1 vor jeder Erweiterung unverändert nachweisen.

Der kleine synthetische Beleg entstand mit dem noch unveränderten Stand0.69.
Er enthält keine Mitgliedsdaten oder tatsächliche Rechtsquelle. Keine Datenbank
oder aktuellen Quellen dürfen beim Prüfen/Nachlesen benötigt werden.
"""

import copy
import hashlib
import json
from pathlib import Path

import pytest

from faktenbasis.kontext import QuellenkontextFehler, eingabe, pruefen

BELEG = Path(__file__).with_name("testdaten") / "quellenkontext_v1_vertragsbeleg.json"
ALTE_PRUEFSUMME = "c783aba16e733dead092e59e74cd859f357ebaac0daec94e133f627aad3f5564"


def test_historischer_quellenvertrag1_bleibt_genau_pruefbar():
    rahmen = json.loads(BELEG.read_text(encoding="utf-8"))["kontext"]
    vorher = copy.deepcopy(rahmen)
    daten = pruefen(rahmen)
    assert rahmen["sha256"] == ALTE_PRUEFSUMME
    assert daten == {k: v for k, v in vorher.items() if k != "sha256"}
    assert daten["version"] == daten["auswahl"]["regel_fassung"] == 1
    assert daten["quellen"][0]["dokumenttext"]["parser_fassung"] == 1
    assert rahmen == vorher


def test_tatsaechlicher_eingabevertrag1_bleibt_zeichengenau():
    beleg = json.loads(BELEG.read_text(encoding="utf-8"))
    assert eingabe(beleg["kontext"], text_sha256="a"*64) == beleg["eingabe"]


@pytest.mark.parametrize("aenderung", ["zusatzfeld", "fremde_version", "nur_versionszahl"])
def test_gueltiger_hash_erlaubt_keine_stille_umdeutung_des_altvertrags(aenderung):
    rahmen = json.loads(BELEG.read_text(encoding="utf-8"))["kontext"]
    if aenderung == "zusatzfeld":
        rahmen["quellen"][0]["bundesland"] = "Oberösterreich"
    else:
        rahmen["version"] = 999 if aenderung == "fremde_version" else 2
    daten = {k: v for k, v in rahmen.items() if k != "sha256"}
    rahmen["sha256"] = hashlib.sha256(json.dumps(
        daten, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()
    with pytest.raises(QuellenkontextFehler):
        pruefen(rahmen)
