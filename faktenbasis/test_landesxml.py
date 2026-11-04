"""Synthetische einzelne Landes-Dokumenttexte; keine echten Netzaufrufe in CI."""

import copy
import hashlib
from io import StringIO

import pytest
from django.core.management import call_command
from django.test import Client
from django.urls import reverse

from faktenbasis import landesrecht, volltext
from faktenbasis.importieren import importieren
from faktenbasis.models import Norm, NormText, NormTextAbruf
from faktenbasis.ris import RisFehler
from faktenbasis.test_landesrecht import NUMMER, STAND, beispiel
from faktenbasis.test_verwaltung import admin
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from faktenbasis.xmltext import PARSER_FASSUNG, xml_adresse, xmltext_parsen
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]
RIS_ID = "LOO00000001"
QUELLE = f"https://ogd.ris.bka.gv.at/Dokumente/Landesnormen/{RIS_ID}/{RIS_ID}.xml"


def xml_beispiel(land="Oberösterreich"):
    return (
        '<risdok xmlns="http://www.bka.gv.at"><nutzdaten>'
        f'<absatz ct="doknr">{RIS_ID}</absatz><absatz ct="gesnr">{NUMMER}</absatz>'
        f'<absatz ct="bundesland">{land}</absatz>'
        '<absatz ct="text">Synthetischer Landeswortlaut<br/>Zweite Zeile<tab/>Feld</absatz>'
        '</nutzdaten></risdok>'
    ).encode()


def metadaten():
    d = beispiel()
    roh = d["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]
    roh["Dokumentliste"] = {"ContentReference": {"ContentType": "MainDocument", "Urls": {
        "ContentUrl": [{"DataType": "Xml", "Url": QUELLE}],
    }}}
    return d


@pytest.fixture
def landnorm(monkeypatch):
    daten = metadaten()
    monkeypatch.setattr(landesrecht, "abrufen", lambda nummer, stand, land: landesrecht.antwort_parsen(daten, nummer, land))
    importieren(NUMMER, STAND, bundesland="Oberoesterreich")
    return Norm.objects.get()


@pytest.fixture
def textquelle(monkeypatch):
    daten, abrufe = [xml_beispiel()], []
    def holen(url):
        assert url == QUELLE
        abrufe.append(url)
        return daten[0]
    monkeypatch.setattr(volltext, "abrufen", holen)
    return daten, abrufe


def test_land_kennungen_und_bundesland_binden_den_originaltext():
    roh = metadaten()["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]
    assert xml_adresse(roh, RIS_ID, bundesland="Oberösterreich") == QUELLE
    raw = xml_beispiel()
    text = xmltext_parsen(raw, RIS_ID, NUMMER, bundesland="Oberösterreich")
    assert text.xml == raw and text.xml_hash == hashlib.sha256(raw).hexdigest()
    assert text.text == "Synthetischer Landeswortlaut\nZweite Zeile\tFeld"
    assert PARSER_FASSUNG == 3


@pytest.mark.parametrize("fehler", ["land", "kein_land", "bundeskennung", "fremde_nummer", "doctype", "verarbeitung", "namensraum"])
def test_fremde_identitaet_und_gefaehrliches_xml_bleiben_abgewiesen(fehler):
    raw, rid, nummer, land = xml_beispiel(), RIS_ID, NUMMER, "Oberösterreich"
    if fehler == "land":
        raw = xml_beispiel("Wien")
    elif fehler == "kein_land":
        raw = raw.replace('<absatz ct="bundesland">Oberösterreich</absatz>'.encode(), b"")
    elif fehler == "bundeskennung":
        rid = "NOR00000001"
    elif fehler == "fremde_nummer":
        nummer = "99999999"
    elif fehler == "doctype":
        raw = b'<!DOCTYPE risdok SYSTEM "file:///nicht-lesen">' + raw
    elif fehler == "verarbeitung":
        raw = b'<?xml-stylesheet href="https://example.invalid/a.xsl"?>' + raw
    else:
        raw = raw.replace(b'xmlns="http://www.bka.gv.at"', b'xmlns="https://example.invalid"')
    with pytest.raises(RisFehler):
        xmltext_parsen(raw, rid, nummer, bundesland=land)


@pytest.mark.parametrize("land", ["", "Oberoesterreich", "Unbekannt", None])
def test_keine_aliasnamen_oder_standard_bundesbehandlung_fuer_land(land):
    with pytest.raises(RisFehler, match="kennung"):
        xmltext_parsen(xml_beispiel(), RIS_ID, NUMMER, bundesland=land)


@pytest.mark.parametrize("fehler", ["land", "app", "id", "fremdhost", "query", "bundespfad", "keine_xml_url"])
def test_nur_die_genau_benannte_land_originalquelle(landnorm, fehler):
    roh = copy.deepcopy(landnorm.rohdaten)
    m = roh["Metadaten"]
    urls = roh["Dokumentliste"]["ContentReference"]["Urls"]["ContentUrl"]
    if fehler == "land":
        m["Landesrecht"]["Bundesland"] = "Wien"
    elif fehler == "app":
        m["Technisch"]["Applikation"] = "BrKons"
    elif fehler == "id":
        m["Technisch"]["ID"] = "LOO00000002"
    elif fehler == "fremdhost":
        urls[0]["Url"] = QUELLE.replace("ogd.ris.bka.gv.at", "example.invalid")
    elif fehler == "query":
        urls[0]["Url"] += "?andererStand=1"
    elif fehler == "bundespfad":
        urls[0]["Url"] = QUELLE.replace("Landesnormen", "Bundesnormen")
    else:
        urls.clear()
    with pytest.raises(RisFehler):
        xml_adresse(roh, RIS_ID, bundesland="Oberösterreich")


@pytest.mark.parametrize("fruehere_fassung", [1, 2])
def test_neue_parserfassung_erhaelt_alte_auswertung_und_originalbytes(landnorm, textquelle, fruehere_fassung):
    raw = xml_beispiel()
    alt = NormText.objects.create(norm=landnorm, quelle=QUELLE, xml=raw, text="Frühere erhaltene Projektion",
        xml_hash=hashlib.sha256(raw).hexdigest(), parser_fassung=fruehere_fassung)
    altzeit = alt.erfasst_am
    neu = volltext.importieren(landnorm)
    wieder = volltext.importieren(landnorm)
    alt.refresh_from_db()
    assert neu.inhalt_id != alt.pk and neu.neu and not wieder.neu
    assert neu.inhalt.parser_fassung == PARSER_FASSUNG == 3 and wieder.inhalt_id == neu.inhalt_id
    assert NormText.objects.count() == NormTextAbruf.objects.count() == 2
    assert alt.text == "Frühere erhaltene Projektion" and alt.erfasst_am == altzeit and bytes(alt.xml) == raw
    assert alt.parser_fassung == fruehere_fassung


def test_falsches_xml_nach_erfolg_erhaelt_den_frueheren_text(landnorm, textquelle):
    eins = volltext.importieren(landnorm)
    textquelle[0][0] = xml_beispiel("Wien")
    with pytest.raises(RisFehler, match="kennung"):
        volltext.importieren(landnorm)
    assert NormText.objects.count() == 1 and NormTextAbruf.objects.count() == 2
    assert not NormTextAbruf.objects.first().erfolgreich
    assert bytes(NormText.objects.get(pk=eins.inhalt_id).xml) == xml_beispiel()


def test_oeffentliche_nachlese_und_xml_export_lesen_nur(landnorm, textquelle, client, monkeypatch):
    eins = volltext.importieren(landnorm)
    vorher = AuditEintrag.objects.count()
    monkeypatch.setattr(volltext, "abrufen", lambda url: pytest.fail("Kein Netz beim Nachlesen"))
    html = client.get(reverse("faktenbasis:norm", args=[landnorm.pk])).content.decode()
    assert "Synthetischer Landeswortlaut" in html and "Oberösterreich" in html
    assert "Neue Modellaufträge können vorhandene Landesquellen" in html
    assert "Diesen Dokumenttext einmal abrufen" not in html
    export = client.get(reverse("faktenbasis:textxml", args=[eins.inhalt_id]))
    assert export.content == xml_beispiel() and export["X-Content-Type-Options"] == "nosniff"
    assert "attachment" in export["Content-Disposition"] and AuditEintrag.objects.count() == vorher


def test_bestehender_admin_weg_csrf_und_get_sperren(landnorm, textquelle, client):
    person = admin(client)
    url = reverse("faktenbasis:dokumenttext_abrufen", args=[landnorm.pk])
    assert client.get(url).status_code == 405
    assert not textquelle[1]
    csrf = Client(enforce_csrf_checks=True)
    csrf.force_login(person)
    assert csrf.post(url).status_code == 403 and not textquelle[1]
    assert "Diesen Dokumenttext einmal abrufen" in client.get(reverse("faktenbasis:norm", args=[landnorm.pk])).content.decode()
    assert client.post(url).status_code == 302 and len(textquelle[1]) == 1
    assert NormText.objects.get().parser_fassung == PARSER_FASSUNG == 3
    assert AuditEintrag.objects.last().ereignis["aktion"] == "faktenbasis_dokumenttext"


def test_einfaches_mitglied_darf_keinen_landestext_abrufen(landnorm, textquelle, client):
    client.force_login(mitglied_anlegen("landleser"))
    assert client.post(reverse("faktenbasis:dokumenttext_abrufen", args=[landnorm.pk])).status_code == 403
    assert not textquelle[1] and not NormTextAbruf.objects.exists()


def test_bestehender_cli_weg_importiert_einen_landestext(landnorm, textquelle):
    out = StringIO()
    call_command("ris_volltext", "--norm", str(landnorm.pk), stdout=out)
    assert "Dokumenttext" in out.getvalue() and len(textquelle[1]) == 1
    assert NormText.objects.get().parser_fassung == PARSER_FASSUNG == 3
