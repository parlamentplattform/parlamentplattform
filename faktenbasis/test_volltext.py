"""Abruf, unveränderliche Inhalte, Fehler und öffentliche Nachlese ohne echtes Netz."""

import hashlib
import json
from email.message import Message
from io import BytesIO, StringIO
from types import SimpleNamespace
from urllib.error import URLError

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse
from django.utils import translation

from faktenbasis import importieren as meta
from faktenbasis import volltext
from faktenbasis.models import Norm, NormText, NormTextAbruf
from faktenbasis.ris import HOECHSTBYTES, ZEITGRENZE, RisFehler, _KeineUmleitung, antwort_parsen
from faktenbasis.test_ris import STAND, beispiel
from faktenbasis.test_xmltext import NUMMER, RIS_ID, xml_beispiel
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from faktenbasis.xmltext import PARSER_FASSUNG
from verfahren.models import AuditEintrag

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


@pytest.fixture
def norm(monkeypatch):
    daten = json.loads(json.dumps(beispiel()).replace("NOR11000363", RIS_ID))
    daten["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]["Metadaten"]["Bundesrecht"]["BrKons"]["ArtikelParagraphAnlage"] = "Art. 1"
    monkeypatch.setattr(meta, "abrufen", lambda *args: antwort_parsen(daten, NUMMER))
    meta.importieren(NUMMER, STAND)
    return Norm.objects.get()


@pytest.fixture
def xml(monkeypatch):
    daten = [xml_beispiel()]
    monkeypatch.setattr(volltext, "abrufen", lambda url: daten[0])
    return daten


def test_inhalt_einmal_abruf_jedes_mal_mit_unveraendertem_erfassungsdatum(norm, xml):
    erster = volltext.importieren(norm)
    inhalt = NormText.objects.get()
    zeit = inhalt.erfasst_am
    assert erster.inhalt_id == inhalt.pk and erster.erfolgreich and erster.neu
    assert bytes(inhalt.xml) == xml[0] and inhalt.xml_hash == hashlib.sha256(xml[0]).hexdigest()
    assert "Änderung des B-VG" in inhalt.text and inhalt.parser_fassung == PARSER_FASSUNG == 2
    zweiter = volltext.importieren(norm)
    assert zweiter.inhalt_id == inhalt.pk and not zweiter.neu
    assert NormText.objects.count() == 1 and NormTextAbruf.objects.count() == 2
    inhalt.refresh_from_db()
    assert inhalt.erfasst_am == zeit
    assert zweiter.beendet_am >= erster.beendet_am
    audit = AuditEintrag.objects.last().ereignis
    assert audit["typ"] == "ris_volltext" and audit["abruf"] == zweiter.pk
    assert "mitglied" not in audit and "xml" not in audit


def test_aenderung_erhaelt_zusaetzlichen_inhalt_statt_zu_ueberschreiben(norm, xml):
    erster = volltext.importieren(norm)
    xml[0] = xml[0].replace(b'ct="text" halign="c">', b'ct="text" halign="c">Testaenderung ', 1)
    zweiter = volltext.importieren(norm)
    assert zweiter.neu and zweiter.inhalt_id != erster.inhalt_id
    assert NormText.objects.count() == 2
    assert bytes(NormText.objects.get(pk=erster.inhalt_id).xml) == xml_beispiel()


@pytest.mark.parametrize("modell", [NormText, NormTextAbruf])
def test_inhalt_und_abruf_duerfen_nicht_geaendert_oder_geloescht_werden(norm, xml, modell):
    volltext.importieren(norm)
    objekt = modell.objects.get()
    for aktion in [objekt.save, objekt.delete, lambda: modell.objects.update(pk=999), modell.objects.all().delete]:
        with pytest.raises(ValidationError):
            aktion()


def test_fehler_nach_erfolg_erhaelt_alte_bytes_und_wird_als_versuch_sichtbar(norm, xml, client, monkeypatch):
    erster = volltext.importieren(norm)
    def kaputt(url):
        raise RisFehler("abruf")
    monkeypatch.setattr(volltext, "abrufen", kaputt)
    with pytest.raises(RisFehler, match="abruf"):
        volltext.importieren(norm)
    assert NormText.objects.count() == 1
    letzter = NormTextAbruf.objects.first()
    assert not letzter.erfolgreich and letzter.inhalt_id is None and letzter.fehlercode == "abruf"
    seite = client.get(reverse("faktenbasis:norm", args=[norm.pk])).content.decode()
    assert "Der letzte Dokumenttext-Abruf ist fehlgeschlagen" in seite and "Änderung des B-VG" in seite
    assert bytes(NormText.objects.get(pk=erster.inhalt_id).xml) == xml_beispiel()


def test_unpassende_metadatenquelle_wird_vor_jedem_netzaufruf_abgewiesen(norm, monkeypatch):
    # Ein eigener künstlicher beschädigter Alt-Schnappschuss, keine Änderung
    # amtlicher Archivdaten: der Importer liest ausschließlich den DB-Stand.
    norm.pk = None
    norm._state.adding = True
    norm.inhalt_hash = "0" * 64
    norm.rohdaten = {}
    norm.save()
    monkeypatch.setattr(volltext, "abrufen", lambda url: pytest.fail("Kein Netz vor Quellenprüfung"))
    with pytest.raises(RisFehler, match="volltextquelle"):
        volltext.importieren(norm)
    assert not NormText.objects.exists()
    assert NormTextAbruf.objects.get().quelle == ""


def test_veraenderte_objektattribute_ersetzen_nicht_die_erhaltene_quelle(norm, xml):
    norm.rohdaten = {}
    norm.ris_id = "NOR00000000"
    lauf = volltext.importieren(norm)
    assert lauf.erfolgreich and lauf.inhalt.text
    assert RIS_ID in lauf.quelle


def test_fremdes_xml_wird_nicht_gespeichert(norm, xml):
    xml[0] = xml[0].replace(RIS_ID.encode(), b"NOR00000000")
    with pytest.raises(RisFehler, match="kennung"):
        volltext.importieren(norm)
    assert not NormText.objects.exists() and NormTextAbruf.objects.get().fehlercode == "kennung"


def test_auditfehler_rollt_neuen_inhalt_und_erfolgsnachweis_zurueck(norm, xml, monkeypatch):
    def kaputt(*args, **kwargs):
        raise RuntimeError("Datenbank-Testfehler")
    monkeypatch.setattr(AuditEintrag, "anhaengen", kaputt)
    with pytest.raises(RuntimeError):
        volltext.importieren(norm)
    assert not NormText.objects.exists() and not NormTextAbruf.objects.exists()


def test_nachlese_escape_originaldownload_hash_und_oeffentliche_schreibsperren(norm, xml, client):
    xml[0] = xml[0].replace(b'ct="text" halign="c">', b'ct="text" halign="c">&lt;script&gt;alarm&lt;/script&gt; ', 1)
    lauf = volltext.importieren(norm)
    url = reverse("faktenbasis:textxml", args=[lauf.inhalt_id])
    antwort = client.get(url)
    assert antwort.status_code == 200 and antwort.content == xml[0]
    assert hashlib.sha256(antwort.content).hexdigest() == lauf.inhalt.xml_hash
    assert antwort["Content-Disposition"] == f'attachment; filename="ris-dokument-{lauf.inhalt_id}.xml"'
    assert antwort["X-Content-Type-Options"] == "nosniff"
    detail = reverse("faktenbasis:norm", args=[norm.pk])
    seite = client.get(detail).content.decode()
    assert "&lt;script&gt;alarm&lt;/script&gt;" in seite and "<script>alarm" not in seite
    assert "Amtlicher Dokumenttext vorhanden" in client.get(reverse("faktenbasis:index")).content.decode()
    for adresse in [url, detail, reverse("faktenbasis:index")]:
        assert client.post(adresse).status_code == 405
    assert client.head(url).status_code == 200
    assert client.get(reverse("faktenbasis:textxml", args=[999999])).status_code == 404
    assert NormTextAbruf.objects.count() == 1


def test_englische_nachlese_stellt_testsprache_wieder_her(norm, xml, client):
    volltext.importieren(norm)
    with translation.override("en"):
        antwort = client.get(reverse("faktenbasis:norm", args=[norm.pk]), HTTP_ACCEPT_LANGUAGE="en")
    assert "Official document texts" in antwort.content.decode()


def test_cli_ist_explizit_und_ruft_nur_einen_bekannten_schnappschuss_ab(norm, xml, monkeypatch):
    ausgabe = StringIO()
    call_command("ris_volltext", norm=norm.pk, stdout=ausgabe)
    assert "Einzeldokument" in ausgabe.getvalue() and NormTextAbruf.objects.count() == 1
    monkeypatch.setattr(volltext, "abrufen", lambda url: pytest.fail("Kein Netz ohne Norm"))
    with pytest.raises(CommandError, match="nicht gefunden"):
        call_command("ris_volltext", norm=999999)


class Antwort(BytesIO):
    def __init__(self, daten, typ="application/xml", status=200):
        super().__init__(daten)
        self.daten, self.status = daten, status
        self.headers = Message()
        self.headers["Content-Type"] = typ

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

def test_netzadapter_ein_request_zeitlimit_und_umleitungsverbot(monkeypatch):
    protokoll = []
    def oeffnen(anfrage, timeout):
        protokoll.append((anfrage.full_url, timeout, anfrage.get_header("Accept")))
        return Antwort(xml_beispiel())
    def opener(handler):
        assert isinstance(handler, _KeineUmleitung)
        return SimpleNamespace(open=oeffnen)
    monkeypatch.setattr(volltext.urllib.request, "build_opener", opener)
    url = f"https://ogd.ris.bka.gv.at/Dokumente/Bundesnormen/{RIS_ID}/{RIS_ID}.xml"
    assert volltext.abrufen(url) == xml_beispiel()
    assert protokoll == [(url, ZEITGRENZE, "application/xml, text/xml, application/octet-stream")]
    with pytest.raises(RisFehler, match="umleitung"):
        _KeineUmleitung().redirect_request(None, None, 302, "", {}, "https://evil.invalid")


@pytest.mark.parametrize("typ,status,inhalt,code", [
    ("text/html", 200, b"<html>", "volltextformat"),
    ("application/xml", 204, b"", "volltextformat"),
    ("application/xml", 200, b"x" * (HOECHSTBYTES + 1), "antwortgroesse"),
], ids=["html", "leerstatus", "uebergroesse"])
def test_netzadapter_weist_format_status_und_groessenfehler_ab(monkeypatch, typ, status, inhalt, code):
    monkeypatch.setattr(volltext.urllib.request, "build_opener", lambda *a: SimpleNamespace(
        open=lambda *a, **kw: Antwort(inhalt, typ, status),
    ))
    with pytest.raises(RisFehler, match=code):
        volltext.abrufen("https://ogd.ris.bka.gv.at/test.xml")


@pytest.mark.parametrize("fehler", [URLError("kein Netz"), TimeoutError("zu langsam")])
def test_netzfehler_haben_keinen_ungeprueften_servertext(monkeypatch, fehler):
    def kaputt(*args, **kwargs):
        raise fehler
    monkeypatch.setattr(volltext.urllib.request, "build_opener", lambda *a: SimpleNamespace(open=kaputt))
    with pytest.raises(RisFehler, match="^abruf$"):
        volltext.abrufen("https://ogd.ris.bka.gv.at/test.xml")
