"""Amtliche Beispielstruktur und defensive Einzelabrufe, vollständig ohne Netz."""

import copy
import io
import json
import urllib.error
from datetime import date
from email.message import Message
from pathlib import Path
from unittest.mock import Mock

import pytest

from faktenbasis import ris
from faktenbasis.ris import RisFehler, abrufen, amtliche_url, antwort_parsen

NUMMER = "10000362"
STAND = date(2026, 11, 2)
BEISPIEL = Path(__file__).with_name("testdaten") / "ris_einzeldokument.json"


def beispiel():
    return json.loads(BEISPIEL.read_text(encoding="utf-8"))


def test_amtliche_antwortform_mit_einzelobjekt_und_nil_ist_lesbar():
    antwort = antwort_parsen(beispiel(), NUMMER)
    norm, = antwort.normen
    assert norm.ris_id == "NOR11000363" and norm.gesetzesnummer == NUMMER
    assert norm.abschnitt == "§ 0" and norm.typ == "BVG"
    assert norm.kurztitel.startswith("Abänderung des Bundes-Verfassungsgesetzes")
    assert "<br" not in norm.titel
    assert len(norm.inhalt_hash) == 64 and len(antwort.antwort_hash) == 64


def test_listenform_und_andere_json_schluesselreihenfolge_aendern_keinen_normhash():
    einzel = beispiel()
    liste = copy.deepcopy(einzel)
    ergebnis = liste["OgdSearchResult"]["OgdDocumentResults"]
    ergebnis["OgdDocumentReference"] = [ergebnis["OgdDocumentReference"]]
    assert antwort_parsen(einzel, NUMMER).normen == antwort_parsen(liste, NUMMER).normen


def test_ein_titeltreffer_zu_einem_anderen_gesetz_wird_nicht_uebernommen():
    with pytest.raises(RisFehler, match="kennung"):
        antwort_parsen(beispiel(), "10000138")


@pytest.mark.parametrize("url", [
    "http://ris.bka.gv.at/a", "https://ris.bka.gv.at.evil.test/a", "https://evil.test/ris.bka.gv.at",
    "https://user@ris.bka.gv.at/a", "https://ris.bka.gv.at:443/a", "//ris.bka.gv.at/a",
    "https://ris.bka.gv.at/a#x", "https://ris.bka.gv.at\\@evil.test/a",
    "https://ris.bka.gv.at/a\nb", None, {"@xsi:nil": "true"},
])
def test_quelladressen_brauchen_einen_eindeutigen_amtlichen_https_host(url):
    with pytest.raises(RisFehler, match="quelladresse"):
        amtliche_url(url)


@pytest.mark.parametrize("pfad,wert", [
    (("Technisch", "ID"), "NOR999"),
    (("Technisch", "Applikation"), "Justiz"),
    (("Bundesrecht", "BrKons", "Gesetzesnummer"), "10000138"),
    (("Allgemein", "DokumentUrl"), "https://ogd.ris.bka.gv.at/eli/bgbl/1962/215/P0/NOR99999999"),
    (("Bundesrecht", "Kurztitel"), {"@xsi:nil": "true"}),
])
def test_unpassende_metadaten_brechen_die_gesamte_seite_ab(pfad, wert):
    daten = beispiel()
    ziel = daten["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]["Metadaten"]
    for schluessel in pfad[:-1]:
        ziel = ziel[schluessel]
    ziel[pfad[-1]] = wert
    with pytest.raises(RisFehler):
        antwort_parsen(daten, NUMMER)


def test_keine_treffer_ist_ein_eindeutiger_leerzustand_keine_fehlermeldung():
    daten = {"OgdSearchResult": {"OgdDocumentResults": {
        "Hits": {"#text": "0", "@pageNumber": "1", "@pageSize": "10"},
    }}}
    for leer in (None, [], {"@xsi:nil": "true"}):
        daten["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"] = leer
        assert antwort_parsen(daten, NUMMER).normen == ()
    for fehlerhaft in ({}, {"OgdSearchResult": {"Error": "Server nicht erreichbar"}}):
        with pytest.raises(RisFehler, match="antwortformat"):
            antwort_parsen(fehlerhaft, NUMMER)


def test_doppelte_dokumentkennung_und_zu_grosse_seite_werden_abgelehnt():
    daten = beispiel()
    ergebnis = daten["OgdSearchResult"]["OgdDocumentResults"]
    ref = ergebnis["OgdDocumentReference"]
    ergebnis["Hits"]["#text"] = "20"
    for anzahl in (2, 11):
        ergebnis["OgdDocumentReference"] = [ref] * anzahl
        with pytest.raises(RisFehler):
            antwort_parsen(daten, NUMMER)


class Scheinantwort(io.BytesIO):
    def __init__(self, inhalt, typ="application/json"):
        super().__init__(inhalt)
        self.headers = Message()
        self.headers["Content-Type"] = typ


def scheinabruf(monkeypatch, inhalt=None, typ="application/json", fehler=None):
    opener = Mock()
    opener.open.side_effect = fehler or (lambda *a, **k: Scheinantwort(
        inhalt if inhalt is not None else json.dumps(beispiel()).encode(), typ,
    ))
    factory = Mock(return_value=opener)
    monkeypatch.setattr(ris.urllib.request, "build_opener", factory)
    return opener, factory


def test_abruf_ist_eine_feste_amtliche_anfrage_ohne_titel_oder_modelltext(monkeypatch):
    opener, factory = scheinabruf(monkeypatch)
    antwort = abrufen(NUMMER, STAND)
    anfrage, = opener.open.call_args.args
    query = ris.urllib.parse.parse_qs(ris.urllib.parse.urlsplit(anfrage.full_url).query)
    assert anfrage.full_url.startswith(ris.API + "?")
    assert query == {
        "Applikation": ["BrKons"], "Gesetzesnummer": [NUMMER], "Fassung.FassungVom": ["2026-11-02"],
        "DokumenteProSeite": ["Ten"], "Seitennummer": ["1"],
    }
    assert "plattform@ddoe.at" in anfrage.get_header("User-agent")
    assert opener.open.call_count == 1 and opener.open.call_args.kwargs == {"timeout": 15}
    assert antwort.api_url == anfrage.full_url
    handler, = factory.call_args.args
    with pytest.raises(RisFehler, match="umleitung"):
        handler.redirect_request(None, None, 302, "", {}, "https://evil.test/")


@pytest.mark.parametrize("inhalt,typ,code", [
    (b"{", "application/json", "antwortformat"),
    (b"\xff", "application/json", "antwortformat"),
    (b"{}", "text/html", "antwortformat"),
    (b"x" * (ris.HOECHSTBYTES + 1), "application/json", "antwortgroesse"),
], ids=["kaputtes-json", "ungueltiges-utf8", "html-statt-json", "zu-gross"])
def test_ungueltige_oder_zu_grosse_antwort_ist_kein_import(monkeypatch, inhalt, typ, code):
    scheinabruf(monkeypatch, inhalt, typ)
    with pytest.raises(RisFehler, match=code):
        abrufen(NUMMER, STAND)


@pytest.mark.parametrize("fehler", [
    TimeoutError(), urllib.error.URLError("nicht erreichbar"),
    urllib.error.HTTPError(ris.API, 503, "nicht erreichbar", {}, None),
])
def test_verbindungsfehler_werden_ohne_rohen_servertext_gemeldet(monkeypatch, fehler):
    scheinabruf(monkeypatch, fehler=fehler)
    with pytest.raises(RisFehler, match="^abruf$"):
        abrufen(NUMMER, STAND)


@pytest.mark.parametrize("nummer,stand", [
    ("123", STAND), ("１００００３６２", STAND), (NUMMER, "2026-11-02"),
])
def test_ungueltige_argumente_rufen_das_netz_nicht_auf(monkeypatch, nummer, stand):
    opener, _ = scheinabruf(monkeypatch)
    with pytest.raises(RisFehler):
        abrufen(nummer, stand)
    opener.open.assert_not_called()


def test_troepfelnde_antwort_ueberschreitet_nicht_die_technische_reservierung(monkeypatch):
    zeiten = iter([0, 0, 1, 2, ris.ZEITGRENZE])
    monkeypatch.setattr(ris.time, "monotonic", lambda: next(zeiten))
    antwort = Mock()
    antwort.read1.return_value = b"x"
    with pytest.raises(RisFehler, match="abrufzeit"):
        ris.begrenzt_lesen(antwort, 0)
    assert antwort.read1.call_count <= 3
