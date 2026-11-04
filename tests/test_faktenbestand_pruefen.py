"""Offline mit dem bestehenden Format, festem Vergleichshash und ohne Zusatzpakete."""

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from plattform_core.faktenbestand import HASH_BEZUEGE, kanonisch, nachweis
from tools.faktenbestand_pruefen import HOECHSTBYTES, PruefFehler, lesen, pruefen

SKRIPT = Path(__file__).resolve().parents[1] / "tools/faktenbestand_pruefen.py"
PRIVAT = "NUR_SYNTHETISCHER_FREMDINHALT"


def beispiel(eintraege=None):
    if eintraege is None:
        eintraege = [{"sammlung": art, "nummer": i + 1, "pruefsumme": str(i) * 64}
                     for i, art in enumerate(HASH_BEZUEGE)]
    return {**nachweis(eintraege, max(1, len(eintraege))),
            "erstellt_am": "2026-11-04T04:00:00+00:00", "hoechstzahl": max(1, len(eintraege))}


def datei(tmp_path, daten):
    p = tmp_path / "Nachweis mit Leerzeichen.json"
    p.write_text(json.dumps(daten, ensure_ascii=False, indent=2), encoding="utf-8")
    return p


@pytest.mark.parametrize("leer", [False, True])
def test_vollstaendiger_und_leerer_bestand_ohne_datenbank(leer):
    d = beispiel([] if leer else None)
    vorher = copy.deepcopy(d)
    e = pruefen(d, d["sha256"])
    assert e["sha256"] == d["sha256"] and e["schnappschuesse"] == len(d["inhalt"]["eintraege"])
    assert all(e[f] is False for f in ("originaldateien_geprueft", "amtliche_signatur_geprueft",
                                     "vollstaendigkeit_bestaetigt", "metadaten_im_hash"))
    assert d == vorher


def test_datum_und_betriebsgrenze_sind_wie_bisher_nicht_im_hash():
    d = beispiel()
    erwartet = d["sha256"]
    d.update(erstellt_am="2026-11-04T05:00:00+01:00", hoechstzahl=10000)
    assert pruefen(d, erwartet)["sha256"] == erwartet


def test_intern_neu_gehashte_datei_besteht_nicht_gegen_den_alten_vergleichshash():
    d = beispiel()
    alt = d["sha256"]
    d["inhalt"]["eintraege"][0]["pruefsumme"] = "f" * 64
    d["sha256"] = hashlib.sha256(kanonisch(d["inhalt"])).hexdigest()
    assert pruefen(d, d["sha256"])["sha256"] == d["sha256"]
    with pytest.raises(PruefFehler, match="pruefsumme"):
        pruefen(d, alt)


@pytest.mark.parametrize("ort", ["wurzel", "inhalt", "sammlung", "eintrag"])
def test_unbekannte_felder_werden_nicht_still_weggefiltert(ort):
    d = beispiel()
    ziel = {"wurzel": d, "inhalt": d["inhalt"], "sammlung": d["inhalt"]["sammlungen"][0],
            "eintrag": d["inhalt"]["eintraege"][0]}[ort]
    ziel["intern"] = PRIVAT
    d["sha256"] = hashlib.sha256(kanonisch(d["inhalt"])).hexdigest()
    with pytest.raises(PruefFehler):
        pruefen(d, d["sha256"])


@pytest.mark.parametrize("fehler", ["zaehler", "zaehler_float", "zaehler_bool", "reihung", "sammlungsfolge",
    "hashbezug", "version", "version_bool", "nummer_bool", "doppelte_nummer", "grenze_bool", "grenze_zu_klein",
    "grenze_aus", "grenze_zu_gross", "datum_naiv", "datum_falsch", "hash", "erwartung"])
def test_form_zahlen_reihung_und_hash_werden_gemeinsam_geprueft(fehler):
    d = beispiel()
    erwartet = d["sha256"]
    s, e = d["inhalt"]["sammlungen"], d["inhalt"]["eintraege"]
    if fehler.startswith("zaehler"):
        s[0]["anzahl"] = {"zaehler": 2, "zaehler_float": 1.0, "zaehler_bool": True}[fehler]
    elif fehler == "reihung":
        e.reverse()
    elif fehler == "sammlungsfolge":
        s.reverse()
    elif fehler == "hashbezug":
        s[0]["hash_bezug"] = "amtliche_signatur"
    elif fehler.startswith("version"):
        d["inhalt"]["fassung"] = True if fehler == "version_bool" else 2
    elif fehler == "nummer_bool":
        e[0]["nummer"] = True
    elif fehler == "doppelte_nummer":
        e[1] = copy.deepcopy(e[0])
    elif fehler.startswith("grenze"):
        d["hoechstzahl"] = {"grenze_bool": True, "grenze_zu_klein": 1, "grenze_aus": 0, "grenze_zu_gross": 10001}[fehler]
    elif fehler.startswith("datum"):
        d["erstellt_am"] = "2026-11-04T04:00:00" if fehler == "datum_naiv" else PRIVAT
    elif fehler == "hash":
        d["sha256"] = "0" * 64
    else:
        erwartet = PRIVAT
    with pytest.raises(PruefFehler):
        pruefen(d, erwartet)


@pytest.mark.parametrize("roh,code", [(b'{"x":1,"x":2}', "doppelte_schluessel"),
    (b'{"x":{"y":1,"y":2}}', "doppelte_schluessel"), (b'{"x":NaN}', "json"),
    (b'{"x":Infinity}', "json"), (b'{}{}', "json"), (b'\xff', "utf8"),
    (b'[' * 1500 + b']' * 1500, "json")],
    ids=["wurzel-doppelt", "unterfeld-doppelt", "nan", "inf", "zwei-objekte", "utf8", "tiefe"])
def test_dateiparser_weist_mehrdeutiges_und_defektes_json_ab(tmp_path, roh, code):
    p = tmp_path / "synthetisch.json"
    p.write_bytes(roh)
    with pytest.raises(PruefFehler, match=code):
        lesen(p)
    assert p.read_bytes() == roh


def test_klammern_und_maskierte_zeichen_im_text_zaehlen_nicht_zur_tiefe(tmp_path):
    d = {"text": 'Üä🙂"' + "\\\\" + "[{" * 100}
    p = datei(tmp_path, d)
    assert lesen(p) == d


def test_dateigrenze_laesst_den_groessten_bekannten_vollbestand_zu(tmp_path):
    d = beispiel([{"sammlung": "norm", "nummer": i + 1, "pruefsumme": "0" * 64} for i in range(10000)])
    p = datei(tmp_path, d)
    assert p.stat().st_size < HOECHSTBYTES
    assert pruefen(lesen(p), d["sha256"])["schnappschuesse"] == 10000
    p.write_bytes(b" " * (HOECHSTBYTES + 1))
    with pytest.raises(PruefFehler, match="dateigroesse"):
        lesen(p)


def test_mehr_als_technische_grenze_wird_nicht_teilweise_geprueft():
    d = beispiel()
    d["inhalt"]["eintraege"] *= 2501
    with pytest.raises(PruefFehler, match="umfang"):
        pruefen(d, d["sha256"])


def test_cli_ohne_sitepackages_ohne_django_und_ohne_dateiaenderung(tmp_path):
    d = beispiel()
    p = datei(tmp_path, d)
    vorher = p.read_bytes()
    r = subprocess.run([sys.executable, "-I", "-S", str(SKRIPT), str(p), "--sha256", d["sha256"]],
        capture_output=True, text=True, encoding="utf-8", timeout=20, check=False, cwd=tmp_path)
    assert r.returncode == 0 and not r.stderr
    assert json.loads(r.stdout)["sha256"] == d["sha256"]
    assert p.read_bytes() == vorher


@pytest.mark.parametrize("fehler", ["falscher_hash", "fremddatei", "fehlende_datei"])
def test_cli_fehler_sind_knapp_und_ohne_echo_fremder_inhalte(tmp_path, fehler):
    d = beispiel()
    p = datei(tmp_path, d)
    erwartet = "0" * 64 if fehler == "falscher_hash" else d["sha256"]
    if fehler == "fremddatei":
        p.write_text(json.dumps({"privat": PRIVAT}), encoding="utf-8")
    elif fehler == "fehlende_datei":
        p = tmp_path / "nicht-vorhanden.json"
    r = subprocess.run([sys.executable, "-I", "-S", str(SKRIPT), str(p), "--sha256", erwartet],
        capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)
    assert r.returncode == 1 and not r.stdout
    assert set(json.loads(r.stderr)) == {"fehler"}
    assert PRIVAT not in r.stderr


def test_cli_verlangt_einen_ausdruecklichen_vergleichshash(tmp_path):
    p = datei(tmp_path, beispiel())
    r = subprocess.run([sys.executable, "-I", "-S", str(SKRIPT), str(p)],
        capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)
    assert r.returncode == 2 and not r.stdout


def test_maskiertes_ungueltiges_unicode_gibt_keinen_traceback_oder_rohinhalt_aus(tmp_path):
    d = beispiel()
    d["inhalt"]["sammlungen"][0]["hash_bezug"] = chr(0xD800)
    p = tmp_path / "defekter-text.json"
    p.write_text(json.dumps(d, ensure_ascii=True), encoding="utf-8")
    r = subprocess.run([sys.executable, "-I", "-S", str(SKRIPT), str(p), "--sha256", d["sha256"]],
        capture_output=True, text=True, encoding="utf-8", timeout=20, check=False)
    assert r.returncode == 1 and not r.stdout
    assert json.loads(r.stderr) == {"fehler": "sammlungen"}
